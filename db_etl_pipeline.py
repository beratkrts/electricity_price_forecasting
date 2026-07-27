import os
import sys
import time
import io
import logging
import hashlib
from datetime import timedelta
import pandas as pd
import requests
from dotenv import load_dotenv
from eptr2 import EPTR2
import yfinance as yf
from sqlalchemy import create_engine, text

# Hava durumu kütüphanen (Kendi yazdığın modül)
from api_trials.weather_fetcher import fetch_turkey_weighted_temperature

# =====================================================================
# 🛠️ LOGLAMA & AYARLAR
# =====================================================================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/db_update.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# =====================================================================
# 🔄 PANDAS SÜTUN EŞLEŞTİRME (MAPPING) SÖZLÜKLERİ
# =====================================================================
MAPPINGS = {
    "mcp": {"date": "ts", "price": "price_try", "priceUsd": "price_usd", "priceEur": "price_eur"},
    "smp": {"date": "ts", "price": "system_marginal_price_try"},
    "load_forecast": {"date": "ts", "lep": "load_forecast_mw", "time": "ts"},
    "kgup": {
        "date": "ts", "total": "total_mw", "naturalGas": "natural_gas_mw", "wind": "wind_mw",
        "lignite": "lignite_mw", "blackCoal": "black_coal_mw", "importCoal": "import_coal_mw",
        "fueloil": "fuel_oil_mw", "geothermal": "geothermal_mw", "dammedHydro": "dammed_hydro_mw",
        "riverHydro": "river_hydro_mw", "naphtha": "naphtha_mw", "biomass": "biomass_mw",
        "solar": "solar_mw", "other": "other_mw"
    },
    "actual_generation": {
        "date": "ts", "total": "total_mw", "naturalGas": "natural_gas_mw", "dammedHydro": "dammed_hydro_mw",
        "lignite": "lignite_mw", "riverHydro": "river_hydro_mw", "importCoal": "import_coal_mw",
        "wind": "wind_mw", "solar": "solar_mw", "fueloil": "fuel_oil_mw", "geothermal": "geothermal_mw",
        "asphaltiteCoal": "asphaltite_coal_mw", "blackCoal": "black_coal_mw", "biomass": "biomass_mw",
        "naphta": "naphtha_mw", "lng": "lng_mw", "importExport": "import_export_mw", "wasteheat": "waste_heat_mw"
    },
    "actual_consumption": {"date": "ts", "consumption": "consumption_mw"},
    "macro": {"date": "entry_date", "usd_try": "usd_try", "brent_oil_usd": "brent_oil_usd"},
    "weather": {"time": "ts", "temperature": "turkey_weighted_temperature_c"},
    "active_fullness": {
        "date": "date_time", "damId": "dam_id", "recordId": "record_id",
        "basinName": "basin_name", "damName": "dam_name", "activeFullness": "active_fullness_percent"
    },
    "water_energy_provision": {
        "date": "date_time", "damName": "dam_name", "basinName": "basin_name",
        "waterEnergyProvision": "water_energy_provision_mwh"
    }
}

