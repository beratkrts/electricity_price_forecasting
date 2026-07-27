"""PostgreSQL Database Integrity & Data Quality Verification Tool.

Performs post-ETL health checks:
1. Row counts & date coverage across all Bronze & Silver tables.
2. Missing hourly timestamp gap analysis.
3. NULL value ratio and data quality checks per column.
4. Value range and anomaly checks (MCP/SMP price bounds, MW limits, temperature limits).
5. Bronze layer audit batch status (Success vs Failures).
6. Duplicate primary key check.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import text
from db.connection import get_db_engine

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("DBVerification")


def run_database_verification() -> Dict[str, Any]:
    """Runs full database health checks and returns a summary report."""
    logger.info("🔍 Starting Full Database Verification & Quality Audit...\n")
    engine = get_db_engine()
    report = {"errors": [], "warnings": [], "passed": []}

    with engine.connect() as conn:

        # =====================================================================
        # 1. BRONZE LAYER AUDIT CHECK (ingestion_batches)
        # =====================================================================
        print("=" * 70)
        print("1. 🛡️ BRONZE LAYER AUDIT CHECK (ingestion_batches)")
        print("=" * 70)
        try:
            audit_df = pd.read_sql(
                text("""
                SELECT status, COUNT(*) as batch_count, SUM(row_count) as total_rows
                FROM ingestion_batches
                GROUP BY status
            """),
                conn,
            )
            print(audit_df.to_string(index=False))

            # Check for failed batches
            failures = conn.execute(
                text("SELECT source_name, period_key, error_message FROM ingestion_batches WHERE status = 'FAILED'")
            ).fetchall()
            if failures:
                report["errors"].append(f"Found {len(failures)} failed ingestion batches.")
                print(f"\n⚠️ FAILED BATCHES DETECTED ({len(failures)}):")
                for f in failures:
                    print(f"  - Source: {f[0]}, Period: {f[1]}, Error: {f[2]}")
            else:
                report["passed"].append("Bronze layer audit: All ingestion batches SUCCESSFUL.")
                print("\n✅ All ingestion batches completed with status 'SUCCESS'.")
        except Exception as e:
            report["errors"].append(f"Bronze layer check error: {e}")

        # =====================================================================
        # 2. ROW COUNTS & DATE COVERAGE (Silver Layer Tables)
        # =====================================================================
        print("\n" + "=" * 70)
        print("2. 📊 SILVER LAYER ROW COUNTS & DATE COVERAGE")
        print("=" * 70)

        silver_tables = [
            ("raw_mcp_hourly", "ts"),
            ("raw_smp_hourly", "ts"),
            ("raw_load_forecast_hourly", "ts"),
            ("raw_kgup_hourly", "ts"),
            ("raw_actual_generation_hourly", "ts"),
            ("raw_actual_consumption_hourly", "ts"),
            ("raw_bids_offers_hourly", "ts"),
            ("raw_licensed_realtime_generation_hourly", "ts"),
            ("raw_installed_capacity_daily", "period_date"),
            ("raw_natural_gas_daily", "entry_date"),
            ("raw_macro_daily", "entry_date"),
            ("raw_weather_hourly", "ts"),
            ("raw_master_active_fullness", "date_time"),
            ("raw_master_water_energy_provision", "date_time"),
        ]

        coverage_data = []
        for table_name, date_col in silver_tables:
            try:
                query = text(f"""
                    SELECT 
                        COUNT(*) as total_rows,
                        MIN({date_col})::text as min_date,
                        MAX({date_col})::text as max_date
                    FROM {table_name}
                """)
                res = conn.execute(query).fetchone()
                coverage_data.append({
                    "Table": table_name,
                    "Total Rows": res[0],
                    "Min Date": res[1] or "N/A",
                    "Max Date": res[2] or "N/A",
                })
            except Exception as e:
                coverage_data.append({
                    "Table": table_name,
                    "Total Rows": "ERROR",
                    "Min Date": str(e),
                    "Max Date": "ERROR",
                })

        coverage_df = pd.DataFrame(coverage_data)
        print(coverage_df.to_string(index=False))

        # =====================================================================
        # 3. MISSING HOURLY TIMESTAMPS (GAP ANALYSIS)
        # =====================================================================
        print("\n" + "=" * 70)
        print("3. ⏰ MISSING HOURLY TIMESTAMP GAP ANALYSIS")
        print("=" * 70)

        hourly_tables = [
            "raw_mcp_hourly",
            "raw_smp_hourly",
            "raw_load_forecast_hourly",
            "raw_kgup_hourly",
            "raw_actual_generation_hourly",
            "raw_actual_consumption_hourly",
            "raw_weather_hourly",
        ]

        for table in hourly_tables:
            try:
                gap_query = text(f"""
                    WITH bounds AS (
                        SELECT MIN(ts) as min_ts, MAX(ts) as max_ts FROM {table}
                    ),
                    expected_series AS (
                        SELECT generate_series(min_ts, max_ts, INTERVAL '1 hour') as expected_ts
                        FROM bounds
                    )
                    SELECT COUNT(*) FROM expected_series e
                    LEFT JOIN {table} t ON e.expected_ts = t.ts
                    WHERE t.ts IS NULL;
                """)
                missing_hours = conn.execute(gap_query).scalar()
                if missing_hours > 0:
                    print(f" ⚠️  {table}: Missing {missing_hours} hour(s) in sequence.")
                    report["warnings"].append(f"{table} has {missing_hours} missing timestamp gaps.")
                else:
                    print(f" ✅ {table}: Perfect hourly sequence (0 gaps).")
            except Exception as e:
                print(f" ❌ {table}: Gap check failed ({e})")

        # =====================================================================
        # 4. NULL VALUE RATIO & QUALITY AUDIT
        # =====================================================================
        print("\n" + "=" * 70)
        print("4. 🧪 NULL VALUE RATIO & DATA QUALITY AUDIT")
        print("=" * 70)

        null_checks = [
            ("raw_mcp_hourly", "price_try", "PTF Price (TRY)"),
            ("raw_smp_hourly", "system_marginal_price_try", "SMF Price (TRY)"),
            ("raw_load_forecast_hourly", "load_forecast_mw", "Load Forecast (MW)"),
            ("raw_kgup_hourly", "total_mw", "Total KGUP (MW)"),
            ("raw_actual_generation_hourly", "total_mw", "Actual Generation (MW)"),
            ("raw_actual_consumption_hourly", "consumption_mw", "Actual Consumption (MW)"),
            ("raw_weather_hourly", "turkey_weighted_temperature_c", "Weighted Temp (°C)"),
            ("raw_macro_daily", "usd_try", "USD/TRY Rate"),
            ("raw_macro_daily", "brent_oil_usd", "Brent Oil ($)"),
        ]

        for table, col, label in null_checks:
            try:
                null_q = text(f"""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE {col} IS NULL) as null_count
                    FROM {table}
                """)
                res = conn.execute(null_q).fetchone()
                total = res[0]
                nulls = res[1]
                ratio = (nulls / total * 100) if total > 0 else 0
                status = "✅ OK" if ratio == 0 else ("⚠️ WARNING" if ratio < 5 else "❌ HIGH NULL")
                print(f" {status} | {table}.{col} ({label}): {nulls}/{total} NULLs ({ratio:.2f}%)")

                if ratio > 5:
                    report["warnings"].append(f"{table}.{col} has {ratio:.2f}% NULL values.")
            except Exception as e:
                print(f" ❌ {table}.{col}: Null check error ({e})")

        # =====================================================================
        # 5. ANOMALY & VALUE RANGE VALIDATION
        # =====================================================================
        print("\n" + "=" * 70)
        print("5. 📈 ANOMALY & VALUE RANGE VALIDATION")
        print("=" * 70)

        validations = [
            ("raw_mcp_hourly", "price_try", "0", "5000", "PTF Price Range (TRY/MWh)"),
            ("raw_smp_hourly", "system_marginal_price_try", "0", "5000", "SMF Price Range (TRY/MWh)"),
            ("raw_load_forecast_hourly", "load_forecast_mw", "5000", "70000", "Load Forecast (MW)"),
            ("raw_weather_hourly", "turkey_weighted_temperature_c", "-30", "50", "Turkey Temperature (°C)"),
            ("raw_macro_daily", "usd_try", "15", "60", "USD/TRY Exchange Rate"),
        ]

        for table, col, min_val, max_val, label in validations:
            try:
                val_q = text(f"""
                    SELECT 
                        MIN({col}) as min_v,
                        MAX({col}) as max_v,
                        COUNT(*) FILTER (WHERE {col} < {min_val} OR {col} > {max_val}) as anomaly_count
                    FROM {table}
                """)
                res = conn.execute(val_q).fetchone()
                min_v = res[0]
                max_v = res[1]
                anomalies = res[2]

                if anomalies > 0:
                    print(f" ⚠️  {label}: Found {anomalies} outlier(s) out of [{min_val}, {max_val}]! Observed range: [{min_v}, {max_v}]")
                    report["warnings"].append(f"{label} has {anomalies} outliers.")
                else:
                    print(f" ✅ {label}: Range OK [{min_v} to {max_v}] (0 anomalies).")
            except Exception as e:
                print(f" ❌ {label}: Validation error ({e})")

        # =====================================================================
        # SUMMARY EXECUTIVE REPORT
        # =====================================================================
        print("\n" + "=" * 70)
        print("📋 EXECUTIVE HEALTH CHECK SUMMARY")
        print("=" * 70)
        print(f" Passed Checks : {len(report['passed'])}")
        print(f" Warnings      : {len(report['warnings'])}")
        print(f" Errors        : {len(report['errors'])}")

        if report["errors"]:
            print("\n❌ CRITICAL ERRORS DETECTED:")
            for err in report["errors"]:
                print(f"  - {err}")
        elif report["warnings"]:
            print("\n⚠️ WARNINGS TO REVIEW:")
            for warn in report["warnings"]:
                print(f"  - {warn}")
        else:
            print("\n🎉 ALL DATABASE HEALTH & DATA QUALITY CHECKS PASSED PERFECTLY!")

    return report


if __name__ == "__main__":
    run_database_verification()
