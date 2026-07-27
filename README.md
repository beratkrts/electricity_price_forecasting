# Enerji-Fiyat-Tahimi
# ⚡ EPİAŞ Elektrik Piyasası Fiyat Tahminleme - Veri Çekme Botu (ETL Extract Phase)

Bu proje, Türkiye Elektrik Piyasası'nda (EPİAŞ) Piyasa Takas Fiyatı (PTF) tahmini yapacak makine öğrenmesi modellerini beslemek amacıyla geliştirilmiş uçtan uca bir veri mühendisliği projesinin **Veri Çıkarma (Extract)** katmanıdır. 

Projenin temel amacı, elektrik piyasası fiyatlarını etkileyen saatlik takip parametrelerini (arz-talep dengesi, piyasa derinliği ve kaynak bazlı üretim) EPİAŞ Şeffaflık Platformu 2.0 API'si üzerinden otomatik olarak toplayıp, ETL veri boru hattına (pipeline) entegre etmektir.

## 🚀 Proje Mimarisi

Sistem, profesyonel bir veri mimarisi standartlarına uygun olarak tasarlanmıştır:

1. **Extract (Bu Repo):** Python ve `eptr2` kütüphanesi kullanılarak hedeflenen saatlik piyasa verileri JSON formatında çekilir.
2. **Transform & Load (ETL):** Çekilen verilerdeki eksik saatler (NULL) doldurulur, tarih formatları eşitlenir ve "Zaman" (Timestamp) sütunu üzerinden birleştirilerek (JOIN) PostgreSQL veritabanına aktarılır.
3. **Machine Learning (ML):** Veritabanından okunan yapılandırılmış veriler (XGBoost / LightGBM) algoritmalarıyla eğitilerek ertesi günün fiyat tahminlemesi yapılır.

## 📊 Çekilen "Altın" Özellikler (Features)

Makine öğrenmesi modelinde Boyut Laneti'ne (Curse of Dimensionality) düşmemek için yalnızca fiyat korelasyonu en yüksek olan "Altın" saatlik veriler hedeflenmiştir:

*   **Fiyat Metrikleri:** PTF (Piyasa Takas Fiyatı) ve SMF (Sistem Marjinal Fiyatı)
*   **Talep (Tüketim) Metrikleri:** Yük Tahmini (Load Plan) ve Gerçekleşen Tüketim
*   **Arz (Üretim) Metrikleri:** Toplam KGÜP, Kaynak Bazlı KGÜP (Doğalgaz, Rüzgar, Kömür vb. kırılımlar) ve Gerçekleşen Üretim
*   **Piyasa Derinliği:** Gün Öncesi Piyasası (GÖP) İşlem Hacmi

## 🛠️ Kurulum ve Ön Gereksinimler

Projeyi yerel ortamınızda çalıştırmak için aşağıdaki adımları izleyin:

**1. Gerekli Kütüphaneleri Yükleyin:**
\`\`\`bash
pip install eptr2 python-dotenv pandas
\`\`\`

**2. Çevre Değişkenlerini (Environment Variables) Ayarlayın:**
Proje ana dizininde bir `.env` dosyası oluşturun ve EPİAŞ Şeffaflık Platformu giriş bilgilerinizi ekleyin:
\`\`\`env
EPIAS_USERNAME=sisteme_kayitli_mail_adresiniz@mail.com
EPIAS_PASSWORD=sifreniz
\`\`\`
*(Not: Güvenlik sebebiyle `.env` dosyası `.gitignore` içine eklenmeli ve asla GitHub'a pushlanmamalıdır.)*

## 🐳 Docker ile Hızlı Kurulum

Projeyi veritabanı (PostgreSQL) ve 7/24 otomatik veri çekme daemon servisi ile birlikte tek komutla çalıştırmak için:

```bash
docker compose up --build -d
```

Kapsamlı Docker mimarisi ve komut rehberi için [docs/docker_guide.md](file:///Users/beratkaratasoglu/etkb_intern_project/enerji_fiyat_tahmini/docs/docker_guide.md) dokümanını inceleyebilirsiniz.


## 💻 Kullanım

Betik dosyası çalıştırıldığında belirtilen tarih aralığındaki tüm saatlik veriler `data/` klasörü içerisine ayrı JSON dosyaları olarak indirilir.

\`\`\`bash
python fetch_ml_features.py
\`\`\`

Örnek Konsol Çıktısı:
\`\`\`text
⚡ 2026-07-01 - 2026-07-02 Dönemi Saatlik ML Verileri Çekiliyor ⚡

-> [01_ptf] (mcp) servisi çağrılıyor...
   [+] Başarılı! Dosya kaydedildi: data/01_ptf.json
-> [03_yuk_tahmini] (load-plan) servisi çağrılıyor...
   [+] Başarılı! Dosya kaydedildi: data/03_yuk_tahmini.json
...
✅ Tüm işlemler tamamlandı. Veriler ETL ekibi için 'data' klasörüne dizildi.
\`\`\`

## 📌 Geliştirici Notları

*   **eptr2 Entegrasyonu:** Toplam KGÜP ve Kaynak Bazlı KGÜP verileri, `eptr2` kütüphanesinin güncel yapısı gereği tek bir çağrıda (`kgup`) sütun kırılımlı olarak elde edilmektedir.
*   **Hata Yönetimi:** Platformda verisi henüz girilmemiş saatler veya resmi tatil kaynaklı boşluklar sistem tarafından otomatik olarak "atlanacak" şekilde try-except bloklarıyla güvenceye alınmıştır.
