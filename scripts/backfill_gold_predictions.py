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


def backfill_365_days_predictions():
    """
    Son 365 gün için walk-forward LightGBM tahminlerini üretir ve DB'ye yazar.
    """
    logger.info("📦 Veritabanından tüm geçmiş veri yükleniyor...")
    create_gold_schema_if_not_exists(run_backfill_if_empty=False)
    
    df_raw = load_all_historical_data()
    df_feat = build_robust_features(df_raw)
    
    feature_cols = get_feature_columns('robust', df_feat)
    target_col = 'mcp_price_usd'

    df_model = df_feat.dropna(subset=feature_cols + [target_col]).copy()
    
    max_days = 365
    max_ts = df_model.index.max()
    logger.info(f"⏳ Son {max_days} gün için walk-forward backfill başlatılıyor...")

    all_records = []
    
    for day_idx in range(max_days - 1, -1, -1):
        test_end = max_ts - pd.Timedelta(days=day_idx)
        test_start = test_end - pd.Timedelta(hours=23)
        train_end = test_start - pd.Timedelta(hours=1)

        tr_df = df_model.loc[:train_end]
        te_df = df_model.loc[test_start:test_end]

        if len(tr_df) < 1000 or len(te_df) < 12:
            continue

        forecaster = LightGBMForecaster()
        forecaster.fit(tr_df[feature_cols], tr_df[target_col].values)

        preds_usd = forecaster.predict(te_df[feature_cols])
        
        latest_usd_try = float(tr_df['usd_try'].iloc[-1]) if 'usd_try' in tr_df.columns else 35.0
        preds_try = preds_usd * latest_usd_try

        for idx_ts, (ts_val, p_usd, p_try) in enumerate(zip(te_df.index, preds_usd, preds_try)):
            all_records.append({
                'target_ts': ts_val,
                'predicted_mcp_usd': float(np.round(p_usd, 4)),
                'predicted_mcp_try': float(np.round(p_try, 4)),
                'model_name': 'LightGBM_v1'
            })

        if len(all_records) % (30 * 24) == 0:
            logger.info(f"⏳ Processed {len(all_records)//24} days of predictions...")

    logger.info(f"💾 Saving {len(all_records)} prediction records to gold.ptf_predictions_daily...")

    engine = get_db_engine()
    insert_sql = text("""
        INSERT INTO gold.ptf_predictions_daily (target_ts, predicted_mcp_usd, predicted_mcp_try, model_name)
        VALUES (:target_ts, :predicted_mcp_usd, :predicted_mcp_try, :model_name)
        ON CONFLICT (target_ts, model_name) 
        DO UPDATE SET 
            predicted_mcp_usd = EXCLUDED.predicted_mcp_usd,
            predicted_mcp_try = EXCLUDED.predicted_mcp_try,
            created_at = CURRENT_TIMESTAMP;
    """)

    # Batch insert in chunks of 1000
    chunk_size = 1000
    with engine.connect() as conn:
        for i in range(0, len(all_records), chunk_size):
            chunk = all_records[i:i+chunk_size]
            conn.execute(insert_sql, chunk)
        conn.commit()

    logger.info("🎉 Backfill completed successfully! Gold layer now has 1 year of historical model predictions.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    backfill_365_days_predictions()
