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

# --- LOGGING SETUP ---
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/daily_update.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ETLPipeline")


def run_daily_pipeline(start_date_str: Optional[str] = None, end_date_str: Optional[str] = None) -> None:
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

    for start_dt, end_dt in periods:
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        start_iso = f"{start_str}T00:00:00+03:00"
        end_iso = f"{end_str}T23:59:59+03:00"
        period_key = start_dt.strftime("%Y-%m") if (end_dt - start_dt).days > 20 else start_str

        logger.info(f"\n⚡ --- PERIOD: {start_str} to {end_str} ---")

        # 1. Market Clearing Price (PTF / MCP)
        mcp_data = fetcher.fetch_eptr2_service("mcp", start_iso, end_iso)
        db.ingest_mcp(mcp_data, period_key)

        # 2. System Marginal Price (SMF / SMP)
        smp_data = fetcher.fetch_eptr2_service("smp", start_iso, end_iso)
        db.ingest_smp(smp_data, period_key)

        # 3. Load Forecast (LEP / Yük Tahmini)
        load_data = fetcher.fetch_eptr2_service("load-plan", start_iso, end_iso)
        db.ingest_load_forecast(load_data, period_key)

        # 4. Final Day-Ahead Generation Plan (KGÜP)
        kgup_data = fetcher.fetch_eptr2_service("kgup", start_iso, end_iso)
        db.ingest_kgup(kgup_data, period_key)

        # 5. Real-Time Actual Generation (Gerçekleşen Üretim)
        rt_gen_data = fetcher.fetch_eptr2_service("rt-gen", start_iso, end_iso)
        db.ingest_actual_generation(rt_gen_data, period_key)

        # 6. Real-Time Actual Consumption (Gerçekleşen Tüketim)
        rt_cons_data = fetcher.fetch_eptr2_service("rt-cons", start_iso, end_iso)
        db.ingest_actual_consumption(rt_cons_data, period_key)

        # 7. Day-Ahead Bids and Offers
        bids_data = fetcher.fetch_eptr2_service("dpp-bids", start_iso, end_iso)
        offers_data = fetcher.fetch_eptr2_service("dpp-offers", start_iso, end_iso)
        db.ingest_bids_offers(bids_data, offers_data, period_key)

        # 8. Licensed Real-Time Generation (Custom Endpoint)
        licensed_gen_data = fetcher.fetch_licensed_realtime_generation(start_iso, end_iso)
        db.ingest_licensed_realtime_generation(licensed_gen_data, period_key)

        # 9. Installed Capacity (Custom Endpoint)
        installed_cap_data = fetcher.fetch_installed_capacity(start_iso, end_iso)
        db.ingest_installed_capacity(installed_cap_data, period_key)

        # 10. Dam Active Fullness (Custom Endpoint)
        fullness_data = fetcher.fetch_active_fullness(start_iso, end_iso)
        db.ingest_active_fullness(fullness_data, period_key)

        # 11. Dam Water Energy Provision (Custom Endpoint)
        provision_data = fetcher.fetch_water_energy_provision(start_iso, end_iso)
        db.ingest_water_energy_provision(provision_data, period_key)

        # 12. Natural Gas Daily Reference Price (GRF)
        gas_price_data = fetcher.fetch_natural_gas_daily_price(start_iso, end_iso)
        db.ingest_natural_gas_daily(gas_price_data, period_key)

        # 13. Weather Data (Open-Meteo)
        weather_data = fetch_weather_in_memory(start_str, end_str)
        db.ingest_weather(weather_data, period_key)

        time.sleep(1)

    # 14. Macro Financial Indicators (yfinance USD/TRY & Brent Oil)
    logger.info("\n📈 Ingesting Macro Financial Indicators (USD/TRY & Brent Oil)...")
    macro_data = fetch_macro_in_memory(start_date="2024-01-01")
    db.ingest_macro(macro_data, period_key="ALL")

    logger.info("🎉 In-Memory Direct Database Pipeline completed successfully!")


if __name__ == "__main__":
    run_daily_pipeline()
