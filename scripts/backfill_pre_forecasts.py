import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Optional
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from db.connection import get_db_engine
from sqlalchemy import text
from src.features.pre_forecasters import (
    create_pre_forecasts_schema_if_not_exists,
    load_wind_features,
    build_pre_forecast_features,
    train_and_predict_pre_forecasters
)
from scripts.predict_daily_pipeline import load_all_historical_data

logger = logging.getLogger("PreForecastersBackfill")

def run_pre_forecasts_backfill(num_days: int = 730, df_raw: Optional[pd.DataFrame] = None):
    logger.info("📦 Pre-Forecasters Backfill başlatılıyor...")
    create_pre_forecasts_schema_if_not_exists()
    
    # Veri zaten yüklendiyse kullan, yoksa veritabanından çek
    if df_raw is None:
        df_raw = load_all_historical_data()
    
    # Open-Meteo rüzgar verisini çek
    min_date = df_raw.index.min().strftime('%Y-%m-%d')
    max_date = df_raw.index.max().strftime('%Y-%m-%d')
    # Backfill'in son günü df_raw'ın son günü; akşam fiyat çekimi sayesinde bu
    # YARIN olabiliyor. Arşiv API'si yarını veremediği için forecast da lazım.
    df_wind = load_wind_features(min_date, max_date)
    
    # Feature'ları oluştur
    df_feat = build_pre_forecast_features(df_raw, df_wind)
    
    max_days = num_days
    max_ts = df_feat.index.max()
    logger.info(f"⏳ Son {max_days} gün için walk-forward simülasyon başlatılıyor...")

    all_records = []
    
    # Her gün için walk-forward simülasyon
    for day_idx in range(max_days - 1, -1, -1):
        test_end = max_ts - pd.Timedelta(days=day_idx)
        test_start = test_end - pd.Timedelta(hours=23)
        train_end = test_start - pd.Timedelta(hours=1)

        train_df = df_feat.loc[:train_end]
        test_df = df_feat.loc[test_start:test_end]

        if len(train_df) < 1000 or len(test_df) < 12:
            continue

        preds_df = train_and_predict_pre_forecasters(train_df, test_df)
        
        for ts_val, row in preds_df.iterrows():
            all_records.append({
                'target_ts': ts_val,
                'predicted_load_lag0': float(row.get('predicted_load_lag0', 0)),
                'predicted_solar_lag0': float(row.get('predicted_solar_lag0', 0)),
                'predicted_wind_lag0': float(row.get('predicted_wind_lag0', 0))
            })

        if len(all_records) % (30 * 24) == 0:
            logger.info(f"⏳ Processed {len(all_records)//24} days of pre-forecasts...")

    logger.info(f"💾 Saving {len(all_records)} pre-forecast records to gold.kgup_load_pre_forecasts...")

    engine = get_db_engine()
    # Pre-forecasts are immutable once written: the first forecast produced for a target
    # hour is the one the price model actually consumed, so it must stay put. This used to
    # be DO UPDATE, and because every run regenerates the last 3 days, a given day's
    # pre-forecast silently changed depending on when it was last rewritten — which made
    # the same day's price prediction irreproducible across runs and machines.
    # The WHERE clause is the only escape hatch: an incomplete (NULL) row gets repaired.
    # To deliberately regenerate a range, DELETE those rows first.
    insert_sql = text("""
        INSERT INTO gold.kgup_load_pre_forecasts (target_ts, predicted_load_lag0, predicted_solar_lag0, predicted_wind_lag0)
        VALUES (:target_ts, :predicted_load_lag0, :predicted_solar_lag0, :predicted_wind_lag0)
        ON CONFLICT (target_ts)
        DO UPDATE SET
            predicted_load_lag0 = EXCLUDED.predicted_load_lag0,
            predicted_solar_lag0 = EXCLUDED.predicted_solar_lag0,
            predicted_wind_lag0 = EXCLUDED.predicted_wind_lag0,
            created_at = CURRENT_TIMESTAMP
        WHERE gold.kgup_load_pre_forecasts.predicted_load_lag0 IS NULL
           OR gold.kgup_load_pre_forecasts.predicted_solar_lag0 IS NULL
           OR gold.kgup_load_pre_forecasts.predicted_wind_lag0 IS NULL;
    """)

    chunk_size = 1000
    with engine.connect() as conn:
        for i in range(0, len(all_records), chunk_size):
            chunk = all_records[i:i+chunk_size]
            conn.execute(insert_sql, chunk)
        conn.commit()

    logger.info("🎉 Pre-Forecasters Backfill completed successfully!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_pre_forecasts_backfill()
