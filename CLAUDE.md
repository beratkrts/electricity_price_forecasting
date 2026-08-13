# CLAUDE.md - Enerji Fiyat Tahmini Projesi

## Proje Özeti

Türkiye elektrik piyasası (EPİAŞ) Gün Öncesi Piyasa Takas Fiyatı (PTF/MCP) tahmini için uçtan uca AI/ML pipeline'ı.
Her gün saat 04:00'te (Europe/Istanbul) 14+ veri kaynağından veri çeker, LightGBM ile yarının 24 saatlik fiyatını tahmin eder ve React dashboard üzerinden sunar.

## Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| ML Model | LightGBM 3-head quantile (P10, P50, P90) — log1p KULLANMAZ |
| Backend API | FastAPI (port 8000) |
| Frontend | React 18 + Vite + TypeScript + ECharts |
| Veritabanı | PostgreSQL 15 (Medallion: Bronze/Silver/Gold) |
| Altyapı | Docker Compose (3 servis: db, app, dashboard) |
| Zamanlayıcı | Python daemon (60s polling, 04:00 tetikleme) |

## Proje Dizin Yapısı

```
enerji_fiyat_tahmini/
├── scripts/                    # Canlı pipeline scriptleri
│   ├── start.sh                # Docker CMD entrypoint (API + ETL daemon)
│   ├── run_service.py          # 24/7 daemon, 04:00 tetikleyici
│   ├── daily_update_pipeline.py # 14-adım ETL orchestrator
│   ├── predict_daily_pipeline.py # LightGBM eğitim + tahmin + DB yazma
│   ├── fetch_epias_data.py     # EPİAŞ/OpenMeteo/yfinance veri çekme
│   ├── api_server.py           # FastAPI backend (/api/db-data, /api/fx)
│   ├── backfill_gold_predictions.py  # İlk kurulumda 2 yıl tahmin geçmişi
│   ├── backfill_pre_forecasts.py     # İlk kurulumda pre-forecast geçmişi
│   ├── run_*_backtest.py       # [DENEYSEL] Çeşitli backtest scriptleri
│   └── fast_cqr_update.py      # [DENEYSEL] CQR kalibrasyon güncellemesi
│
├── src/
│   ├── models/
│   │   ├── lightgbm_model.py   # LightGBMForecaster sınıfı (canlı)
│   │   ├── epnet.py            # [DENEYSEL] CNN+LSTM/GRU/BiLSTM modelleri
│   │   └── cqr_calibrator.py   # [DENEYSEL] Conformalized Quantile Regression
│   ├── features/
│   │   ├── feature_engineering.py  # 65+ feature (base/core/full/robust)
│   │   ├── pre_forecasters.py  # Yük/Güneş/Rüzgar alt-modelleri
│   │   └── holidays.py         # Türkiye resmi tatilleri
│   ├── routing/
│   │   ├── model_router.py     # [DENEYSEL] Rejim bazlı model yönlendirme
│   │   └── regime_detector.py  # [DENEYSEL] NORMAL/CRASH/VOLATILE rejim tespiti
│   └── utils/
│       └── fallback_logger.py  # Fallback log yardımcısı
│
├── db/
│   ├── connection.py           # SQLAlchemy engine factory + checksum
│   ├── ingest_epias.py         # EpiasDBIngestor (SHA-256, ON CONFLICT upsert)
│   └── sql/
│       └── 01_init_schema.sql  # PostgreSQL şema (Bronze/Silver/Gold)
│
├── app/frontend/               # React dashboard
│   ├── src/
│   │   ├── App.tsx             # Ana uygulama (state yönetimi, routing)
│   │   ├── pages/              # Home, Forecast, Analysis sayfaları
│   │   ├── components/         # Chart, MetricCards, Header, CurrencyTicker
│   │   ├── services/           # API çağrıları (energyDataService, fxService)
│   │   └── types/              # TypeScript tipleri
│   ├── package.json
│   ├── vite.config.ts
│   └── nginx.conf              # Production reverse proxy
│
├── config/
│   ├── city_coordinates.json   # 26 bölge koordinatları + tüketim ağırlıkları
│   └── city_percentages.json   # 81 il elektrik tüketim yüzdeleri
│
├── eda/                        # [GIT-DIŞI] Notebook'lar ve EDA scriptleri
├── data/                       # [GIT-DIŞI] Ham JSON verileri (2024-01 ~ 2024-08)
├── logs/                       # [GIT-DIŞI] daily_update.log, anomalies.log
├── docs/                       # [GIT-DIŞI] Proje dokümanları
│
├── docker-compose.yml          # 3 servis: db, app, dashboard
├── Dockerfile                  # Python 3.11-slim + PyTorch CPU
├── requirements.txt            # Python bağımlılıkları
└── .env                        # [GIT-DIŞI] EPİAŞ ve PostgreSQL credentials
```

