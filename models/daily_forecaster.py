"""Production Daily Retraining and Day-Ahead (24-Hour) Price Forecasting Module.

Calendar & Data Timeline Alignment:
- Today is T (e.g., 28 July). EPİAŞ publishes T's prices yesterday, so DB max MCP price is 28 July 23:00.
- Every day at 04:00 AM (or early afternoon before 12:30 PM deadline):
  1. We load all historical data up to T (28 July 23:00).
  2. Retrain LightGBM Regressor on the most recent 6 months (4,380 hours).
  3. Predict TOMORROW T+1 (29 July 00:00 to 29 July 23:00) 24-hour Day-Ahead PTF prices ($/MWh and TRY/MWh).
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sqlalchemy import text
from sklearn.metrics import mean_absolute_error

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from db.connection import get_db_engine

logger = logging.getLogger(__name__)


def load_gold_master_dataframe():
    """Loads and merges Silver layer tables into a unified hourly time series DataFrame."""
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
            ng.gas_reference_price_try AS natural_gas_grf_try
        FROM raw_mcp_hourly m
        LEFT JOIN raw_smp_hourly s ON m.ts = s.ts
        LEFT JOIN raw_load_forecast_hourly l ON m.ts = l.ts
        LEFT JOIN raw_kgup_hourly k ON m.ts = k.ts
        LEFT JOIN raw_actual_generation_hourly g ON m.ts = g.ts
        LEFT JOIN raw_actual_consumption_hourly c ON m.ts = c.ts
        LEFT JOIN raw_weather_hourly w ON m.ts = w.ts
        LEFT JOIN raw_macro_daily mc ON DATE(m.ts) = mc.entry_date
        LEFT JOIN raw_natural_gas_daily ng ON DATE(m.ts) = ng.entry_date
        ORDER BY m.ts ASC;
    """)

    with engine.connect() as conn:
        df_raw = pd.read_sql(master_sql, conn)

    df_raw['ts'] = pd.to_datetime(df_raw['ts']).dt.tz_convert('Europe/Istanbul')
    df_raw = df_raw.set_index('ts').sort_index()

    df_raw['usd_try'] = df_raw['usd_try'].ffill().bfill()
    df_raw['brent_oil_usd'] = df_raw['brent_oil_usd'].ffill().bfill()
    df_raw['natural_gas_grf_try'] = df_raw['natural_gas_grf_try'].ffill().bfill()

    return df_raw


