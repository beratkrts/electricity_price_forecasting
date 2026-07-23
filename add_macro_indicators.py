import os
import json
from pathlib import Path
import pandas as pd
import yfinance as yf

def add_macro_indicators():
    root_folder = Path("epias_data")
    
    if not root_folder.exists():
        print("[!] ERROR: 'epias_data' folder not found. Please run this script in the root directory where data exists.")
        return

    # Find existing month folders (e.g., epias_data/2024-01, epias_data/2024-02, ...)
    month_folders = sorted([f for f in root_folder.iterdir() if f.is_dir() and len(f.name) == 7 and f.name.replace('-', '').isdigit()])
    
    if not month_folders:
        print("[!] No monthly subfolders found inside 'epias_data'.")
        return

    print(f"Found {len(month_folders)} monthly folders. Fetching macro indicators via yfinance...\n")

    # Set date range based on existing folders
    start_date = "2024-01-01"
    today = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    end_date = (today + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    # Download USD/TRY (USDTRY=X) and Brent Crude Oil (BZ=F)
    try:
        macro_data = yf.download(["USDTRY=X", "BZ=F"], start=start_date, end=end_date, interval="1d")["Close"]
        macro_data = macro_data.reset_index()
        macro_data['Date'] = pd.to_datetime(macro_data['Date']).dt.tz_localize(None)
        
        # Forward & Backward fill for weekends/holidays (Electricity market is 24/7)
        macro_data = macro_data.ffill().bfill()
        macro_data = macro_data.rename(columns={"USDTRY=X": "usd_try", "BZ=F": "brent_oil_usd", "Date": "date"})
        print("[+] Macro financial data fetched successfully.\n")
    except Exception as e:
        print(f"[!] ERROR - Failed to fetch data from yfinance: {e}")
        return

    # Process each month folder
    for folder in month_folders:
        try:
            year, month = map(int, folder.name.split("-"))
            start_dt = pd.Timestamp(year=year, month=month, day=1)
            end_dt = start_dt + pd.offsets.MonthEnd(1)

            # Filter macro data for the specific month
            month_macro = macro_data[(macro_data['date'] >= start_dt) & (macro_data['date'] <= end_dt)].copy()
            month_macro['date'] = month_macro['date'].dt.strftime("%Y-%m-%d")
            
            # Target JSON path
            target_file = folder / "09_macro_indicators.json"
            
            # Save as JSON
            month_macro.to_json(target_file, orient="records", force_ascii=False, indent=4)
            print(f"   [+] Saved {target_file.name} to -> {folder.name}")
            
        except Exception as e:
            print(f"   [!] ERROR processing folder {folder.name}: {e}")

    print("\nAll macro data successfully injected into existing folders!")

if __name__ == "__main__":
    add_macro_indicators()