## Canlı Pipeline Akışı (Production)

```
04:00 Europe/Istanbul (run_service.py daemon)
    │
    ▼
daily_update_pipeline.py
    │
    ├── 1-13. EPİAŞ API → Bronze audit + Silver upsert
    │   (MCP, SMP, KGÜP, Load, ActGen, ActCons, Bids,
    │    Licensed, Capacity, Dam, Gas, Weather, Macro)
    │
    ├── 14. Macro (yfinance: USD/TRY, Brent Oil)
    │
    ├── 15. Tomorrow's weather forecast (Open-Meteo)
    │
    └── 16. predict_daily_pipeline.py
            │
            ├── Tüm geçmiş veri yükle (2024-01-01+)
            ├── Pre-forecasters güncelle (son 3 gün)
            ├── build_robust_features() (65+ feature)
            ├── 3x LightGBM eğit (P10, P50, P90)
            ├── Yarının 24h placeholder'ını oluştur
            ├── Hava durumu + pre-forecast enjekte et
            ├── Feature pipeline çalıştır (aynı pipeline)
            ├── 3 model ile tahmin üret
            ├── Quantile crossover koruması (P10≤P50≤P90)
            ├── USD→TRY dönüşümü (4-aşamalı resolver)
            └── gold.ptf_predictions_daily upsert
```

## Veritabanı Katmanları (Medallion Architecture)

| Katman | Tablolar | Amaç |
|--------|----------|------|
| Bronze | `ingestion_batches` | SHA-256 audit trail, duplicate prevention |
| Silver | `raw_mcp_hourly`, `raw_smp_hourly`, `raw_kgup_hourly`, `raw_load_forecast_hourly`, `raw_actual_generation_hourly`, `raw_actual_consumption_hourly`, `raw_weather_hourly`, `raw_weather_forecast_hourly`, `raw_macro_daily`, `raw_natural_gas_daily`, `raw_bids_offers_hourly`, `raw_master_water_energy_provision`, `raw_wind_history_hourly` | Normalize saatlik/günlük zaman serileri |
| Gold | `gold.ptf_predictions_daily`, `gold.kgup_load_pre_forecasts` | ML tahminleri + pre-forecast sonuçları |

## API Endpoints

### `GET /api/db-data`
| Parametre | Açıklama |
|-----------|----------|
| `date` | `latest`, `today`, `7d`, `1m`, `3m`, `6m`, `1y`, `2y`, `YYYY-MM-DD`, `YYYY-MM-DD_to_YYYY-MM-DD` |
| `type` | `next_day_forecast`, `prediction_bounds`, `performance`, `today_performance`, `range_performance`, `mcp`, `smp`, `kgup`, `load_forecast`, `actual_generation`, `lightgbm` |
| `group_by` | `hour` (default), `day`, `month` |

### `GET /api/fx`
USD/TRY ve EUR/TRY döviz kurları (3 kademeli fallback: ExchangeRate-API → Yahoo Finance → DB cache, 5dk cache)

## Feature Hiyerarşisi

| Set | Feature Sayısı | Açıklama |
|-----|----------------|----------|
| BASE | ~13 | Takvim + tatil + fiyat lag/rolling |
| CORE | ~35 | + Yük/KGÜP lagları, arz-talep, yenilenebilir oranları |
| FULL | ~39 | + Gerçekleşen üretim/tüketim lagları |
| ROBUST | ~65+ | + Cyclic encoding, baskı oranları, rejim flag'leri, CDH/HDH, pre-forecast lag0, ramp rate, risk skoru |

**Canlıda `build_robust_features()` kullanılır.** Target: `mcp_price_usd` (USD/MWh)

## Veri Kaynakları

