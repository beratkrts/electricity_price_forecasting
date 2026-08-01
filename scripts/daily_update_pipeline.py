import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))
"""Daily In-Memory ETL Pipeline.

Streamlines data collection from EPİAŞ Transparency API, Open-Meteo Weather API,
and yfinance Macro indicators directly into PostgreSQL Bronze and Silver layers
without intermediate disk-based JSON storage.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

from db.ingest_epias import EpiasDBIngestor
from fetch_epias_data import EpiasFetcher, fetch_weather_in_memory, fetch_macro_in_memory
from predict_daily_pipeline import run_daily_prediction

# --- LOGGING SETUP ---
os.makedirs("logs", exist_ok=True)

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 1. Main log handler (INFO and above)
main_file_handler = logging.FileHandler("logs/daily_update.log", encoding="utf-8")
main_file_handler.setLevel(logging.INFO)
main_file_handler.setFormatter(log_formatter)

# 2. Anomalies / Errors dedicated handler (WARNING and ERROR only - concise, non-repetitive)
anomaly_file_handler = logging.FileHandler("logs/anomalies.log", encoding="utf-8")
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


def run_daily_pipeline(start_date_str: Optional[str] = None, end_date_str: Optional[str] = None, force_prediction: bool = False) -> None:
    """Executes the in-memory ETL pipeline for the specified date range or defaults to historical sync."""
    logger.info("🚀 Starting In-Memory Direct Database Ingestion Pipeline...")

    # Load environment variables
    env_path = next(
        (path / ".env" for path in [Path.cwd(), *Path.cwd().parents] if (path / ".env").exists()),
        None,
    )
    if env_path:
        load_dotenv(env_path)

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
        periods = [(start_dt, end_dt)]
    else:
        # Default backfill range: monthly chunks from 2024-01-01 to today
        monthly_starts = pd.date_range(start="2024-01-01", end=today_dt, freq="MS")
        periods = [
            (m_start, min(m_start + pd.offsets.MonthEnd(1), today_dt))
            for m_start in monthly_starts
        ]

    logger.info(f"Processing {len(periods)} execution period(s)...")

    def should_fetch(source_name: str, p_key: str) -> bool:
        """Determines whether API call should be made or skipped."""
        # Always fetch if it's the current active month (so new days are updated daily)
        if p_key == current_month_key:
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
        if should_fetch("mcp", period_key):
            mcp_data = fetcher.fetch_eptr2_service("mcp", start_iso, end_iso)
            db.ingest_mcp(mcp_data, period_key)

        # 2. System Marginal Price (SMF / SMP)
        if should_fetch("smp", period_key):
            smp_data = fetcher.fetch_eptr2_service("smp", start_iso, end_iso)
            db.ingest_smp(smp_data, period_key)

        # 3. Load Forecast (LEP / Yük Tahmini)
        if should_fetch("load_forecast", period_key):
            load_data = fetcher.fetch_eptr2_service("load-plan", start_iso, end_iso)
            db.ingest_load_forecast(load_data, period_key)

        # 4. Final Day-Ahead Generation Plan (KGÜP)
        if should_fetch("kgup", period_key):
            kgup_data = fetcher.fetch_eptr2_service("kgup", start_iso, end_iso)
            db.ingest_kgup(kgup_data, period_key)

        # 5. Real-Time Actual Generation (Gerçekleşen Üretim)
        if should_fetch("actual_generation", period_key):
            rt_gen_data = fetcher.fetch_eptr2_service("rt-gen", start_iso, end_iso)
            db.ingest_actual_generation(rt_gen_data, period_key)

        # 6. Real-Time Actual Consumption (Gerçekleşen Tüketim)
        if should_fetch("actual_consumption", period_key):
            rt_cons_data = fetcher.fetch_eptr2_service("rt-cons", start_iso, end_iso)
            db.ingest_actual_consumption(rt_cons_data, period_key)

        # 7. Day-Ahead Bids and Offers (dam-bid & dam-offer)
        if should_fetch("bids_offers", period_key):
            bids_data = fetcher.fetch_eptr2_service("dam-bid", start_iso, end_iso)
            offers_data = fetcher.fetch_eptr2_service("dam-offer", start_iso, end_iso)
            db.ingest_bids_offers(bids_data, offers_data, period_key)

        # 8. Licensed Real-Time Generation (ren-rt-gen via eptr2)
        if should_fetch("licensed_realtime_generation", period_key):
            licensed_gen_data = fetcher.fetch_eptr2_service("ren-rt-gen", start_iso, end_iso)
            db.ingest_licensed_realtime_generation(licensed_gen_data, period_key)

        # 9. Installed Capacity (ren-capacity via eptr2)
        if should_fetch("installed_capacity", period_key):
            installed_cap_data = fetcher.fetch_installed_capacity(period_iso=f"{start_str}T00:00:00+03:00")
            db.ingest_installed_capacity(installed_cap_data, period_key)

        # 10. Dam Active Fullness (Custom Endpoint)
        if should_fetch("active_fullness", period_key):
            fullness_data = fetcher.fetch_active_fullness(start_iso, end_iso)
            db.ingest_active_fullness(fullness_data, period_key)

        # 11. Dam Water Energy Provision (Custom Endpoint)
        if should_fetch("water_energy_provision", period_key):
            provision_data = fetcher.fetch_water_energy_provision(start_iso, end_iso)
            db.ingest_water_energy_provision(provision_data, period_key)

        # 12. Natural Gas Daily Reference Price (GRF)
        if should_fetch("natural_gas_daily", period_key):
            gas_price_data = fetcher.fetch_natural_gas_daily_price(start_iso, end_iso)
            db.ingest_natural_gas_daily(gas_price_data, period_key)

        # 13. Weather Data (Open-Meteo)
        if should_fetch("weather", period_key):
            weather_data = fetch_weather_in_memory(start_str, end_str)
            db.ingest_weather(weather_data, period_key)

        time.sleep(0.5)

    # 14. Macro Financial Indicators (yfinance USD/TRY & Brent Oil)
    logger.info("\n📈 Ingesting Macro Financial Indicators (USD/TRY & Brent Oil)...")
    macro_data = fetch_macro_in_memory(start_date="2024-01-01")
    db.ingest_macro(macro_data, period_key="ALL")

    logger.info("🎉 In-Memory Direct Database Pipeline completed successfully!")

    # 15. LightGBM Daily Prediction Execution & DB Ingestion
    logger.info("\n🔮 Step 15: Executing LightGBM Daily Prediction & Gold Ingestion...")
    try:
        run_daily_prediction(force=force_prediction)
    except Exception as e:
        logger.error(f"❌ Error during LightGBM daily prediction step: {e}")


if __name__ == "__main__":
    run_daily_pipeline()
