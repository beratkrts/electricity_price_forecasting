import os
import time
import json
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from eptr2 import EPTR2
import yfinance as yf

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
    
    root_folder = "epias_data"
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

        # --- B. SAVE MACRO FINANCIAL DATA FOR THIS MONTH ---
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

    print("\nAll operations completed successfully. EPİAŞ & Macro data is ready!")

if __name__ == "__main__":
    main()