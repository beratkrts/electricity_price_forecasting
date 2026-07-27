import time
import logging
from datetime import datetime, timedelta
import pandas as pd
from daily_update_pipeline import run_daily_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def get_seconds_until_next_4am():
    """Calculates seconds remaining until the next 4:00 AM Europe/Istanbul time."""
    now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
    target = now_istanbul.replace(hour=4, minute=0, second=0, microsecond=0)
    
    if now_istanbul >= target:
        target += timedelta(days=1)
        
    seconds_remaining = (target - now_istanbul).total_seconds()
    return target, seconds_remaining

def main():
    logging.info("⚡ Starting EPİAŞ & Weather Continuous Background Daemon ⚡")
    
    # 1. Initial check and backfill on startup
    logging.info("🔍 Running initial startup sync & gap check...")
    try:
        run_daily_pipeline()
    except Exception as e:
        logging.error(f"Error during initial sync: {e}")

    # 2. Continuous 24/7 Loop
    while True:
        target_time, seconds_to_wait = get_seconds_until_next_4am()
        hours = seconds_to_wait / 3600
        logging.info(f"⏳ Sleeping for {seconds_to_wait:.0f} seconds ({hours:.2f} hours) until next scheduled run at {target_time.strftime('%Y-%m-%d %H:%M:%S')} Istanbul time.")
        
        time.sleep(seconds_to_wait)
        
        logging.info("⏰ 4:00 AM Triggered! Starting daily scheduled execution...")
        try:
            run_daily_pipeline()
        except Exception as e:
            logging.error(f"Error during scheduled execution: {e}")

if __name__ == "__main__":
    main()
