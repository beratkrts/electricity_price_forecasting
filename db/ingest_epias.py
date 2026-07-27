import os
import json
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from db.connection import get_db_url, calculate_checksum

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DB_Ingestion")

class EpiasDBIngestor:
    def __init__(self, db_url=None):
        self.db_url = db_url or get_db_url()
        self.engine = create_engine(self.db_url, pool_pre_ping=True)

    def init_db(self, schema_file="sql/01_init_schema.sql"):
        """Executes the SQL schema file to create tables if they do not exist."""
        if os.path.exists(schema_file):
            logger.info(f"Initializing database schema from {schema_file}...")
            with open(schema_file, "r", encoding="utf-8") as f:
                sql_script = f.read()
            with self.engine.begin() as conn:
                conn.execute(text(sql_script))
            logger.info("Database schema initialized successfully.")
        else:
            logger.warning(f"Schema file {schema_file} not found!")

    def is_already_ingested(self, source_name, checksum):
        """Checks if an API payload batch with the exact checksum was already ingested into Bronze layer."""
        query = text("""
            SELECT id FROM ingestion_batches 
            WHERE source_name = :source_name AND checksum = :checksum AND status = 'SUCCESS'
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"source_name": source_name, "checksum": checksum}).fetchone()
            return result[0] if result else None

    def record_ingestion_batch(self, source_name, period_key, checksum, row_count, status="SUCCESS", error_msg=None):
        """Inserts or updates an audit record in ingestion_batches (1. Katman / Bronze API Batch Track)."""
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
                "error_msg": error_msg
            }).fetchone()
            return result[0]

    # -------------------------------------------------------------------------
    # 2. KATMAN (SILVER) API ETL AKTARIM METOTLARI
    # -------------------------------------------------------------------------

    def ingest_mcp(self, records, period_key):
        """Ingests PTF (MCP) API records directly into raw_mcp_hourly after ETL."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("mcp", checksum)
        if existing_id:
            logger.info(f"[MCP] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = [{
            "ts": r.get("date"),
            "price_try": r.get("price"),
            "price_usd": r.get("priceUsd"),
            "price_eur": r.get("priceEur"),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[MCP] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_smp(self, records, period_key):
        """Ingests SMF (SMP) API records directly into raw_smp_hourly after ETL."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("smp", checksum)
        if existing_id:
            logger.info(f"[SMP] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("smp", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_smp_hourly (ts, system_marginal_price_try, ingestion_id)
            VALUES (:ts, :smp, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                system_marginal_price_try = EXCLUDED.system_marginal_price_try,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data_to_insert = [{
            "ts": r.get("date"),
            "smp": r.get("systemMarginalPrice"),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[SMP] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_load_forecast(self, records, period_key):
        """Ingests Yük Tahmini (LEP) API records directly into raw_load_forecast_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("load_forecast", checksum)
        if existing_id:
            logger.info(f"[LOAD_FORECAST] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("load_forecast", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_load_forecast_hourly (ts, load_forecast_mw, ingestion_id)
            VALUES (:ts, :lep, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                load_forecast_mw = EXCLUDED.load_forecast_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data_to_insert = [{
            "ts": r.get("date"),
            "lep": r.get("lep"),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[LOAD_FORECAST] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_kgup(self, records, period_key):
        """Ingests Kesinleşmiş Gün Öncesi Üretim Planı (KGÜP) API records directly into raw_kgup_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("kgup", checksum)
        if existing_id:
            logger.info(f"[KGUP] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("kgup", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_kgup_hourly (
                ts, total_mw, natural_gas_mw, wind_mw, lignite_mw, black_coal_mw,
                import_coal_mw, fuel_oil_mw, geothermal_mw, dammed_hydro_mw,
                river_hydro_mw, naphtha_mw, biomass_mw, solar_mw, other_mw, ingestion_id
            ) VALUES (
                :ts, :toplam, :dogalgaz, :ruzgar, :linyit, :tasKomur,
                :ithalKomur, :fuelOil, :jeotermal, :barajli,
                :akarsu, :nafta, :biokutle, :gunes, :diger, :ingestion_id
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
        data_to_insert = [{
            "ts": r.get("date"),
            "toplam": r.get("toplam", 0),
            "dogalgaz": r.get("dogalgaz", 0),
            "ruzgar": r.get("ruzgar", 0),
            "linyit": r.get("linyit", 0),
            "tasKomur": r.get("tasKomur", 0),
            "ithalKomur": r.get("ithalKomur", 0),
            "fuelOil": r.get("fuelOil", 0),
            "jeotermal": r.get("jeotermal", 0),
            "barajli": r.get("barajli", 0),
            "akarsu": r.get("akarsu", 0),
            "nafta": r.get("nafta", 0),
            "biokutle": r.get("biokutle", 0),
            "gunes": r.get("gunes", 0),
            "diger": r.get("diger", 0),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[KGUP] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_actual_generation(self, records, period_key):
        """Ingests Gerçekleşen Üretim API records directly into raw_actual_generation_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("actual_generation", checksum)
        if existing_id:
            logger.info(f"[ACTUAL_GEN] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("actual_generation", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_actual_generation_hourly (
                ts, total_mw, natural_gas_mw, dammed_hydro_mw, lignite_mw, river_hydro_mw,
                import_coal_mw, wind_mw, solar_mw, fuel_oil_mw, geothermal_mw, asphaltite_coal_mw,
                black_coal_mw, biomass_mw, naphtha_mw, lng_mw, import_export_mw, waste_heat_mw, ingestion_id
            ) VALUES (
                :ts, :total, :naturalGas, :dammedHydro, :lignite, :river,
                :importCoal, :wind, :sun, :fueloil, :geothermal, :asphaltiteCoal,
                :blackCoal, :biomass, :naphta, :lng, :importExport, :wasteheat, :ingestion_id
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
        data_to_insert = [{
            "ts": r.get("date"),
            "total": r.get("total", 0),
            "naturalGas": r.get("naturalGas", 0),
            "dammedHydro": r.get("dammedHydro", 0),
            "lignite": r.get("lignite", 0),
            "river": r.get("river", 0),
            "importCoal": r.get("importCoal", 0),
            "wind": r.get("wind", 0),
            "sun": r.get("sun", 0),
            "fueloil": r.get("fueloil", 0),
            "geothermal": r.get("geothermal", 0),
            "asphaltiteCoal": r.get("asphaltiteCoal", 0),
            "blackCoal": r.get("blackCoal", 0),
            "biomass": r.get("biomass", 0),
            "naphta": r.get("naphta", 0),
            "lng": r.get("lng", 0),
            "importExport": r.get("importExport", 0),
            "wasteheat": r.get("wasteheat", 0),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[ACTUAL_GEN] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_actual_consumption(self, records, period_key):
        """Ingests Gerçekleşen Tüketim API records directly into raw_actual_consumption_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("actual_consumption", checksum)
        if existing_id:
            logger.info(f"[ACTUAL_CONS] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("actual_consumption", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_actual_consumption_hourly (ts, consumption_mw, ingestion_id)
            VALUES (:ts, :consumption, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                consumption_mw = EXCLUDED.consumption_mw,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data_to_insert = [{
            "ts": r.get("date"),
            "consumption": r.get("consumption"),
            "ingestion_id": ingestion_id
        } for r in records]

        with self.engine.begin() as conn:
            conn.execute(insert_query, data_to_insert)
        logger.info(f"[ACTUAL_CONS] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_bids_offers(self, bids_records, offers_records, period_key):
        """Ingests Alış (bids) and Satış (offers) API records directly into raw_bids_offers_hourly."""
        combined = {"bids": bids_records, "offers": offers_records}
        checksum = calculate_checksum(combined)
        existing_id = self.is_already_ingested("bids_offers", checksum)
        if existing_id:
            logger.info(f"[BIDS_OFFERS] {period_key} batch already ingested. Skipping.")
            return 0

        total_rows = max(len(bids_records or []), len(offers_records or []))
        ingestion_id = self.record_ingestion_batch("bids_offers", period_key, checksum, total_rows)

        data_map = {}
        for r in (bids_records or []):
            dt = r.get("date")
            if dt:
                data_map[dt] = {"ts": dt, "bid": r.get("bidQuantity"), "offer": None, "ingestion_id": ingestion_id}
        for r in (offers_records or []):
            dt = r.get("date")
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

        data_to_insert = list(data_map.values())
        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[BIDS_OFFERS] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_macro(self, records, period_key):
        """Ingests Makro Göstergeler (USD/TRY & Brent Oil) directly into raw_macro_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("macro", checksum)
        if existing_id:
            logger.info(f"[MACRO] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = [{
            "entry_date": r.get("date") or r.get("Date"),
            "usd_try": r.get("usd_try") or r.get("USDTRY=X"),
            "brent_oil_usd": r.get("brent_oil_usd") or r.get("BZ=F"),
            "ingestion_id": ingestion_id
        } for r in records if (r.get("date") or r.get("Date"))]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[MACRO] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_natural_gas_daily(self, records, period_key):
        """Ingests Doğalgaz Günlük Referans Fiyatı (GRF) directly into raw_natural_gas_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("natural_gas_daily", checksum)
        if existing_id:
            logger.info(f"[NATURAL_GAS] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = [{
            "entry_date": r.get("date") or r.get("gas_date"),
            "grf_try": r.get("grfTl") or r.get("price") or r.get("grf_price_try"),
            "grf_usd": r.get("grfUsd"),
            "grf_eur": r.get("grfEur"),
            "ingestion_id": ingestion_id
        } for r in records if (r.get("date") or r.get("gas_date"))]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[NATURAL_GAS] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_licensed_realtime_generation(self, records, period_key):
        """Ingests Lisanslı Gerçekleşen Üretim API records directly into raw_licensed_realtime_generation_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("licensed_realtime_generation", checksum)
        if existing_id:
            logger.info(f"[LICENSED_GEN] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = [{
            "ts": r.get("date") or r.get("hour"),
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
            "ingestion_id": ingestion_id
        } for r in records if (r.get("date") or r.get("hour"))]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[LICENSED_GEN] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_installed_capacity(self, records, period_key):
        """Ingests Kurulu Güç API records directly into raw_installed_capacity_daily."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("installed_capacity", checksum)
        if existing_id:
            logger.info(f"[INSTALLED_CAPACITY] {period_key} batch already ingested. Skipping.")
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
        
        data_to_insert = [{
            "period_date": p_date,
            "energy_type": r.get("renewableEnergyType") or r.get("type", "Unknown"),
            "licensed": r.get("licencedCapacity", 0),
            "unlicensed": r.get("unlicencedCapacity", 0),
            "total": r.get("total", 0),
            "ingestion_id": ingestion_id
        } for r in records if (r.get("renewableEnergyType") or r.get("type"))]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[INSTALLED_CAPACITY] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_weather(self, records, period_key):
        """Ingests Türkiye Ağırlıklı Sıcaklık (Open-Meteo) directly into raw_weather_hourly."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("weather", checksum)
        if existing_id:
            logger.info(f"[WEATHER] {period_key} batch already ingested. Skipping.")
            return 0

        ingestion_id = self.record_ingestion_batch("weather", period_key, checksum, len(records))
        insert_query = text("""
            INSERT INTO raw_weather_hourly (ts, turkey_weighted_temperature_c, ingestion_id)
            VALUES (:ts, :temp, :ingestion_id)
            ON CONFLICT (ts) DO UPDATE SET
                turkey_weighted_temperature_c = EXCLUDED.turkey_weighted_temperature_c,
                ingestion_id = EXCLUDED.ingestion_id;
        """)
        data_to_insert = [{
            "ts": r.get("date_time") or r.get("date") or r.get("time"),
            "temp": r.get("turkey_weighted_temperature_c") or r.get("temp"),
            "ingestion_id": ingestion_id
        } for r in records if (r.get("date_time") or r.get("date") or r.get("time"))]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[WEATHER] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records for {period_key}.")
        return len(data_to_insert)

    def ingest_active_fullness(self, records, period_key="master_snapshot"):
        """Ingests Baraj Aktif Doluluk Oranları (Master Snapshot) directly into raw_master_active_fullness."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("active_fullness", checksum)
        if existing_id:
            logger.info(f"[ACTIVE_FULLNESS] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = [{
            "dam_id": r.get("damId") or r.get("id", 0),
            "date_time": r.get("date"),
            "record_id": r.get("id"),
            "basin_name": r.get("basin", "Unknown"),
            "dam_name": r.get("dam", "Unknown"),
            "fullness": r.get("activeFullnessAmount", 0),
            "ingestion_id": ingestion_id
        } for r in records if (r.get("damId") or r.get("id")) and r.get("date")]

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[ACTIVE_FULLNESS] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records.")
        return len(data_to_insert)

    def ingest_water_energy_provision(self, records, period_key="master_snapshot"):
        """Ingests Baraj Su Enerji Karşılığı (Master Snapshot) directly into raw_master_water_energy_provision."""
        if not records:
            return 0
        checksum = calculate_checksum(records)
        existing_id = self.is_already_ingested("water_energy_provision", checksum)
        if existing_id:
            logger.info(f"[WATER_ENERGY_PROVISION] {period_key} batch already ingested. Skipping.")
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
        data_to_insert = []
        for r in records:
            dt = r.get("date") or r.get("Tarih") or r.get("tarih") or r.get("Date")
            d_name = r.get("damName") or r.get("Baraj Adı") or r.get("dam_name") or r.get("Dam Name")
            b_name = r.get("basinName") or r.get("Havza Adı") or r.get("basin_name") or r.get("Basin Name")
            prov = r.get("waterEnergyProvision") or r.get("Su Enerji Karşılığı (MWh)") or r.get("provision", 0)
            if d_name and dt:
                data_to_insert.append({
                    "date_time": dt,
                    "dam_name": str(d_name).strip(),
                    "basin_name": str(b_name).strip() if b_name else None,
                    "provision": prov,
                    "ingestion_id": ingestion_id
                })

        if data_to_insert:
            with self.engine.begin() as conn:
                conn.execute(insert_query, data_to_insert)
            logger.info(f"[WATER_ENERGY_PROVISION] ETL Direct API Ingest: Inserted/Updated {len(data_to_insert)} records.")
        return len(data_to_insert)
