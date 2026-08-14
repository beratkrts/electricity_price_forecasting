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
        payload = {"startDate": start_iso, "endDate": end_iso}
        for attempt in range(1, self.max_retries + 1):
            token = self.get_token()
            if not token:
                return []
            headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
            try:
                res = requests.post(ACTIVE_FULLNESS_URL, headers=headers, json=payload, timeout=60)
                if res.status_code == 401:
                    logger.warning("EPİAŞ API returned 401 Unauthorized. Token expired. Refreshing...")
                    self._tgt_token = None
                    continue
                res.raise_for_status()
                return find_record_list(res.json()) or []
            except Exception as e:
                logger.warning(f"Error fetching active fullness (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * attempt)
        return []

    def fetch_water_energy_provision(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Fetches dam water energy provision in memory with retries."""
        payload = {"startDate": start_iso, "endDate": end_iso, "exportType": "CSV"}
        for attempt in range(1, self.max_retries + 1):
            token = self.get_token()
            if not token:
                return []
            headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
            try:
                res = requests.post(WATER_ENERGY_PROVISION_URL, headers=headers, json=payload, timeout=60)
                if res.status_code == 401:
                    logger.warning("EPİAŞ API returned 401 Unauthorized. Token expired. Refreshing...")
                    self._tgt_token = None
                    continue
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
        payload = {"startDate": start_iso, "endDate": end_iso}
        for attempt in range(1, self.max_retries + 1):
            token = self.get_token()
            if not token:
                return []
            headers = {"Content-Type": "application/json", "Accept": "application/json", "TGT": token}
            try:
                res = requests.post(NATURAL_GAS_PRICE_URL, headers=headers, json=payload, timeout=60)
                if res.status_code == 401:
                    logger.warning("EPİAŞ API returned 401 Unauthorized. Token expired. Refreshing...")
                    self._tgt_token = None
                    continue
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


def fetch_live_fx_fallback_rate() -> Optional[float]:
    """Fetches real-time USD/TRY exchange rate from open ExchangeRate API as dynamic fallback."""
    try:
        import requests
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        if r.status_code == 200:
            val = r.json().get("rates", {}).get("TRY")
            if val:
                return float(val)
    except Exception as e:
        logger.warning(f"Could not fetch dynamic FX fallback rate: {e}")
    return None


def resolve_usd_try_rate(df: Optional[pd.DataFrame] = None, engine: Any = None) -> float:
    """
    Robust 4-Tier Dynamic USD/TRY Exchange Rate Resolver.
    Guarantees pipeline resilience without breaking or using static hardcoded numbers.
    Logs every fallback trigger to logs/fallbacks.log.
    """
    from src.utils.fallback_logger import log_fallback

    # Tier 1: Input DataFrame
    if df is not None and 'usd_try' in df.columns:
        valid_s = df['usd_try'].dropna()
        if len(valid_s) > 0:
            return float(valid_s.iloc[-1])

    # Tier 2: Live ExchangeRate API
    live_val = fetch_live_fx_fallback_rate()
    if live_val and live_val > 0:
        log_fallback("DataFetcher", "DataFrame USD/TRY rate missing, fell back to Live ExchangeRate API", live_val)
        return float(live_val)

    # Tier 3: PostgreSQL Database Query
    if engine is not None:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                row = conn.execute(text("SELECT usd_try FROM raw_macro_daily WHERE usd_try IS NOT NULL ORDER BY entry_date DESC LIMIT 1;")).fetchone()
                if row and row[0]:
                    log_fallback("DataFetcher", "Live FX API failed, fell back to PostgreSQL raw_macro_daily", float(row[0]))
                    return float(row[0])
        except Exception as e:
            logger.warning(f"DB FX resolution query failed: {e}")

    # Tier 4: Live Frankfurter ECB API
    try:
        s = fetch_historical_usdtry_frankfurter()
        if not s.empty:
            rate = float(s.dropna().iloc[-1])
            log_fallback("DataFetcher", "DB FX query failed, fell back to Frankfurter ECB API", rate)
            return rate
    except Exception as e:
        logger.warning(f"Frankfurter FX resolution failed: {e}")

    # Safety net if completely offline and DB is empty
    log_fallback("DataFetcher", "All FX providers and DB failed, using dynamic safety net", 36.0)
    return 36.0


# Weekends plus a holiday bridge; anything longer is a real data outage, not a closed market.
MARKET_GAP_FFILL_LIMIT = 4


def _fill_market_gaps(s: pd.Series, limit: int = MARKET_GAP_FFILL_LIMIT) -> pd.Series:
    """Forward-fills non-trading days (weekends/holidays) up to `limit` days only.

    Longer gaps deliberately stay NaN: a stale price repeated for a week is
    indistinguishable from real movement downstream, whereas a NaN is visible.
    Leading NaNs (before the first observation) are back-filled so the series
    still starts at start_date.
    """
    s = s.astype(float)
    filled = s.ffill(limit=limit)
    first_valid = s.first_valid_index()
    if first_valid is not None:
        filled.loc[:first_valid] = filled.loc[:first_valid].bfill()
    return filled


def fetch_historical_usdtry_frankfurter(start_date: str = "2023-01-01", end_date: Optional[str] = None) -> pd.Series:
    """Fetches official historical USD/TRY exchange rates from Frankfurter (ECB API)."""
    try:
        import requests
        if not end_date:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        url = f"https://api.frankfurter.app/{start_date}..{end_date}?from=USD&to=TRY"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            rates = res.json().get("rates", {})
            if rates:
                df = pd.DataFrame([{"Date": k, "usd_try": v.get("TRY")} for k, v in rates.items()])
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date").sort_index()
                full_idx = pd.date_range(start=start_date, end=end_date, freq="D")
                return _fill_market_gaps(df["usd_try"].reindex(full_idx))
    except Exception as e:
        logger.warning(f"Could not fetch historical USD/TRY from Frankfurter API: {e}")
    return pd.Series(dtype=float)


def fetch_historical_brent_oil_fred(start_date: str = "2023-01-01", end_date: Optional[str] = None) -> pd.Series:
    """Fetches official historical Brent Oil prices from FRED (Federal Reserve Bank of St. Louis API).

    NOTE: FRED's DCOILBRENTEU series is published with a 2-3 business day lag, so its
    tail is always stale. Used only as a fallback for yfinance BZ=F (see fetch_macro_in_memory).
    """
    try:
        if not end_date:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
        df = pd.read_csv(url)
        if not df.empty and "observation_date" in df.columns and "DCOILBRENTEU" in df.columns:
            df["observation_date"] = pd.to_datetime(df["observation_date"])
            df["DCOILBRENTEU"] = pd.to_numeric(df["DCOILBRENTEU"], errors="coerce")
            df = df.set_index("observation_date").sort_index()
            df = df.loc[start_date:]
            full_idx = pd.date_range(start=start_date, end=end_date, freq="D")
            return _fill_market_gaps(df["DCOILBRENTEU"].reindex(full_idx))
    except Exception as e:
        logger.warning(f"Could not fetch historical Brent Oil from FRED API: {e}")
    return pd.Series(dtype=float)


def fetch_historical_brent_oil_yfinance(start_date: str = "2023-01-01", end_date: Optional[str] = None) -> pd.Series:
    """Fetches Brent Oil futures (BZ=F) from Yahoo Finance — same-day, no publication lag.

    Preferred over FRED because DCOILBRENTEU lags 2-3 business days, which used to leave
    the most recent days forward-filled with a stale price.
    """
    try:
        if not end_date:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        # yfinance treats `end` as exclusive, so request one extra day to include end_date itself.
        yf_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for attempt in range(1, 4):
            try:
                t_df = yf.download("BZ=F", start=start_date, end=yf_end, interval="1d",
                                   progress=False, timeout=15, auto_adjust=False)
                if not t_df.empty and "Close" in t_df.columns:
                    close_col = t_df["Close"]
                    if isinstance(close_col, pd.DataFrame):
                        close_col = close_col.iloc[:, 0]
                    close_col.index = pd.to_datetime(close_col.index).tz_localize(None).normalize()
                    full_idx = pd.date_range(start=start_date, end=end_date, freq="D")
                    return _fill_market_gaps(close_col.reindex(full_idx))
            except Exception as e:
                logger.warning(f"yfinance attempt {attempt}/3 failed for BZ=F: {e}")
                time.sleep(2 * attempt)
    except Exception as e:
        logger.warning(f"Could not fetch Brent Oil from yfinance: {e}")
    return pd.Series(dtype=float)


def fetch_macro_in_memory(start_date: str = "2023-01-01", end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches macro indicators (USD/TRY & Brent Oil) into memory safely as list of dicts with retries and fallbacks."""
    try:
        # Never extend past today: macro observations for future dates do not exist, and
        # reindexing to a future end_date used to write a forward-filled row for tomorrow.
        if not end_date:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        else:
            today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
            if end_date > today_str:
                logger.warning(f"macro end_date {end_date} is in the future; clamping to {today_str}.")
                end_date = today_str

        logger.info(f"Fetching macro indicators ({start_date} to {end_date})...")

        df_dict = {}
        tickers = ["USDTRY=X", "BZ=F"]

        # 1. Try official Frankfurter API for historical USD/TRY exchange rates first
        try:
            usd_series = fetch_historical_usdtry_frankfurter(start_date, end_date)
            if not usd_series.empty:
                df_dict["USDTRY=X"] = usd_series
                logger.info(f"✅ Ingested {len(usd_series)} official historical USD/TRY exchange rates from Frankfurter API.")
        except Exception as e:
            logger.warning(f"Frankfurter historical FX fetch error: {e}")

        # 2. Brent Oil: yfinance BZ=F first (same-day), FRED only as a fallback.
        #    FRED's DCOILBRENTEU lags 2-3 business days, which left the latest days stale.
        try:
            brent_series = fetch_historical_brent_oil_yfinance(start_date, end_date)
            if not brent_series.empty:
                df_dict["BZ=F"] = brent_series
                logger.info(f"✅ Ingested {len(brent_series)} Brent Oil prices from yfinance (BZ=F).")
        except Exception as e:
            logger.warning(f"yfinance Brent Oil fetch error: {e}")

        if "BZ=F" not in df_dict:
            try:
                brent_series = fetch_historical_brent_oil_fred(start_date, end_date)
                if not brent_series.empty:
                    from src.utils.fallback_logger import log_fallback
                    df_dict["BZ=F"] = brent_series
                    last_val = float(brent_series.dropna().iloc[-1]) if brent_series.notna().any() else 0.0
                    log_fallback("DataFetcher", "yfinance BZ=F unavailable, fell back to FRED DCOILBRENTEU (2-3 day publication lag)", last_val)
                    logger.info(f"✅ Ingested {len(brent_series)} official historical Brent Oil prices from FRED API.")
            except Exception as e:
                logger.warning(f"FRED historical Brent Oil fetch error: {e}")

        full_idx = pd.date_range(start=start_date, end=end_date, freq="D")

        for symbol in tickers:
            if symbol in df_dict:
                continue

            fetched = False
            # yfinance treats `end` as exclusive, so request one extra day to include end_date.
            yf_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            for attempt in range(1, 4):
                try:
                    t_df = yf.download(symbol, start=start_date, end=yf_end, interval="1d",
                                       progress=False, timeout=15, auto_adjust=False)
                    if not t_df.empty and "Close" in t_df.columns:
                        close_col = t_df["Close"]
                        if isinstance(close_col, pd.DataFrame):
                            close_col = close_col.iloc[:, 0]
                        close_col.index = pd.to_datetime(close_col.index).tz_localize(None).normalize()
                        df_dict[symbol] = _fill_market_gaps(close_col.reindex(full_idx))
                        fetched = True
                        break
                except Exception as e:
                    logger.warning(f"yfinance attempt {attempt}/3 failed for symbol {symbol}: {e}")
                    time.sleep(2 * attempt)

            if not fetched:
                logger.warning(f"⚠️ yfinance unavailable for {symbol}. Omitting symbol from fetch batch to preserve existing DB values.")

        if df_dict:
            # Every source is already reindexed onto full_idx and gap-filled within
            # MARKET_GAP_FFILL_LIMIT, so no blanket ffill/bfill here — that would silently
            # revive stale values across long outages.
            macro = pd.DataFrame(df_dict)
            macro.index = pd.to_datetime(macro.index).strftime("%Y-%m-%d")
            macro = macro.reset_index()
            date_col = macro.columns[0]

            records = []
            for _, row in macro.iterrows():
                dt_str = str(row[date_col]).split("T")[0].split(" ")[0]
                usd_val = row.get("USDTRY=X") if "USDTRY=X" in row else None
                brent_val = row.get("BZ=F") if "BZ=F" in row else None
                records.append({
                    "entry_date": dt_str,
                    "usd_try": float(usd_val) if pd.notna(usd_val) else None,
                    "brent_oil_usd": float(brent_val) if pd.notna(brent_val) else None,
                })
            return records
    except Exception as e:
        logger.error(f"Error fetching macro indicators: {e}")
    return []

