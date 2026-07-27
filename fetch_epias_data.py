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
from api_trials.weather_fetcher import fetch_turkey_weighted_temperature

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


def get_tgt_token(username: str, password: str) -> str:
    """Retrieves CAS Ticket Granting Ticket (TGT) for EPİAŞ Transparency 2.0 API."""
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
    tgt = response.text.strip()
    if not tgt:
        raise ValueError("EPİAŞ CAS authentication returned an empty TGT token.")
    return tgt


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

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, env_path: Optional[str] = None):
        self.username = username
        self.password = password
        if username and password:
            kwargs = {"username": username, "password": password}
            if env_path:
                kwargs["dotenv_path"] = str(env_path)
            self.eptr = EPTR2(**kwargs)
        else:
            self.eptr = None
        self._tgt_token = None

    def get_token(self) -> Optional[str]:
        """Lazy loads and caches the TGT authentication token."""
        if not self._tgt_token and self.username and self.password:
            try:
                self._tgt_token = get_tgt_token(self.username, self.password)
                logger.info("EPİAŞ TGT authentication token acquired successfully.")
            except Exception as e:
                logger.error(f"Failed to acquire EPİAŞ TGT token: {e}")
        return self._tgt_token

    def fetch_eptr2_service(self, service_name: str, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches standard EPİAŞ service data via eptr2 library in memory."""
        try:
            if not self.eptr:
                raise ValueError("eptr2 client is not initialized.")
            logger.info(f"Calling eptr2 service: '{service_name}' ({start_iso} to {end_iso})...")
            res = self.eptr.call(service_name, start_date=start_iso, end_date=end_iso)
            if isinstance(res, pd.DataFrame):
                return res.to_dict(orient="records")
            elif isinstance(res, list):
                return res
            elif isinstance(res, dict):
                return find_record_list(res) or []
            return []
        except Exception as e:
            logger.error(f"Error fetching eptr2 service '{service_name}': {e}")
            return []

    def fetch_installed_capacity(self, period_iso: str) -> List[Dict[str, Any]]:
        """Fetches renewable installed capacity data via eptr2 'ren-capacity' into memory."""
        try:
            if not self.eptr:
                raise ValueError("eptr2 client is not initialized.")
            logger.info(f"Calling eptr2 service: 'ren-capacity' for period {period_iso}...")
            res = self.eptr.call("ren-capacity", period=period_iso)
            if isinstance(res, pd.DataFrame):
                return res.to_dict(orient="records")
            elif isinstance(res, list):
                return res
            elif isinstance(res, dict):
                return find_record_list(res) or []
            return []
        except Exception as e:
            logger.error(f"Error fetching installed capacity for period '{period_iso}': {e}")
            return []

    def fetch_active_fullness(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches dam active fullness percentages into memory."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso}
        try:
            res = requests.post(ACTIVE_FULLNESS_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            return find_record_list(res.json()) or []
        except Exception as e:
            logger.error(f"Error fetching active fullness: {e}")
            return []

    def fetch_water_energy_provision(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches dam water energy provision in memory."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso, "exportType": "CSV"}
        try:
            res = requests.post(WATER_ENERGY_PROVISION_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            if "text/csv" in res.headers.get("Content-Type", "") or res.text.startswith("Tarih"):
                res.encoding = "utf-8-sig"
                df = pd.read_csv(io.StringIO(res.text), sep=";")
                return df.to_dict(orient="records")
            return find_record_list(res.json()) or []
        except Exception as e:
            logger.error(f"Error fetching water energy provision: {e}")
            return []

    def fetch_natural_gas_daily_price(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches natural gas daily reference price (GRF) into memory."""
        token = self.get_token()
        if not token:
            return []
        headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
        payload = {"startDate": start_iso, "endDate": end_iso}
        try:
            res = requests.post(NATURAL_GAS_PRICE_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            return find_record_list(res.json()) or []
        except Exception as e:
            logger.error(f"Error fetching natural gas daily reference price: {e}")
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


def fetch_macro_in_memory(start_date: str = "2024-01-01", end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches yfinance macro indicators (USD/TRY & Brent Oil) into memory as list of dicts."""
    try:
        if not end_date:
            end_date = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        
        logger.info(f"Fetching macro indicators from yfinance ({start_date} to {end_date})...")
        macro = yf.download(["USDTRY=X", "BZ=F"], start=start_date, end=end_date, interval="1d", progress=False)["Close"]
        if not macro.empty:
            macro = macro.reset_index()
            macro["Date"] = pd.to_datetime(macro["Date"]).dt.strftime("%Y-%m-%d")
            macro = macro.ffill().bfill()
            return macro.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching macro indicators: {e}")
    return []
