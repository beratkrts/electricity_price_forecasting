# ⚡ EPİAŞ Enerji Fiyat Tahmini & Yapay Zeka Dashboard
![Project Status](https://img.shields.io/badge/Status-Production_Ready-success)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![React](https://img.shields.io/badge/Frontend-React_Vite-cyan)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)

Bu proje, Türkiye Elektrik Piyasası'nda (EPİAŞ) **Gün Öncesi Piyasası (GÖP) Piyasa Takas Fiyatını (PTF)** tahmin etmek için tasarlanmış, uçtan uca (End-to-End) bir **Yapay Zeka (AI) ve Veri Mühendisliği** platformudur. 

Proje; sadece veri çekmekle kalmaz, meteorolojik ve makroekonomik verilerle zenginleştirilmiş gelişmiş Makine Öğrenmesi (LightGBM) algoritmalarını eğitir, günlük olarak otomatik tahmin üretir ve sonuçları modern bir web arayüzünde (Dashboard) analiz eder.

---

## 🚀 Proje Mimarisi ve Özellikler

Sistem, profesyonel bir veri mimarisi standartlarına uygun olarak 4 temel ayaktan oluşur:

### 1. 🔄 Veri Mühendisliği & Akıllı ETL Pipeline
* **Çoklu Veri Kaynağı:** EPİAŞ Şeffaflık Platformu (Arz/Talep, Fiyatlar), Yahoo Finance (Canlı USD/TRY, Brent Petrol), ve Open-Meteo API (Saatlik Meteoroloji Tahminleri).
* **Akıllı Backfill & Günlük Senkronizasyon:** Veritabanı ilk kez ayağa kalktığında otomatik olarak geçmiş 2 yıllık (730 gün) veriyi indirir ve modeli eğitir. Sonrasında günlük cron-job olarak sadece eksik günleri (son 2 ay) günceller.
* **Medallion Mimarisi:** PostgreSQL üzerinde `raw` (ham veri) ve `gold` (tahmin sonuçları) tabloları şeklinde yapılandırılmıştır. T+1 mantığıyla hedefler daima tam "yarını" gösterecek şekilde hizalanır.

### 2. 🧠 Yapay Zeka (AI) Modellemesi
* **LightGBM:** Geçmiş fiyat gecikmeleri (Lags), tatil günleri, döviz kurları, sıcaklık tahminleri ve arz-talep oranları gibi onlarca özelliği kullanan optimize edilmiş model.
* **Hedef Dönüşümü (Target Transformation):** Fiyat volatilitesini (dalgalanmasını) yönetmek için Hareketli Ağırlıklı Ortalama (MWA - Residual Learning) ve baz modelleme stratejileri içerir.
* **Sabitlik (Reproducibility):** Model, farklı ortamlarda milimetrik olarak aynı sonuçları üretecek şekilde deterministik olarak yapılandırılmıştır.

### 3. ⚙️ FastAPI Backend Sunucusu
* Modellerden çıkan tahminleri, tarihi gerçekleşen PTF verilerini ve gerçek zamanlı hata metriklerini (WAPE, MAPE, MAE) hesaplayıp Frontend'e REST API üzerinden sunar.
* Dolar (USD) bazlı hataların anlık hesaplamasını yaparak yanıltıcı kur manipülasyonlarını engeller.

### 4. 📊 Modern React Dashboard (Frontend)
* **Glassmorphism Tasarım:** Son derece şık, kullanıcı deneyimi odaklı, karanlık mod (Dark Mode) destekli modern arayüz.
* **Çift Para Birimi (TRY / USD):** Kullanıcı verileri TL veya Dolar cinsinden anlık olarak (canlı kura bölerek/çarparak) inceleyebilir. Geçmiş verilerin orijinal dolar değerlerini bozmadan en sağlıklı finansal dönüşümü yapar.
* **Dinamik Performans Metrikleri:** Seçilen tarih aralıklarına (1 Ay, 3 Ay vb.) göre modelin ne kadar hata yaptığını (WAPE) anlık olarak veritabanından sorgulayıp grafiğe döker.

---

## 🛠️ Hızlı Başlangıç (Docker ile Kurulum)

Projeyi yerel ortamınızda (veritabanı, backend, frontend ve günlük pipeline ile) ayağa kaldırmanın en kolay yolu Docker kullanmaktır.

**1. Çevre Değişkenlerini Ayarlayın:**
Ana dizinde bir `.env` dosyası oluşturun ve bilgilerinizi girin:
```env
EPIAS_USERNAME=mail_adresiniz@mail.com
EPIAS_PASSWORD=sifreniz

# Opsiyonel - Veritabanı ayarları
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_DB=energy_db
POSTGRES_HOST=postgres_db
POSTGRES_PORT=5432
```

**2. Docker Compose'u Çalıştırın:**
```bash
docker compose up --build -d
```

Bu komut ile:
* PostgreSQL veritabanı kurulacak.
* Pipeline otomatik devreye girip geçmiş verileri indirecek ve ilk Yapay Zeka modelini eğitecek.
* FastAPI backend `http://localhost:8000` adresinde yayına başlayacak.
* React Dashboard `http://localhost:3000` adresinde kullanıma hazır olacak.

---

## 📂 Repoda Neler Var?
* `app/frontend/`: React + Vite + TypeScript ile yazılmış modern Dashboard uygulaması.
* `scripts/`: Günlük veri çekme, ETL, ve tahmin işlemlerini yürüten Python boru hatları (pipeline).
* `src/`: Veritabanı (SQLAlchemy) bağlantıları ve Makine Öğrenmesi (LightGBM) sınıflarının çekirdek kodları.
* `docs/`: Mimari planlar ve veri sözlüğü (Data Dictionary) gibi teknik dokümantasyonlar.

---
*Not: Bu proje, T.C. Enerji ve Tabii Kaynaklar Bakanlığı (ETKB) staj projesi kapsamında geliştirilmiştir.*
