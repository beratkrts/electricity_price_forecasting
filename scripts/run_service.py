"""24/7 Continuous Background Daemon Service.

Performs an initial startup sync/gap-fill, then enters a 24/7 loop sleeping until
4:00 AM Europe/Istanbul time to trigger daily execution of the in-memory ETL pipeline.

Supports Laptop Sleep & Resume safety:
Uses short 60-second polling checks so if a laptop/computer goes to sleep overnight,
the daemon immediately detects missed 4:00 AM runs upon waking up and executes
the ETL pipeline instantly without needing a manual container restart.
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

import time
import logging
from datetime import timedelta
import pandas as pd
from daily_update_pipeline import run_daily_pipeline, fetch_published_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DaemonService")


#: GÖP sonuçlarının yayımlanmasından sonraki hafif çekim saati.
#: Yarının takas fiyatı öğleden sonra (~14:00) belli oluyor. Tek koşumuz 04:00'te
#: olduğu için o fiyat veritabanına ancak ertesi sabah giriyordu; yani bugün
#: ürettiğimiz tahminin tutup tutmadığını yarın sabah öğreniyorduk. Bu tetikleyici
#: o gecikmeyi ~14 saatten sıfıra indiriyor: akşam fiyat gelir, dashboard aynı
#: gün performansı gösterebilir.
PRICE_FETCH_HOUR = 15


def get_target_4am() -> pd.Timestamp:
    """Calculates target datetime for 4:00 AM Europe/Istanbul time."""
    now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
    target = now_istanbul.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_istanbul > target:
        target += timedelta(days=1)
    return target


def get_target_price_fetch() -> pd.Timestamp:
    """Bugünkü (veya kaçırıldıysa yarınki) fiyat çekim saatini döndürür."""
    now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
    target = now_istanbul.replace(hour=PRICE_FETCH_HOUR, minute=0, second=0, microsecond=0)
    if now_istanbul > target:
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
    price_target = get_target_price_fetch()
    
    while True:
        now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
        seconds_remaining = (target_time - now_istanbul).total_seconds()

        # If target 4:00 AM has arrived or was passed while computer was asleep
        if seconds_remaining <= 0:
            logger.info("⏰ 4:00 AM Scheduled Trigger (or missed run detected after sleep)! Running daily ETL pipeline...")
            max_attempts = 3
            success = False
            for attempt in range(1, max_attempts + 1):
                try:
                    run_daily_pipeline(force_prediction=True)
                    success = True
                    break
                except Exception as e:
                    logger.error(f"Error during scheduled ETL execution (attempt {attempt}/{max_attempts}): {e}")
                    if attempt < max_attempts:
                        logger.info("⏳ Retrying ETL pipeline in 5 minutes...")
                        time.sleep(300)
            
            if not success:
                logger.error("❌ Daily ETL execution failed after all retry attempts.")

            # Reset target to next 4:00 AM
            target_time = get_target_4am()
            now_istanbul = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None)
            seconds_remaining = (target_time - now_istanbul).total_seconds()
            hours = seconds_remaining / 3600
            logger.info(
                f"⏳ Sleeping until next 4:00 AM target: {target_time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({hours:.2f} hours remaining)."
            )

        # Akşam fiyat çekimi — 04:00 koşusundan BAĞIMSIZ ve çok daha dar kapsamlı.
        # Sadece yayımlanan GÖP fiyatını alır; tahmin üretmez, pre-forecast'a
        # dokunmaz, tam ETL koşmaz. Bu yüzden 04:00 koşusunun kurduğu hiçbir şeyi
        # bozamaz. Hata alırsa döngü devam eder — bu çekim kritik yol üzerinde değil,
        # sadece geri bildirimi hızlandırıyor.
        if (price_target - now_istanbul).total_seconds() <= 0:
            logger.info(f"💰 {PRICE_FETCH_HOUR}:00 price fetch trigger — pulling published day-ahead prices...")
            try:
                n = fetch_published_prices()
                if n:
                    logger.info("✅ Published prices in DB — model performance can now be shown same day.")
                else:
                    logger.warning("⚠️ No published prices returned; will retry at next trigger.")
            except Exception as e:
                logger.error(f"Error during scheduled price fetch: {e}")
            price_target = get_target_price_fetch()
            logger.info(f"⏳ Next price fetch: {price_target.strftime('%Y-%m-%d %H:%M:%S')}")

        # Sleep in short 60-second chunks to safely handle computer sleep/wake events
        sleep_duration = min(60, max(1, int(seconds_remaining)))
        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()
