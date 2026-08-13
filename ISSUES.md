# Tespit Edilen Sorunlar ve İyileştirme Önerileri

## Kritik Sorunlar

### 1. Veri boşluğu kontrolü çok katı
**Dosya:** `scripts/predict_daily_pipeline.py:229-231`
```python
if last_available_date != target_today_str:
    raise RuntimeError(f"Data gap detected...")
```
- Pipeline 04:00'te çalışıyor. Eğer EPİAŞ API'si gecikirse veya bugünün verileri henüz gelmediyse pipeline tamamen durur.
- `df_model` NaN-drop sonrası son tarih bugünden farklı olabilir (feature NaN'ler yüzünden).
- **Öneri:** Son kullanılabilir tarihe dayalı esnek kontrol. T-1 verisinin yeterliliğini kontrol et.

### 2. SMP TRY/USD karışıklığı
**Dosya:** `scripts/predict_daily_pipeline.py:83` ve `src/features/feature_engineering.py`
- DB'den `smp_price_try` (TRY cinsinden) çekiliyor.
- Feature engineering'de `smp_usd_lag_48` adıyla kullanılıyor ama aslında TRY değeri.
- DB şemasında `raw_smp_hourly` tablosunda sadece `system_marginal_price_try` var, USD karşılığı yok.
- **Not:** Model zaten `smp_price_try` değeriyle eğitildi. Feature adı `smp_usd_lag_48` olsa da model bu sütunu "TRY cinsinden SMP'nin 48 saatlik lag'ı" olarak öğrendi. Sadece ismi düzeltmek (rename) modeli etkilemez ve backfill gerektirmez. Eğer gerçekten USD'ye çevirmek istersek (`smp_try / usd_try`) feature dağılımı değişir ve **backfill + yeniden eğitim gerekir** — bu opsiyonel bir iyileştirme.
- **Öneri (hızlı):** Feature adını `smp_try_lag_48` olarak düzelt (backfill gerektirmez).
- **Öneri (kapsamlı):** SMP'yi USD'ye çevir, backfill yap, model yeniden eğit.

## Orta Seviye Sorunlar

### 3. Frontend'de kullanılmayan model referansları
**Dosya:** `app/frontend/src/types/energy.ts`
- `epnetForecast`, `hybridForecast` tipleri tanımlanmış ama API asla bu verileri dönmüyor.
- `seriesConfigs` içinde EPNet ve Hybrid seçenekleri var ama verisi her zaman 0.
- **Öneri:** Frontend tiplerini ve UI bileşenlerini sadece LightGBM + P10/P90'a sadeleştir.

### 4. Feature engineering'de regime/routing logic kalıntıları
**Dosyalar:** `src/routing/model_router.py`, `src/routing/regime_detector.py`
- Canlıda kullanılmıyor, sadece backtest scriptlerinde referans var.
- Feature engineering'de de regime ile ilgili feature'lar olabilir ama model routing aktif değil.
- **Durum:** CLAUDE.md'de deneysel olarak işaretlendi. Temizlik yapılabilir.

### 5. `run_service.py` duplicate import ve docstring yerleşimi
**Dosya:** `scripts/run_service.py:1,18`
- `import sys` iki kez yazılmış.
- Module docstring sys.path manipülasyonundan sonra, `__doc__` olarak kayıtlanmaz.

## Düşük Seviye / İyileştirme Önerileri

### 6. Log dosyaları rotation yok
**Dosya:** `scripts/daily_update_pipeline.py:38-39`
- `FileHandler` kullanılıyor, `RotatingFileHandler` değil.
- Uzun süre çalışan bir üretim sisteminde log dosyaları büyüyecek.
- **Öneri:** `RotatingFileHandler(maxBytes=10MB, backupCount=5)` kullan.

### 7. FX prevClose sadece Yahoo Finance'den geliyor
**Dosya:** `scripts/api_server.py`, `app/frontend/src/services/fxService.ts:82,86`
- Frontend CurrencyTicker'da günlük % değişim hesabı için `prevClose` kullanılıyor.
- ExchangeRate-API (primary) bu değeri dönmüyor, sadece Yahoo Finance fallback'inde var.
- Primary kaynak kullanıldığında `prevClose` boş kalır, % değişim yanlış hesaplanır.
- **Öneri:** `prevClose`'u DB'deki `raw_macro_daily` tablosundan önceki günün kuru olarak hesapla.

### 8. Test coverage çok düşük
- `tests/` klasöründe sadece `verify_database.py` var.
- Feature engineering, model, API endpoint testleri yok.
- **Öneri:** En azından kritik pipeline bileşenleri için unit test ekle.

### 9. `.env` dosyasında credential'lar plaintext
**Dosya:** `.env`
- EPİAŞ kullanıcı adı ve şifresi düz metin.
- **Öneri:** Üretimde Docker secrets veya environment-based secret management kullan.

---

## Kaldırılan / Geçersiz Tespitler

| # | Eski Tespit | Neden Kaldırıldı |
|---|-------------|------------------|
| Eski 1 | Model her gün sıfırdan eğitiliyor | Bilinçli tasarım kararı. LightGBM ~17K satırda hızlı, maliyet düşük. |
| Eski 7 | Pre-forecast leakage riski | Pre-forecaster farklı hedef tahmin ediyor (yük/güneş/rüzgar vs fiyat). Dolaylı etki minimal. |
| Eski 8 | start.sh bash versiyon bağımlılığı | python:3.11-slim bash 5.x içeriyor, sorun yok. |
| Eski 13 | gold.kgup_load_pre_forecasts tanımsız | Aslında `01_init_schema.sql:236`'da tanımlanmış. Yanlış tespit. |
| Eski 14 | Bugünün verileri proxy olarak kullanılıyor | Bilinçli tasarım. KGÜP/yük tahmini EPİAŞ'ta GÖP kapanışından sonra yayınlanıyor, T+1 için mevcut değil. Pre-forecaster bu sebeple var. |
| Eski 15 | Docker volume'da model persistence yok | Model disk'e kaydedilmiyor (RAM'de eğitilip kullanılıyor). Her gün yeniden eğitim yapılıyor, volume gereksiz. Backfill DB'de persist ediliyor. |
