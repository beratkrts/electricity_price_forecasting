import json
import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fetch_epias_data import fetch_installed_capacity, find_record_list, get_tgt_token


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
    period = os.getenv("INSTALLED_CAPACITY_PERIOD", today.strftime("%Y-%m-%dT00:00:00+03:00"))
    period = '2022-08-01T00:00:00+03:00'

    print(f"🔑 Requesting TGT Token for EPİAŞ API...")
    tgt_token = get_tgt_token(username, password)

    print(f"🚀 Fetching Installed Capacity data for period: {period[:10]}...")
    records = fetch_installed_capacity(tgt_token, period)

    output_dir = PROJECT_ROOT / "data" / "api_trials"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"installed_capacity_{period[:10]}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=4)

    record_count = len(records) if isinstance(records, list) else "unknown"
    print(f"✅ Installed capacity records fetched: {record_count}")
    print(f"💾 Saved to: {output_file}")


if __name__ == "__main__":
    main()
