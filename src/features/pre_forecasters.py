import pandas as pd
import numpy as np
import httpx
import logging
from sklearn.linear_model import Ridge
import lightgbm as lgb
from sqlalchemy import text
from db.connection import get_db_engine

logger = logging.getLogger("PreForecasters")

# Rüzgar santrallerinin yoğunlaştığı üç il. İki fonksiyon da bunu kullanıyor.
CITY_COORDS = {
    'izmir': {'lat': 38.41, 'lon': 27.14},
    'canakkale': {'lat': 40.15, 'lon': 26.40},
    'balikesir': {'lat': 39.64, 'lon': 27.88},
}
WIND_COLS = [f'wind_{c}' for c in CITY_COORDS]

def fetch_openmeteo_wind_history(start_date_str, end_date_str):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_wind_history_hourly (
                ts TIMESTAMP WITH TIME ZONE PRIMARY KEY,
                wind_izmir NUMERIC,
                wind_canakkale NUMERIC,
                wind_balikesir NUMERIC
            );
        """))
        conn.commit()
        max_ts = conn.execute(text("SELECT MAX(ts) FROM raw_wind_history_hourly")).scalar()

    if max_ts is not None:
        fetch_start_date = max_ts.strftime('%Y-%m-%d')
    else:
        fetch_start_date = start_date_str

    if fetch_start_date < end_date_str:
        logger.info(f"Fetching missing Open-Meteo wind data from {fetch_start_date} to {end_date_str}...")
        cities = CITY_COORDS
        df_weather = None
        failed_cities = []
        for city, coords in cities.items():
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={coords['lat']}&longitude={coords['lon']}&start_date={fetch_start_date}&end_date={end_date_str}&hourly=wind_speed_100m&timezone=Europe%2FIstanbul"
            try:
                resp = httpx.get(url, timeout=30.0)
                data = resp.json()
                if 'hourly' not in data:
                    failed_cities.append(city)
                    continue
                times = pd.to_datetime(data['hourly']['time']).tz_localize('Europe/Istanbul', ambiguous='infer', nonexistent='shift_forward')
                speeds = data['hourly']['wind_speed_100m']
                temp_df = pd.DataFrame({'ts': times, f'wind_{city}': speeds}).set_index('ts')
                if df_weather is None: df_weather = temp_df
                else: df_weather = df_weather.join(temp_df)
            except Exception as e:
                failed_cities.append(city)
                logger.error(f"Error fetching wind for {city}: {e}")

        # Hepsi düşerse SESSİZCE DEVAM ETME. Pre-forecast'lar değiştirilemez
        # (gold.kgup_load_pre_forecasts, ON CONFLICT ... WHERE ... IS NULL), yani
        # rüzgar verisi olmadan hesaplanan bir satır kalıcı olarak yanlış kalır ve
        # ancak elle DELETE ile düzeltilebilir. Değiştirilemez bir depoda "eksik"
        # geri alınabilir, "yanlış" geri alınamaz — o yüzden burada hata fırlatıyoruz.
        # 19 Ağustos 2026'da tam bu oldu: internet yokken üç şehir de DNS hatası
        # verdi, satırlar yine yazıldı, ve sağlıklı koşu üzerine yazamadı.
        if failed_cities and df_weather is None:
            raise RuntimeError(
                f"Open-Meteo wind fetch failed for every city ({', '.join(failed_cities)}). "
                "Refusing to write pre-forecasts: rows in gold.kgup_load_pre_forecasts are "
                "immutable, so a row computed without wind data stays permanently wrong."
            )
        if failed_cities:
            logger.warning(
                "Wind fetch failed for %d/%d cities (%s); continuing with the rest.",
                len(failed_cities), len(cities), ", ".join(failed_cities))

        if df_weather is not None and not df_weather.empty:
            recs = df_weather.reset_index().to_dict('records')
            for rec in recs:
                for k in rec.keys():
                    if pd.isna(rec[k]): rec[k] = None
            insert_sql = text("""
                INSERT INTO raw_wind_history_hourly (ts, wind_izmir, wind_canakkale, wind_balikesir)
                VALUES (:ts, :wind_izmir, :wind_canakkale, :wind_balikesir)
                ON CONFLICT (ts) DO UPDATE SET 
                    wind_izmir = EXCLUDED.wind_izmir,
                    wind_canakkale = EXCLUDED.wind_canakkale,
                    wind_balikesir = EXCLUDED.wind_balikesir;
            """)
            with engine.connect() as conn:
                conn.execute(insert_sql, recs)
                conn.commit()

    df_all_wind = pd.read_sql("SELECT * FROM raw_wind_history_hourly ORDER BY ts", engine, index_col='ts')
    if df_all_wind.index.tz is None:
        df_all_wind.index = df_all_wind.index.tz_localize('Europe/Istanbul')
    else:
        df_all_wind.index = df_all_wind.index.tz_convert('Europe/Istanbul')
    return df_all_wind

def fetch_openmeteo_wind_forecast(past_days: int = 2, forecast_days: int = 3):
    """Yarının rüzgar hızı — ARŞİV API'si bunu veremez.

    `archive-api.open-meteo.com` yapısı gereği yalnızca geçmişi döndürüyor;
    yarın istenince açıkça reddediyor:
        "Parameter 'end_date' is out of allowed range from 1940-01-01 to <bugün>"

    Tahmin sabah 04:00'te üretiliyor ve hedefi ERTESİ GÜN. O saatte yarının
    KGÜP'ü ve yük tahmini yayımlanmamış oluyor (GÖP öğlene kadar açık) — zaten
    ön-tahmincilerin varlık sebebi bu. Ama METEOROLOJİ tahmini geleceğe bakar
    ve 04:00'te elimizdedir. Ön-tahmincinin sahip olabileceği tek geleceğe
    dönük sinyal budur; arşiv API'si kullanıldığı sürece yarının rüzgar hızı
    NaN kalıyor ve LightGBM sessizce 14 günlük otoregresif gecikmeye
    yaslanıyor (ölçüm: her gün ortalama ~4.000 MW düşük tahmin).

    DB'YE YAZILMAZ. `raw_wind_history_hourly`'nin MAX(ts)'i arşiv çekiminin
    nereden başlayacağını belirliyor; oraya yarını yazmak bugünün reanaliz
    verisinin kalıcı olarak atlanmasına yol açardı.
    """
    frames, failed = None, []
    for city, coords in CITY_COORDS.items():
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}"
               f"&longitude={coords['lon']}&hourly=wind_speed_100m"
               f"&past_days={past_days}&forecast_days={forecast_days}"
               f"&timezone=Europe%2FIstanbul")
        try:
            data = httpx.get(url, timeout=30.0).json()
            if 'hourly' not in data:
                failed.append(city)
                continue
            idx = pd.to_datetime(data['hourly']['time']).tz_localize(
                'Europe/Istanbul', ambiguous='infer', nonexistent='shift_forward')
            s = pd.Series(data['hourly']['wind_speed_100m'], index=idx, name=f'wind_{city}')
            frames = s.to_frame() if frames is None else frames.join(s, how='outer')
        except Exception as exc:  # noqa: BLE001
            logger.error("Open-Meteo wind FORECAST failed for %s: %s", city, exc)
            failed.append(city)

    if failed:
        logger.warning("Wind forecast failed for %d/%d cities (%s)",
                       len(failed), len(CITY_COORDS), ", ".join(failed))
    return frames


def load_wind_features(start_date_str, end_date_str, with_forecast: bool = True):
    """Arşiv (geçmiş reanaliz) + forecast (bugünün kalanı ve yarın).

    Arşiv önceliklidir: bir saat için reanaliz varsa o kullanılır, forecast
    yalnızca arşivin ulaşamadığı saatleri doldurur.
    """
    # Arşivden ASLA bugünden ötesi istenmemeli: API 400 döndürüyor, üç şehir de
    # düşmüş sayılıyor ve "hepsi düştü" koruması yanlış yere tetikleniyor.
    # `end_date_str` çoğu çağrıda df_raw'ın son günü = akşam fiyat çekimi
    # sayesinde YARIN olabiliyor.
    today = pd.Timestamp.now(tz='Europe/Istanbul').strftime('%Y-%m-%d')
    archive_end = min(end_date_str, today)
    hist = fetch_openmeteo_wind_history(start_date_str, archive_end)
    if not with_forecast:
        return hist
    fc = fetch_openmeteo_wind_forecast()
    if fc is None or fc.empty:
        logger.warning("Wind forecast unavailable; falling back to archive only.")
        return hist
    if hist is None or hist.empty:
        return fc
    gap = fc[~fc.index.isin(hist.index)]
    if gap.empty:
        return hist
    logger.info("Wind: archive %s → %s, forecast adds %d hours (to %s)",
                hist.index.min().date(), hist.index.max(), len(gap), gap.index.max())
    return pd.concat([hist, gap]).sort_index()


def assert_wind_available(df_features, target_index, context: str = ""):
    """Hedef saatlerde rüzgar hızı yoksa SESSİZCE DEVAM ETME.

    `gold.kgup_load_pre_forecasts` değiştirilemez (ON CONFLICT ... WHERE ... IS
    NULL). Rüzgar hızı NaN iken hesaplanan satır kalıcı olarak yanlış kalır ve
    ancak elle DELETE ile düzelir. LightGBM NaN'ı kendi hallettiği için bu hata
    çökme olarak değil, sessiz bir kalite kaybı olarak görünüyordu.
    """
    present = [c for c in WIND_COLS if c in df_features.columns]
    missing_cols = [c for c in WIND_COLS if c not in df_features.columns]
    if not present:
        raise RuntimeError(
            f"Wind speed columns absent for {context or 'target hours'} "
            f"({', '.join(missing_cols)}). Refusing to write immutable pre-forecasts.")
    sub = df_features.reindex(target_index)[present]
    if sub.isna().all(axis=None):
        raise RuntimeError(
            f"Wind speed is entirely missing for {context or 'target hours'} "
            f"({target_index.min()} → {target_index.max()}). The archive API cannot "
            "return future dates — use load_wind_features(), which merges the "
            "forecast API. Refusing to write immutable pre-forecasts.")
    n_bad = int(sub.isna().all(axis=1).sum())
    if n_bad:
        logger.warning("Wind speed missing for %d/%d target hours (%s)",
                       n_bad, len(sub), context)


def build_pre_forecast_features(df_raw, df_wind):
    df = df_raw.copy()
    if df_wind is not None:
        df = df.join(df_wind)
    
    # Çapraz platform ve tz-aware uyumluluğu için DatetimeIndex garantisi
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True).tz_convert('Europe/Istanbul')

    df['hour'] = df.index.hour
    df['dayofweek'] = df.index.dayofweek
    df['month'] = df.index.month
    df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)

    temp_col = None
    for c in ['temperature_c', 'temp_c', 'turkey_weighted_temperature_c']:
        if c in df.columns:
            temp_col = c
            break
    if temp_col:
        df['temp_c'] = df[temp_col]
        df['cdh'] = np.maximum(df['temp_c'] - 18.0, 0.0)
        df['hdh'] = np.maximum(18.0 - df['temp_c'], 0.0)

    for city in ['izmir', 'canakkale', 'balikesir']:
        if f'wind_{city}' in df.columns:
            df[f'wind_power_{city}'] = df[f'wind_{city}'] ** 3

    targets = ['load_forecast_mw', 'kgup_wind_mw', 'kgup_solar_mw', 'kgup_wind', 'kgup_solar']
    for t in targets:
        if t in df.columns:
            prefix = t.replace('_mw', '')
            for i in range(1, 15):
                df[f'{t}_lag_{i}d'] = df[t].shift(24 * i)
                df[f'{prefix}_lag_{i}d'] = df[t].shift(24 * i)
                
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
