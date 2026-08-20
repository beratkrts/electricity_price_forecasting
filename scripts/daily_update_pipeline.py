"""Daily In-Memory ETL Pipeline.

Streamlines data collection from EPİAŞ Transparency API, Open-Meteo Weather API,
and yfinance Macro indicators directly into PostgreSQL Bronze and Silver layers
without intermediate disk-based JSON storage.
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

import os
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

from db.ingest_epias import EpiasDBIngestor
from fetch_epias_data import (
    EpiasFetcher,
    fetch_weather_in_memory,
    fetch_tomorrow_weather_forecast_in_memory,
    fetch_macro_in_memory,
)
from predict_daily_pipeline import run_daily_prediction

# --- LOGGING SETUP ---
os.makedirs("logs", exist_ok=True)

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 1. Main log handler (INFO and above)
main_file_handler = RotatingFileHandler("logs/daily_update.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
main_file_handler.setLevel(logging.INFO)
main_file_handler.setFormatter(log_formatter)

# 2. Anomalies / Errors dedicated handler (WARNING and ERROR only - concise, non-repetitive)
anomaly_file_handler = RotatingFileHandler("logs/anomalies.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
anomaly_file_handler.setLevel(logging.WARNING)
anomaly_file_handler.setFormatter(log_formatter)

# 3. Console output handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Prevent duplicate handlers on re-initialization
if not root_logger.handlers:
    root_logger.addHandler(main_file_handler)
    root_logger.addHandler(anomaly_file_handler)
    root_logger.addHandler(console_handler)

logger = logging.getLogger("ETLPipeline")

# How far back a first-time install ingests raw history. Moved from 2023-01-01 to cover the
# 2021-2022 shocks (Jan 2022 Iran gas cut, Feb 2022 war shock) that the crisis/event impact
# analysis needs. This does NOT widen the price model's training window — that is pinned
# separately by predict_daily_pipeline.TRAINING_DATA_START, because 2021-2022 was the
# azami fiyat limiti (price cap) regime and would distort the live model.
HISTORY_START = "2021-01-01"


def run_daily_pipeline(start_date_str: Optional[str] = None, end_date_str: Optional[str] = None, force_prediction: bool = False) -> None:
    """Executes the in-memory ETL pipeline for the specified date range or defaults to historical sync."""
    logger.info("🚀 Starting In-Memory Direct Database Ingestion Pipeline...")

    # Her adım kendi istisnasını yutup devam ediyor. Bu bilinçli — tek bir kaynak
    # düştüğünde tüm koşu çökmesin. Ama 19 Ağustos 2026'da internet tamamen yokken
    # 16 adımın HEPSİ düştü ve pipeline yine "başarıyla tamamlandı" yazdı; kimse
    # fark etmedi ve bozuk tahmin sağlıklı koşuyu kilitledi. Artık düşen adımlar
    # sayılıyor ve kapanış mesajı buna göre yazılıyor.
    failed_steps: list[str] = []

    def check_fetched(step: str, data) -> bool:
        """Fetch denendi ama boş döndü mü — SESSİZ başarısızlık kontrolü.

        fetch_epias_data.py üç denemeden sonra istisna FIRLATMIYOR, `return []`
        yapıyor. Ingestor da `if not records: return 0` diyor. Sonuçta adımın
        except bloğu hiç tetiklenmiyor ve başarısızlık hiçbir yere yazılmıyor.
        20 Ağustos 2026'da tam bu oldu: DNS koptu, lisanslı üretim ve kurulu
        kapasite alınamadı, ama log'da tek bir uyarı bile yok.

        Bu yüzden fetch'ten sonra dönen verinin boş olup olmadığına da bakıyoruz.
        Sadece should_fetch() true dönüp gerçekten deneme yapıldıysa çağrılır;
        veri zaten DB'deyse deneme olmaz ve bu kontrol de çalışmaz.
        """
        if not data:
            logger.warning("⚠️ [%s] Fetch returned no data (silent failure, no exception).", step)
            failed_steps.append(step)
            return False
        return True

    # Load environment variables robustly from project_root
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        logger.warning(f"⚠️ .env file not found at {env_path}")

    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    # Initialize DB Ingestor and API Fetcher
    db = EpiasDBIngestor()
    db.init_db()  # Ensure database schema tables exist

    fetcher = EpiasFetcher(username=username, password=password, env_path=str(env_path) if env_path else None)

    today_dt = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    current_month_key = today_dt.strftime("%Y-%m")

    # Determine execution periods
    if start_date_str and end_date_str:
        start_dt = pd.to_datetime(start_date_str)
        end_dt = pd.to_datetime(end_date_str)
        sync_start = start_dt
        periods = [(start_dt, end_dt)]
    else:
        # Smart Auto-Detection: Check if database is empty for initial full backfill
        db_has_data = False
        try:
            with db.engine.connect() as conn:
                res = conn.execute(text("SELECT COUNT(*) FROM raw_mcp_hourly;")).scalar()
                if res and res > 100:
                    db_has_data = True
        except Exception:
            db_has_data = False

        if db_has_data:
            # Daily routine sync: check recent 2 months
            sync_start = (today_dt - pd.DateOffset(months=2)).replace(day=1)
            logger.info("ℹ️ Existing database detected. Running fast daily sync (recent 2 months)...")
        else:
            # Initial first-time run: full historical backfill from HISTORY_START.
            sync_start = pd.to_datetime(HISTORY_START)
            logger.info(f"📦 Empty database detected. Triggering initial full historical backfill from {HISTORY_START}...")

        monthly_starts = pd.date_range(start=sync_start, end=today_dt, freq="MS")
        periods = [
            (m_start, min(m_start + pd.offsets.MonthEnd(1), today_dt))
            for m_start in monthly_starts
        ]

    logger.info(f"Processing {len(periods)} execution period(s)...")

    def should_fetch(source_name: str, p_key: str, s_dt: pd.Timestamp) -> bool:
        """Determines whether API call should be made or skipped."""
        # Always fetch if period is part of the current active month (so new daily data is updated)
        if s_dt.strftime("%Y-%m") == current_month_key:
            return True
        # For past completed months, skip API call if already in DB
        if db.is_period_ingested(source_name, p_key):
            logger.info(f"  ⏩ [{source_name.upper()}] Period '{p_key}' completed historical month already in DB. Skipping API call.")
            return False
        return True

    for start_dt, end_dt in periods:
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        start_iso = f"{start_str}T00:00:00+03:00"
        end_iso = f"{end_str}T23:59:59+03:00"
        period_key = start_dt.strftime("%Y-%m") if (end_dt - start_dt).days > 20 else start_str

        logger.info(f"\n⚡ --- PERIOD: {start_str} to {end_str} ---")

        # 1. Market Clearing Price (PTF / MCP)
        try:
            if should_fetch("mcp", period_key, start_dt):
                mcp_data = fetcher.fetch_eptr2_service("mcp", start_iso, end_iso)
                if check_fetched("MCP", mcp_data):
                    db.ingest_mcp(mcp_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [MCP] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("MCP")

        # 2. System Marginal Price (SMF / SMP)
        try:
            if should_fetch("smp", period_key, start_dt):
                smp_data = fetcher.fetch_eptr2_service("smp", start_iso, end_iso)
                if check_fetched("SMP", smp_data):
                    db.ingest_smp(smp_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [SMP] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("SMP")

        # 3. Load Forecast (LEP / Yük Tahmini)
        try:
            if should_fetch("load_forecast", period_key, start_dt):
                load_data = fetcher.fetch_eptr2_service("load-plan", start_iso, end_iso)
                if check_fetched("LOAD_FORECAST", load_data):
                    db.ingest_load_forecast(load_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [LOAD_FORECAST] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("LOAD_FORECAST")

        # 4. Final Day-Ahead Generation Plan (KGÜP)
        try:
            if should_fetch("kgup", period_key, start_dt):
                kgup_data = fetcher.fetch_eptr2_service("kgup", start_iso, end_iso)
                if check_fetched("KGUP", kgup_data):
                    db.ingest_kgup(kgup_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [KGUP] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("KGUP")

        # 5. Real-Time Actual Generation (Gerçekleşen Üretim)
        try:
            if should_fetch("actual_generation", period_key, start_dt):
                rt_gen_data = fetcher.fetch_eptr2_service("rt-gen", start_iso, end_iso)
                if check_fetched("ACTUAL_GEN", rt_gen_data):
                    db.ingest_actual_generation(rt_gen_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [ACTUAL_GEN] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("ACTUAL_GEN")

        # 6. Real-Time Actual Consumption (Gerçekleşen Tüketim)
        try:
            if should_fetch("actual_consumption", period_key, start_dt):
                rt_cons_data = fetcher.fetch_eptr2_service("rt-cons", start_iso, end_iso)
                if check_fetched("ACTUAL_CONS", rt_cons_data):
                    db.ingest_actual_consumption(rt_cons_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [ACTUAL_CONS] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("ACTUAL_CONS")

        # 7. Day-Ahead Bids and Offers (dam-bid & dam-offer)
        try:
            if should_fetch("bids_offers", period_key, start_dt):
                bids_data = fetcher.fetch_eptr2_service("dam-bid", start_iso, end_iso)
                offers_data = fetcher.fetch_eptr2_service("dam-offer", start_iso, end_iso)
                db.ingest_bids_offers(bids_data, offers_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [BIDS_OFFERS] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("BIDS_OFFERS")

        # 8. Licensed Real-Time Generation (ren-rt-gen via eptr2)
        try:
            if should_fetch("licensed_realtime_generation", period_key, start_dt):
                licensed_gen_data = fetcher.fetch_eptr2_service("ren-rt-gen", start_iso, end_iso)
                db.ingest_licensed_realtime_generation(licensed_gen_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [LICENSED_GEN] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("LICENSED_GEN")

        # 9. Installed Capacity (ren-capacity via eptr2)
        try:
            if should_fetch("installed_capacity", period_key, start_dt):
                installed_cap_data = fetcher.fetch_installed_capacity(period_iso=f"{start_str}T00:00:00+03:00")
                db.ingest_installed_capacity(installed_cap_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [INSTALLED_CAP] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("INSTALLED_CAP")

        # 10. Dam Active Fullness (Custom Endpoint)
        try:
            if should_fetch("active_fullness", period_key, start_dt):
                fullness_data = fetcher.fetch_active_fullness(start_iso, end_iso)
                db.ingest_active_fullness(fullness_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [ACTIVE_FULLNESS] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("ACTIVE_FULLNESS")

        # 11. Dam Water Energy Provision (Custom Endpoint)
        try:
            if should_fetch("water_energy_provision", period_key, start_dt):
                provision_data = fetcher.fetch_water_energy_provision(start_iso, end_iso)
                db.ingest_water_energy_provision(provision_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [WATER_PROVISION] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("WATER_PROVISION")

        # 12. Natural Gas Daily Reference Price (GRF)
        try:
            if should_fetch("natural_gas_daily", period_key, start_dt):
                gas_price_data = fetcher.fetch_natural_gas_daily_price(start_iso, end_iso)
                db.ingest_natural_gas_daily(gas_price_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [NATURAL_GAS] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("NATURAL_GAS")

        # 13. Weather Data (Open-Meteo Archive)
        try:
            if should_fetch("weather", period_key, start_dt):
                weather_data = fetch_weather_in_memory(start_str, end_str)
                if check_fetched("WEATHER", weather_data):
                    db.ingest_weather(weather_data, period_key)
        except Exception as e:
            logger.warning(f"⚠️ [WEATHER] Step skipped due to fetch/ingest error: {e}")
            failed_steps.append("WEATHER")

        time.sleep(0.5)

    # 14. Macro Financial Indicators (USD/TRY & Brent Oil)
    try:
        logger.info("\n📈 Ingesting Macro Financial Indicators (USD/TRY & Brent Oil)...")
        macro_start = sync_start.strftime("%Y-%m-%d")
        logger.info(f"  fetching macro range: {macro_start} -> today")
        macro_data = fetch_macro_in_memory(start_date=macro_start)
        if macro_data:
            db.ingest_macro(macro_data, period_key="ALL")
    except Exception as e:
        logger.warning(f"⚠️ [MACRO] Step skipped due to error: {e}")
        failed_steps.append("MACRO")

    # 15. Live Weather Forecast & Historical Forecast Seeding
    try:
        logger.info("\n🌤️ Ingesting Tomorrow's Live Weather Forecast...")
        weather_fc_data = fetch_tomorrow_weather_forecast_in_memory()
        if weather_fc_data:
            db.ingest_weather_forecast(weather_fc_data)

        # Seed raw_weather_forecast_hourly from raw_weather_hourly for past dates on initial/clean installs
        with db.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO raw_weather_forecast_hourly (ts, turkey_weighted_temperature_forecast_c)
                SELECT ts, turkey_weighted_temperature_c 
                FROM raw_weather_hourly 
                WHERE turkey_weighted_temperature_c IS NOT NULL
                ON CONFLICT (ts) DO NOTHING;
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"⚠️ [WEATHER_FORECAST] Step skipped due to error: {e}")
        failed_steps.append("WEATHER_FORECAST")

    if failed_steps:
        logger.error(
            "❌ ETL completed with %d FAILED step(s): %s — this run's data is INCOMPLETE. "
            "A prediction built on it will be wrong; re-run once connectivity is restored.",
            len(failed_steps), ", ".join(failed_steps))
    else:
        logger.info("🎉 In-Memory Direct Database Pipeline completed successfully!")

    # 16. LightGBM Daily Prediction Execution & DB Ingestion
    # Tahmini EKSİK veriyle üretmek, üretmemekten kötü: gold.ptf_predictions_daily'ye
    # yazılan bozuk bir tahmin, sonraki sağlıklı koşunun "zaten var" kontrolüne
    # takılıp kilit oluyor (19 Ağustos 2026). Kaynaklardan biri düştüyse tahmin
    # adımı hiç çalıştırılmaz; erişim düzelince koşu tekrarlandığında üretilir.
    #
    # EŞİK NEDEN "HERHANGİ BİRİ" DEĞİL: bazı kaynakların düşmesi zararsız
    # (ACTIVE_FULLNESS, WATER_PROVISION geçmişi zaten gelmiyor; MACRO düşerse
    # yfinance mevcut DB değerlerini koruyor). Fiyat modelinin girdisi olan
    # çekirdek seriler düşerse tahmin anlamsızlaşır — kapı sadece onlara bakar.
    CORE_STEPS = {"MCP", "SMP", "LOAD_FORECAST", "KGUP", "ACTUAL_GEN", "ACTUAL_CONS", "WEATHER"}
    failed_core = CORE_STEPS.intersection(failed_steps)

    if failed_core:
        logger.error(
            "⛔ Step 16 SKIPPED: core data steps failed (%s). Refusing to write a forecast "
            "from incomplete data — a bad forecast would block the next healthy run's "
            "'already exists' check. Re-run the pipeline once connectivity is restored.",
            ", ".join(sorted(failed_core)))
    else:
        logger.info("\n🔮 Step 16: Executing LightGBM Daily Prediction & Gold Ingestion...")
        try:
            run_daily_prediction(force=force_prediction)
        except Exception as e:
            logger.error(f"❌ Error during LightGBM daily prediction step: {e}")


def fetch_published_prices(days_ahead: int = 1) -> int:
    """Yayımlanan GÖP takas fiyatlarını çeker. Tam pipeline değil, sadece fiyat.

    NEDEN AYRI BİR FONKSİYON: GÖP sonuçları öğleden sonra (~14:00) yayımlanıyor,
    yani yarının fiyatı bugün öğleden sonra belli oluyor. Ama tek koşumuz 04:00'te
    olduğu için o fiyat veritabanına ancak ERTESİ SABAH giriyordu. Sonuç: bugün
    ürettiğimiz tahminin tutup tutmadığını yarın sabah öğreniyorduk, oysa bu akşam
    öğrenebiliriz. Yaklaşık 14 saatlik gereksiz gecikme.

    Bilinçli olarak DAR tutuldu:
      - sadece MCP çekilir, tam ETL koşmaz
      - tahmin üretmez, pre-forecast'a dokunmaz
      - dolayısıyla 04:00 koşusunun kurduğu hiçbir şeyi bozamaz

    Dönen değer: HEDEF GÜNÜN veritabanındaki saat sayısı (yazılan toplam değil).

    Neden hedef günün sayısı: fiyat geç yayımlanırsa çekim yine de bugünün 24
    saatini getirir ve "başarılı" görünür, ama asıl istediğimiz yarının fiyatıdır.
    Toplam sayıya bakmak bu durumu gizler; çağıran taraf yarının tam gelip
    gelmediğini bilmek zorunda ki gerekirse tekrar denesin.
    """
    logger.info("💰 Fetching published day-ahead prices (light run, no prediction)...")

    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    db = EpiasDBIngestor()
    fetcher = EpiasFetcher(username=username, password=password,
                           env_path=str(env_path) if env_path else None)

    today = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    end = today + pd.Timedelta(days=days_ahead)
    start_iso = f"{today:%Y-%m-%d}T00:00:00+03:00"
    end_iso = f"{end:%Y-%m-%d}T23:59:59+03:00"

    try:
        mcp = fetcher.fetch_eptr2_service("mcp", start_iso, end_iso)
    except Exception as e:
        logger.error("❌ Published price fetch failed: %s", e)
        return 0
    if not mcp:
        logger.warning("⚠️ Published price fetch returned no data — prices may not be out yet.")
        return 0

    db.ingest_mcp(mcp, f"{today:%Y-%m-%d}_pub")

    # Hedef gün (varsayılan: yarın) gerçekten tam geldi mi
    with db.engine.connect() as conn:
        hedef_saat = conn.execute(text(
            "SELECT count(*) FROM raw_mcp_hourly "
            "WHERE (ts AT TIME ZONE 'Europe/Istanbul')::date = :g"),
            {"g": end.date()}).scalar() or 0

    # 23 eşiği yaz/kış saati geçişleri için: o günler 23 veya 25 saat sürebiliyor.
    if hedef_saat >= 23:
        logger.info("✅ Published prices complete for %s (%d hours) — model performance "
                    "can be evaluated today.", end.date(), hedef_saat)
    else:
        logger.warning("⚠️ %s prices not published yet (%d/24 hours). Fetch will be retried.",
                       end.date(), hedef_saat)
    return hedef_saat


if __name__ == "__main__":
    run_daily_pipeline()
