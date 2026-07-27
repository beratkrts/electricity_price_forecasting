"""Database ETL Pipeline Entry Point.

Direct wrapper for running the in-memory EPİAŞ & Weather ETL pipeline.
"""

from daily_update_pipeline import run_daily_pipeline

if __name__ == "__main__":
    run_daily_pipeline()