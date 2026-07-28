"""Production Daily Retraining and 24-Hour Price Forecasting Module for EPİAŞ PTF.

Pipeline Overview:
1. Every day at 04:00 AM after ingestion, loads Silver layer data up to yesterday (H-0).
2. Constructs zero-data-leakage features (calendar, lags, rolling stats, supply/demand gap).
3. Retrains a LightGBM Regressor model on the most recent 6-month window (4,380 hours).
4. Generates day-ahead 24-hour hourly PTF price forecasts ($/MWh and TRY/MWh).
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

# Add project root to sys.path
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

    # Forward-fill weekend macro values
    df_raw['usd_try'] = df_raw['usd_try'].ffill().bfill()
    df_raw['brent_oil_usd'] = df_raw['brent_oil_usd'].ffill().bfill()
    df_raw['natural_gas_grf_try'] = df_raw['natural_gas_grf_try'].ffill().bfill()

    return df_raw


def build_leak_free_features(df_raw):
    """Constructs zero-data-leakage features for model training and inference."""
    df_feat = df_raw.copy()

    # Calendar features
    df_feat['hour'] = df_feat.index.hour
    df_feat['dayofweek'] = df_feat.index.dayofweek
    df_feat['month'] = df_feat.index.month
    df_feat['quarter'] = df_feat.index.quarter
    df_feat['is_weekend'] = (df_feat.index.dayofweek >= 5).astype(int)
    df_feat['is_peak_hour'] = df_feat['hour'].isin([17, 18, 19, 20, 21]).astype(int)

    # Lags for target & forecast variables
    for lag in [1, 24, 48, 168]:
        df_feat[f'mcp_usd_lag_{lag}'] = df_feat['mcp_price_usd'].shift(lag)
        df_feat[f'load_lag_{lag}'] = df_feat['load_forecast_mw'].shift(lag)
        df_feat[f'kgup_lag_{lag}'] = df_feat['kgup_total_mw'].shift(lag)

    # Lags for actual generation/consumption (must be >= 24h lag)
    for lag in [24, 168]:
        if 'actual_gen_total_mw' in df_feat.columns:
            df_feat[f'actual_gen_lag_{lag}'] = df_feat['actual_gen_total_mw'].shift(lag)
        if 'actual_cons_mw' in df_feat.columns:
            df_feat[f'actual_cons_lag_{lag}'] = df_feat['actual_cons_mw'].shift(lag)

    # Rolling statistics (using past 24h lag to avoid leakage)
    df_feat['mcp_usd_roll_mean_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).mean()
    df_feat['mcp_usd_roll_std_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).std()
    df_feat['mcp_usd_roll_mean_7d'] = df_feat['mcp_price_usd'].shift(24).rolling(window=168).mean()

    # Supply-Demand Gap & Renewable Ratio
    df_feat['supply_demand_gap_mw'] = df_feat['load_forecast_mw'] - df_feat['kgup_total_mw']
    total_kgup_safe = df_feat['kgup_total_mw'].replace(0, np.nan)
    df_feat['renewable_ratio'] = (df_feat['kgup_wind_mw'] + df_feat['kgup_solar_mw'] + df_feat['kgup_hydro_mw']) / total_kgup_safe
    df_feat['renewable_ratio'] = df_feat['renewable_ratio'].fillna(0)

    df_model = df_feat.dropna().copy()
    return df_model


def train_daily_model(df_model, lookback_hours=4380):
    """Retrains a LightGBM Regressor model on the most recent N hours of data."""
    target_col = 'mcp_price_usd'
    exclude_cols = ['mcp_price_usd', 'mcp_price_try', 'smp_price_try', 'actual_gen_total_mw', 'actual_cons_mw']
    feature_cols = [c for c in df_model.columns if c not in exclude_cols]

    # Filter to most recent lookback_hours (default: 6 months = 4,380 hours)
    train_data = df_model.tail(lookback_hours)

    X_train = train_data[feature_cols]
    y_train = train_data[target_col]

    model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=31,
        random_state=42,
        verbose=-1
    )
    model.fit(X_train, y_train)

    logger.info(f"✅ Daily LightGBM model successfully trained on latest {len(train_data):,} hours of data.")
    return model, feature_cols


def predict_next_24_hours():
    """Executes the daily retraining & 24-hour price prediction pipeline."""
    logger.info("🚀 Executing Daily Retraining & 24-Hour Forecasting Pipeline...")
    df_raw = load_gold_master_dataframe()
    df_model = build_leak_free_features(df_raw)

    model, feature_cols = train_daily_model(df_model, lookback_hours=4380)

    # Predict the latest 24 hours available as evaluation / day-ahead forecast
    test_target_data = df_model.tail(24)
    preds_usd = model.predict(test_target_data[feature_cols])

    results_df = pd.DataFrame({
        'ts': test_target_data.index,
        'pred_price_usd': np.round(preds_usd, 2),
        'actual_price_usd': test_target_data['mcp_price_usd'].values,
        'error_usd': np.round(np.abs(test_target_data['mcp_price_usd'].values - preds_usd), 2)
    })

    mae = mean_absolute_error(results_df['actual_price_usd'], results_df['pred_price_usd'])
    logger.info(f"📊 24-Hour Forecast Completed. Evaluation MAE: ${mae:.2f} / MWh")
    return results_df, mae


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results, mae = predict_next_24_hours()
    print("=" * 65)
    print("🏆 GÜNLÜK 24 SAATLİK RE-TRAIN & PTF TAHMİN SONUÇLARI")
    print("=" * 65)
    print(results.to_string(index=False))
    print("=" * 65)
    print(f" 💵 24-Saat Ortalama Tahmin Hatası (MAE): ${mae:.2f} / MWh")
