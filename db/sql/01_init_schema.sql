-- =============================================================================
-- ENERJİ FİYAT TAHMİNİ PROJESİ - POSTGRESQL VERİ TABANI BAŞLANGIÇ ŞEMASI (01_init_schema.sql)
-- Katmanlar: Bronze (API Ingestion & Audit Track) & Silver (Normalized Time Series)
-- =============================================================================

SET timezone = 'Europe/Istanbul';

-- -----------------------------------------------------------------------------
-- 1. BRONZE KATMANI: API ETL Ingestion Audit & Checksum Takip Tablosu
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_batches (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,    -- Örn: 'mcp', 'smp', 'actual_generation', 'macro'
    period_key VARCHAR(50) NOT NULL,      -- Örn: '2026-07' veya '2026-07-27'
    checksum VARCHAR(64) NOT NULL,        -- EPİAŞ API'sinden gelen bellekteki verinin SHA-256 dijital imzası
    row_count INT DEFAULT 0,              -- Çekilen ve işlenen toplam kayıt sayısı
    status VARCHAR(20) DEFAULT 'SUCCESS', -- 'SUCCESS', 'FAILED', 'SKIPPED'
    error_message TEXT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_source_checksum UNIQUE (source_name, checksum)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_source_period ON ingestion_batches(source_name, period_key);

-- -----------------------------------------------------------------------------
-- 2. SILVER KATMANI: Saatlik / Günlük Ham Zaman Serisi Tabloları
-- -----------------------------------------------------------------------------

-- 2.1 Piyasa Takas Fiyatı (PTF - MCP)
CREATE TABLE IF NOT EXISTS raw_mcp_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    price_try NUMERIC(12, 4),
    price_usd NUMERIC(12, 4),
    price_eur NUMERIC(12, 4),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.2 Sistem Marjinal Fiyatı (SMF - SMP)
CREATE TABLE IF NOT EXISTS raw_smp_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    system_marginal_price_try NUMERIC(12, 4),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.3 Yük Tahmini (LEP)
CREATE TABLE IF NOT EXISTS raw_load_forecast_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    load_forecast_mw NUMERIC(12, 2),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.4 Kesinleşmiş Gün Öncesi Üretim Planı (KGÜP)
CREATE TABLE IF NOT EXISTS raw_kgup_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    total_mw NUMERIC(12, 2),
    natural_gas_mw NUMERIC(12, 2) DEFAULT 0,
    wind_mw NUMERIC(12, 2) DEFAULT 0,
    lignite_mw NUMERIC(12, 2) DEFAULT 0,
    black_coal_mw NUMERIC(12, 2) DEFAULT 0,
    import_coal_mw NUMERIC(12, 2) DEFAULT 0,
    fuel_oil_mw NUMERIC(12, 2) DEFAULT 0,
    geothermal_mw NUMERIC(12, 2) DEFAULT 0,
    dammed_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    river_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    naphtha_mw NUMERIC(12, 2) DEFAULT 0,
    biomass_mw NUMERIC(12, 2) DEFAULT 0,
    solar_mw NUMERIC(12, 2) DEFAULT 0,
    other_mw NUMERIC(12, 2) DEFAULT 0,
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.5 Gerçekleşen Üretim (Kaynak Bazlı)
CREATE TABLE IF NOT EXISTS raw_actual_generation_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    total_mw NUMERIC(12, 2),
    natural_gas_mw NUMERIC(12, 2) DEFAULT 0,
    dammed_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    lignite_mw NUMERIC(12, 2) DEFAULT 0,
    river_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    import_coal_mw NUMERIC(12, 2) DEFAULT 0,
    wind_mw NUMERIC(12, 2) DEFAULT 0,
    solar_mw NUMERIC(12, 2) DEFAULT 0,
    fuel_oil_mw NUMERIC(12, 2) DEFAULT 0,
    geothermal_mw NUMERIC(12, 2) DEFAULT 0,
    asphaltite_coal_mw NUMERIC(12, 2) DEFAULT 0,
    black_coal_mw NUMERIC(12, 2) DEFAULT 0,
    biomass_mw NUMERIC(12, 2) DEFAULT 0,
    naphtha_mw NUMERIC(12, 2) DEFAULT 0,
    lng_mw NUMERIC(12, 2) DEFAULT 0,
    import_export_mw NUMERIC(12, 2) DEFAULT 0,
    waste_heat_mw NUMERIC(12, 2) DEFAULT 0,
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.6 Gerçekleşen Tüketim
CREATE TABLE IF NOT EXISTS raw_actual_consumption_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    consumption_mw NUMERIC(12, 2),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.7 GÖP Alış / Satış Teklif Miktarları
CREATE TABLE IF NOT EXISTS raw_bids_offers_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    bid_quantity_mw NUMERIC(12, 2),
    offer_quantity_mw NUMERIC(12, 2),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.8 Makro Göstergeler (Dolar & Brent Petrol)
CREATE TABLE IF NOT EXISTS raw_macro_daily (
    entry_date DATE PRIMARY KEY,
    usd_try NUMERIC(10, 4),
    brent_oil_usd NUMERIC(10, 4),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.9 Doğalgaz Günlük Referans Fiyatı (GRF)
CREATE TABLE IF NOT EXISTS raw_natural_gas_daily (
    entry_date DATE PRIMARY KEY,
    gas_reference_price_try NUMERIC(12, 4),
    grf_usd NUMERIC(12, 4),
    grf_eur NUMERIC(12, 4),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.10 Lisanslı Gerçekleşen Üretim (Kaynak Bazlı - Yenilenebilir ve Diğer)
CREATE TABLE IF NOT EXISTS raw_licensed_realtime_generation_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    total_mw NUMERIC(12, 2),
    wind_mw NUMERIC(12, 2) DEFAULT 0,
    geothermal_mw NUMERIC(12, 2) DEFAULT 0,
    dammed_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    canal_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    river_hydro_mw NUMERIC(12, 2) DEFAULT 0,
    landfill_gas_mw NUMERIC(12, 2) DEFAULT 0,
    biogas_mw NUMERIC(12, 2) DEFAULT 0,
    solar_mw NUMERIC(12, 2) DEFAULT 0,
    biomass_mw NUMERIC(12, 2) DEFAULT 0,
    other_mw NUMERIC(12, 2) DEFAULT 0,
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.11 Günlük / Periyodik Kurulu Güç Dağılımı
CREATE TABLE IF NOT EXISTS raw_installed_capacity_daily (
    period_date DATE NOT NULL,
    energy_type VARCHAR(50) NOT NULL,
    licensed_capacity_mw NUMERIC(12, 4) DEFAULT 0,
    unlicensed_capacity_mw NUMERIC(12, 4) DEFAULT 0,
    total_capacity_mw NUMERIC(12, 4) DEFAULT 0,
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_installed_capacity PRIMARY KEY (period_date, energy_type)
);

-- 2.12 Türkiye Ağırlıklı Saatlik Sıcaklık (Open-Meteo Gerçekleşen Hava Durumu)
CREATE TABLE IF NOT EXISTS raw_weather_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    turkey_weighted_temperature_c NUMERIC(5, 2),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.12b Türkiye Ağırlıklı Saatlik Sıcaklık Tahminleri (Open-Meteo Weather Forecast)
CREATE TABLE IF NOT EXISTS raw_weather_forecast_hourly (
    ts TIMESTAMPTZ PRIMARY KEY,
    turkey_weighted_temperature_forecast_c NUMERIC(5, 2),
    forecast_run_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2.13 Baraj Aktif Doluluk Oranları (Master Snapshot)
CREATE TABLE IF NOT EXISTS raw_master_active_fullness (
    dam_id INT NOT NULL,
    date_time TIMESTAMPTZ NOT NULL,
    record_id BIGINT,
    basin_name VARCHAR(100) NOT NULL,
    dam_name VARCHAR(100) NOT NULL,
    active_fullness_percent NUMERIC(8, 4) DEFAULT 0,
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_dam_active_fullness PRIMARY KEY (dam_id, date_time)
);

-- 2.14 Baraj Su Enerji Karşılığı (Master Snapshot)
CREATE TABLE IF NOT EXISTS raw_master_water_energy_provision (
    id SERIAL PRIMARY KEY,
    date_time TIMESTAMPTZ,
    dam_name VARCHAR(100) NOT NULL,
    basin_name VARCHAR(100),
    water_energy_provision_mwh NUMERIC(14, 4),
    ingestion_id INT REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_dam_provision_date UNIQUE (dam_name, date_time)
);

-- -----------------------------------------------------------------------------
-- İNDEKS TASARIMLARI
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_mcp_ts ON raw_mcp_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_smp_ts ON raw_smp_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_load_forecast_ts ON raw_load_forecast_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_kgup_ts ON raw_kgup_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_actual_gen_ts ON raw_actual_generation_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_actual_cons_ts ON raw_actual_consumption_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_weather_ts ON raw_weather_hourly(ts);
