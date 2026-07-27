import os
import sys
import time
import io
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests
from dotenv import load_dotenv
from eptr2 import EPTR2
import yfinance as yf

# Import weather fetcher from api_trials
from api_trials.weather_fetcher import fetch_turkey_weighted_temperature, load_city_weights_and_coords

# --- LOGGING CONFIGURATION ---
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/daily_update.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

CAS_TICKET_URL = "https://giris.epias.com.tr/cas/v1/tickets"
LICENSED_REALTIME_GENERATION_URL = "https://seffaflik.epias.com.tr/electricity-service/v1/renewables/data/licensed-realtime-generation"
INSTALLED_CAPACITY_URL = "https://seffaflik.epias.com.tr/electricity-service/v1/renewables/data/new-installed-capacity"
ACTIVE_FULLNESS_URL = "https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/active-fullness"
WATER_ENERGY_PROVISION_URL = "https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/water-energy-provision"
NATURAL_GAS_PRICE_URL = "https://seffaflik.epias.com.tr/natural-gas-service/v1/markets/sgp/data/daily-reference-price"


def get_tgt_token(username, password):
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    response = requests.post(CAS_TICKET_URL, data={"username": username, "password": password}, headers=headers, timeout=30)
    response.raise_for_status()
    tgt = response.text.strip()
    if not tgt:
        raise ValueError("EPİAŞ CAS returned empty TGT token.")
    return tgt


def find_record_list(value):
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return value
        return None
    if isinstance(value, dict):
        for preferred_key in ("items", "data", "content", "body"):
            if preferred_key in value:
                records = find_record_list(value[preferred_key])
                if records is not None:
                    return records
        for nested_value in value.values():
            records = find_record_list(nested_value)
            if records is not None:
                return records
    return None


