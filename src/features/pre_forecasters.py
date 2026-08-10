import pandas as pd
import numpy as np
import httpx
import logging
from sklearn.linear_model import Ridge
import lightgbm as lgb
from sqlalchemy import text
from db.connection import get_db_engine

logger = logging.getLogger("PreForecasters")

def fetch_openmeteo_wind_history(start_date_str, end_date_str):
    cities = {
        'izmir': {'lat': 38.41, 'lon': 27.14},
        'canakkale': {'lat': 40.15, 'lon': 26.40},
        'balikesir': {'lat': 39.64, 'lon': 27.88}
    }
    df_weather = None
    logger.info(f"Fetching Open-Meteo wind data from {start_date_str} to {end_date_str}...")
    for city, coords in cities.items():
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={coords['lat']}&longitude={coords['lon']}&start_date={start_date_str}&end_date={end_date_str}&hourly=wind_speed_100m&timezone=Europe%2FIstanbul"
        try:
            resp = httpx.get(url, timeout=30.0)
            data = resp.json()
            if 'hourly' not in data:
                logger.error(f"Failed to fetch {city}: {data}")
                continue
            times = pd.to_datetime(data['hourly']['time']).tz_localize('Europe/Istanbul', ambiguous='infer', nonexistent='shift_forward')
            speeds = data['hourly']['wind_speed_100m']
            temp_df = pd.DataFrame({'ts': times, f'wind_{city}': speeds}).set_index('ts')
            if df_weather is None: df_weather = temp_df
            else: df_weather = df_weather.join(temp_df)
        except Exception as e:
            logger.error(f"Error fetching wind for {city}: {e}")
    return df_weather

def build_pre_forecast_features(df_raw, df_wind):
    df = df_raw.copy()
    if df_wind is not None:
        df = df.join(df_wind)
    
    df['hour'] = df.index.hour
    df['dayofweek'] = df.index.dayofweek
    df['month'] = df.index.month
    df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)

    if 'temp_c' in df.columns:
        df['cdh'] = np.maximum(df['temp_c'] - 18.0, 0.0)
        df['hdh'] = np.maximum(18.0 - df['temp_c'], 0.0)

    for city in ['izmir', 'canakkale', 'balikesir']:
        if f'wind_{city}' in df.columns:
            df[f'wind_power_{city}'] = df[f'wind_{city}'] ** 3

    targets = ['load_forecast_mw', 'kgup_wind', 'kgup_solar']
    for t in targets:
        if t in df.columns:
            for i in range(1, 15):
                df[f'{t}_lag_{i}d'] = df[t].shift(24 * i)
                
    return df

def train_and_predict_pre_forecasters(train_df, test_df):
    """
    Trains Load, Solar, and Wind models on train_df, and predicts on test_df.
    Returns a DataFrame with the predictions for the test_df index.
    """
    results = pd.DataFrame(index=test_df.index)
    
    # 1. Load Forecast
    load_feats = ['hour', 'dayofweek', 'month', 'is_weekend', 'temp_c', 'cdh', 'hdh'] + [f'load_forecast_mw_lag_{i}d' for i in range(1, 15)]
    valid_load_feats = [c for c in load_feats if c in train_df.columns]
    
    if len(valid_load_feats) > 0 and 'load_forecast_mw' in train_df.columns:
        tr_clean = train_df.dropna(subset=valid_load_feats + ['load_forecast_mw'])
        if len(tr_clean) > 100:
            lgb_load = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42, n_jobs=-1, verbose=-1)
            lgb_load.fit(tr_clean[valid_load_feats], tr_clean['load_forecast_mw'])
            results['predicted_load_lag0'] = lgb_load.predict(test_df[valid_load_feats])

    # 2. Solar KGUP
    solar_feats = [f'kgup_solar_lag_{i}d' for i in range(1, 15)]
    valid_solar_feats = [c for c in solar_feats if c in train_df.columns]
    
    if len(valid_solar_feats) > 0 and 'kgup_solar_mw' in train_df.columns:
        tr_clean = train_df.dropna(subset=valid_solar_feats + ['kgup_solar_mw'])
        if len(tr_clean) > 100:
            ridge_solar = Ridge(alpha=100.0)
            ridge_solar.fit(tr_clean[valid_solar_feats], tr_clean['kgup_solar_mw'])
            preds = ridge_solar.predict(test_df[valid_solar_feats].fillna(0))
            results['predicted_solar_lag0'] = np.maximum(preds, 0)

    # 3. Wind KGUP
    wind_feats = ['hour', 'month'] + [f'wind_power_{c}' for c in ['izmir', 'canakkale', 'balikesir']] + [f'wind_{c}' for c in ['izmir', 'canakkale', 'balikesir']] + [f'kgup_wind_lag_{i}d' for i in range(1, 15)]
    valid_wind_feats = [c for c in wind_feats if c in train_df.columns]
    
    if len(valid_wind_feats) > 0 and 'kgup_wind_mw' in train_df.columns:
        tr_clean = train_df.dropna(subset=valid_wind_feats + ['kgup_wind_mw'])
        if len(tr_clean) > 100:
            lgb_wind = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42, n_jobs=-1, verbose=-1)
            lgb_wind.fit(tr_clean[valid_wind_feats], tr_clean['kgup_wind_mw'])
            preds = lgb_wind.predict(test_df[valid_wind_feats])
            results['predicted_wind_lag0'] = np.maximum(preds, 0)

    return results

def create_pre_forecasts_schema_if_not_exists():
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gold.kgup_load_pre_forecasts (
                target_ts TIMESTAMP WITH TIME ZONE PRIMARY KEY,
                predicted_load_lag0 NUMERIC(10, 4),
                predicted_solar_lag0 NUMERIC(10, 4),
                predicted_wind_lag0 NUMERIC(10, 4),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()
