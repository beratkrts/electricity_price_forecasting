import os
import time
import json
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from eptr2 import EPTR2

def main():
    # --- 1. KİMLİK DOĞRULAMA (Güvenli .env Bağlantısı) ---
    env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
    if env_path is None:
        raise FileNotFoundError('.env dosyası bulunamadı. Lütfen dizini kontrol et.')

    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    if not username or not password:
        raise ValueError('Kimlik bilgileri .env içinde eksik!')

    # API Bağlantısını Kur
    eptr = EPTR2(username=username, password=password, dotenv_path=str(env_path))

    # --- 2. GÜNCELLENEN 8'Lİ KADRO ---
    endpoints = {
        "01_yuk_tahmini": "load-plan",
        "02_kgup": "kgup",
        "03_ptf": "mcp",
        "04_smf": "smp",
        "05_alis_teklifleri": "dam-bid",
        "06_satis_teklifleri": "dam-offer",
        "07_gerceklesen_uretim": "rt-gen",
        "08_gerceklesen_tuketim": "rt-cons"
    }

    # --- 3. ZAMAN DÖNGÜSÜ (2024 Ocak - Şu Anki Zaman) ---
    # 2024 Ocak'tan 2026 Temmuz'a kadar aylık frekans (MS = Month Start)
    aylik_periyotlar = pd.date_range(start="2024-01-01", end="2026-07-01", freq="MS")
    
    ana_klasor = "epias_data"
    os.makedirs(ana_klasor, exist_ok=True)
    print("⚡ EPİAŞ ETL Botu Başlatıldı: Aylık Bloklar Halinde Veri Çekimi ⚡\n")

    for i in range(len(aylik_periyotlar)):
        # Ayın ilk ve son gününü dinamik olarak hesaplıyoruz
        start_dt = aylik_periyotlar[i]
        end_dt = start_dt + pd.offsets.MonthEnd(1)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        # Her ay için temiz bir klasör açıyoruz
        klasor_adi = f"{ana_klasor}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(klasor_adi, exist_ok=True)
        
        print(f"\n🚀 Hedef Dönem: {start_str} - {end_str} | Klasör: {klasor_adi}")
        
        for dosya_adi, call_key in endpoints.items():
            print(f"   -> [{dosya_adi}] ({call_key}) servisi çağrılıyor...")
            try:
                # API'nin İstediği Saat Dilimli Format (+03:00)
                start_iso = f"{start_str}T00:00:00+03:00"
                end_iso = f"{end_str}T23:59:59+03:00"
                
                # API Çağrısı
                res = eptr.call(call_key, start_date=start_iso, end_date=end_iso)
                
                # Veri boş dönmediyse kaydet
                if res is not None:
                    dosya_yolu = f"{klasor_adi}/{dosya_adi}.json"
                    
                    if hasattr(res, 'to_json'):
                        res.to_json(dosya_yolu, orient="records", force_ascii=False, indent=4)
                    elif hasattr(res, 'to_dict'):
                        with open(dosya_yolu, "w", encoding="utf-8") as f:
                            json.dump(res.to_dict(), f, ensure_ascii=False, indent=4)
                    else:
                        with open(dosya_yolu, "w", encoding="utf-8") as f:
                            json.dump(res, f, ensure_ascii=False, indent=4)
                else:
                    print(f"      [-] {dosya_adi} servisi bu ay için boş döndü.")
                    
            except Exception as e:
                print(f"      [!] HATA - {dosya_adi} çekerken bir sorun oluştu: {e}")
            
            # API Banı Yememek İçin Bekleme
            time.sleep(2) 

    print("\n✅ Bütün işlemler başarıyla tamamlandı. Veriler işlenmeye hazır!")

if __name__ == "__main__":
    main()