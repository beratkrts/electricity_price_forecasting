"""24/7 Continuous Background Daemon Service.

Performs an initial startup sync/gap-fill, then enters a 24/7 loop sleeping until
4:00 AM Europe/Istanbul time to trigger daily execution of the in-memory ETL pipeline.
"""

import time
import logging
import sys
from datetime import datetime, timedelta
import pandas as pd
from daily_update_pipeline import run_daily_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DaemonService")


def get_seconds_until_next_4am() -> tuple[pd.Timestamp, float]:
    """Calculates target datetime and seconds remaining until 4:00 AM Europe/Istanbul time."""
    now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
    target = now_istanbul.replace(hour=4, minute=0, second=0, microsecond=0)

    if now_istanbul >= target:
        target += timedelta(days=1)

    seconds_remaining = (target - now_istanbul).total_seconds()
    return target, seconds_remaining


def main() -> None:
    logger.info("⚡ Starting EPİAŞ & Weather Continuous In-Memory Background Daemon ⚡")

    # 1. Initial startup sync and gap check
    logger.info("🔍 Running initial startup sync and data gap check...")
    try:
        run_daily_pipeline()
    except Exception as e:
        logger.error(f"Error during initial startup sync: {e}")

    # 2. Continuous 24/7 loop
    while True:
        target_time, seconds_to_wait = get_seconds_until_next_4am()
        hours = seconds_to_wait / 3600
        logger.info(
            f"⏳ Sleeping for {seconds_to_wait:.0f} seconds ({hours:.2f} hours) "
            f"until next scheduled run at {target_time.strftime('%Y-%m-%d %H:%M:%S')} (Istanbul time)."
        )

        time.sleep(seconds_to_wait)

        logger.info("⏰ 4:00 AM Scheduled Trigger! Running daily ETL pipeline...")
        try:
            run_daily_pipeline()
        except Exception as e:
            logger.error(f"Error during scheduled ETL execution: {e}")


if __name__ == "__main__":
    main()
