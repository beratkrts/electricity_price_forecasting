"""
Günlük LightGBM Tahmin Pipeline Script'i.

PostgreSQL veritabanındaki 2024-01-01'den itibaren TÜM geçmiş veriyi yükler,
Robust Feature Set ile LightGBM (log-transform) modelini eğitir,
önümüzdeki 24 saat için PTF tahminlerini üretir ve
`gold.ptf_predictions_daily` tablosuna kaydeder.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import lightgbm as lgb

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from db.connection import get_db_engine
from sqlalchemy import text
from src.features.feature_engineering import build_robust_features, get_feature_columns
from src.models.lightgbm_model import LightGBMForecaster

logger = logging.getLogger("DailyPredictionPipeline")


def create_gold_schema_if_not_exists(run_backfill_if_empty: bool = True):
    """gold şemasını ve gold.ptf_predictions_daily tablosunu oluşturur. Boşsa son 1 yılı otomatik doldurur."""
    engine = get_db_engine()
    count = 0
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gold.ptf_predictions_daily (
                target_ts TIMESTAMP WITH TIME ZONE,
                predicted_mcp_usd NUMERIC(10, 4),
                predicted_mcp_try NUMERIC(10, 4),
                model_name VARCHAR(50) DEFAULT 'LightGBM_v1',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (target_ts, model_name)
            );
        """))
        conn.commit()
        
        # Tablo verisini kontrol et
        count = conn.execute(text("SELECT COUNT(*) FROM gold.ptf_predictions_daily;")).scalar()

    # Connection kapandıktan sonra backfill gerekiyorsa çalıştır
    if run_backfill_if_empty and count < 1000:
        logger.info("⚡ First-time deployment detected or empty gold table! Automatically running 365-day backfill for dashboard history...")
        from backfill_gold_predictions import backfill_365_days_predictions
        try:
            backfill_365_days_predictions()
        except Exception as e:
            logger.error(f"Error during automatic backfill: {e}")


def load_all_historical_data():
    """2024-01-01'den itibaren veritabanındaki TÜM geçmiş verileri çeker."""
    engine = get_db_engine()
    master_sql = text("""
        SELECT 
            m.ts,
            m.price_usd AS mcp_price_usd,
            m.price_try AS mcp_price_try,
            s.system_marginal_price_try AS smp_price_try,
            l.load_forecast_mw,
            k.total_mw AS kgup_total_mw,
            k.natural_gas_mw AS kgup_gas_mw,
            k.wind_mw AS kgup_wind_mw,
            k.solar_mw AS kgup_solar_mw,
            k.dammed_hydro_mw + k.river_hydro_mw AS kgup_hydro_mw,
            k.import_coal_mw + k.lignite_mw + k.black_coal_mw AS kgup_coal_mw,
            g.total_mw AS actual_gen_total_mw,
            c.consumption_mw AS actual_cons_mw,
            w.turkey_weighted_temperature_c AS temperature_c,
            mc.usd_try,
            mc.brent_oil_usd,
            ng.gas_reference_price_try AS natural_gas_grf_try,
            wp.hydro_water_energy_mwh
        FROM raw_mcp_hourly m
        LEFT JOIN raw_smp_hourly s ON m.ts = s.ts
        LEFT JOIN raw_load_forecast_hourly l ON m.ts = l.ts
        LEFT JOIN raw_kgup_hourly k ON m.ts = k.ts
        LEFT JOIN raw_actual_generation_hourly g ON m.ts = g.ts
        LEFT JOIN raw_actual_consumption_hourly c ON m.ts = c.ts
        LEFT JOIN raw_weather_hourly w ON m.ts = w.ts
        LEFT JOIN raw_macro_daily mc ON DATE(m.ts) = mc.entry_date
        LEFT JOIN raw_natural_gas_daily ng ON DATE(m.ts) = ng.entry_date
        LEFT JOIN (
            SELECT DATE(date_time) AS entry_date, SUM(water_energy_provision_mwh) AS hydro_water_energy_mwh
            FROM raw_master_water_energy_provision
            GROUP BY DATE(date_time)
        ) wp ON DATE(m.ts) = wp.entry_date
        ORDER BY m.ts ASC;
    """)

    with engine.connect() as conn:
        df_raw = pd.read_sql(master_sql, conn)

    df_raw['ts'] = pd.to_datetime(df_raw['ts']).dt.tz_convert('Europe/Istanbul')
    df_raw = df_raw.set_index('ts').sort_index()

    df_raw['usd_try'] = df_raw['usd_try'].ffill().bfill()
    df_raw['brent_oil_usd'] = df_raw['brent_oil_usd'].ffill().bfill()
    df_raw['natural_gas_grf_try'] = df_raw['natural_gas_grf_try'].ffill().bfill()
    if 'hydro_water_energy_mwh' in df_raw.columns:
        df_raw['hydro_water_energy_mwh'] = df_raw['hydro_water_energy_mwh'].ffill().bfill()

    return df_raw