# =====================================================================
# 🗄️ DATABASE MANAGER (BRONZE & SILVER KATMAN YÖNETİCİSİ)
# =====================================================================
class DatabaseManager:
    def __init__(self):
        env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
        load_dotenv(env_path)
        
        db_user = os.getenv("DB_USER", "postgres")
        db_pass = os.getenv("DB_PASS", "postgres") # Şifreni .env dosyasından okur
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "epias_db")
        
        self.engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")

    def calculate_checksum(self, df: pd.DataFrame) -> str:
        data_str = df.to_json(orient='records', date_format='iso')
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def check_and_insert_ingestion(self, source_name: str, period_key: str, checksum: str, row_count: int):
        with self.engine.begin() as conn:
            check_query = text("SELECT id FROM ingestion_batches WHERE source_name = :source AND checksum = :checksum")
            result = conn.execute(check_query, {"source": source_name, "checksum": checksum}).fetchone()
            
            if result:
                return None # Checksum eşleşti, bu veri zaten var! (Duplicate koruması)
            
            insert_query = text("""
                INSERT INTO ingestion_batches (source_name, period_key, checksum, row_count, status)
                VALUES (:source, :period, :checksum, :rows, 'SUCCESS')
                RETURNING id
            """)
            ingestion_id = conn.execute(insert_query, {
                "source": source_name, "period": period_key, "checksum": checksum, "rows": row_count
            }).scalar()
            return ingestion_id

    def save_to_silver(self, df: pd.DataFrame, table_name: str, source_name: str, period_key: str):
        if df is None or df.empty:
            return False

        checksum = self.calculate_checksum(df)
        try:
            ingestion_id = self.check_and_insert_ingestion(source_name, period_key, checksum, len(df))
            if not ingestion_id:
                logging.info(f"   ⏩ {source_name} ({period_key}) zaten güncel. Pas geçiliyor.")
                return False
                
            df_copy = df.copy()
            df_copy['ingestion_id'] = ingestion_id
            df_copy.to_sql(table_name, self.engine, if_exists='append', index=False)
            logging.info(f"   ✅ {source_name} ({period_key}) DB'ye yazıldı! (ID: {ingestion_id})")
            return True
        except Exception as e:
            logging.error(f"   [!] DB Yazma Hatası ({source_name}): {e}")
            return False

