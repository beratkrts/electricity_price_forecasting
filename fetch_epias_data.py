import os
import time
import json
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from eptr2 import EPTR2

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

    # --- 2. UPDATED SET OF 8 ENDPOINTS ---
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

    # --- 3. TIME LOOP (January 2024 - Current Time) ---
    # Monthly frequency from January 2024 to July 2026 (MS = Month Start).
    monthly_periods = pd.date_range(start="2024-01-01", end="2026-07-01", freq="MS")
    
    root_folder = "epias_data"
    os.makedirs(root_folder, exist_ok=True)
    print("EPIAS ETL Bot Started: Fetching Data in Monthly Blocks\n")

    for i in range(len(monthly_periods)):
        # Dynamically calculate the first and last day of the month.
        start_dt = monthly_periods[i]
        end_dt = start_dt + pd.offsets.MonthEnd(1)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        # Create a separate folder for each month.
        folder_name = f"{root_folder}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(folder_name, exist_ok=True)
        
        print(f"\nTarget Period: {start_str} - {end_str} | Folder: {folder_name}")
        
        for file_name, call_key in endpoints.items():
            print(f"   -> Calling [{file_name}] ({call_key}) service...")
            try:
                # Timezone-aware format required by the API (+03:00).
                start_iso = f"{start_str}T00:00:00+03:00"
                end_iso = f"{end_str}T23:59:59+03:00"
                
                # API call.
                res = eptr.call(call_key, start_date=start_iso, end_date=end_iso)
                
                # Save the response if it is not empty.
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
            
            # Wait to avoid API rate limits.
            time.sleep(2) 

    print("\nAll operations completed successfully. The data is ready for processing!")

if __name__ == "__main__":
    main()
