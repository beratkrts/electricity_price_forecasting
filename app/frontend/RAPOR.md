# EPİAŞ PTF Enerji Fiyat Tahminleme Dashboard ve Mimari Raporu (Son Güncel Sürüm)

**Hazırlanma Tarihi:** 31 Temmuz 2026  
**Proje Adı:** EPİAŞ Piyasa Takas Fiyatı (PTF) Gelecek Fiyat Tahminleme ve Karar Destek Dashboard'u  
**Proje Durumu:** ℹ️ Demo Modu (Model Eğitimi ve Veri Simülasyonu Aşamasında - Gerçek API ve PostgreSQL Veritabanı Entegrasyonuna Tam Hazır Altyapı)  
**Ana Hedef:** Sadece ve Yalnızca EPİAŞ Piyasa Takas Fiyatı (PTF) Tahmini, Model Karşılaştırması ve Veritabanı İncelemesi  

---

## 1. YÖNETİCİ ÖZETİ VE ÇOKLU SAYFA MİMARİSİ (MULTI-PAGE ROUTING)

Projenin yapısı modern bir SPA (Single Page Application) olarak React Router kütüphanesi kullanılarak **3 Ana Sayfa** düzenine (Multi-Page Architecture) geçirilmiştir.

```
+-----------------------------------------------------------------------------------+
| HEADER: Logo | YÖNLENDİRME (Ana Sayfa | Kıyaslama | Analiz) | Canlı Yenile | İndir|
+-----------------------------------------------------------------------------------+
|                                                                                   |
| 🌐 1. SAYFA (HOME - ANA SAYFA)                                                    |
| - Gelecek Gün (1 Ağustos) PTF Tahmin Alanı                                        |
| - 24 Saat, 7 Gün, 1 Ay Tahmin Aralığı Seçici Düğmeler (Yeni Özellik)              |
| - Sol: Tahmin Modelleri Seçici & Hibrit Ağırlık Slider'ı                          |
| - Üst: Modellerin Tahmin Ortalamaları ve 1 Haftalık Başarı Trendleri              |
| - Sağ Grafik: Sadece Gelecek PTF Tahmin Eğrileri                                  |
|                                                                                   |
| 📈 2. SAYFA (FORECAST - TAHMİN KIYASLAMA)                                         |
| - 31 Temmuz Sabah Tahminimiz vs EPİAŞ Gerçekleşen PTF Kıyaslaması                 |
| - Kıyaslama Tarihi Seçici (Geçmişe Dönük Kıyaslama)                               |
| - WAPE, MAPE Hata Payları Kartları                                                |
| - Kesişim Pingleme (Toggle ile Göster/Gizle) Aktif Kıyaslama Grafiği              |
| - [YENİ] Tahmin vs Gerçekleşen Verilerin Listelendiği DATA TABLOSU Görünümü       |
|                                                                                   |
| 📊 3. SAYFA (ANALYSIS - ANALİZLER VE VERİTABANI)                                  |
| - İlk açıldığında varsayılan olarak boş ve seçim bekleyen tasarım                 |
| - Seçim Menüsü ile PostgreSQL Tablolarına (KGÜP, Yük Tahmini vb.) Erişim          |
| - Grafik ve Tablo Çift Görünüm Desteği                                            |
|                                                                                   |
+-----------------------------------------------------------------------------------+
| FOOTER: Canlı Piyasa & Kur Döngüsü (USD/TRY, EUR/TRY, Brent, TTF, EU ETS)         |
+-----------------------------------------------------------------------------------+
```

---

## 2. PROJE VE OPERASYONEL İŞ MANTIĞI

### 2.1 Tahmin ve Yayın Zaman Çizelgesi (D-1 ➔ D ➔ D+1)

Projemizin operasyonel zaman akışı şu şekildedir:

```
[30 Temmuz (D-1)]  --->  [31 Temmuz Sabahı 04:00 (D Günü)]  --->  [1 Ağustos (D+1)]
 Tamamlanan Tüm           ETL Veri Çekme + EPNet AI Tahmini       Tahmin Edilen 24
 Piyasalar & Santral      31 Temmuz Sabahı Dashboard'da Yayın       Saatlik PTF Eğrisi
 Verileri (D-1)           (EPİAŞ 12:30 İhale Kapanışından Önce)
```

1. **Sabah ETL'inin (04:00 AM) Amacı**:
   - 31 Temmuz sabahı çalışarak 30 Temmuz (D-1) gününün tamamen kesinleşmiş 24 saatlik piyasa gerçekleşmelerini (PTF, SMF, Üretim/Tüketim) veritabanına işler.
2. **Sabah Tahmini ve Yayınlama**:
   - `src/models/epnet.py` (CNN+LSTM), `LightGBM` ve `Hibrit Model` bu verilerle çalışarak **1 Ağustos'un (D+1)** 24 saatlik PTF fiyatlarını tahmin eder ve piyasa teklifleri kapanmadan önce yayımlar.
3. **EPİAŞ İlanı ve Doğrulama**:
   - EPİAŞ saat **14:15'te** gerçekleşen resmi PTF'yi ilan ettiğinde, sabah yaptığımız kilitli tahmin ile gerçek fiyatlar **Tahmin Kıyaslama** sayfasında kıyaslanarak Hata Payı (MAPE %) ve Kesişim Pinglemesi anında görüntülenir.

---

## 3. DASHBOARD BÖLÜMLERİ VE YENİ ÖZELLİKLER

### 🏠 1. Ana Sayfa (Home - Gelecek Tahminleri)
- **Yeni Tahmin Aralığı**: 24 Saat, 7 Gün, 1 Ay butonları eklenmiştir. Seçime göre dinamik olarak 1 aya varan uzun vadeli tahmin grafiklerini çizer.
- Hibrit ağırlık slider'ı tam tutarlı doğrusal kombinasyon mantığıyla çalışır.

### 📈 2. Tahmin Kıyaslama Sayfası (Forecast - Kıyaslama ve Hata Payı)
- WAPE, MAPE hesaplamaları kartlarda görüntülenir.
- **Tarih Seçici**: Kullanıcı geçmişteki herhangi bir tarihe gidip o günkü sabah tahmini ile gerçekleşen PTF'yi kıyaslayabilir.
- **Data Tablosu Özelliği**: İstenildiğinde sağ üstteki butona tıklayarak geçmiş saatlere ait tüm gerçekleşen vs tahmin edilen PTF verilerini hata paylarıyla birlikte tablo formatında görüntüleyebilir.

### 🗄️ 3. Analiz Sayfası (Analysis - Veritabanı Explorer)
- Veritabanı inceleyici alanı ilk açılışta boş durur, kullanıcıya rehberlik eden seçim kartlarıyla veri çağrıldığında grafik ve tablo formatında detaylı analize imkan tanır.

---

## 4. DOCKER VE DEPLOYMENT MİMARİSİ

```bash
# Docker container derleme ve çalıştırma
docker compose up -d --build
```
- **Port**: `http://localhost:8080` (veya Dev ortamında `http://localhost:3000`).