# =====================================================================
# 🚀 ANA ETL BORU HATTI
# =====================================================================
def run_daily_pipeline():
    logging.info("🚀 Starting DB-Integrated EPIAS & Weather Pipeline...")
    
    env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")
    
    eptr = EPTR2(username=username, password=password, dotenv_path=str(env_path))
    db = DatabaseManager()
    
    # 🔑 TGT Token Al (Custom Uç Noktalar İçin)
    tgt_token = None
    try:
        res = requests.post("https://giris.epias.com.tr/cas/v1/tickets", 
                            data={"username": username, "password": password}, 
                            headers={"Accept": "text/plain", "Content-Type": "application/x-www-form-urlencoded"})
        if res.status_code == 201:
            tgt_token = res.text
            logging.info("🔑 TGT Token başarıyla alındı.")
    except Exception as e:
        logging.error(f"TGT Token Hatası: {e}")

    today_dt = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    monthly_periods = pd.date_range(start="2024-01-01", end=today_dt, freq="MS")

    # EPTR2 Üzerinden Çekilecek Standart Servisler
    eptr2_services = [
        ("mcp", "mcp", "raw_mcp_hourly"),
        ("smp", "smp", "raw_smp_hourly"),
        ("load-plan", "load_forecast", "raw_load_forecast_hourly"),
        ("kgup", "kgup", "raw_kgup_hourly"),
        ("rt-gen", "actual_generation", "raw_actual_generation_hourly"),
        ("rt-cons", "actual_consumption", "raw_actual_consumption_hourly")
    ]

    for i in range(len(monthly_periods)):
        start_dt = monthly_periods[i]
        end_dt = min(start_dt + pd.offsets.MonthEnd(1), today_dt)
        
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        start_iso = f"{start_str}T00:00:00+03:00"
        end_iso = f"{end_str}T23:59:59+03:00"
        period_key = start_dt.strftime('%Y-%m')
        
        logging.info(f"\n🔄 --- DÖNEM: {start_str} - {end_str} ---")

        # 1. EPTR2 SERVİSLERİ
        for eptr_key, map_key, table_name in eptr2_services:
            try:
                data = eptr.call(eptr_key, start_date=start_iso, end_date=end_iso)
                if data:
                    df = pd.DataFrame(data)
                    df.rename(columns=MAPPINGS[map_key], inplace=True)
                    
                    # Sadece SQL'de karşılığı olan sütunları filtrele (Fazlalıkları at)
                    expected_cols = list(MAPPINGS[map_key].values())
                    df = df[df.columns.intersection(expected_cols)]
                    
                    db.save_to_silver(df, table_name=table_name, source_name=map_key, period_key=period_key)
            except Exception as e:
                logging.error(f"   [!] Hata ({map_key}): {e}")
            time.sleep(1)

        # 2. HAVA DURUMU (Open-Meteo)
        try:
            df_weather = fetch_turkey_weighted_temperature(start_str, end_str)
            if not df_weather.empty:
                df_weather.rename(columns=MAPPINGS["weather"], inplace=True)
                expected_cols = list(MAPPINGS["weather"].values())
                df_weather = df_weather[df_weather.columns.intersection(expected_cols)]
                db.save_to_silver(df_weather, table_name="raw_weather_hourly", source_name="weather", period_key=period_key)
        except Exception as e:
            logging.error(f"   [!] Hata (Weather): {e}")

        # 3. AKTİF DOLULUK (/data/ endpoint - JSON)
        if tgt_token:
            try:
                res_af = requests.post("https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/active-fullness",
                                       json={"startDate": start_iso, "endDate": end_iso},
                                       headers={"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token})
                if res_af.status_code == 200:
                    records = res_af.json().get("items", []) or res_af.json()
                    if records:
                        df_af = pd.DataFrame(records)
                        df_af.rename(columns=MAPPINGS["active_fullness"], inplace=True)
                        expected_cols = list(MAPPINGS["active_fullness"].values())
                        df_af = df_af[df_af.columns.intersection(expected_cols)]
                        db.save_to_silver(df_af, table_name="raw_master_active_fullness", source_name="active_fullness", period_key=period_key)
            except Exception as e:
                logging.error(f"   [!] Hata (Active Fullness): {e}")

        # 4. SU ENERJİSİ KARŞILIĞI (/export/ endpoint - CSV to JSON) -> Hata Çözüldü!
        if tgt_token:
            try:
                res_we = requests.post("https://seffaflik.epias.com.tr/electricity-service/v1/dams/export/water-energy-provision",
                                       json={"startDate": start_iso, "endDate": end_iso, "exportType": "CSV"},
                                       headers={"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token})
                if res_we.status_code == 200:
                    res_we.encoding = 'utf-8-sig'
                    df_we = pd.read_csv(io.StringIO(res_we.text), sep=";")
                    if not df_we.empty:
                        df_we.rename(columns=MAPPINGS["water_energy_provision"], inplace=True)
                        expected_cols = list(MAPPINGS["water_energy_provision"].values())
                        df_we = df_we[df_we.columns.intersection(expected_cols)]
                        db.save_to_silver(df_we, table_name="raw_master_water_energy_provision", source_name="water_energy_provision", period_key=period_key)
            except Exception as e:
                logging.error(f"   [!] Hata (Water Energy): {e}")
                
        time.sleep(2) # Aya geçmeden ufak dinlenme

    # 5. MAKRO GÖSTERGELER (Dolar & Brent Petrol) -> Günlük Veri Tüm Süreç İçin Tek Sefer Çekilir
    logging.info("\n📈 Makro Veriler (yfinance) güncelleniyor...")
    try:
        end_macro = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        macro_data = yf.download(["USDTRY=X", "BZ=F"], start="2024-01-01", end=end_macro, interval="1d", progress=False)["Close"]
        if not macro_data.empty:
            macro_data = macro_data.reset_index()
            macro_data['Date'] = pd.to_datetime(macro_data['Date']).dt.tz_localize(None)
            macro_data = macro_data.ffill().bfill()
            
            macro_data.rename(columns=MAPPINGS["macro"], inplace=True)
            expected_cols = list(MAPPINGS["macro"].values())
            macro_data = macro_data[macro_data.columns.intersection(expected_cols)]
            
            # Makro veri günlüktür, period_key olarak 'ALL' verebiliriz veya aya bölebiliriz. 
            # Topluca yollamak için period_key="ALL" yapıyorum, DB Manager Checksum ile kopyaları ezer.
            db.save_to_silver(macro_data, table_name="raw_macro_daily", source_name="macro", period_key="ALL")
    except Exception as e:
        logging.error(f"   [!] Hata (Macro): {e}")

    logging.info("🎉 Tüm işlemler başarıyla tamamlandı. Veritabanı güncel!")

if __name__ == "__main__":
    run_daily_pipeline()