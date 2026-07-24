import json
import os
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def add_macro_indicators():
    print("🚀 Fetching macro indicators (USD/TRY & Brent Oil) via yfinance...")

    start_date = "2024-01-01"
    today = pd.Timestamp.now(tz="Europe/Istanbul").normalize().tz_localize(None)
    end_date = (today + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        macro_data = yf.download(["USDTRY=X", "BZ=F"], start=start_date, end=end_date, interval="1d")["Close"]
        macro_data = macro_data.reset_index()
        macro_data['Date'] = pd.to_datetime(macro_data['Date']).dt.tz_localize(None)

        macro_data = macro_data.ffill().bfill()
        macro_data = macro_data.rename(columns={"USDTRY=X": "usd_try", "BZ=F": "brent_oil_usd", "Date": "date"})
        print(f"✅ Macro financial data fetched successfully: {len(macro_data)} records.\n")
    except Exception as e:
        print(f"[!] ERROR - Failed to fetch data from yfinance: {e}")
        return

    # Save standalone trial file under data/api_trials/
    output_dir = PROJECT_ROOT / "data" / "api_trials"
    output_dir.mkdir(parents=True, exist_ok=True)
    trial_file = output_dir / "macro_indicators.json"

    macro_export = macro_data.copy()
    macro_export['date'] = macro_export['date'].dt.strftime("%Y-%m-%d")
    macro_export.to_json(trial_file, orient="records", force_ascii=False, indent=4)
    print(f"💾 Saved trial file to: {trial_file}")

    # Check potential root directories (data or epias_data) for monthly folders
    for folder_name in ["data", "epias_data"]:
        root_folder = PROJECT_ROOT / folder_name
        if not root_folder.exists():
            continue

        month_folders = sorted([f for f in root_folder.iterdir() if f.is_dir() and len(f.name) == 7 and f.name.replace('-', '').isdigit()])
        if month_folders:
            print(f"Injecting macro data into {len(month_folders)} monthly folders inside '{folder_name}/'...")
            for folder in month_folders:
                try:
                    year, month = map(int, folder.name.split("-"))
                    start_dt = pd.Timestamp(year=year, month=month, day=1)
                    end_dt = start_dt + pd.offsets.MonthEnd(1)

                    month_macro = macro_data[(macro_data['date'] >= start_dt) & (macro_data['date'] <= end_dt)].copy()
                    month_macro['date'] = month_macro['date'].dt.strftime("%Y-%m-%d")

                    target_file = folder / "09_macro_indicators.json"
                    month_macro.to_json(target_file, orient="records", force_ascii=False, indent=4)
                    print(f"   [+] Saved {target_file.name} to -> {folder.name}")

                except Exception as e:
                    print(f"   [!] ERROR processing folder {folder.name}: {e}")


if __name__ == "__main__":
    add_macro_indicators()