"""
Geçmiş bir gün aralığı için canlı T+1 tahmin akışını (predict_daily_pipeline.py
ADIM 5a + 5c + 5d) BİREBİR replay eder ve sonucu gold tablolarına yazar.

Kullanım amacı: bir arıza penceresindeki bozuk `gold.kgup_load_pre_forecasts` ve
`gold.ptf_predictions_daily` satırlarını, DÜZELTİLMİŞ kodla (forecast-API'li
ön-tahminci) yeniden üretmek. Backtest DEĞİL — her hedef gün için yalnız o
sabah bilinebilecek veri kullanılır (T→T+1 proxy, D-1 kuru, saklanmış hava tahmini).

    # önce kuru çalıştır (yazmaz, sadece kıyas tablosu basar)
    docker exec enerji_etl_app python scripts/replay_and_write.py --start 2026-08-28 --end 2026-08-30
    # sonuç iyiyse yaz
    docker exec enerji_etl_app python scripts/replay_and_write.py --start 2026-08-28 --end 2026-08-30 --write

NOT: regenerate edilen ön-tahmin rüzgar hızı OpenMeteo arşiv/forecast-recent'ten
gelir → o sabahki gerçek D-1 tahmininden biraz daha iyi (küçük ileriye-bakış).
Kabul edilebilir: dashboard'daki tüm geçmiş satırlar benzer şekilde üretiliyor.
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from db.connection import get_db_engine
from sqlalchemy import text
from src.features.feature_engineering import build_robust_features, get_feature_columns
from src.models.lightgbm_model import LightGBMForecaster
from src.features.pre_forecasters import (
    load_wind_features, build_pre_forecast_features,
    train_and_predict_pre_forecasters, assert_wind_available,
)
from predict_daily_pipeline import load_all_historical_data
from fetch_epias_data import resolve_usd_try_rate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ReplayAndWrite")

IST = "Europe/Istanbul"
LGB_PARAMS = dict(objective="quantile", n_estimators=300, learning_rate=0.03,
                  max_depth=8, num_leaves=63, min_child_samples=10,
                  verbose=-1, random_state=42)
PROXY_COLS = ["load_forecast_mw", "kgup_total_mw", "kgup_gas_mw", "kgup_wind_mw",
              "kgup_solar_mw", "kgup_hydro_mw", "kgup_coal_mw",
              "actual_gen_total_mw", "actual_cons_mw", "smp_price_try"]
MACRO_COLS = ["usd_try", "brent_oil_usd", "natural_gas_grf_try", "hydro_water_energy_mwh"]

PF_UPSERT = text("""
    INSERT INTO gold.kgup_load_pre_forecasts
        (target_ts, predicted_load_lag0, predicted_solar_lag0, predicted_wind_lag0)
    VALUES (:target_ts, :predicted_load_lag0, :predicted_solar_lag0, :predicted_wind_lag0)
    ON CONFLICT (target_ts) DO UPDATE SET
        predicted_load_lag0 = EXCLUDED.predicted_load_lag0,
        predicted_solar_lag0 = EXCLUDED.predicted_solar_lag0,
        predicted_wind_lag0 = EXCLUDED.predicted_wind_lag0,
        created_at = CURRENT_TIMESTAMP;
""")
PRED_UPSERT = text("""
    INSERT INTO gold.ptf_predictions_daily
        (target_ts, predicted_mcp_usd, predicted_mcp_try,
         predicted_mcp_usd_p10, predicted_mcp_try_p10,
         predicted_mcp_usd_p90, predicted_mcp_try_p90, model_name)
    VALUES (:target_ts, :predicted_mcp_usd, :predicted_mcp_try,
            :predicted_mcp_usd_p10, :predicted_mcp_try_p10,
            :predicted_mcp_usd_p90, :predicted_mcp_try_p90, :model_name)
    ON CONFLICT (target_ts, model_name) DO UPDATE SET
        predicted_mcp_usd = EXCLUDED.predicted_mcp_usd,
        predicted_mcp_try = EXCLUDED.predicted_mcp_try,
        predicted_mcp_usd_p10 = EXCLUDED.predicted_mcp_usd_p10,
        predicted_mcp_try_p10 = EXCLUDED.predicted_mcp_try_p10,
        predicted_mcp_usd_p90 = EXCLUDED.predicted_mcp_usd_p90,
        predicted_mcp_try_p90 = EXCLUDED.predicted_mcp_try_p90,
        created_at = CURRENT_TIMESTAMP;