def run_daily_prediction(force: bool = False):
    """
    Tüm veriyle LightGBM modelini eğitir, gelecek 24 saat için tahmin yapar ve DB'ye yazar.
    force=False ise ve bugün/yarın için tahminler zaten DB'de varsa çalıştırmayı atlar.
    """
    logger.info("🔮 Running Daily LightGBM Prediction Pipeline...")
    
    # 1. DB tablosunu doğrula
    create_gold_schema_if_not_exists()

    engine = get_db_engine()

    # 2. Eğer force=False ise veritabanında yarının (gelecek günün) tahminlerinin tam (24 saat) olup olmadığını kontrol et
    if not force:
        with engine.connect() as conn:
            check_sql = text("""
                SELECT COUNT(*) 
                FROM gold.ptf_predictions_daily 
                WHERE target_ts::date >= (CURRENT_DATE + INTERVAL '1 day');
            """)
            count = conn.execute(check_sql).scalar()
            if count and count >= 24:
                max_date = conn.execute(text("SELECT MAX(target_ts::date) FROM gold.ptf_predictions_daily;")).scalar()
                logger.info(f"✅ Tomorrow's predictions ({max_date}) already exist in database ({count} hours). Skipping re-prediction.")
                return
    
    # 3. Tüm geçmiş veriyi yükle
    df_raw = load_all_historical_data()
    logger.info(f"📊 Total historical dataset loaded: {len(df_raw)} records ({df_raw.index.min()} -> {df_raw.index.max()})")

    # 3. Robust Feature Mühendisliği
    df_feat = build_robust_features(df_raw)
    feature_cols = get_feature_columns('robust', df_feat)
    target_col = 'mcp_price_usd'

    # Sadece eğitimde kullanılan sütunlar üzerinde dropna yapılır
    df_model = df_feat.dropna(subset=feature_cols + [target_col]).copy()

    # Son bilinen dolar kuru
    latest_usd_try = float(df_raw['usd_try'].iloc[-1]) if 'usd_try' in df_raw.columns else 35.0

    # 4. LightGBM Eğitimi (Tüm Geçmiş Veri İle)
    X_train = df_model[feature_cols]
    y_train = df_model[target_col].values

    forecaster = LightGBMForecaster()
    forecaster.fit(X_train, y_train)
    logger.info("🌲 LightGBM Model trained successfully on all historical data.")

    # 5. Gelecek 24 Saat İçin Inference Verisi Hazırlama
    last_ts = df_model.index.max()
    next_24h_index = pd.date_range(start=last_ts + pd.Timedelta(hours=1), periods=24, freq='h')
    
    # Son mevcuttaki verileri future df olarak kopyala
    future_df = df_model.tail(24).copy()
    future_df.index = next_24h_index

    # 🚀 Gelecek 24 saatin takvim ve döngüsel özniteliklerini yeni indekse göre güncelle!
    future_df['hour'] = future_df.index.hour
    future_df['dayofweek'] = future_df.index.dayofweek
    future_df['month'] = future_df.index.month
    future_df['quarter'] = future_df.index.quarter
    future_df['dayofyear'] = future_df.index.dayofyear
    future_df['is_weekend'] = (future_df.index.dayofweek >= 5).astype(int)
    future_df['is_peak_hour'] = future_df['hour'].isin([17, 18, 19, 20, 21]).astype(int)

    # 🚀 Gelecek 24 saatin 24h ve 48h lag özniteliklerini en son bilinen gerçek değerlerle güncelle!
    if 'mcp_price_usd' in df_model.columns:
        future_df['mcp_usd_lag_24'] = df_model['mcp_price_usd'].tail(24).values
    if 'load_forecast_mw' in df_model.columns:
        future_df['load_lag_24'] = df_model['load_forecast_mw'].tail(24).values
    if 'kgup_total_mw' in df_model.columns:
        future_df['kgup_lag_24'] = df_model['kgup_total_mw'].tail(24).values
    if 'kgup_wind_mw' in df_model.columns:
        future_df['kgup_wind_lag_24'] = df_model['kgup_wind_mw'].tail(24).values
    if 'kgup_solar_mw' in df_model.columns:
        future_df['kgup_solar_lag_24'] = df_model['kgup_solar_mw'].tail(24).values
    if 'kgup_hydro_mw' in df_model.columns:
        future_df['kgup_hydro_lag_24'] = df_model['kgup_hydro_mw'].tail(24).values
    if 'kgup_gas_mw' in df_model.columns:
        future_df['kgup_gas_lag_24'] = df_model['kgup_gas_mw'].tail(24).values

    if 'smp_usd_lag_48' in df_model.columns:
        future_df['smp_usd_lag_48'] = df_model['smp_usd_lag_48'].tail(24).values
    if 'temperature_lag_48' in df_model.columns:
        future_df['temperature_lag_48'] = df_model['temperature_lag_48'].tail(24).values
    if 'brent_oil_lag_48' in df_model.columns:
        future_df['brent_oil_lag_48'] = df_model['brent_oil_lag_48'].tail(24).values
    if 'natural_gas_grf_lag_48' in df_model.columns:
        future_df['natural_gas_grf_lag_48'] = df_model['natural_gas_grf_lag_48'].tail(24).values

    # 🌡️ Open-Meteo Forecast API üzerinden yarının canlı sıcaklık tahminini çek ve türevlerini hesapla!
    try:
        from src.data_ingestion.api_trials.weather_fetcher import fetch_tomorrow_weighted_temperature_forecast
        weather_fc = fetch_tomorrow_weighted_temperature_forecast()
        tomorrow_temps = weather_fc['temp_c']
        if len(tomorrow_temps) == 24:
            future_df['temp_forecast_lag0'] = tomorrow_temps
        else:
            future_df['temp_forecast_lag0'] = df_model['temperature_c'].tail(24).values
    except Exception as e:
        logger.warning(f"Could not fetch live weather forecast: {e}, falling back to tail(24)")
        future_df['temp_forecast_lag0'] = df_model['temperature_c'].tail(24).values

    future_df['cdh_cooling_load'] = np.maximum(future_df['temp_forecast_lag0'] - 18.0, 0.0)
    future_df['hdh_heating_load'] = np.maximum(18.0 - future_df['temp_forecast_lag0'], 0.0)
    if 'temperature_lag_48' in future_df.columns:
        future_df['temp_diff_from_yesterday'] = future_df['temp_forecast_lag0'] - future_df['temperature_lag_48']

    from src.features.holidays import add_holiday_features
    future_df = add_holiday_features(future_df)

    future_df['sin_hour'] = np.sin(2 * np.pi * future_df['hour'] / 24.0)
    future_df['cos_hour'] = np.cos(2 * np.pi * future_df['hour'] / 24.0)
    future_df['sin_dow'] = np.sin(2 * np.pi * future_df['dayofweek'] / 7.0)
    future_df['cos_dow'] = np.cos(2 * np.pi * future_df['dayofweek'] / 7.0)
    future_df['sin_month'] = np.sin(2 * np.pi * future_df['month'] / 12.0)
    future_df['cos_month'] = np.cos(2 * np.pi * future_df['month'] / 12.0)
    future_df['sin_doy'] = np.sin(2 * np.pi * future_df['dayofyear'] / 365.25)
    future_df['cos_doy'] = np.cos(2 * np.pi * future_df['dayofyear'] / 365.25)

    # Tahmin Üret
    preds_usd = forecaster.predict(future_df[feature_cols])
    preds_try = preds_usd * latest_usd_try

    results_df = pd.DataFrame({
        'target_ts': next_24h_index,
        'predicted_mcp_usd': np.round(preds_usd, 4),
        'predicted_mcp_try': np.round(preds_try, 4),
        'model_name': 'LightGBM_v1'
    })

    # 6. Veritabanı gold.ptf_predictions_daily Tablosuna Kaydet (Upsert / Insert)
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

    records = results_df.to_dict(orient='records')
    with engine.connect() as conn:
        conn.execute(insert_sql, records)
        conn.commit()

    logger.info(f"✅ Successfully wrote 24-hour predictions to gold.ptf_predictions_daily (Range: {next_24h_index.min()} -> {next_24h_index.max()})")
    logger.info(f"💵 Sample Predictions (USD): Min ${preds_usd.min():.2f} | Max ${preds_usd.max():.2f} | Mean ${preds_usd.mean():.2f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_daily_prediction()
