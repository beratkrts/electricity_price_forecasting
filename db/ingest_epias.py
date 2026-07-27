"""Database Ingestion Module for Bronze and Silver Layers.

Performs diskless, in-memory ingestion of raw API payloads directly into PostgreSQL:
1. Calculates SHA-256 payload checksum and audits batch execution in Bronze Layer (ingestion_batches).
2. Upserts normalized time-series records into Silver Layer (raw_* tables) with ON CONFLICT resolution.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from db.connection import get_db_url, get_db_engine, calculate_checksum

logger = logging.getLogger("DatabaseIngestor")


class EpiasDBIngestor:
    """Manages Bronze layer audit logging and Silver layer time-series upserts."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or get_db_url()
        self.engine = get_db_engine(self.db_url)

    def init_db(self, schema_file: str = "sql/01_init_schema.sql") -> None:
        """Executes the SQL schema file to create missing tables and indexes."""
        if os.path.exists(schema_file):
            logger.info(f"Initializing database schema from '{schema_file}'...")
            with open(schema_file, "r", encoding="utf-8") as f:
                sql_script = f.read()
            with self.engine.begin() as conn:
                conn.execute(text(sql_script))
            logger.info("Database schema initialized successfully.")
        else:
            logger.warning(f"Schema file '{schema_file}' not found.")

    def is_already_ingested(self, source_name: str, checksum: str) -> Optional[int]:
        """Checks if a batch with the exact SHA-256 checksum has already been ingested successfully."""
        query = text("""
            SELECT id FROM ingestion_batches 
            WHERE source_name = :source_name AND checksum = :checksum AND status = 'SUCCESS'
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"source_name": source_name, "checksum": checksum}).fetchone()
            return result[0] if result else None

    def record_ingestion_batch(
        self,
        source_name: str,
        period_key: str,
        checksum: str,
        row_count: int,
        status: str = "SUCCESS",
        error_msg: Optional[str] = None,
    ) -> int:
        """Inserts or updates an audit record in the Bronze layer (ingestion_batches)."""
        query = text("""
            INSERT INTO ingestion_batches (source_name, period_key, checksum, row_count, status, error_message, fetched_at)
            VALUES (:source_name, :period_key, :checksum, :row_count, :status, :error_msg, NOW())
            ON CONFLICT (source_name, checksum) DO UPDATE SET
                row_count = EXCLUDED.row_count,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                fetched_at = NOW()
            RETURNING id;
        """)
        with self.engine.begin() as conn:
            result = conn.execute(query, {
                "source_name": source_name,
                "period_key": period_key,
                "checksum": checksum,
                "row_count": row_count,
                "status": status,
                "error_msg": error_msg,
            }).fetchone()
            return result[0]

    # -------------------------------------------------------------------------
    # SILVER LAYER UPSERT METHODS
    # -------------------------------------------------------------------------

    def ingest_mcp(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Market Clearing Price (PTF / MCP) records into raw_mcp_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("mcp", checksum):
            logger.info(f"[MCP] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("mcp", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_mcp_hourly (ts, price_try, price_usd, price_eur, ingestion_id)
            VALUES (:ts, :price_try, :price_usd, :price_eur, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                price_try = EXCLUDED.price_try,
                price_usd = EXCLUDED.price_usd,
                price_eur = EXCLUDED.price_eur,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("ts"),
            "price_try": r.get("price") or r.get("price_try"),
            "price_usd": r.get("priceUsd") or r.get("price_usd"),
            "price_eur": r.get("priceEur") or r.get("price_eur"),
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[MCP] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_smp(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests System Marginal Price (SMF / SMP) records into raw_smp_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("smp", checksum):
            logger.info(f"[SMP] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("smp", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_smp_hourly (ts, system_marginal_price_try, ingestion_id)
            VALUES (:ts, :smp, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                system_marginal_price_try = EXCLUDED.system_marginal_price_try,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("ts"),
            "smp": r.get("systemMarginalPrice") or r.get("price") or r.get("system_marginal_price_try"),
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[SMP] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_load_forecast(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Load Forecast (Yük Tahmini) records into raw_load_forecast_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("load_forecast", checksum):
            logger.info(f"[LOAD_FORECAST] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("load_forecast", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_load_forecast_hourly (ts, load_forecast_mw, ingestion_id)
            VALUES (:ts, :lep, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                load_forecast_mw = EXCLUDED.load_forecast_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("time") or r.get("ts"),
            "lep": r.get("lep") or r.get("load_forecast_mw"),
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("time") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[LOAD_FORECAST] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_kgup(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Final Day-Ahead Generation Plan (KGÜP) records into raw_kgup_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("kgup", checksum):
            logger.info(f"[KGUP] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("kgup", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_kgup_hourly (
                ts, total_mw, natural_gas_mw, wind_mw, lignite_mw, black_coal_mw,
                import_coal_mw, fuel_oil_mw, geothermal_mw, dammed_hydro_mw,
                river_hydro_mw, naphtha_mw, biomass_mw, solar_mw, other_mw, ingestion_id
            ) VALUES (
                :ts, :total, :gas, :wind, :lignite, :black_coal,
                :import_coal, :fuel_oil, :geothermal, :dammed_hydro,
                :river_hydro, :naphtha, :biomass, :solar, :other, :ingestion_id
            )
            ON CONFLICT (ts) DO UPDATE SET
                total_mw = EXCLUDED.total_mw,
                natural_gas_mw = EXCLUDED.natural_gas_mw,
                wind_mw = EXCLUDED.wind_mw,
                lignite_mw = EXCLUDED.lignite_mw,
                black_coal_mw = EXCLUDED.black_coal_mw,
                import_coal_mw = EXCLUDED.import_coal_mw,
                fuel_oil_mw = EXCLUDED.fuel_oil_mw,
                geothermal_mw = EXCLUDED.geothermal_mw,
                dammed_hydro_mw = EXCLUDED.dammed_hydro_mw,
                river_hydro_mw = EXCLUDED.river_hydro_mw,
                naphtha_mw = EXCLUDED.naphtha_mw,
                biomass_mw = EXCLUDED.biomass_mw,
                solar_mw = EXCLUDED.solar_mw,
                other_mw = EXCLUDED.other_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("ts"),
            "total": r.get("toplam") or r.get("total_mw") or 0,
            "gas": r.get("dogalgaz") or r.get("natural_gas_mw") or 0,
            "wind": r.get("ruzgar") or r.get("wind_mw") or 0,
            "lignite": r.get("linyit") or r.get("lignite_mw") or 0,
            "black_coal": r.get("tasKomur") or r.get("black_coal_mw") or 0,
            "import_coal": r.get("ithalKomur") or r.get("import_coal_mw") or 0,
            "fuel_oil": r.get("fuelOil") or r.get("fuel_oil_mw") or 0,
            "geothermal": r.get("jeotermal") or r.get("geothermal_mw") or 0,
            "dammed_hydro": r.get("barajli") or r.get("dammed_hydro_mw") or 0,
            "river_hydro": r.get("akarsu") or r.get("river_hydro_mw") or 0,
            "naphtha": r.get("nafta") or r.get("naphtha_mw") or 0,
            "biomass": r.get("biokutle") or r.get("biomass_mw") or 0,
            "solar": r.get("gunes") or r.get("solar_mw") or 0,
            "other": r.get("diger") or r.get("other_mw") or 0,
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[KGUP] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_actual_generation(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Actual Real-Time Generation (Gerçekleşen Üretim) into raw_actual_generation_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("actual_generation", checksum):
            logger.info(f"[ACTUAL_GEN] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("actual_generation", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_actual_generation_hourly (
                ts, total_mw, natural_gas_mw, dammed_hydro_mw, lignite_mw, river_hydro_mw,
                import_coal_mw, wind_mw, solar_mw, fuel_oil_mw, geothermal_mw, asphaltite_coal_mw,
                black_coal_mw, biomass_mw, naphtha_mw, lng_mw, import_export_mw, waste_heat_mw, ingestion_id
            ) VALUES (
                :ts, :total, :gas, :dammed_hydro, :lignite, :river_hydro,
                :import_coal, :wind, :solar, :fuel_oil, :geothermal, :asphaltite,
                :black_coal, :biomass, :naphtha, :lng, :import_export, :waste_heat, :ingestion_id
            )
            ON CONFLICT (ts) DO UPDATE SET
                total_mw = EXCLUDED.total_mw,
                natural_gas_mw = EXCLUDED.natural_gas_mw,
                dammed_hydro_mw = EXCLUDED.dammed_hydro_mw,
                lignite_mw = EXCLUDED.lignite_mw,
                river_hydro_mw = EXCLUDED.river_hydro_mw,
                import_coal_mw = EXCLUDED.import_coal_mw,
                wind_mw = EXCLUDED.wind_mw,
                solar_mw = EXCLUDED.solar_mw,
                fuel_oil_mw = EXCLUDED.fuel_oil_mw,
                geothermal_mw = EXCLUDED.geothermal_mw,
                asphaltite_coal_mw = EXCLUDED.asphaltite_coal_mw,
                black_coal_mw = EXCLUDED.black_coal_mw,
                biomass_mw = EXCLUDED.biomass_mw,
                naphtha_mw = EXCLUDED.naphtha_mw,
                lng_mw = EXCLUDED.lng_mw,
                import_export_mw = EXCLUDED.import_export_mw,
                waste_heat_mw = EXCLUDED.waste_heat_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("ts"),
            "total": r.get("total") or r.get("total_mw") or 0,
            "gas": r.get("naturalGas") or r.get("natural_gas_mw") or 0,
            "dammed_hydro": r.get("dammedHydro") or r.get("dammed_hydro_mw") or 0,
            "lignite": r.get("lignite") or r.get("lignite_mw") or 0,
            "river_hydro": r.get("river") or r.get("river_hydro_mw") or 0,
            "import_coal": r.get("importCoal") or r.get("import_coal_mw") or 0,
            "wind": r.get("wind") or r.get("wind_mw") or 0,
            "solar": r.get("sun") or r.get("solar_mw") or 0,
            "fuel_oil": r.get("fueloil") or r.get("fuel_oil_mw") or 0,
            "geothermal": r.get("geothermal") or r.get("geothermal_mw") or 0,
            "asphaltite": r.get("asphaltiteCoal") or r.get("asphaltite_coal_mw") or 0,
            "black_coal": r.get("blackCoal") or r.get("black_coal_mw") or 0,
            "biomass": r.get("biomass") or r.get("biomass_mw") or 0,
            "naphtha": r.get("naphta") or r.get("naphtha_mw") or 0,
            "lng": r.get("lng") or r.get("lng_mw") or 0,
            "import_export": r.get("importExport") or r.get("import_export_mw") or 0,
            "waste_heat": r.get("wasteheat") or r.get("waste_heat_mw") or 0,
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[ACTUAL_GEN] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_actual_consumption(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Actual Consumption (Gerçekleşen Tüketim) into raw_actual_consumption_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("actual_consumption", checksum):
            logger.info(f"[ACTUAL_CONS] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("actual_consumption", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_actual_consumption_hourly (ts, consumption_mw, ingestion_id)
            VALUES (:ts, :consumption, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                consumption_mw = EXCLUDED.consumption_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("ts"),
            "consumption": r.get("consumption") or r.get("consumption_mw"),
            "ingestion_id": ingestion_id,
        } for r in records if r.get("date") or r.get("ts")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[ACTUAL_CONS] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_bids_offers(self, bids_records: List[Dict], offers_records: List[Dict], period_key: str) -> int:
        """Ingests Day-Ahead Market Bids & Offers into raw_bids_offers_hourly."""
        combined = {"bids": bids_records, "offers": offers_records}
        checksum = calculate_checksum(combined)
        if self.is_already_ingested("bids_offers", checksum):
            logger.info(f"[BIDS_OFFERS] Period {period_key} already ingested. Skipping.")
            return 0

        total_rows = max(len(bids_records or []), len(offers_records or []))
        ingestion_id = self.record_ingestion_batch("bids_offers", period_key, checksum, total_rows)

        data_map = {}
        for r in (bids_records or []):
            dt = r.get("date") or r.get("ts")
            if dt:
                data_map[dt] = {"ts": dt, "bid": r.get("bidQuantity"), "offer": None, "ingestion_id": ingestion_id}
        for r in (offers_records or []):
            dt = r.get("date") or r.get("ts")
            if dt:
                if dt not in data_map:
                    data_map[dt] = {"ts": dt, "bid": None, "offer": r.get("offerQuantity"), "ingestion_id": ingestion_id}
                else:
                    data_map[dt]["offer"] = r.get("offerQuantity")

        insert_query = text("""
            INSERT INTO raw_bids_offers_hourly (ts, bid_quantity_mw, offer_quantity_mw, ingestion_id)
            VALUES (:ts, :bid, :offer, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                bid_quantity_mw = COALESCE(EXCLUDED.bid_quantity_mw, raw_bids_offers_hourly.bid_quantity_mw),
                offer_quantity_mw = COALESCE(EXCLUDED.offer_quantity_mw, raw_bids_offers_hourly.offer_quantity_mw),
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = list(data_map.values())
        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[BIDS_OFFERS] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_macro(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Macro indicators (USD/TRY exchange rate & Brent Oil price) into raw_macro_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("macro", checksum):
            logger.info(f"[MACRO] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("macro", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_macro_daily (entry_date, usd_try, brent_oil_usd, ingestion_id)
            VALUES (:entry_date, :usd_try, :brent_oil_usd, :ingestion_id)
            ON CONFLICT (entry_date) DO UPDATE SET
                usd_try = EXCLUDED.usd_try,
                brent_oil_usd = EXCLUDED.brent_oil_usd,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "entry_date": r.get("date") or r.get("Date") or r.get("entry_date"),
            "usd_try": r.get("usd_try") or r.get("USDTRY=X"),
            "brent_oil_usd": r.get("brent_oil_usd") or r.get("BZ=F"),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("date") or r.get("Date") or r.get("entry_date"))]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[MACRO] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_natural_gas_daily(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Natural Gas Daily Reference Price (GRF) into raw_natural_gas_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("natural_gas_daily", checksum):
            logger.info(f"[NATURAL_GAS] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("natural_gas_daily", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_natural_gas_daily (entry_date, gas_reference_price_try, grf_usd, grf_eur, ingestion_id)
            VALUES (:entry_date, :grf_try, :grf_usd, :grf_eur, :ingestion_id)
            ON CONFLICT (entry_date) DO UPDATE SET
                gas_reference_price_try = EXCLUDED.gas_reference_price_try,
                grf_usd = EXCLUDED.grf_usd,
                grf_eur = EXCLUDED.grf_eur,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "entry_date": r.get("date") or r.get("gas_date") or r.get("entry_date"),
            "grf_try": r.get("grfTl") or r.get("price") or r.get("gas_reference_price_try"),
            "grf_usd": r.get("grfUsd"),
            "grf_eur": r.get("grfEur"),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("date") or r.get("gas_date") or r.get("entry_date"))]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[NATURAL_GAS] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_licensed_realtime_generation(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Licensed Real-time Generation into raw_licensed_realtime_generation_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("licensed_realtime_generation", checksum):
            logger.info(f"[LICENSED_GEN] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("licensed_realtime_generation", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_licensed_realtime_generation_hourly (
                ts, total_mw, wind_mw, geothermal_mw, dammed_hydro_mw, canal_hydro_mw,
                river_hydro_mw, landfill_gas_mw, biogas_mw, solar_mw, biomass_mw, other_mw, ingestion_id
            ) VALUES (
                :ts, :total, :wind, :geothermal, :dammed_hydro, :canal_hydro,
                :river_hydro, :landfill_gas, :biogas, :solar, :biomass, :other, :ingestion_id
            )
            ON CONFLICT (ts) DO UPDATE SET
                total_mw = EXCLUDED.total_mw,
                wind_mw = EXCLUDED.wind_mw,
                geothermal_mw = EXCLUDED.geothermal_mw,
                dammed_hydro_mw = EXCLUDED.dammed_hydro_mw,
                canal_hydro_mw = EXCLUDED.canal_hydro_mw,
                river_hydro_mw = EXCLUDED.river_hydro_mw,
                landfill_gas_mw = EXCLUDED.landfill_gas_mw,
                biogas_mw = EXCLUDED.biogas_mw,
                solar_mw = EXCLUDED.solar_mw,
                biomass_mw = EXCLUDED.biomass_mw,
                other_mw = EXCLUDED.other_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date") or r.get("hour") or r.get("ts"),
            "total": r.get("toplam", 0),
            "wind": r.get("ruzgar", 0),
            "geothermal": r.get("jeotermal", 0),
            "dammed_hydro": r.get("rezervuarli", 0),
            "canal_hydro": r.get("kanalTipi", 0),
            "river_hydro": r.get("nehirTipi", 0),
            "landfill_gas": r.get("copGazi", 0),
            "biogas": r.get("biyogaz", 0),
            "solar": r.get("gunes", 0),
            "biomass": r.get("biyokutle", 0),
            "other": r.get("diger", 0),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("date") or r.get("hour") or r.get("ts"))]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[LICENSED_GEN] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_installed_capacity(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Installed Capacity breakdown into raw_installed_capacity_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("installed_capacity", checksum):
            logger.info(f"[INSTALLED_CAPACITY] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("installed_capacity", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_installed_capacity_daily (
                period_date, energy_type, licensed_capacity_mw, unlicensed_capacity_mw, total_capacity_mw, ingestion_id
            ) VALUES (
                :period_date, :energy_type, :licensed, :unlicensed, :total, :ingestion_id
            )
            ON CONFLICT (period_date, energy_type) DO UPDATE SET
                licensed_capacity_mw = EXCLUDED.licensed_capacity_mw,
                unlicensed_capacity_mw = EXCLUDED.unlicensed_capacity_mw,
                total_capacity_mw = EXCLUDED.total_capacity_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        p_date = period_key.split("T")[0] if "T" in period_key else (f"{period_key}-01" if len(period_key.split("-")) == 2 else period_key)
        data = [{
            "period_date": p_date,
            "energy_type": r.get("renewableEnergyType") or r.get("type", "Unknown"),
            "licensed": r.get("licencedCapacity", 0),
            "unlicensed": r.get("unlicencedCapacity", 0),
            "total": r.get("total", 0),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("renewableEnergyType") or r.get("type"))]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[INSTALLED_CAPACITY] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_weather(self, records: List[Dict[str, Any]], period_key: str) -> int:
        """Ingests Turkey-weighted temperature hourly data into raw_weather_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("weather", checksum):
            logger.info(f"[WEATHER] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("weather", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_weather_hourly (ts, turkey_weighted_temperature_c, ingestion_id)
            VALUES (:ts, :temp, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                turkey_weighted_temperature_c = EXCLUDED.turkey_weighted_temperature_c,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data = [{
            "ts": r.get("date_time") or r.get("date") or r.get("time") or r.get("ts"),
            "temp": r.get("turkey_weighted_temperature_c") or r.get("temp"),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("date_time") or r.get("date") or r.get("time") or r.get("ts"))]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[WEATHER] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_active_fullness(self, records: List[Dict[str, Any]], period_key: str = "master_snapshot") -> int:
        """Ingests Dam Active Fullness snapshot into raw_master_active_fullness."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("active_fullness", checksum):
            logger.info(f"[ACTIVE_FULLNESS] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("active_fullness", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_master_active_fullness (
                dam_id, date_time, record_id, basin_name, dam_name, active_fullness_percent, ingestion_id, updated_at
            ) VALUES (
                :dam_id, :date_time, :record_id, :basin_name, :dam_name, :fullness, :ingestion_id, NOW()
            )
            ON CONFLICT (dam_id, date_time) DO UPDATE SET
                record_id = EXCLUDED.record_id,
                basin_name = EXCLUDED.basin_name,
                dam_name = EXCLUDED.dam_name,
                active_fullness_percent = EXCLUDED.active_fullness_percent,
                ingestion_id = EXCLUDED.ingestion_id,
                updated_at = NOW();
        """)
        data = [{
            "dam_id": r.get("damId") or r.get("id", 0),
            "date_time": r.get("date"),
            "record_id": r.get("id"),
            "basin_name": r.get("basin", "Unknown"),
            "dam_name": r.get("dam", "Unknown"),
            "fullness": r.get("activeFullnessAmount", 0),
            "ingestion_id": ingestion_id,
        } for r in records if (r.get("damId") or r.get("id")) and r.get("date")]

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[ACTIVE_FULLNESS] Ingested {len(data)} records for {period_key}.")
        return len(data)

    def ingest_water_energy_provision(self, records: List[Dict[str, Any]], period_key: str = "master_snapshot") -> int:
        """Ingests Dam Water Energy Provision snapshot into raw_master_water_energy_provision."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        if self.is_already_ingested("water_energy_provision", checksum):
            logger.info(f"[WATER_ENERGY_PROVISION] Period {period_key} already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("water_energy_provision", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_master_water_energy_provision (
                date_time, dam_name, basin_name, water_energy_provision_mwh, ingestion_id, updated_at
            ) VALUES (
                :date_time, :dam_name, :basin_name, :provision, :ingestion_id, NOW()
            )
            ON CONFLICT (dam_name, date_time) DO UPDATE SET
                basin_name = EXCLUDED.basin_name,
                water_energy_provision_mwh = EXCLUDED.water_energy_provision_mwh,
                ingestion_id = EXCLUDED.ingestion_id,
                updated_at = NOW();
        """)
        data = []
        for r in records:
            dt = r.get("date") or r.get("Tarih") or r.get("tarih") or r.get("Date")
            d_name = r.get("damName") or r.get("Baraj Adı") or r.get("dam_name") or r.get("Dam Name")
            b_name = r.get("basinName") or r.get("Havza Adı") or r.get("basin_name") or r.get("Basin Name")
            prov = r.get("waterEnergyProvision") or r.get("Su Enerji Karşılığı (MWh)") or r.get("provision", 0)
            if d_name and dt:
                data.append({
                    "date_time": dt,
                    "dam_name": str(d_name).strip(),
                    "basin_name": str(b_name).strip() if b_name else None,
                    "provision": prov,
                    "ingestion_id": ingestion_id,
                })

        if data:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data)
            logger.info(f"[WATER_ENERGY_PROVISION] Ingested {len(data)} records for {period_key}.")
        return len(data)
