import os
import json
from dotenv import load_dotenv
from eptr2 import EPTR2

# Kimlik bilgilerini .env dosyasından güvenli bir şekilde çekiyoruz
load_dotenv()
username = os.getenv("EPIAS_USERNAME")
password = os.getenv("EPIAS_PASSWORD")

if not username or not password:
    print("Hata: .env dosyasında EPIAS_USERNAME veya EPIAS_PASSWORD eksik!")
    exit()

# EPTR2 nesnemizi (object) başlatıyoruz
eptr = EPTR2(username=username, password=password)

def fetch_ml_hourly_features(start_date, end_date):
    # eptr2 kütüphanesinin güncel alias'ları ile hazırlanmış "Altın Kadro"
    ml_calls = {
        "01_ptf": "mcp",
        "02_smf": "smp",
        "03_yuk_tahmini": "load-plan",
        "04_gerceklesen_tuketim": "rt-cons",
        "05_kgup_kaynak_bazli": "kgup", # Doğalgaz, rüzgar vb. tüm kırılımları otomatik içerir
        "06_gerceklesen_uretim": "rt-gen",
        "07_islem_hacmi": "dam-volume"
    }

    # Dosyaların düşeceği klasörü hazırlayalım
    os.makedirs("data", exist_ok=True)
    print(f"\n⚡ {start_date} - {end_date} Dönemi Saatlik ML Verileri Çekiliyor ⚡\n")

    for name, call_key in ml_calls.items():
        print(f"-> [{name}] ({call_key}) servisi çağrılıyor...")
        try:
            # Arka planda EPİAŞ'a gidip veriyi Pandas DataFrame veya dict olarak getirir
            res = eptr.call(call_key, start_date=start_date, end_date=end_date)
            
            # Veri başarılı çekildiyse ve boş değilse dosyaya yaz
            if res is not None and not (hasattr(res, 'empty') and res.empty):
                file_path = f"data/{name}.json"
                
                # Pandas DataFrame dönerse to_json, sözlük dönerse json.dump kullanıyoruz
                if hasattr(res, 'to_json'):
                    res.to_json(file_path, orient="records", force_ascii=False, indent=4)
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(res, f, ensure_ascii=False, indent=4)
                        
                print(f"   [+] Başarılı! Dosya kaydedildi: {file_path}")
            else:
                print("   [-] Veri bulunamadı (Tatil günü veya sistemde o saate ait kayıt yok).")
                
        except Exception as e:
            print(f"   [-] Sistem Hatası: {e}")

    print("\n✅ Tüm işlemler tamamlandı. Veriler ETL ekibi için 'data' klasörüne dizildi.")

if __name__ == "__main__":
    # Test için tarihleri değiştirebilirsin
    fetch_ml_hourly_features("2026-07-01", "2026-07-02")