import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to sys.path dynamically regardless of OS or user directory
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from db.connection import get_db_engine
    from sqlalchemy import text
except Exception as e:
    print(json.dumps([]))
    sys.exit(0)

if len(sys.argv) < 3:
    print(json.dumps([]))
    sys.exit(0)

date_param = sys.argv[1]
type_param = sys.argv[2]

try:
    engine = get_db_engine()

    if type_param == 'next_day_forecast':
        # Get predictions for the latest available target date (e.g. 2026-08-01)
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
            print(json.dumps(data, default=str))

    elif type_param == 'performance':
        # Compute performance metrics (MAPE, WAPE, MAE) by comparing gold predictions vs realized PTF
        days_map = {'1d': 1, '7d': 7, '1m': 30, '3m': 90, '6m': 180, '1y': 365}
        days = days_map.get(date_param, 365)
        
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
            WHERE g.target_ts >= (SELECT MAX(ts) FROM raw_mcp_hourly) - INTERVAL ':days days';
        """.replace(':days', str(days))

        with engine.connect() as conn:
            res = conn.execute(text(sql)).mappings().all()
            data = [dict(r) for r in res]
            print(json.dumps(data, default=str))

    elif type_param == 'today_performance':
        # Today's hourly comparison (e.g. 2026-07-31) between PTF and LightGBM prediction
        sql = """
            SELECT 
                TO_CHAR(m.ts, 'HH24:00') as hour,
                ROUND(m.price_try, 2) as ptf,
                ROUND(g.predicted_mcp_try, 2) as lightgbm_forecast
            FROM raw_mcp_hourly m
            LEFT JOIN gold.ptf_predictions_daily g ON m.ts = g.target_ts
            WHERE m.ts::date = :dt
            ORDER BY m.ts;
        """
        with engine.connect() as conn:
            res = conn.execute(text(sql), {'dt': date_param}).mappings().all()
            data = [dict(r) for r in res]
            print(json.dumps(data, default=str))

    else:
        # Generic single series fetch
        sql_map = {
            'mcp': "SELECT TO_CHAR(ts, 'HH24:00') as hour, price_try as price FROM raw_mcp_hourly WHERE ts::date = :dt ORDER BY ts",
            'smp': "SELECT TO_CHAR(ts, 'HH24:00') as hour, system_marginal_price_try as price FROM raw_smp_hourly WHERE ts::date = :dt ORDER BY ts",
            'kgup': "SELECT TO_CHAR(ts, 'HH24:00') as hour, total_mw as toplam FROM raw_kgup_hourly WHERE ts::date = :dt ORDER BY ts",
            'load_forecast': "SELECT TO_CHAR(ts, 'HH24:00') as hour, load_forecast_mw as lep FROM raw_load_forecast_hourly WHERE ts::date = :dt ORDER BY ts",
            'actual_generation': "SELECT TO_CHAR(ts, 'HH24:00') as hour, total_mw as total FROM raw_actual_generation_hourly WHERE ts::date = :dt ORDER BY ts",
            'lightgbm': "SELECT TO_CHAR(target_ts, 'HH24:00') as hour, predicted_mcp_try as price FROM gold.ptf_predictions_daily WHERE target_ts::date = :dt ORDER BY target_ts"
        }

        if type_param in sql_map:
            with engine.connect() as conn:
                res = conn.execute(text(sql_map[type_param]), {'dt': date_param}).mappings().all()
                data = [dict(r) for r in res]
                print(json.dumps(data, default=str))
        else:
            print(json.dumps([]))

except Exception as e:
    print(json.dumps([]))
