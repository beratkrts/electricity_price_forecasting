import os
import time
import io
import json
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv
from eptr2 import EPTR2
import yfinance as yf

CAS_TICKET_URL = "https://giris.epias.com.tr/cas/v1/tickets"
LICENSED_REALTIME_GENERATION_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/"
    "renewables/data/licensed-realtime-generation"
)

INSTALLED_CAPACITY_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/"
    "renewables/data/new-installed-capacity"
)

ACTIVE_FULLNESS_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/"
    "dams/data/active-fullness"
)

WATER_ENERGY_PROVISION_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/"
    "dams/data/water-energy-provision"
)

NATURAL_GAS_PRICE_URL = (
    "https://seffaflik.epias.com.tr/natural-gas-service/v1/"
    "markets/sgp/data/daily-reference-price"
)



def get_tgt_token(username, password):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/plain",
    }
    response = requests.post(
        CAS_TICKET_URL,
        data={"username": username, "password": password},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    tgt_token = response.text.strip()
    if not tgt_token:
        raise ValueError("EPİAŞ CAS returned an empty TGT token.")

    return tgt_token


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


def find_page_info(value):
    if not isinstance(value, dict):
        return {}

    page = value.get("page")
    if isinstance(page, dict):
        return page

    for nested_value in value.values():
        page = find_page_info(nested_value)
        if page:
            return page

    return {}


def fetch_licensed_realtime_generation(tgt_token, start_iso, end_iso, page_size=1000):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TGT": tgt_token,
    }

    all_records = []
    page_number = 1

    while True:
        payload = {
            "startDate": start_iso,
            "endDate": end_iso,
            "page": {
                "number": page_number,
                "size": page_size,
            },
        }
        response = requests.post(
            LICENSED_REALTIME_GENERATION_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        response_payload = response.json()
        records = find_record_list(response_payload) or []
        all_records.extend(records)

        page_info = find_page_info(response_payload)
        total_pages = page_info.get("totalPages") or page_info.get("totalPage")
        if total_pages and page_number >= int(total_pages):
            break

        total_elements = page_info.get("totalElements") or page_info.get("total")
        if total_elements and len(all_records) >= int(total_elements):
            break

        if len(records) < page_size:
            break

        page_number += 1

    return all_records


def fetch_active_fullness(tgt_token, start_iso, end_iso):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TGT": tgt_token,
    }
    payload = {
        "startDate": start_iso,
        "endDate": end_iso,
    }
    response = requests.post(
        ACTIVE_FULLNESS_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    response_payload = response.json()
    return find_record_list(response_payload) or []


def fetch_water_energy_provision(tgt_token, start_iso, end_iso):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TGT": tgt_token,
    }
    payload = {
        "startDate": start_iso,
        "endDate": end_iso,
        "exportType": "CSV",
    }
    response = requests.post(
        WATER_ENERGY_PROVISION_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    response.encoding = "utf-8-sig"
    df = pd.read_csv(io.StringIO(response.text), sep=";")
    return df.to_dict(orient="records")


def fetch_installed_capacity(tgt_token, period):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TGT": tgt_token,
    }
    payload = {
        "period": period,
    }
    response = requests.post(
        INSTALLED_CAPACITY_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    response_payload = response.json()
    return find_record_list(response_payload) or response_payload

def fetch_natural_gas_daily_reference_price(tgt_token, start_iso, end_iso, page_size = 1000):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "TGT": tgt_token,
    }

    all_records = []
    page_number = 1

    while True:
        payload = {
            "startDate": start_iso,
            "endDate": end_iso,
            "page": {
                "number": page_number,
                "size": page_size,
            },
        }
        response = requests.post(
            NATURAL_GAS_PRICE_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        response_payload = response.json()
        records = find_record_list(response_payload) or []
        all_records.extend(records)

        page_info = find_page_info(response_payload)
        total_pages = page_info.get("totalPages") or page_info.get("totalPage")
        if total_pages and page_number >= int(total_pages):
            break

        total_elements = page_info.get("totalElements") or page_info.get("total")
        if total_elements and len(all_records) >= int(total_elements):
            break

        if len(records) < page_size:
            break

        page_number += 1

    return all_records



def main():
    # --- 1. AUTHENTICATION (Secure .env Connection) ---
    env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
    if env_path is None:
        raise FileNotFoundError('.env file was not found. Please check the directory.')

    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    if not username or not password:
        raise ValueError('Credentials are missing in the .env file!')

    # Initialize the API connection.
    eptr = EPTR2(username=username, password=password, dotenv_path=str(env_path))

    try:
        tgt_token = get_tgt_token(username, password)
        print("EPİAŞ direct API TGT token received successfully.")
    except Exception as e:
        tgt_token = None
        print(f"[!] WARNING - Could not get EPİAŞ direct API TGT token. Licensed generation data will be skipped: {e}")

    # --- 2. UPDATED SET OF 8 EPİAŞ ENDPOINTS ---
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

    # --- 3. TIME LOOP (January 2024 - Today) ---
    today = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    current_month_start = today.replace(day=1)
    monthly_periods = pd.date_range(start="2024-01-01", end=current_month_start, freq="MS")
    
    root_folder = "data"
    os.makedirs(root_folder, exist_ok=True)
    print("EPIAS ETL Bot Started: Fetching Data in Monthly Blocks\n")

    # --- 4. FETCH FINANCIAL DATA (USD/TRY & BRENT OIL) VIA YFINANCE ---
    print(" Fetching macro indicators (USD/TRY & Brent Oil) via yfinance...")
    start_global = "2024-01-01"
    end_global = (today + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    # Tickers: USDTRY=X (USD/TRY), BZ=F (Brent Crude Oil)
    macro_data = yf.download(["USDTRY=X", "BZ=F"], start=start_global, end=end_global, interval="1d")["Close"]
    macro_data = macro_data.reset_index()
    macro_data['Date'] = pd.to_datetime(macro_data['Date']).dt.tz_localize(None)
    
    # Missing values (weekends/holidays) forward filled
    macro_data = macro_data.ffill().bfill()
    macro_data = macro_data.rename(columns={"USDTRY=X": "usd_try", "BZ=F": "brent_oil_usd", "Date": "date"})

    # --- 5. MAIN MONTHLY DATA FETCHING LOOP ---
    for i in range(len(monthly_periods)):
        start_dt = monthly_periods[i]
        end_dt = min(start_dt + pd.offsets.MonthEnd(1), today)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        folder_name = f"{root_folder}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(folder_name, exist_ok=True)
        
        print(f"\nTarget Period: {start_str} - {end_str} | Folder: {folder_name}")
        
        # --- A. EPİAŞ ENDPOINTS LOOP ---
        for file_name, call_key in endpoints.items():
            print(f"   -> Calling [{file_name}] ({call_key}) service...")
            try:
                start_iso = f"{start_str}T00:00:00+03:00"
                end_iso = f"{end_str}T23:59:59+03:00"
                
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
                else:
                    print(f"      [-] {file_name} service returned no data for this month.")
                    
            except Exception as e:
                print(f"      [!] ERROR - A problem occurred while fetching {file_name}: {e}")
            
            time.sleep(2)

        # --- B. SAVE LICENSED REALTIME GENERATION ---
        print("   -> Calling [10_licensed_realtime_generation] direct EPİAŞ API service...")
        try:
            if tgt_token is None:
                print("      [-] 10_licensed_realtime_generation skipped because TGT token is missing.")
            else:
                licensed_generation = fetch_licensed_realtime_generation(tgt_token, start_iso, end_iso)
                licensed_file_path = f"{folder_name}/10_licensed_realtime_generation.json"

                with open(licensed_file_path, "w", encoding="utf-8") as f:
                    json.dump(licensed_generation, f, ensure_ascii=False, indent=4)

                print(f"      [+] 10_licensed_realtime_generation saved successfully. Records: {len(licensed_generation)}")
        except Exception as e:
            print(f"      [!] ERROR - A problem occurred while fetching licensed generation data: {e}")

        # --- E. SAVE INSTALLED CAPACITY ---
        print("   -> Calling [13_installed_capacity] direct EPİAŞ API service...")
        try:
            if tgt_token is None:
                print("      [-] 13_installed_capacity skipped because TGT token is missing.")
            else:
                period_str = f"{start_str}T00:00:00+03:00"
                installed_cap = fetch_installed_capacity(tgt_token, period_str)
                ic_file_path = f"{folder_name}/13_installed_capacity.json"

                with open(ic_file_path, "w", encoding="utf-8") as f:
                    json.dump(installed_cap, f, ensure_ascii=False, indent=4)

                cap_len = len(installed_cap) if isinstance(installed_cap, list) else 1
                print(f"      [+] 13_installed_capacity saved successfully. Records: {cap_len}")
        except Exception as e:
            print(f"      [!] ERROR - A problem occurred while fetching installed capacity data: {e}")

        # --- F. SAVE MACRO FINANCIAL DATA FOR THIS MONTH ---
        print("   -> Processing Financial Data (USD/TRY & Brent Oil)...")
        try:
            # Slicing financial data for the current month
            month_macro = macro_data[(macro_data['date'] >= start_dt) & (macro_data['date'] <= end_dt)].copy()
            month_macro['date'] = month_macro['date'].dt.strftime("%Y-%m-%d")
            
            macro_file_path = f"{folder_name}/09_macro_indicators.json"
            month_macro.to_json(macro_file_path, orient="records", force_ascii=False, indent=4)
            print("      [+] 09_macro_indicators saved successfully.")
        except Exception as e:
            print(f"      [!] ERROR - A problem occurred while saving financial data: {e}")

    # --- 6. FETCH SINGLE MASTER SNAPSHOTS (ACTIVE FULLNESS & WATER ENERGY PROVISION) ---
    print("\n⚡ Fetching Static Master Data Snapshots (Active Fullness & Water Energy Provision) ⚡")
    today_str = today.strftime("%Y-%m-%d")
    today_start_iso = f"{today_str}T00:00:00+03:00"
    today_end_iso = f"{today_str}T23:59:59+03:00"

    # --- A. ACTIVE DAM FULLNESS SNAPSHOT ---
    print("   -> Calling [active_fullness] master snapshot service...")
    try:
        if tgt_token is None:
            print("      [-] active_fullness skipped because TGT token is missing.")
        else:
            active_fullness = fetch_active_fullness(tgt_token, today_start_iso, today_end_iso)
            af_file_path = f"{root_folder}/master_active_fullness.json"

            with open(af_file_path, "w", encoding="utf-8") as f:
                json.dump(active_fullness, f, ensure_ascii=False, indent=4)

            print(f"      [+] master_active_fullness saved successfully. Records: {len(active_fullness)} -> {af_file_path}")
    except Exception as e:
        print(f"      [!] ERROR - A problem occurred while fetching active fullness snapshot: {e}")

    # --- B. WATER ENERGY PROVISION SNAPSHOT ---
    print("   -> Calling [water_energy_provision] master snapshot service...")
    try:
        if tgt_token is None:
            print("      [-] water_energy_provision skipped because TGT token is missing.")
        else:
            water_energy = fetch_water_energy_provision(tgt_token, today_start_iso, today_end_iso)
            we_file_path = f"{root_folder}/master_water_energy_provision.json"

            with open(we_file_path, "w", encoding="utf-8") as f:
                json.dump(water_energy, f, ensure_ascii=False, indent=4)

            print(f"      [+] master_water_energy_provision saved successfully. Records: {len(water_energy)} -> {we_file_path}")
    except Exception as e:
        print(f"      [!] ERROR - A problem occurred while fetching water energy provision snapshot: {e}")

    print("\nAll operations completed successfully. EPİAŞ & Macro data is ready!")

if __name__ == "__main__":
    main()