def fetch_licensed_realtime_generation(tgt_token, start_iso, end_iso, page_size=1000):
    headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token}
    all_records = []
    page_number = 1
    while True:
        payload = {"startDate": start_iso, "endDate": end_iso, "page": {"number": page_number, "size": page_size}}
        response = requests.post(LICENSED_REALTIME_GENERATION_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_payload = response.json()
        records = find_record_list(response_payload) or []
        all_records.extend(records)
        if len(records) < page_size:
            break
        page_number += 1
    return all_records


def fetch_natural_gas_daily_reference_price(tgt_token, start_iso, end_iso):
    headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token}
    payload = {"startDate": start_iso, "endDate": end_iso}
    response = requests.post(NATURAL_GAS_PRICE_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return find_record_list(response.json()) or []


def fetch_active_fullness(tgt_token, start_iso, end_iso):
    headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token}
    payload = {"startDate": start_iso, "endDate": end_iso}
    response = requests.post(ACTIVE_FULLNESS_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return find_record_list(response.json()) or []


def fetch_water_energy_provision(tgt_token, start_iso, end_iso):
    headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": tgt_token}
    payload = {"startDate": start_iso, "endDate": end_iso, "exportType": "CSV"}
    response = requests.post(WATER_ENERGY_PROVISION_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    response.encoding = "utf-8-sig"
    df = pd.read_csv(io.StringIO(response.text), sep=";")
    return df.to_dict(orient="records")


def find_latest_fetched_date(data_dir="data", default_start="2024-01-01"):
    """
    Scans data directory monthly folders to find the last complete date fetched.
    Returns the date string from which we need to resume fetching (start_missing_date).
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        return default_start

    month_dirs = sorted([d for d in data_path.iterdir() if d.is_dir() and len(d.name) == 7 and "-" in d.name])
    if not month_dirs:
        return default_start

    latest_date = None

    # Inspect the most recent month folders to find max timestamp in files
    for month_dir in reversed(month_dirs[-3:]):
        files_to_check = [
            month_dir / "03_mcp.json",
            month_dir / "01_load_forecast.json",
            month_dir / "13_turkey_weighted_temperature.json"
        ]
        for filepath in files_to_check:
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    if isinstance(records, list) and len(records) > 0:
                        # Extract date strings from records
                        dates = []
                        for r in records:
                            dt_val = r.get("date") or r.get("date_time") or r.get("dt") or r.get("tarih")
                            if dt_val:
                                dates.append(str(dt_val)[:10])
                        if dates:
                            max_d = max(dates)
                            if latest_date is None or max_d > latest_date:
                                latest_date = max_d
                except Exception as e:
                    logging.warning(f"Could not parse date from {filepath}: {e}")

    if latest_date is None:
        return default_start

    # Resume from 1 day after the latest found date to avoid re-fetching full historical months
    resume_dt = datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)
    return resume_dt.strftime("%Y-%m-%d")


def run_daily_pipeline():
    logging.info("🚀 Starting Daily EPIAS & Weather Data Pipeline...")

    # Load credentials
    env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
    if env_path is None:
        logging.error(".env file missing!")
        return

    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    if not username or not password:
        logging.error("EPİAŞ credentials missing in .env!")
        return

    eptr = EPTR2(username=username, password=password, dotenv_path=str(env_path))
    try:
        tgt_token = get_tgt_token(username, password)
        logging.info("🔑 TGT Token retrieved successfully.")
    except Exception as e:
        tgt_token = None
        logging.warning(f"⚠️ Could not get TGT token: {e}")

    # Determine date range
    today_dt = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    today_str = today_dt.strftime("%Y-%m-%d")
    
    start_missing_date = find_latest_fetched_date("data", default_start="2024-01-01")
    
    # If start_missing_date > today_str, we are already up to date!
    if start_missing_date > today_str:
        logging.info(f"✨ Data is already up-to-date as of {today_str}. No new period to fetch.")
        start_missing_date = today_str

    logging.info(f"📅 Target Execution Period: {start_missing_date} to {today_str}")

    # Generate monthly blocks for missing date range
    monthly_periods = pd.date_range(start=start_missing_date, end=today_dt, freq="MS")
    if len(monthly_periods) == 0:
        monthly_periods = pd.DatetimeIndex([pd.Timestamp(start_missing_date)])

    endpoints = {
        "01_load_forecast": "load-plan",
        "02_kgup": "kgup",
        "03_mcp": "mcp",
        "04_smp": "smp",
        "05_purchase_bids": "dam-bid",
        "06_sale_offers": "dam-offer",
        "07_actual_generation": "rt-gen",
        "08_actual_consumption": "rt-cons"
    }

    # Fetch Macro Financial Data (USD/TRY & Brent)
    logging.info("📈 Fetching Macro Financial Data (yfinance)...")
    start_macro = "2024-01-01"
    end_macro = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    macro_data = yf.download(["USDTRY=X", "BZ=F"], start=start_macro, end=end_macro, interval="1d", progress=False)["Close"]
    macro_data = macro_data.reset_index()
    macro_data['Date'] = pd.to_datetime(macro_data['Date']).dt.tz_localize(None)
    macro_data = macro_data.ffill().bfill()
    macro_data = macro_data.rename(columns={"USDTRY=X": "usd_try", "BZ=F": "brent_oil_usd", "Date": "date"})

    root_folder = "data"

    for i in range(len(monthly_periods)):
        start_dt = monthly_periods[i]
        end_dt = min(start_dt + pd.offsets.MonthEnd(1), today_dt)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        folder_name = f"{root_folder}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(folder_name, exist_ok=True)

        logging.info(f"🔄 Processing Block: {start_str} to {end_str} -> Folder: {folder_name}")

        start_iso = f"{start_str}T00:00:00+03:00"
        end_iso = f"{end_str}T23:59:59+03:00"

        # A. EPİAŞ EPTR2 Endpoints
        for file_name, call_key in endpoints.items():
            try:
                res = eptr.call(call_key, start_date=start_iso, end_date=end_iso)
                if res is not None:
                    file_path = f"{folder_name}/{file_name}.json"
                    if hasattr(res, 'to_json'):
                        res.to_json(file_path, orient="records", force_ascii=False, indent=4)
                    elif hasattr(res, 'to_dict'):
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(res.to_dict(), f, ensure_ascii=False, indent=4)
                    else:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(res, f, ensure_ascii=False, indent=4)
                    logging.info(f"   [+] {file_name} updated successfully.")
            except Exception as e:
                logging.error(f"   [!] Error fetching {file_name}: {e}")
            time.sleep(1)

        # B. Licensed Realtime Generation
        if tgt_token:
            try:
                lic_gen = fetch_licensed_realtime_generation(tgt_token, start_iso, end_iso)
                with open(f"{folder_name}/10_licensed_realtime_generation.json", "w", encoding="utf-8") as f:
                    json.dump(lic_gen, f, ensure_ascii=False, indent=4)
                logging.info(f"   [+] 10_licensed_realtime_generation updated. Records: {len(lic_gen)}")
            except Exception as e:
                logging.error(f"   [!] Error fetching 10_licensed_realtime_generation: {e}")

        # C. Macro Indicators
        try:
            m_macro = macro_data[(macro_data['date'] >= start_dt) & (macro_data['date'] <= end_dt)].copy()
            m_macro['date'] = m_macro['date'].dt.strftime("%Y-%m-%d")
            m_macro.to_json(f"{folder_name}/09_macro_indicators.json", orient="records", force_ascii=False, indent=4)
            logging.info("   [+] 09_macro_indicators updated.")
        except Exception as e:
            logging.error(f"   [!] Error saving macro indicators: {e}")

        # D. Natural Gas Daily Ref Price
        if tgt_token:
            try:
                ng_price = fetch_natural_gas_daily_reference_price(tgt_token, start_iso, end_iso)
                with open(f"{folder_name}/12_natural_gas_daiy_ref_price.json", "w", encoding="utf-8") as f:
                    json.dump(ng_price, f, ensure_ascii=False, indent=4)
                logging.info(f"   [+] 12_natural_gas_daiy_ref_price updated. Records: {len(ng_price)}")
            except Exception as e:
                logging.error(f"   [!] Error fetching natural gas price: {e}")

        # E. Turkey Consumption Weighted Temperature (26 Cities)
        try:
            df_weather = fetch_turkey_weighted_temperature(start_str, end_str)
            if not df_weather.empty:
                df_weather.to_json(f"{folder_name}/13_turkey_weighted_temperature.json", orient="records", force_ascii=False, indent=4)
                logging.info(f"   [+] 13_turkey_weighted_temperature updated. Records: {len(df_weather)}")
        except Exception as e:
            logging.error(f"   [!] Error fetching turkey weighted temperature: {e}")

    # --- MASTER SNAPSHOTS UPDATE (DAM FULLNESS & WATER ENERGY) ---
    logging.info("🌊 Fetching Current Master Dam Snapshots...")
    if tgt_token:
        try:
            today_start_iso = f"{today_str}T00:00:00+03:00"
            today_end_iso = f"{today_str}T23:59:59+03:00"

            active_fullness = fetch_active_fullness(tgt_token, today_start_iso, today_end_iso)
            with open(f"{root_folder}/master_active_fullness.json", "w", encoding="utf-8") as f:
                json.dump(active_fullness, f, ensure_ascii=False, indent=4)
            logging.info("   [+] Master Active Fullness snapshot updated.")

            water_energy = fetch_water_energy_provision(tgt_token, today_start_iso, today_end_iso)
            with open(f"{root_folder}/master_water_energy_provision.json", "w", encoding="utf-8") as f:
                json.dump(water_energy, f, ensure_ascii=False, indent=4)
            logging.info("   [+] Master Water Energy Provision snapshot updated.")
        except Exception as e:
            logging.error(f"   [!] Error updating master dam snapshots: {e}")

    logging.info("🎉 Daily Update & Gap Backfilling Completed Successfully!")


if __name__ == "__main__":
    run_daily_pipeline()
