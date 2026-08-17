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

-- -----------------------------------------------------------------------------
-- 3. GOLD LAYER TABLES
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.ptf_predictions_daily (
    target_ts TIMESTAMPTZ,
    predicted_mcp_usd NUMERIC(10, 4),
    predicted_mcp_try NUMERIC(10, 4),
    predicted_mcp_usd_p10 NUMERIC(10, 4),
    predicted_mcp_try_p10 NUMERIC(10, 4),
    predicted_mcp_usd_p90 NUMERIC(10, 4),
    predicted_mcp_try_p90 NUMERIC(10, 4),
    model_name VARCHAR(50) DEFAULT 'LightGBM_v1',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (target_ts, model_name)
);

CREATE TABLE IF NOT EXISTS gold.kgup_load_pre_forecasts (
    target_ts TIMESTAMPTZ PRIMARY KEY,
    predicted_load_lag0 NUMERIC(10, 4),
    predicted_solar_lag0 NUMERIC(10, 4),
    predicted_wind_lag0 NUMERIC(10, 4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gold_predictions_target_ts ON gold.ptf_predictions_daily(target_ts);


-- -----------------------------------------------------------------------------
-- 4. BRONZE KATMANI (HABER ARŞİVİ) — Kriz & Olay İstihbarat Sistemi
--    Bkz. CRISIS_ANALYSIS_PLAN.md. Bu katman HAM'dır ve değiştirilmez:
--    türetilmiş her şey (alaka filtresi, LLM etiketleri) silver/gold'a yazılır.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.news_raw (
    article_id   BIGINT PRIMARY KEY,           -- URL'deki sıralı ID: ...-41334h.htm -> 41334
    url          TEXT NOT NULL UNIQUE,
    source       VARCHAR(50) NOT NULL DEFAULT 'enerjigunlugu',
    published_at TIMESTAMPTZ NOT NULL,         -- itemprop=datePublished — YETKİLİ yayın anı
    modified_at  TIMESTAMPTZ,                  -- itemprop=dateModified
    section      VARCHAR(100),                 -- itemprop=articleSection (Elektrik/Doğalgaz/Mevzuat/...)
    title        TEXT NOT NULL,                -- itemprop=headline
    description  TEXT,                         -- itemprop=description (spot)
    body         TEXT NOT NULL,                -- itemprop=articleBody, boşluk normalize
    body_chars   INT NOT NULL,
    keywords     TEXT[],                       -- itemprop=keywords — editör etiketleri, kural filtresini besler
    author       VARCHAR(200),
    content_hash CHAR(64) NOT NULL,            -- SHA-256(title|body) — mükerrer içerik tespiti
    http_status  SMALLINT,
    fetched_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_published_at ON bronze.news_raw(published_at);
CREATE INDEX IF NOT EXISTS idx_news_section      ON bronze.news_raw(section);
CREATE INDEX IF NOT EXISTS idx_news_hash         ON bronze.news_raw(content_hash);
CREATE INDEX IF NOT EXISTS idx_news_keywords     ON bronze.news_raw USING GIN(keywords);
-- Tam metin arama: LLM hiç çalışmasa bile anahtar kelimeyle vaka çalışması yapılabilsin.
-- 'simple' konfigürasyonu bilinçli: PostgreSQL'de Türkçe stemmer yok, yanlış kök bulmaktansa hiç bulma.
CREATE INDEX IF NOT EXISTS idx_news_fts ON bronze.news_raw
    USING GIN(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(body,'')));

-- Başarısız çekimler: hedefli yeniden deneme için. Başarılı çekimde satır silinir.
CREATE TABLE IF NOT EXISTS bronze.news_fetch_errors (
    url         TEXT PRIMARY KEY,
    article_id  BIGINT,
    http_status SMALLINT,
    error       TEXT,
    attempts    INT DEFAULT 1,
    last_try_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 5. SILVER: RESMÎ AZAMİ FİYAT LİMİTİ (TAVAN) SERİSİ
--    Kaynak: EPİAŞ/EPDK duyurularının haber arşivindeki karşılıkları
--    (bronze.news_raw). Her satırın provenance'ı var.
--
--    NEDEN GEREKLİ: Tavan daha önce aylık maksimumdan İSTATİSTİKLE çıkarılıyordu.
--    O yöntem 23 ayda birebir tuttu ama iki yerde sessizce yanlıştı:
--      (a) tavan ay ortasında değişebiliyor (2021-10-15, 2022-05-19,
--          2025-04-05, 2026-04-04) — aylık maksimum düşük olanı hiç görmüyor;
--      (b) fiyat tavana hiç değmediği aylarda maksimum tavan DEĞİL
--          (Şubat 2021: resmî 572, veri maksimumu 335).
--    Analiz modeli sansürsüz saatlerde eğitileceği için doğru maske şart.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.price_cap_official (
    effective_from    DATE PRIMARY KEY,        -- yürürlük başlangıcı (dahil)
    cap_try           NUMERIC(12,2) NOT NULL,  -- TL/MWh, GÖP ve DGP'ye birlikte uygulanır
    source_article_id BIGINT,                  -- bronze.news_raw provenance
    note              TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Herhangi bir saat için geçerli tavan + tavanda mı bayrağı.
-- Analiz modelinin eğitim maskesi bu görünümden gelir.
CREATE OR REPLACE VIEW silver.mcp_with_cap AS
SELECT m.ts, m.price_try, m.price_usd,
       c.cap_try, c.effective_from AS cap_effective_from,
       (c.cap_try IS NOT NULL AND m.price_try >= c.cap_try * 0.999) AS at_cap
FROM public.raw_mcp_hourly m
LEFT JOIN LATERAL (
    SELECT p.cap_try, p.effective_from FROM silver.price_cap_official p
    WHERE p.effective_from <= (m.ts AT TIME ZONE 'Europe/Istanbul')::date
    ORDER BY p.effective_from DESC LIMIT 1
) c ON TRUE;

-- Resmî tavan serisi — haber arşivinden derlendi, 67 ayın 67'sinde doğrulandı.
-- Yeniden derlemek için: CRISIS_CASE_IRAN_2022.md §3.2b
INSERT INTO silver.price_cap_official (effective_from, cap_try, source_article_id, note) VALUES
    ('2021-02-01', 572, 41077, NULL),
    ('2021-03-01', 569, 41563, NULL),
    ('2021-04-01', 567, 42050, NULL),
    ('2021-05-01', 578, 42445, 'haber "11 TL arttı" diyor: 567+11'),
    ('2021-06-01', 595, 42974, NULL),
    ('2021-07-01', 617, 43403, NULL),
    ('2021-08-01', 636, 43863, NULL),
    ('2021-09-01', 674, 44243, NULL),
    ('2021-10-01', 718, 44641, NULL),
    ('2021-10-15', 1078, 44932, 'AY ORTASI değişiklik; haber 728 TL diyor ama 44641 Ekim tavanını 718 vermişti'),
    ('2021-11-01', 1131, 45102, NULL),
    ('2021-12-01', 1217, 45589, NULL),
    ('2022-01-01', 1345, 46117, NULL),
    ('2022-02-01', 1524, 46596, NULL),
    ('2022-03-01', 1745, 47113, NULL),
    ('2022-04-01', 2500, 47685, 'kaynak bazlı teklif tavanı: gaz/ithal kömür 2,5 TL/kWh, diğer 1,2 TL/kWh. PTF tek fiyat olduğu için etkin tavan 2500; veride 1200 kümesi YOK (doğrulandı)'),
    ('2022-05-19', 2750, 48414, 'AY ORTASI değişiklik'),
    ('2022-06-01', 3200, 48558, NULL),
    ('2022-07-01', 3750, 49021, NULL),
    ('2022-08-01', 4000, 49427, NULL),
    ('2022-09-01', 4800, 49974, NULL),
    ('2023-01-01', 4200, 52175, NULL),
    ('2023-02-01', 3650, 52617, 'EPDK 26 Ocak 2023 duyurusu: 4.200 -> 3.650, Subat''tan itibaren. Kacirilmis DUSUS: fiyat tavani asmadigi icin oz-test bunu yakalamiyordu.'),
    ('2023-03-01', 3050, 53075, NULL),
    ('2023-04-01', 2600, 53499, NULL),
    ('2023-07-04', 2700, 54712, 'EPDK kararı, haber 2023-07-04'),
    ('2024-07-01', 3000, 59281, NULL),
    ('2025-04-05', 3400, 62872, 'AY ORTASI değişiklik'),
    ('2026-04-04', 4500, 67710, 'AY ORTASI değişiklik, +%32,4')
ON CONFLICT (effective_from) DO NOTHING;