""")


def preforecast_for_day(df_raw, hist, d_start, d_idx):
    """ADIM 5c: rüzgar/güneş/yük ön-tahmini — canlı load_wind_features + ML."""
    df_wind = load_wind_features(hist.index.min().strftime("%Y-%m-%d"),
                                 d_start.strftime("%Y-%m-%d"))
    train_pre = build_pre_forecast_features(hist, df_wind)

    trailing = df_raw.loc[d_start - pd.Timedelta(days=20):].copy()
    if df_wind is not None:
        trailing = trailing.drop(columns=[c for c in df_wind.columns if c in trailing.columns],
                                 errors="ignore")
    future_pre_full = build_pre_forecast_features(trailing, df_wind)
    future_pre = future_pre_full.loc[d_idx].copy()

    assert_wind_available(future_pre, d_idx, context=f"{d_start.date()} replay pre-forecast")
    preds = train_and_predict_pre_forecasters(train_pre, future_pre)
    for c in ["predicted_load_lag0", "predicted_solar_lag0", "predicted_wind_lag0"]:
        if c not in preds.columns:
            preds[c] = 0.0
    return preds.reindex(d_idx)


def price_for_day(hist, d_idx, d_start, preds_pf, engine):
    """ADIM 5a + 5d: T→T+1 proxy + full feature pipeline + 3-head quantile."""
    placeholder = pd.DataFrame(index=d_idx, columns=hist.columns, dtype="float64")
    ext = pd.concat([hist, placeholder])

    for c in MACRO_COLS:
        if c in ext.columns:
            ext[c] = ext[c].ffill()
    for c in PROXY_COLS:
        if c in ext.columns:
            ext.loc[d_idx, c] = hist[c].tail(24).values

    # hava tahmini: o gün için saklanmış raw_weather_forecast_hourly; yoksa dünün proxy'si
    wf = pd.read_sql(text("SELECT ts, turkey_weighted_temperature_forecast_c t "
                          "FROM raw_weather_forecast_hourly WHERE ts >= :a AND ts < :b ORDER BY ts"),
                     engine, params={"a": d_idx[0].isoformat(), "b": (d_idx[-1] + pd.Timedelta(hours=1)).isoformat()})
    if len(wf) == 24:
        wf["ts"] = pd.to_datetime(wf["ts"], utc=True).dt.tz_convert(IST)
        temps = wf.set_index("ts")["t"].reindex(d_idx).values
    else:
        logger.warning("  %s: saklanmış hava tahmini eksik (%d/24), dünün sıcaklığı proxy",
                       d_start.date(), len(wf))
        temps = hist["temperature_c"].tail(24).values
    for c in ("temperature_c", "temperature_forecast_c"):
        if c in ext.columns:
            ext.loc[d_idx, c] = temps

    for c in ["predicted_load_lag0", "predicted_solar_lag0", "predicted_wind_lag0"]:
        ext.loc[d_idx, c] = preds_pf[c].values

    feat = build_robust_features(ext)
    fcols = get_feature_columns("robust", feat)
    train = feat.loc[feat.index < d_start].dropna(subset=fcols + ["mcp_price_usd"])
    fut = feat.loc[d_idx, fcols].fillna(0.0)

    out = {}
    for q, alpha in (("p50", 0.50), ("p10", 0.10), ("p90", 0.90)):
        m = LightGBMForecaster(params={**LGB_PARAMS, "alpha": alpha})
        m.fit(train[fcols], train["mcp_price_usd"].values)
        out[q] = m.predict(fut)
    p50, p10, p90 = out["p50"], np.minimum(out["p10"], out["p50"]), np.maximum(out["p90"], out["p50"])

    fx = float(hist["usd_try"].dropna().iloc[-1])
    return pd.DataFrame({
        "target_ts": d_idx,
        "predicted_mcp_usd": np.round(p50, 4), "predicted_mcp_try": np.round(p50 * fx, 4),
        "predicted_mcp_usd_p10": np.round(p10, 4), "predicted_mcp_try_p10": np.round(p10 * fx, 4),
        "predicted_mcp_usd_p90": np.round(p90, 4), "predicted_mcp_try_p90": np.round(p90 * fx, 4),
        "model_name": "LightGBM_v1",
    }), fx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--write", action="store_true", help="verilmezse kuru çalışır, DB'ye yazmaz")
    a = ap.parse_args()

    engine = get_db_engine()
    df_raw = load_all_historical_data()
    logger.info("veri %s -> %s (%d saat)", df_raw.index.min(), df_raw.index.max(), len(df_raw))

    actual = pd.read_sql(text("SELECT ts, price_usd FROM raw_mcp_hourly WHERE ts >= :a"),
                         engine, params={"a": a.start})
    actual["ts"] = pd.to_datetime(actual["ts"], utc=True).dt.tz_convert(IST)
    actual = actual.set_index("ts")["price_usd"]

    days = pd.date_range(a.start, a.end, freq="D", tz=IST)
    pf_recs, pred_recs, summary = [], [], []
    for d in days:
        d_idx = pd.date_range(d, periods=24, freq="h", tz=IST)
        hist = df_raw[df_raw.index < d]
        if len(hist) < 2000:
            logger.warning("%s atlandı: yetersiz geçmiş", d.date()); continue

        preds_pf = preforecast_for_day(df_raw, hist, d, d_idx)
        pred_df, fx = price_for_day(hist, d_idx, d, preds_pf, engine)

        for ts, r in preds_pf.iterrows():
            pf_recs.append({"target_ts": ts.to_pydatetime(),
                            "predicted_load_lag0": float(r.predicted_load_lag0),
                            "predicted_solar_lag0": float(r.predicted_solar_lag0),
                            "predicted_wind_lag0": float(r.predicted_wind_lag0)})
        pred_recs += pred_df.assign(target_ts=pred_df.target_ts.dt.to_pydatetime()).to_dict("records")

        a_mean = actual.reindex(d_idx).mean()
        summary.append((d.date(), preds_pf.predicted_wind_lag0.mean(),
                        pred_df.predicted_mcp_usd.mean(), a_mean,
                        pred_df.predicted_mcp_usd.mean() - a_mean, fx))

    s = pd.DataFrame(summary, columns=["gun", "pre_wind_MW", "pred_usd", "gercek_usd", "bias", "fx"])
    print("\n" + s.round(2).to_string(index=False) + "\n")

    if not a.write:
        logger.info("KURU ÇALIŞMA — DB'ye yazılmadı. Yazmak için --write ekle.")
        return

    with engine.begin() as conn:
        conn.execute(PF_UPSERT, pf_recs)
        conn.execute(PRED_UPSERT, pred_recs)
    logger.info("YAZILDI: %d ön-tahmin satırı, %d tahmin satırı", len(pf_recs), len(pred_recs))


if __name__ == "__main__":
    main()
