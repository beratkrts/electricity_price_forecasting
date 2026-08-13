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
                predicted_mcp_usd_p10 NUMERIC(10, 4),
                predicted_mcp_try_p10 NUMERIC(10, 4),
                predicted_mcp_usd_p90 NUMERIC(10, 4),
                predicted_mcp_try_p90 NUMERIC(10, 4),
                model_name VARCHAR(50) DEFAULT 'LightGBM_v1',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (target_ts, model_name)
            );
        """))
        # Sütunlar yoksa ekle (Geriye dönük uyumluluk)
        conn.execute(text("ALTER TABLE gold.ptf_predictions_daily ADD COLUMN IF NOT EXISTS predicted_mcp_usd_p10 NUMERIC(10, 4);"))
        conn.execute(text("ALTER TABLE gold.ptf_predictions_daily ADD COLUMN IF NOT EXISTS predicted_mcp_try_p10 NUMERIC(10, 4);"))
        conn.execute(text("ALTER TABLE gold.ptf_predictions_daily ADD COLUMN IF NOT EXISTS predicted_mcp_usd_p90 NUMERIC(10, 4);"))
        conn.execute(text("ALTER TABLE gold.ptf_predictions_daily ADD COLUMN IF NOT EXISTS predicted_mcp_try_p90 NUMERIC(10, 4);"))
        conn.commit()
        
        # Tablo verisini kontrol et
        count = conn.execute(text("SELECT COUNT(*) FROM gold.ptf_predictions_daily;")).scalar()

    # Connection kapandıktan sonra backfill gerekiyorsa çalıştır
    if run_backfill_if_empty and count < 1000:
        logger.info("⚡ First-time deployment detected or empty gold table! Automatically running 2-year (730-day) backfill for dashboard history...")
        from scripts.backfill_pre_forecasts import run_pre_forecasts_backfill
        from scripts.backfill_gold_predictions import backfill_historical_predictions
        try:
            logger.info("Step 1: Running Pre-Forecasts Backfill (Load, Solar, Wind)...")
            run_pre_forecasts_backfill(num_days=730)
            logger.info("Step 2: Running PTF Model Backfill...")
            backfill_historical_predictions(num_days=730)
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
            wf.turkey_weighted_temperature_forecast_c AS temperature_forecast_c,
            mc.usd_try,
            mc.brent_oil_usd,
            ng.gas_reference_price_try AS natural_gas_grf_try,
            wp.hydro_water_energy_mwh,
            pf.predicted_load_lag0,
            pf.predicted_solar_lag0,
            pf.predicted_wind_lag0
        FROM raw_mcp_hourly m
        LEFT JOIN raw_smp_hourly s ON m.ts = s.ts
        LEFT JOIN raw_load_forecast_hourly l ON m.ts = l.ts
        LEFT JOIN raw_kgup_hourly k ON m.ts = k.ts
        LEFT JOIN raw_actual_generation_hourly g ON m.ts = g.ts
        LEFT JOIN raw_actual_consumption_hourly c ON m.ts = c.ts
        LEFT JOIN raw_weather_hourly w ON m.ts = w.ts
        LEFT JOIN raw_weather_forecast_hourly wf ON m.ts = wf.ts
        LEFT JOIN raw_macro_daily mc ON DATE(m.ts) = mc.entry_date
        LEFT JOIN raw_natural_gas_daily ng ON DATE(m.ts) = ng.entry_date
        LEFT JOIN (
            SELECT DATE(date_time) AS entry_date, SUM(water_energy_provision_mwh) AS hydro_water_energy_mwh
            FROM raw_master_water_energy_provision
            GROUP BY DATE(date_time)
        ) wp ON DATE(m.ts) = wp.entry_date
        LEFT JOIN gold.kgup_load_pre_forecasts pf ON m.ts = pf.target_ts
        ORDER BY m.ts ASC;
    """)

    with engine.connect() as conn:
        df_raw = pd.read_sql(master_sql, conn)

    ts_series = pd.to_datetime(df_raw['ts'])
    if ts_series.dt.tz is None:
        df_raw['ts'] = ts_series.dt.tz_localize('Europe/Istanbul')
    else:
        df_raw['ts'] = ts_series.dt.tz_convert('Europe/Istanbul')
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
    
    # 1. DB tablosunu doğrula ve boşsa otomatik 2 yıllık backfill tetikle
    create_gold_schema_if_not_exists()

    engine = get_db_engine()

    # 2. Eğer force=False ise veritabanında yarının tahminlerinin tam olup olmadığını kontrol et
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

    # Son 3 günün Rüzgar/Güneş pre-forecast tahminlerini güncelle
    from scripts.backfill_pre_forecasts import run_pre_forecasts_backfill
    logger.info("🌤️ Generating daily Pre-Forecasts (Wind, Solar, Load) for the last 3 days...")
    run_pre_forecasts_backfill(num_days=3, df_raw=df_raw)

    # 3. Robust Feature Mühendisliği
    df_feat = build_robust_features(df_raw)
    feature_cols = get_feature_columns('robust', df_feat)
    target_col = 'mcp_price_usd'

    # Sadece eğitimde kullanılan sütunlar üzerinde dropna yapılır
    df_model = df_feat.dropna(subset=feature_cols + [target_col]).copy()

    # Son bilinen dolar kuru (4-Aşamalı dinamik çözümleyici: DB dataframe -> Canlı API -> DB Query -> ECB API)
    from fetch_epias_data import resolve_usd_try_rate
    latest_usd_try = resolve_usd_try_rate(df=df_raw, engine=engine)

    # 4. LightGBM Eğitimi (Tüm Geçmiş Veri İle - 3 Başlı Quantile Regression)
    X_train = df_model[feature_cols]
    y_train = df_model[target_col].values

    # P50 (Medyan - Klasik Nokta Tahmini)
    forecaster = LightGBMForecaster(params={
        'objective': 'quantile', 'alpha': 0.50,
        'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63,
        'min_child_samples': 10,
        'verbose': -1, 'random_state': 42
    })
    forecaster.fit(X_train, y_train)

    # P10 (Alt Sınır - %10 Güven)
    forecaster_p10 = LightGBMForecaster(params={
        'objective': 'quantile', 'alpha': 0.10,
        'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63,
        'min_child_samples': 10,
        'verbose': -1, 'random_state': 42
    })
    forecaster_p10.fit(X_train, y_train)

    # P90 (Üst Sınır - %90 Güven)
    forecaster_p90 = LightGBMForecaster(params={
        'objective': 'quantile', 'alpha': 0.90,
        'n_estimators': 300, 'learning_rate': 0.03, 'max_depth': 8, 'num_leaves': 63,
        'min_child_samples': 10,
        'verbose': -1, 'random_state': 42
    })
    forecaster_p90.fit(X_train, y_train)
    logger.info("🌲 3-Head LightGBM Quantile Models (P10, P50, P90) trained successfully.")

    # 5. Gelecek 24 Saat İçin Inference Verisi Hazırlama (GÖP Piyasasında Tahmin Hedefi HER ZAMAN Yarındır - T+1)
    # ═══════════════════════════════════════════════════════════════════════════════
    # K1 FIX: Artık future_df'i MANUEL inşa etmiyoruz. Bunun yerine df_raw'a yarının
    # 24 saatlik placeholder satırlarını ekliyoruz, canlı verileri (hava durumu,
    # pre-forecast) bu satırlara enjekte ediyoruz, ve ardından EĞİTİMDE KULLANILAN
    # AYNI build_robust_features() pipeline'ını çalıştırarak tüm lag, rolling, ratio
    # ve rejim özniteliklerinin OTOMATIK ve DOĞRU hesaplanmasını sağlıyoruz.
    # ═══════════════════════════════════════════════════════════════════════════════
    target_tomorrow = (pd.Timestamp.now(tz="Europe/Istanbul") + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    next_24h_index = pd.date_range(start=f"{target_tomorrow} 00:00:00+03:00", periods=24, freq="h")
    
    # CRITICAL FIX: Ensure df_model actually has data up to "today" (target_tomorrow - 1 day)
    target_today_str = (pd.Timestamp.now(tz="Europe/Istanbul")).strftime("%Y-%m-%d")
    last_available_date = df_model.index.max().strftime("%Y-%m-%d")
    
    days_gap = (pd.Timestamp(target_today_str) - pd.Timestamp(last_available_date)).days
    if days_gap > 2:
        logger.error(f"❌ Cannot generate prediction for {target_tomorrow}! Data gap too large ({days_gap} days). Latest: {last_available_date}, Expected: {target_today_str}. Aborting.")
        raise RuntimeError(f"Data gap too large ({days_gap} days). Latest data: {last_available_date}, Expected: {target_today_str}")
    elif days_gap > 0:
        logger.warning(f"⚠️ Data gap: {days_gap} day(s). Latest data: {last_available_date}. Proceeding with available data.")

    # --- ADIM 5a: df_raw'a yarının 24 saatlik placeholder satırlarını ekle ---
    df_extended = df_raw.copy()
    tomorrow_placeholder = pd.DataFrame(index=next_24h_index)
    
    # Yarın için bilinen ham değerleri ileriye taşı (ffill): kur, petrol, doğalgaz vb.
    for col in df_extended.columns:
        tomorrow_placeholder[col] = np.nan
    df_extended = pd.concat([df_extended, tomorrow_placeholder])
    
    # Forward-fill macro değişkenler (kur, petrol, doğalgaz - bunlar gün içinde değişmez)
    for macro_col in ['usd_try', 'brent_oil_usd', 'natural_gas_grf_try', 'hydro_water_energy_mwh']:
        if macro_col in df_extended.columns:
            df_extended[macro_col] = df_extended[macro_col].ffill()
    
    # Yarının son bilinen saatlik üretim/tüketim/yük verilerini bugünden kopyala (T → T+1 proxy)
    for proxy_col in ['load_forecast_mw', 'kgup_total_mw', 'kgup_gas_mw', 'kgup_wind_mw', 
                       'kgup_solar_mw', 'kgup_hydro_mw', 'kgup_coal_mw',
                       'actual_gen_total_mw', 'actual_cons_mw', 'smp_price_try']:
        if proxy_col in df_extended.columns:
            today_values = df_raw[proxy_col].tail(24).values
            df_extended.loc[next_24h_index, proxy_col] = today_values

    # --- ADIM 5b: Canlı hava durumu tahminini yarının satırlarına enjekte et ---
    try:
        from src.data_ingestion.api_trials.weather_fetcher import fetch_tomorrow_weighted_temperature_forecast
        from db.ingest_epias import EpiasDBIngestor
        weather_fc = fetch_tomorrow_weighted_temperature_forecast()
        tomorrow_temps = weather_fc.get('temp_c', [])
        tomorrow_times = weather_fc.get('time', [])
        
        if len(tomorrow_temps) == 24:
            records_fc = [{'date_time': t, 'turkey_weighted_temperature_c': temp} for t, temp in zip(tomorrow_times, tomorrow_temps)]
            EpiasDBIngestor().ingest_weather_forecast(records_fc)
            df_extended.loc[next_24h_index, 'temperature_c'] = tomorrow_temps
            df_extended.loc[next_24h_index, 'temperature_forecast_c'] = tomorrow_temps
        else:
            # Bugünün sıcaklığını proxy olarak kullan
            df_extended.loc[next_24h_index, 'temperature_c'] = df_raw['temperature_c'].tail(24).values if 'temperature_c' in df_raw.columns else 25.0
    except Exception as e:
        from src.utils.fallback_logger import log_fallback
        log_fallback("DailyPredictionPipeline", f"Live weather forecast API failed ({e}), falling back to today's temperature")
        logger.warning(f"Could not fetch live weather forecast: {e}, falling back to today's temperature")
        if 'temperature_c' in df_raw.columns:
            df_extended.loc[next_24h_index, 'temperature_c'] = df_raw['temperature_c'].tail(24).values

    # --- ADIM 5c: Pre-Forecast (Rüzgar/Güneş/Tüketim) tahminlerini enjekte et ---
    from src.features.pre_forecasters import fetch_openmeteo_wind_history, build_pre_forecast_features, train_and_predict_pre_forecasters
    
    try:
        min_date = df_raw.index.min().strftime('%Y-%m-%d')
        max_date = df_raw.index.max().strftime('%Y-%m-%d')
        df_wind = fetch_openmeteo_wind_history(min_date, max_date)
        
        # Pre-forecaster özellikleri (eğitim verisi)
        df_pre_feat = build_pre_forecast_features(df_raw, df_wind)
        train_pre_df = df_pre_feat.copy()
        
        # CRITICAL FIX: Pass a trailing window (last 20 days) so lag_1d...lag_14d exist for tomorrow!
        trailing_start = next_24h_index.min() - pd.Timedelta(days=20)
        future_window = df_extended.loc[trailing_start:].copy()
        if df_wind is not None:
            overlap_cols = [c for c in df_wind.columns if c in future_window.columns]
            if overlap_cols:
                future_window = future_window.drop(columns=overlap_cols)
        future_pre_full = build_pre_forecast_features(future_window, df_wind)
        future_pre_df = future_pre_full.loc[next_24h_index].copy()
        
        # Pre-forecast tahmin et
        preds_df = train_and_predict_pre_forecasters(train_pre_df, future_pre_df)
        
        # Yarının satırlarına enjekte et
        if 'predicted_load_lag0' in preds_df.columns:
            df_extended.loc[next_24h_index, 'predicted_load_lag0'] = preds_df['predicted_load_lag0'].values
        if 'predicted_solar_lag0' in preds_df.columns:
            df_extended.loc[next_24h_index, 'predicted_solar_lag0'] = preds_df['predicted_solar_lag0'].values
        if 'predicted_wind_lag0' in preds_df.columns:
            df_extended.loc[next_24h_index, 'predicted_wind_lag0'] = preds_df['predicted_wind_lag0'].values
        
        # DB'ye kaydet (Audit için)
        insert_pre_sql = text("""
            INSERT INTO gold.kgup_load_pre_forecasts (target_ts, predicted_load_lag0, predicted_solar_lag0, predicted_wind_lag0)
            VALUES (:target_ts, :predicted_load_lag0, :predicted_solar_lag0, :predicted_wind_lag0)
            ON CONFLICT (target_ts) DO UPDATE SET 
                predicted_load_lag0 = EXCLUDED.predicted_load_lag0,
                predicted_solar_lag0 = EXCLUDED.predicted_solar_lag0,
                predicted_wind_lag0 = EXCLUDED.predicted_wind_lag0;
        """)
        for col in ['predicted_load_lag0', 'predicted_solar_lag0', 'predicted_wind_lag0']:
            if col not in preds_df.columns:
                preds_df[col] = 0.0
        recs = preds_df.reset_index().rename(columns={'index': 'target_ts', 'ts': 'target_ts'}).to_dict('records')
        with engine.connect() as conn:
            conn.execute(insert_pre_sql, recs)
            conn.commit()
    except Exception as e:
        from src.utils.fallback_logger import log_fallback
        log_fallback("DailyPredictionPipeline", f"Pre-forecast ML generation failed ({e}), falling back to EPİAŞ load/wind/solar forecasts")
        logger.error(f"Pre-forecast generation failed: {e}")
        if 'load_forecast_mw' in df_raw.columns:
            df_extended.loc[next_24h_index, 'predicted_load_lag0'] = df_raw['load_forecast_mw'].tail(24).values
        if 'kgup_solar_mw' in df_raw.columns:
            df_extended.loc[next_24h_index, 'predicted_solar_lag0'] = df_raw['kgup_solar_mw'].tail(24).values
        if 'kgup_wind_mw' in df_raw.columns:
            df_extended.loc[next_24h_index, 'predicted_wind_lag0'] = df_raw['kgup_wind_mw'].tail(24).values

    # --- ADIM 5d: Genişletilmiş veri üzerinde TAM feature pipeline'ını çalıştır ---
    # Bu sayede tüm lag (24, 48, 168), rolling (mean, std, 7d), ratio, rejim flag,
    # supply-demand gap, pressure ratio, cyclic, holiday, ve CDH/HDH öznitelikleri
    # eğitimle BİREBİR AYNI şekilde otomatik hesaplanır.
    df_extended_feat = build_robust_features(df_extended)
    
    # Yarının 24 satırını çıkar — bu artık tam ve doğru feature'lara sahip
    future_df = df_extended_feat.loc[next_24h_index].copy()
    
    # Eksik feature'ları 0 ile doldur (nadiren olur ama güvenlik için)
    for col in feature_cols:
        if col in future_df.columns:
            future_df[col] = future_df[col].fillna(0.0)
        else:
            future_df[col] = 0.0
            logger.warning(f"⚠️ Feature '{col}' not found in future_df, filled with 0.0")

    # Tahmin Üret (3 Model)
    preds_usd = forecaster.predict(future_df[feature_cols])
    preds_usd_p10 = forecaster_p10.predict(future_df[feature_cols])
    preds_usd_p90 = forecaster_p90.predict(future_df[feature_cols])

    # Quantile Crossover Koruması (Monotonic Guarantee: P10 <= P50 <= P90)
    preds_usd_p10 = np.minimum(preds_usd_p10, preds_usd)
    preds_usd_p90 = np.maximum(preds_usd_p90, preds_usd)

    preds_try = preds_usd * latest_usd_try
    preds_try_p10 = preds_usd_p10 * latest_usd_try
    preds_try_p90 = preds_usd_p90 * latest_usd_try

    preds_try_p10 = np.minimum(preds_try_p10, preds_try)
    preds_try_p90 = np.maximum(preds_try_p90, preds_try)

    results_df = pd.DataFrame({
        'target_ts': next_24h_index,
        'predicted_mcp_usd': np.round(preds_usd, 4),
        'predicted_mcp_try': np.round(preds_try, 4),
        'predicted_mcp_usd_p10': np.round(preds_usd_p10, 4),
        'predicted_mcp_try_p10': np.round(preds_try_p10, 4),
        'predicted_mcp_usd_p90': np.round(preds_usd_p90, 4),
        'predicted_mcp_try_p90': np.round(preds_try_p90, 4),
        'model_name': 'LightGBM_v1'
    })

    # 6. Veritabanı gold.ptf_predictions_daily Tablosuna Kaydet (Upsert / Insert)
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

    records = results_df.to_dict(orient='records')
    with engine.connect() as conn:
        conn.execute(insert_sql, records)
        conn.commit()

    logger.info(f"✅ Successfully wrote 24-hour predictions to gold.ptf_predictions_daily (Range: {next_24h_index.min()} -> {next_24h_index.max()})")
    logger.info(f"💵 Sample Predictions (USD): Min ${preds_usd.min():.2f} | Max ${preds_usd.max():.2f} | Mean ${preds_usd.mean():.2f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_daily_prediction()
