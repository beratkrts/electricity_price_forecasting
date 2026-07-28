"""24/7 Continuous Background Daemon Service.

Performs an initial startup sync/gap-fill, then enters a 24/7 loop sleeping until
4:00 AM Europe/Istanbul time to trigger daily execution of the in-memory ETL pipeline.

Supports Laptop Sleep & Resume safety:
Uses short 60-second polling checks so if a laptop/computer goes to sleep overnight,
the daemon immediately detects missed 4:00 AM runs upon waking up and executes
the ETL pipeline instantly without needing a manual container restart.
"""

import time
import logging
import sys
from datetime import timedelta
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


def get_target_4am() -> pd.Timestamp:
    """Calculates target datetime for 4:00 AM Europe/Istanbul time."""
    now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
    target = now_istanbul.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_istanbul >= target:
        target += timedelta(days=1)
    return target


def main() -> None:
    logger.info("⚡ Starting EPİAŞ & Weather Continuous In-Memory Background Daemon ⚡")

    # 1. Initial startup sync and gap check
    logger.info("🔍 Running initial startup sync and data gap check...")
    try:
        run_daily_pipeline()
    except Exception as e:
        logger.error(f"Error during initial startup sync: {e}")

    # 2. Continuous 24/7 loop with laptop sleep/wake protection
    target_time = get_target_4am()
    
    while True:
        now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
        seconds_remaining = (target_time - now_istanbul).total_seconds()

        # If target 4:00 AM has arrived or was passed while computer was asleep
        if seconds_remaining <= 0:
            logger.info("⏰ 4:00 AM Scheduled Trigger (or missed run detected after sleep)! Running daily ETL pipeline...")
            try:
                run_daily_pipeline()
            except Exception as e:
                logger.error(f"Error during scheduled ETL execution: {e}")
            
            # Reset target to next 4:00 AM
            target_time = get_target_4am()
            now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
            seconds_remaining = (target_time - now_istanbul).total_seconds()
            hours = seconds_remaining / 3600
            logger.info(
                f"⏳ Sleeping until next 4:00 AM target: {target_time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({hours:.2f} hours remaining)."
            )

        # Sleep in short 60-second chunks to safely handle computer sleep/wake events
        sleep_duration = min(60, max(1, int(seconds_remaining)))
        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()