def build_leak_free_features(df_raw):
    """Constructs zero-data-leakage features for training and inference."""
    df_feat = df_raw.copy()

    df_feat['hour'] = df_feat.index.hour
    df_feat['dayofweek'] = df_feat.index.dayofweek
    df_feat['month'] = df_feat.index.month
    df_feat['quarter'] = df_feat.index.quarter
    df_feat['is_weekend'] = (df_feat.index.dayofweek >= 5).astype(int)
    df_feat['is_peak_hour'] = df_feat['hour'].isin([17, 18, 19, 20, 21]).astype(int)

    for lag in [1, 24, 48, 168]:
        df_feat[f'mcp_usd_lag_{lag}'] = df_feat['mcp_price_usd'].shift(lag)
        df_feat[f'load_lag_{lag}'] = df_feat['load_forecast_mw'].shift(lag)
        df_feat[f'kgup_lag_{lag}'] = df_feat['kgup_total_mw'].shift(lag)

    for lag in [24, 168]:
        if 'actual_gen_total_mw' in df_feat.columns:
            df_feat[f'actual_gen_lag_{lag}'] = df_feat['actual_gen_total_mw'].shift(lag)
        if 'actual_cons_mw' in df_feat.columns:
            df_feat[f'actual_cons_lag_{lag}'] = df_feat['actual_cons_mw'].shift(lag)

    df_feat['mcp_usd_roll_mean_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).mean()
    df_feat['mcp_usd_roll_std_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).std()
    df_feat['mcp_usd_roll_mean_7d'] = df_feat['mcp_price_usd'].shift(24).rolling(window=168).mean()

    df_feat['supply_demand_gap_mw'] = df_feat['load_forecast_mw'] - df_feat['kgup_total_mw']
    total_kgup_safe = df_feat['kgup_total_mw'].replace(0, np.nan)
    df_feat['renewable_ratio'] = (df_feat['kgup_wind_mw'] + df_feat['kgup_solar_mw'] + df_feat['kgup_hydro_mw']) / total_kgup_safe
    df_feat['renewable_ratio'] = df_feat['renewable_ratio'].fillna(0)

    return df_feat


def train_daily_model(df_model, lookback_hours=4380):
    """Retrains LightGBM Regressor on the most recent N hours of available historical data."""
    target_col = 'mcp_price_usd'
    exclude_cols = ['mcp_price_usd', 'mcp_price_try', 'smp_price_try', 'actual_gen_total_mw', 'actual_cons_mw']
    feature_cols = [c for c in df_model.columns if c not in exclude_cols]

    clean_train = df_model.dropna(subset=[target_col] + feature_cols).tail(lookback_hours)

    X_train = clean_train[feature_cols]
    y_train = clean_train[target_col]

    model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=31,
        random_state=42,
        verbose=-1
    )
    model.fit(X_train, y_train)

    logger.info(f"✅ Daily LightGBM model successfully trained on latest {len(clean_train):,} hours of historical data.")
    return model, feature_cols


def predict_tomorrow_24_hours():
    """Generates 24-hour Day-Ahead PTF forecast for TOMORROW (T+1)."""
    logger.info("🚀 Executing Day-Ahead (T+1) Daily Retraining & Forecasting Pipeline...")
    df_raw = load_gold_master_dataframe()

    # Determine last available timestamp in DB (e.g., 2026-07-28 23:00)
    last_db_ts = df_raw.index.max()
    tomorrow_start = last_db_ts + pd.Timedelta(hours=1)
    tomorrow_end = tomorrow_start + pd.Timedelta(hours=23)

    logger.info(f"📅 DB Max Timestamp: {last_db_ts}")
    logger.info(f"🎯 Tomorrow Forecast Target Range: {tomorrow_start} -> {tomorrow_end}")

    # Generate future 24-hour timestamps for tomorrow
    future_timestamps = pd.date_range(start=tomorrow_start, end=tomorrow_end, freq='h')
    df_future = pd.DataFrame(index=future_timestamps)

    # Merge historical raw data with future timestamps
    df_combined = pd.concat([df_raw, df_future]).sort_index()

    # Forward fill forecast/macro variables into tomorrow
    ffill_cols = ['load_forecast_mw', 'kgup_total_mw', 'kgup_gas_mw', 'kgup_wind_mw', 'kgup_solar_mw', 
                  'kgup_hydro_mw', 'kgup_coal_mw', 'temperature_c', 'usd_try', 'brent_oil_usd', 'natural_gas_grf_try']
    for col in ffill_cols:
        if col in df_combined.columns:
            df_combined[col] = df_combined[col].ffill()

    # Build leak-free feature matrix across combined data
    df_feat = build_leak_free_features(df_combined)

    # Train model on historical data only
    model, feature_cols = train_daily_model(df_feat, lookback_hours=4380)

    # Predict tomorrow's 24 hours
    tomorrow_features = df_feat.loc[future_timestamps, feature_cols]
    preds_usd = model.predict(tomorrow_features)
    usd_rates = df_combined.loc[future_timestamps, 'usd_try'].values

    forecast_df = pd.DataFrame({
        'ts': future_timestamps,
        'pred_price_usd': np.round(preds_usd, 2),
        'pred_price_try': np.round(preds_usd * usd_rates, 2),
        'usd_try_rate': np.round(usd_rates, 4)
    })

    logger.info(f"✨ Successfully generated Day-Ahead 24-Hour Forecast for {tomorrow_start.strftime('%Y-%m-%d')}.")
    return forecast_df


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    forecast_df = predict_tomorrow_24_hours()
    print("=" * 75)
    print(f"🏆 YARININ GÜN ÖNCESİ PİYASASI (24-SAAT) PTF TAHMİN TABLOSU ({forecast_df['ts'].min().strftime('%Y-%m-%d')})")
    print("=" * 75)
    print(forecast_df.to_string(index=False))
    print("=" * 75)
