import sys
import time
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))
"""In-Memory Data Fetcher Module for EPİAŞ, Open-Meteo, and Financial APIs.

Fetches data directly into memory without saving intermediate JSON files to disk.
"""

import logging
import io
from typing import List, Dict, Any, Optional
import pandas as pd
import requests
from eptr2 import EPTR2
import yfinance as yf

# Import weather fetcher logic
from src.data_ingestion.api_trials.weather_fetcher import fetch_turkey_weighted_temperature

logger = logging.getLogger("DataFetcher")

# --- EPİAŞ API CONSTANTS ---
CAS_TICKET_URL = "https://giris.epias.com.tr/cas/v1/tickets"
ACTIVE_FULLNESS_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/active-fullness"
)
WATER_ENERGY_PROVISION_URL = (
    "https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/water-energy-provision"
)
NATURAL_GAS_PRICE_URL = (
    "https://seffaflik.epias.com.tr/natural-gas-service/v1/markets/sgp/data/daily-reference-price"
)


def get_tgt_token(username: str, password: str, max_retries: int = 3, retry_delay: float = 5.0, timeout: int = 60) -> str:
    """Retrieves CAS Ticket Granting Ticket (TGT) for EPİAŞ Transparency 2.0 API with retries and timeout."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/plain",
    }
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                CAS_TICKET_URL,
                data={"username": username, "password": password},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            tgt = response.text.strip()
            if not tgt:
                raise ValueError("EPİAŞ CAS authentication returned an empty TGT token.")
            return tgt
        except Exception as e:
            last_exception = e
            logger.warning(f"EPİAŞ TGT authentication attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    raise RuntimeError(f"Failed to acquire EPİAŞ TGT token after {max_retries} attempts: {last_exception}")


def find_record_list(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """Recursively extracts record list from EPİAŞ API nested response payloads."""
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
        return None

    if isinstance(payload, pd.DataFrame):
        return payload.to_dict(orient="records")

    if isinstance(payload, dict):
        for preferred_key in ("items", "data", "content", "body"):
            if preferred_key in payload:
                records = find_record_list(payload[preferred_key])
                if records is not None:
                    return records
        for nested in payload.values():
            records = find_record_list(nested)
            if records is not None:
                return records
    return None


class EpiasFetcher:
    """In-memory fetcher for EPİAŞ Transparency API datasets using eptr2 library."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, env_path: Optional[str] = None, max_retries: int = 3):
        self.username = username
        self.password = password
        self.env_path = env_path
        self.max_retries = max_retries
        self.eptr = None
        self._tgt_token = None

        if username and password:
            kwargs = {"username": username, "password": password}
            if env_path:
                kwargs["dotenv_path"] = str(env_path)

            for attempt in range(1, max_retries + 1):
                try:
                    self.eptr = EPTR2(**kwargs)
                    logger.info("EPTR2 client initialized successfully.")
                    break
                except Exception as e:
                    logger.warning(f"EPTR2 initialization attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        time.sleep(5 * attempt)
        else:
            self.eptr = None

    def get_token(self) -> Optional[str]:
        """Lazy loads and caches the TGT authentication token."""
        if not self._tgt_token and self.username and self.password:
            try:
                self._tgt_token = get_tgt_token(self.username, self.password, max_retries=self.max_retries)
                logger.info("EPİAŞ TGT authentication token acquired successfully.")
            except Exception as e:
                logger.error(f"Failed to acquire EPİAŞ TGT token: {e}")
        return self._tgt_token

    def fetch_eptr2_service(self, service_name: str, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches standard EPİAŞ service data via eptr2 library in memory with retries."""
        if not self.eptr:
            logger.error("eptr2 client is not initialized.")
            return []

        logger.info(f"Calling eptr2 service: '{service_name}' ({start_iso} to {end_iso})...")
        for attempt in range(1, self.max_retries + 1):
            try:
                res = self.eptr.call(service_name, start_date=start_iso, end_date=end_iso)
                if isinstance(res, pd.DataFrame):
                    return res.to_dict(orient="records")
                elif isinstance(res, list):
                    return res
                elif isinstance(res, dict):
                    return find_record_list(res) or []
                return []
            except Exception as e:
                logger.warning(f"Error fetching eptr2 service '{service_name}' (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []

    def fetch_installed_capacity(self, period_iso: str) -> List[Dict[str, Any]]:
        """Fetches renewable installed capacity data via eptr2 'ren-capacity' into memory with retries."""
        if not self.eptr:
            logger.error("eptr2 client is not initialized.")
            return []

        logger.info(f"Calling eptr2 service: 'ren-capacity' for period {period_iso}...")
        for attempt in range(1, self.max_retries + 1):
            try:
                res = self.eptr.call("ren-capacity", period=period_iso)
                if isinstance(res, pd.DataFrame):
                    return res.to_dict(orient="records")
                elif isinstance(res, list):
                    return res
                elif isinstance(res, dict):
                    return find_record_list(res) or []
                return []
            except Exception as e:
                logger.warning(f"Error fetching installed capacity for period '{period_iso}' (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []

    def fetch_active_fullness(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches dam active fullness percentages into memory with retries."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso}
        for attempt in range(1, self.max_retries + 1):
            try:
                res = requests.post(ACTIVE_FULLNESS_URL, headers=headers, json=payload, timeout=60)
                res.raise_for_status()
                return find_record_list(res.json()) or []
            except Exception as e:
                logger.warning(f"Error fetching active fullness (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []

    def fetch_water_energy_provision(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches dam water energy provision in memory with retries."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso, "exportType": "CSV"}
        for attempt in range(1, self.max_retries + 1):
            try:
                res = requests.post(WATER_ENERGY_PROVISION_URL, headers=headers, json=payload, timeout=60)
                res.raise_for_status()
                if "text/csv" in res.headers.get("Content-Type", "") or res.text.startswith("Tarih"):
                    res.encoding = "utf-8-sig"
                    df = pd.read_csv(io.StringIO(res.text), sep=";")
                    return df.to_dict(orient="records")
                return find_record_list(res.json()) or []
            except Exception as e:
                logger.warning(f"Error fetching water energy provision (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []

    def fetch_natural_gas_daily_price(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches natural gas daily reference price (GRF) into memory with retries."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso}
        for attempt in range(1, self.max_retries + 1):
            try:
                res = requests.post(NATURAL_GAS_PRICE_URL, headers=headers, json=payload, timeout=60)
                res.raise_for_status()
                return find_record_list(res.json()) or []
            except Exception as e:
                logger.warning(f"Error fetching natural gas daily reference price (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []


# --- AUXILIARY EXTERNAL FETCHERS ---

def fetch_weather_in_memory(start_str: str, end_str: str) -> List[Dict[str, Any]]:
    """Fetches Open-Meteo weighted Turkey temperature into memory as list of dicts."""
    try:
        df = fetch_turkey_weighted_temperature(start_str, end_str)
        if not df.empty:
            df_reset = df.reset_index()
            return df_reset.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
    return []


def fetch_tomorrow_weather_forecast_in_memory() -> List[Dict[str, Any]]:
    """Fetches live Open-Meteo Turkey-weighted temperature forecast for tomorrow into memory as list of dicts."""
    try:
        from src.data_ingestion.api_trials.weather_fetcher import fetch_tomorrow_weighted_temperature_forecast
        res = fetch_tomorrow_weighted_temperature_forecast()
        records = []
        for t, temp in zip(res.get("time", []), res.get("temp_c", [])):
            records.append({
                "date_time": t,
                "turkey_weighted_temperature_c": temp
            })
        return records
    except Exception as e:
        logger.error(f"Error fetching weather forecast data: {e}")
    return []


def fetch_macro_in_memory(start_date: str = "2024-01-01", end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches yfinance macro indicators (USD/TRY & Brent Oil) into memory safely as list of dicts."""
    try:
        if not end_date:
            end_date = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(f"Fetching macro indicators from yfinance ({start_date} to {end_date})...")

        df_dict = {}
        for ticker_symbol in ["USDTRY=X", "BZ=F"]:
            try:
                t_df = yf.download(ticker_symbol, start=start_date, end=end_date, interval="1d", progress=False)
                if not t_df.empty:
                    if "Close" in t_df.columns:
                        close_col = t_df["Close"]
                        if isinstance(close_col, pd.DataFrame):
                            close_col = close_col.iloc[:, 0]
                        df_dict[ticker_symbol] = close_col
            except Exception as e:
                logger.warning(f"yfinance failed for ticker {ticker_symbol}: {e}")

        if df_dict:
            macro = pd.DataFrame(df_dict)
            macro = macro.reset_index()
            macro["Date"] = pd.to_datetime(macro["Date"]).dt.strftime("%Y-%m-%d")
            macro = macro.ffill().bfill()
            return macro.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching macro indicators: {e}")
    return []