| Kaynak | API | Frekans | Veri |
|--------|-----|---------|------|
| EPİAŞ EPTR2 | `eptr2` lib | Saatlik | MCP, SMP, KGÜP, Load, ActGen, ActCons, Bids |
| EPİAŞ Custom | REST | Günlük | Dam fullness, Water energy, Natural gas GRF |
| Open-Meteo | REST | Saatlik | Ağırlıklı sıcaklık (26 bölge), rüzgar hızı (3 şehir) |
| Yahoo Finance | `yfinance` | Günlük | USD/TRY, Brent Oil |

## Geliştirme Komutları

```bash
# Backend (API + ETL)
cd /Users/beratkaratasoglu/etkb_intern_project/enerji_fiyat_tahmini
python scripts/api_server.py          # API sunucusu (port 8000)
python scripts/run_service.py         # Daemon servisi (ETL + tahmin)
python scripts/predict_daily_pipeline.py  # Manuel tahmin çalıştır

# Frontend
cd app/frontend
npm install && npm run dev            # Dev server (port 3000)
npm run build                         # Production build

# Docker (tam deployment)
docker compose up --build -d
```

## Önemli Notlar

- **Timezone:** Tüm zaman damgaları `Europe/Istanbul` (UTC+3). `DatetimeIndex` + `tz_localize/convert` zorunlu.
- **Data leakage koruması:** Tüm lag'lar shift(24/48/168) ile. Exogenous değişkenler 48h gecikmeli.
- **Quantile crossover:** P10 ≤ P50 ≤ P90 monotonic garanti her zaman uygulanır.
- **İlk deployment:** `gold.ptf_predictions_daily < 1000 satır` ise otomatik 730 gün backfill tetiklenir.
- **USD/TRY resolver:** 4 aşamalı: df_raw → yfinance API → DB query → ECB API fallback.
- **Model her gün sıfırdan eğitilir** (tüm geçmiş veri ile). Disk'e kaydedilmez.

## Canlıda KULLANILMAYAN (Deneysel) Modüller

| Modül | Durum | Açıklama |
|-------|-------|----------|
| `src/models/epnet.py` | Deneysel | CNN+LSTM/GRU/BiLSTM neural network. Backtest'lerde test edildi, canlıya alınmadı. |
| `src/models/cqr_calibrator.py` | Deneysel | CQR kalibratörü. P10/P90 bounds LightGBM'in native quantile'ı ile üretiliyor. |
| `src/routing/model_router.py` | Deneysel | Rejim bazlı EPNet/LightGBM ensemble. Canlıda sadece LightGBM kullanılıyor. |
| `src/routing/regime_detector.py` | Deneysel | NORMAL/CRASH/VOLATILE piyasa rejim tespiti. Canlıya entegre değil. |
| `scripts/run_*_backtest.py` | Deneysel | Çeşitli backtest senaryoları. |
| `scripts/fast_cqr_update.py` | Deneysel | CQR model güncelleme scripti. |
| `scripts/backfill_*_experimental*.py` | Deneysel | Deneysel tahmin backfill scriptleri. |

## Dokümantasyon

| Dosya | İçerik |
|-------|--------|
| `CLAUDE.md` | Bu dosya — proje rehberi |
| `ISSUES.md` | Tespit edilen sorunlar ve iyileştirme önerileri |
| `EXPERIMENT_REPORT.md` | Tüm model deneylerinin sonuç tabloları ve karşılaştırması |
| `EXPERIMENT_WORKFLOW.md` | Sistematik deney çalışma rehberi ve repo temizleme planı |

## Model Versiyonları

| Model | Durum | Fark |
|-------|-------|------|
| **LightGBM_v1** | CANLI (`gold.ptf_predictions_daily`) | Quantile P10/P50/P90, robust features, min_child=20 |
| **lgb_lag0_v2** | Deneysel (`gold.ptf_predictions_experimental`) | + lag0 renewable ratios, min_child=10 |
| **lgb_cqr_v2** | Deneysel (`gold.ptf_predictions_experimental`) | lgb_lag0_v2 + CQR kalibre güven aralığı |
| Eski Log1p | Kaldırıldı | Notebook benchmark'larının çoğu buna ait |

**Not:** Notebook'lardaki WAPE %16.53, MAE $8.44 değerleri **eski log1p modele** aittir, canlıdaki quantile modele değil.
