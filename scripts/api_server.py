"""Lightweight FastAPI API Server for Production Docker Deployment.

Replicates the Vite dev-mode middleware plugin (energyDataPlugin in vite.config.ts)
so that the frontend can fetch data in production via Nginx reverse proxy.

Endpoints:
  GET /api/db-data?date=...&type=...  — Energy data from PostgreSQL
  GET /api/fx                         — Live USD/TRY & EUR/TRY from Yahoo Finance
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import json
import logging
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from db.connection import get_db_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("APIServer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 API Server starting up...")
    yield
    logger.info("🛑 API Server shutting down...")


app = FastAPI(title="Enerji Fiyat Tahmini API", lifespan=lifespan)


@app.get("/api/db-data")
async def db_data(date: str = Query(..., description="Date param or 'latest'"),
                  type: str = Query(..., description="Query type")):
    """Serves energy data from PostgreSQL, same logic as query_db.py."""
    try:
        engine = get_db_engine()

        if type == "next_day_forecast":
            sql = """
                SELECT 
                    TO_CHAR(target_ts, 'HH24:00') as hour, 
                    ROUND(predicted_mcp_try, 2) as lightgbm_forecast,
                    TO_CHAR(target_ts, 'YYYY-MM-DD') as target_date
                FROM gold.ptf_predictions_daily 
                WHERE target_ts::date = (SELECT MAX(target_ts::date) FROM gold.ptf_predictions_daily) 
                ORDER BY target_ts;
            """
            with engine.connect() as conn:
                res = conn.execute(text(sql)).mappings().all()
                data = [dict(r) for r in res]
                return JSONResponse(content=json.loads(json.dumps(data, default=str)))

        elif type == "performance":
            if "_to_" in date:
                parts = date.split("_to_")
                start_dt, end_dt = parts[0], parts[1]
                sql = """
                    SELECT 
                        COUNT(*) as total_hours,
                        ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try) / NULLIF(m.price_try, 0) * 100), 2) as mape,
                        ROUND((SUM(ABS(g.predicted_mcp_try - m.price_try)) / NULLIF(SUM(m.price_try), 0) * 100), 2) as wape,
                        ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try)), 2) as mae,
                        ROUND(AVG(g.predicted_mcp_try), 2) as avg_predicted,
                        ROUND(AVG(m.price_try), 2) as avg_actual
                    FROM gold.ptf_predictions_daily g
                    JOIN raw_mcp_hourly m ON g.target_ts = m.ts
                    WHERE g.target_ts::date >= :start_dt AND g.target_ts::date <= :end_dt;
                """
                with engine.connect() as conn:
                    res = conn.execute(text(sql), {"start_dt": start_dt, "end_dt": end_dt}).mappings().all()
                    data = [dict(r) for r in res]
                    return JSONResponse(content=json.loads(json.dumps(data, default=str)))
            else:
                days_map = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
                days = days_map.get(date, 365)
                if date == "1d":
                    sql = """
                        SELECT 
                            COUNT(*) as total_hours,
                            ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try) / NULLIF(m.price_try, 0) * 100), 2) as mape,
                            ROUND((SUM(ABS(g.predicted_mcp_try - m.price_try)) / NULLIF(SUM(m.price_try), 0) * 100), 2) as wape,
                            ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try)), 2) as mae,
                            ROUND(AVG(g.predicted_mcp_try), 2) as avg_predicted,
                            ROUND(AVG(m.price_try), 2) as avg_actual
                        FROM gold.ptf_predictions_daily g
                        JOIN raw_mcp_hourly m ON g.target_ts = m.ts
                        WHERE m.ts::date = (SELECT MAX(ts::date) FROM raw_mcp_hourly);
                    """
                else:
                    days_map = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
                    days = days_map.get(date, 365)
                    sql = """
                        SELECT 
                            COUNT(*) as total_hours,
                            ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try) / NULLIF(m.price_try, 0) * 100), 2) as mape,
                            ROUND((SUM(ABS(g.predicted_mcp_try - m.price_try)) / NULLIF(SUM(m.price_try), 0) * 100), 2) as wape,
                            ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try)), 2) as mae,
                            ROUND(AVG(g.predicted_mcp_try), 2) as avg_predicted,
                            ROUND(AVG(m.price_try), 2) as avg_actual
                        FROM gold.ptf_predictions_daily g
                        JOIN raw_mcp_hourly m ON g.target_ts = m.ts
                        WHERE g.target_ts::date >= ((SELECT MAX(ts::date) FROM raw_mcp_hourly) - (:days || ' days')::INTERVAL);
                    """.replace(":days", str(days))
                with engine.connect() as conn:
                    res = conn.execute(text(sql)).mappings().all()
                    data = [dict(r) for r in res]
                    return JSONResponse(content=json.loads(json.dumps(data, default=str)))

        elif type == "today_performance" or type == "range_performance":
            if "_to_" in date:
                parts = date.split("_to_")
                start_dt, end_dt = parts[0], parts[1]
                target_clause = "m.ts::date >= :start_dt AND m.ts::date <= :end_dt"
                params = {"start_dt": start_dt, "end_dt": end_dt}
            elif date in ["latest", "today", "1d"]:
                target_clause = "m.ts::date = (SELECT MAX(ts::date) FROM raw_mcp_hourly)"
                params = {}
            elif date in ["7d", "1m", "3m", "6m", "1y"]:
                days_map = {"7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
                days = days_map.get(date, 365)
                target_clause = f"m.ts::date >= ((SELECT MAX(ts::date) FROM raw_mcp_hourly) - INTERVAL '{days} days')"
                params = {}
            else:
                target_clause = "m.ts::date = :dt"
                params = {"dt": date}

            sql = f"""
                SELECT 
                    TO_CHAR(m.ts, 'YYYY-MM-DD HH24:00') as timestamp,
                    TO_CHAR(m.ts, 'YYYY-MM-DD') as date,
                    TO_CHAR(m.ts, 'HH24:00') as hour,
                    ROUND(m.price_try, 2) as ptf,
                    ROUND(g.predicted_mcp_try, 2) as lightgbm_forecast
                FROM raw_mcp_hourly m
                LEFT JOIN gold.ptf_predictions_daily g ON m.ts = g.target_ts
                WHERE {target_clause}
                ORDER BY m.ts;
            """
            metrics_sql = f"""
                SELECT 
                    COUNT(*) as total_hours,
                    ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try) / NULLIF(m.price_try, 0) * 100), 2) as mape,
                    ROUND((SUM(ABS(g.predicted_mcp_try - m.price_try)) / NULLIF(SUM(m.price_try), 0) * 100), 2) as wape,
                    ROUND(AVG(ABS(g.predicted_mcp_try - m.price_try)), 2) as mae,
                    ROUND(AVG(g.predicted_mcp_try), 2) as avg_predicted,
                    ROUND(AVG(m.price_try), 2) as avg_actual
                FROM gold.ptf_predictions_daily g
                JOIN raw_mcp_hourly m ON g.target_ts = m.ts
                WHERE {target_clause};
            """
            with engine.connect() as conn:
                res = conn.execute(text(sql), params).mappings().all()
                data = [dict(r) for r in res]
                
                m_res = conn.execute(text(metrics_sql), params).mappings().first()
                metrics = dict(m_res) if m_res else {}

                return JSONResponse(content={
                    "series": data,
                    "metrics": metrics
                })

        else:
            sql_map = {
                "mcp": "SELECT TO_CHAR(ts, 'HH24:00') as hour, price_try as price FROM raw_mcp_hourly WHERE ts::date = :dt ORDER BY ts",
                "smp": "SELECT TO_CHAR(ts, 'HH24:00') as hour, system_marginal_price_try as price FROM raw_smp_hourly WHERE ts::date = :dt ORDER BY ts",
                "kgup": "SELECT TO_CHAR(ts, 'HH24:00') as hour, total_mw as toplam FROM raw_kgup_hourly WHERE ts::date = :dt ORDER BY ts",
                "load_forecast": "SELECT TO_CHAR(ts, 'HH24:00') as hour, load_forecast_mw as lep FROM raw_load_forecast_hourly WHERE ts::date = :dt ORDER BY ts",
                "actual_generation": "SELECT TO_CHAR(ts, 'HH24:00') as hour, total_mw as total FROM raw_actual_generation_hourly WHERE ts::date = :dt ORDER BY ts",
                "lightgbm": "SELECT TO_CHAR(target_ts, 'HH24:00') as hour, predicted_mcp_try as price FROM gold.ptf_predictions_daily WHERE target_ts::date = :dt ORDER BY target_ts",
            }
            if type in sql_map:
                with engine.connect() as conn:
                    res = conn.execute(text(sql_map[type]), {"dt": date}).mappings().all()
                    data = [dict(r) for r in res]
                    return JSONResponse(content=json.loads(json.dumps(data, default=str)))
            else:
                return JSONResponse(content=[])

    except Exception as e:
        logger.error(f"DB query error: {e}")
        return JSONResponse(content=[])


@app.get("/api/fx")
async def fx_rates():
    """Fetches live USD/TRY and EUR/TRY exchange rates with multiple fallback APIs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            usd_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/USDTRY=X")
            eur_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/EURTRY=X")

            if usd_resp.status_code == 200 and eur_resp.status_code == 200:
                usd_data = usd_resp.json()
                eur_data = eur_resp.json()
                usd_result = usd_data["chart"]["result"][0]
                eur_result = eur_data["chart"]["result"][0]

                return JSONResponse(content={
                    "USD": {
                        "price": usd_result["meta"]["regularMarketPrice"],
                        "prevClose": usd_result["meta"].get("previousClose", usd_result["meta"]["regularMarketPrice"]),
                    },
                    "EUR": {
                        "price": eur_result["meta"]["regularMarketPrice"],
                        "prevClose": eur_result["meta"].get("previousClose", eur_result["meta"]["regularMarketPrice"]),
                    },
                })
    except Exception as e:
        logger.warning(f"Yahoo Finance fetch failed: {e}. Trying fallback API...")

    # Fallback to open exchange rate API
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://api.exchangerate-api.com/v4/latest/USD")
            if resp.status_code == 200:
                rates = resp.json().get("rates", {})
                usd_try = rates.get("TRY", 33.15)
                eur_val = rates.get("EUR", 0.92)
                eur_try = usd_try / eur_val if eur_val else 36.10
                return JSONResponse(content={
                    "USD": {"price": round(usd_try, 4), "prevClose": round(usd_try * 0.998, 4)},
                    "EUR": {"price": round(eur_try, 4), "prevClose": round(eur_try * 0.998, 4)},
                })
    except Exception as e:
        logger.error(f"Fallback FX fetch error: {e}")

    return JSONResponse(content={"error": "Failed to fetch live FX rates"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
