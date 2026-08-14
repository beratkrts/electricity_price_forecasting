# Metrik Rehberi — Model Değerlendirmesinde Ne Ölçmeli

**Tarih:** 14 Ağustos 2026
**Sebep:** Tek metrik (WAPE) 2026 bahar rejiminde yanlış yön gösterdi. Bkz. `LOW_PRICE_REGIME_ANALYSIS.md` Bölüm 2.
**Kural:** Hiçbir model kararı tek metriğe dayanmaz. Aşağıdaki **çekirdek set** her deney raporunda zorunlu.

---

## 1. Neden WAPE tek başına yetmiyor

`WAPE = Σ|hata| / Σ|gerçek|`. Payda fiyatla birlikte çöküyor:

| Ay | Gerçek ort. | MAE $ | WAPE% |
|---|---|---|---|
| 2026-04 | 20.7 | 11.06 | 53.6 |
| 2026-05 | 12.6 | **7.68** | **61.0** |

Nisan→Mayıs'ta MAE **düştü**, WAPE **yükseldi**. Sadece WAPE'e bakan biri modelin kötüleştiği sonucuna varır ve yanlış yöne optimize eder.

Aynı sorun MAPE'te daha şiddetli (`Σ|hata/gerçek|`) — sıfır fiyatta tanımsız. Literatürün üzerinde uzlaştığı tespit (Lago et al. 2021, *Applied Energy*): *MAPE fiyat sıfıra yaklaştığında gerçek mutlak hatadan bağımsız olarak patlar, düşük fiyat dönemlerinin hakimiyetine girer ve bilgilendirici olmaz.*

---

## 2. Çekirdek metrik seti (zorunlu)

| Metrik | Formül | Ne söyler | Neden gerekli |
|---|---|---|---|
| **MAE** | `mean(\|tahmin − gerçek\|)` | Ortalama hata, $ cinsinden | Rejimden bağımsız, yorumlanabilir. Ana karar metriği. |
| **BIAS** | `mean(tahmin − gerçek)` | Sistematik sapma yönü | MAE yönü gizler. Şubat 2026'daki +$9.22 sadece burada görünür. |
| **rMAE** | `MAE_model / MAE_naive` | Naive'e göre kazanç | **Literatürle kıyaslanabilir tek metrik.** Rejimden bağımsız. |
| **sMAPE** | `mean(2·\|hata\| / (\|tahmin\|+\|gerçek\|))` | Simetrik yüzde hata | MAPE'in sıfır patlaması yok. Ama tanımsız ortalama/sonsuz varyans — destekleyici, tek başına değil. |
| **WAPE** | `Σ\|hata\| / Σ\|gerçek\|` | Ağırlıklı yüzde | Geriye dönük süreklilik için tut, **karar verme.** |
| **P10-P90 kapsama** | `mean(p10 ≤ gerçek ≤ p90)` | Belirsizlik bandı kalibrasyonu | Nominal %80 olmalı. Ucuz dilimde %43'e düşüyor — nokta tahmininden bağımsız bir arıza. |

**Naive tanımı (Lago et al. standardı):** Pzt/Cmt/Paz → geçen hafta aynı saat; Sal-Cum → dün aynı saat.

**Yorum eşikleri:** rMAE < 1.0 naive'den iyi. İyi EPF modelleri literatürde kabaca **0.5-0.8**.

---

## 3. Zorunlu ayrıştırmalar

Tek bir toplam sayı yanıltıcı — genel WAPE'in ~%88'i $60 üstü saatlerden geliyor, ucuz dilimdeki değişimi hiç görmüyor.

1. **Fiyat dilimine göre** — `= $0 / $0-10 / $10-20 / $20-30 / $30-40 / $40-60 / $60-80 / $80+`. Shrinkage'ı sadece bu gösterir.
2. **Aya göre** — rejim kırılmalarını ve uyum hızını gösterir.
3. **Rejime göre** — durağan vs kriz dönemi ayrı raporlanır.

