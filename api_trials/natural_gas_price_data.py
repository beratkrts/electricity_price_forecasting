import json
import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fetch_epias_data import fetch_natural_gas_daily_reference_price, get_tgt_token


def find_env_file():
    return next((path / ".env" for path in [Path.cwd(), *Path.cwd().parents] if (path / ".env").exists()), None)


def main():
    env_path = find_env_file()
    if env_path is None:
        raise FileNotFoundError(".env file was not found. Please check the directory.")

    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    if not username or not password:
        raise ValueError("Credentials are missing in the .env file!")

    today = pd.Timestamp.now(tz="Europe/Istanbul").normalize()
    start_of_month = today.replace(day=1)

    default_start = start_of_month.strftime("%Y-%m-%dT00:00:00+03:00")
    default_end = today.strftime("%Y-%m-%dT23:59:59+03:00")

    start_iso = default_start
    end_iso = default_end

    print(f"🔑 Requesting TGT Token for EPİAŞ API...")
    tgt_token = get_tgt_token(username, password)

    print(f"🚀 Fetching Natural Gas DRP data ({start_iso[:10]} to {end_iso[:10]})...")
    data = fetch_natural_gas_daily_reference_price(tgt_token, start_iso, end_iso)

    output_dir = PROJECT_ROOT / "data" / "api_trials"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"natural_gas_daily_reference_price{start_iso[:10]}_{end_iso[:10]}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"✅ Natural Gas DRP records fetched: {len(data)}")
    print(f"💾 Saved to: {output_file}")


if __name__ == "__main__":
    main()
