"""
Son 365 gün için LightGBM walk-forward backtest tahminlerini 
veritabanındaki `gold.ptf_predictions_daily` tablosuna dolduran tohumlama (seed/backfill) script'i.

Dashboard'un son 1 yıla kadar geçmiş model performansını ve 
gerçekleşen vs tahmin edilen (Actual vs Predicted) grafiklerini 
kesintisiz gösterebilmesi için kullanılır.
"""

import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from db.connection import get_db_engine
from sqlalchemy import text
from src.features.feature_engineering import build_robust_features, get_feature_columns
from src.models.lightgbm_model import LightGBMForecaster
from predict_daily_pipeline import create_gold_schema_if_not_exists, load_all_historical_data

logger = logging.getLogger("GoldBackfill")


def backfill_historical_predictions(num_days: int = 730):
    """
    Son 2 yıl (730 gün) için walk-forward LightGBM tahminlerini üretir ve DB'ye yazar.
    """
    logger.info("📦 Veritabanından tüm geçmiş veri yükleniyor...")
    create_gold_schema_if_not_exists(run_backfill_if_empty=False)
    
    df_raw = load_all_historical_data()
    df_feat = build_robust_features(df_raw)
    
    feature_cols = get_feature_columns('robust', df_feat)
    target_col = 'mcp_price_usd'

    df_model = df_feat.dropna(subset=feature_cols + [target_col]).copy()
    
    max_days = num_days
    max_ts = df_model.index.max()
    logger.info(f"⏳ Son {max_days} gün (2 yıl) için walk-forward backfill başlatılıyor...")

    all_records = []
    
    for day_idx in range(max_days - 1, -1, -1):
        test_end = max_ts - pd.Timedelta(days=day_idx)
        test_start = test_end - pd.Timedelta(hours=23)
        train_end = test_start - pd.Timedelta(hours=1)

        tr_df = df_model.loc[:train_end]
        te_df = df_model.loc[test_start:test_end]

        if len(tr_df) < 1000 or len(te_df) < 12:
            continue

        # P50 (Medyan)
        forecaster = LightGBMForecaster(params={'objective': 'quantile', 'alpha': 0.50, 'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63, 'min_child_samples': 10, 'verbose': -1, 'random_state': 42})
        forecaster.fit(tr_df[feature_cols], tr_df[target_col].values)

        # P10 (Alt Sınır)
        forecaster_p10 = LightGBMForecaster(params={'objective': 'quantile', 'alpha': 0.10, 'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63, 'min_child_samples': 10, 'verbose': -1, 'random_state': 42})
        forecaster_p10.fit(tr_df[feature_cols], tr_df[target_col].values)

        # P90 (Üst Sınır)
        forecaster_p90 = LightGBMForecaster(params={'objective': 'quantile', 'alpha': 0.90, 'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63, 'min_child_samples': 10, 'verbose': -1, 'random_state': 42})
        forecaster_p90.fit(tr_df[feature_cols], tr_df[target_col].values)

        preds_usd = forecaster.predict(te_df[feature_cols])
        preds_usd_p10 = forecaster_p10.predict(te_df[feature_cols])
        preds_usd_p90 = forecaster_p90.predict(te_df[feature_cols])
        
        # Quantile Crossover Koruması (Monotonic Guarantee: P10 <= P50 <= P90)
        preds_usd_p10 = np.minimum(preds_usd_p10, preds_usd)
        preds_usd_p90 = np.maximum(preds_usd_p90, preds_usd)

        # Historical FX rate conversion: Use exact exchange rate of THAT test period in history
        if 'usd_try' in te_df.columns and not te_df['usd_try'].isna().all():
            day_usd_try_s = te_df['usd_try'].ffill().bfill()
            if day_usd_try_s.isna().any():
                from fetch_epias_data import resolve_usd_try_rate
                fallback_fx = resolve_usd_try_rate(df=tr_df, engine=engine)
                day_usd_try_s = day_usd_try_s.fillna(fallback_fx)
            day_usd_try = day_usd_try_s.values
        else:
            from fetch_epias_data import resolve_usd_try_rate
            day_usd_try = resolve_usd_try_rate(df=tr_df, engine=engine)

        preds_try = preds_usd * day_usd_try
        preds_try_p10 = preds_usd_p10 * day_usd_try
        preds_try_p90 = preds_usd_p90 * day_usd_try

        preds_try_p10 = np.minimum(preds_try_p10, preds_try)
        preds_try_p90 = np.maximum(preds_try_p90, preds_try)

        for idx_ts, (ts_val, p_usd, p_try, p_usd_10, p_try_10, p_usd_90, p_try_90) in enumerate(zip(te_df.index, preds_usd, preds_try, preds_usd_p10, preds_try_p10, preds_usd_p90, preds_try_p90)):
            all_records.append({
                'target_ts': ts_val,
                'predicted_mcp_usd': float(np.round(p_usd, 4)),
                'predicted_mcp_try': float(np.round(p_try, 4)),
                'predicted_mcp_usd_p10': float(np.round(p_usd_10, 4)),
                'predicted_mcp_try_p10': float(np.round(p_try_10, 4)),
                'predicted_mcp_usd_p90': float(np.round(p_usd_90, 4)),
                'predicted_mcp_try_p90': float(np.round(p_try_90, 4)),
                'model_name': 'LightGBM_v1'
            })

        if len(all_records) % (30 * 24) == 0:
            logger.info(f"⏳ Processed {len(all_records)//24} days of predictions...")

    logger.info(f"💾 Saving {len(all_records)} prediction records to gold.ptf_predictions_daily...")

    engine = get_db_engine()
    insert_sql = text("""
        INSERT INTO gold.ptf_predictions_daily (
            target_ts, predicted_mcp_usd, predicted_mcp_try,
            predicted_mcp_usd_p10, predicted_mcp_try_p10,
            predicted_mcp_usd_p90, predicted_mcp_try_p90,
            model_name
        )
        VALUES (
            :target_ts, :predicted_mcp_usd, :predicted_mcp_try,
            :predicted_mcp_usd_p10, :predicted_mcp_try_p10,
            :predicted_mcp_usd_p90, :predicted_mcp_try_p90,
            :model_name
        )
        ON CONFLICT (target_ts, model_name) 
        DO UPDATE SET 
            predicted_mcp_usd = EXCLUDED.predicted_mcp_usd,
            predicted_mcp_try = EXCLUDED.predicted_mcp_try,
            predicted_mcp_usd_p10 = EXCLUDED.predicted_mcp_usd_p10,
            predicted_mcp_try_p10 = EXCLUDED.predicted_mcp_try_p10,
            predicted_mcp_usd_p90 = EXCLUDED.predicted_mcp_usd_p90,
            predicted_mcp_try_p90 = EXCLUDED.predicted_mcp_try_p90,
            created_at = CURRENT_TIMESTAMP;
    """)

    # Batch insert in chunks of 1000
    chunk_size = 1000
    with engine.connect() as conn:
        for i in range(0, len(all_records), chunk_size):
            chunk = all_records[i:i+chunk_size]
            conn.execute(insert_sql, chunk)
        conn.commit()

    logger.info("🎉 Backfill completed successfully! Gold layer now has 2 years of historical model predictions.")


# Backward compatibility alias
backfill_365_days_predictions = backfill_historical_predictions


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    backfill_365_days_predictions()