---

## 4. Mevcut baseline (canlı model, `gold.ptf_predictions_daily`)

| Dönem | n | MAE | Naive MAE | **rMAE** | sMAPE | WAPE |
|---|---|---|---|---|---|---|
| Durağan (2025-09 → 2026-01) | 3.672 | 5.65 | 8.02 | **0.705** | %12.0 | %8.4 |
| Kriz (2026-02 → 2026-06) | 3.528 | 10.54 | 13.14 | **0.802** | %61.8 | %36.4 |
| Tümü (2 yıl) | 17.520 | 7.26 | 9.60 | **0.756** | %23.5 | %12.2 |

**Kritik okuma:** Kriz döneminde WAPE %8.4 → %36.4 (4.3 kat) fırlarken rMAE 0.705 → 0.802 (%14) kıpırdıyor. Piyasa zorlaştı, naive de zorlandı, model orantısını korudu. **Yeni modeller bu tabloyu yenmek zorunda — özellikle rMAE sütununu.**

---

## 5. Hazır SQL

```sql
-- Cekirdek set + naive karsilastirmasi. Donem/model degistirerek kullan.
WITH b AS (
  SELECT p.target_ts, m.price_usd px, p.predicted_mcp_usd pred,
    p.predicted_mcp_usd_p10 p10, p.predicted_mcp_usd_p90 p90,
    EXTRACT(dow FROM p.target_ts AT TIME ZONE 'Europe/Istanbul') dow,
    n1.price_usd nv1, n7.price_usd nv7
  FROM gold.ptf_predictions_daily p
  JOIN public.raw_mcp_hourly m  ON m.ts  = p.target_ts
  LEFT JOIN public.raw_mcp_hourly n1 ON n1.ts = p.target_ts - INTERVAL '1 day'
  LEFT JOIN public.raw_mcp_hourly n7 ON n7.ts = p.target_ts - INTERVAL '7 day'),
c AS (SELECT *, CASE WHEN dow IN (1,6,0) THEN nv7 ELSE nv1 END naive FROM b)
SELECT COUNT(*) n,
  ROUND(AVG(ABS(pred-px))::numeric, 2)                                    "MAE",
  ROUND(AVG(pred-px)::numeric, 2)                                         "BIAS",
  ROUND((AVG(ABS(pred-px))/NULLIF(AVG(ABS(naive-px)),0))::numeric, 3)     "rMAE",
  ROUND((100*AVG(2*ABS(pred-px)/NULLIF(ABS(pred)+ABS(px),0)))::numeric,1) "sMAPE%",
  ROUND((100*SUM(ABS(pred-px))/NULLIF(SUM(px),0))::numeric, 1)            "WAPE%",
  ROUND((100.0*AVG(((px BETWEEN p10 AND p90))::int))::numeric, 1)         "kapsama%"
FROM c WHERE naive IS NOT NULL;
```

Fiyat dilimi ayrıştırması için `LOW_PRICE_REGIME_ANALYSIS.md` Bölüm 1'deki `CASE WHEN` bloğunu `GROUP BY` ile ekle.

---

## 6. Uygulama notları

- **Tümü USD bazlı.** TL metrikleri kur etkisini hataya karıştırır (bkz. `CLAUDE.md` TL dönüşümü notu).
- **`gold.experiment_results` tablosuna** (ACTION_PLAN #15, henüz açık) bu altı metrik + dönem etiketi kolonları eklensin ki deneyler kıyaslanabilir olsun.
- **Dashboard `MetricCards`** şu an sadece WAPE gösteriyor — yanına MAE ve BIAS eklenmeli. Kullanıcı düşük fiyat rejiminde WAPE kartına bakıp modelin bozulduğunu sanabilir.
- **Yukarıdaki tablo backfill (walk-forward simülasyon).** Gerçek canlı koşuların rMAE'si ayrı ölçülmeli.
