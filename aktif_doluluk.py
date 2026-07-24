import os
import time
import json
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

def main():
    # --- 1. KİMLİK BİLGİLERİNİ OKUMA ---
    env_path = next((path / '.env' for path in [Path.cwd(), *Path.cwd().parents] if (path / '.env').exists()), None)
    if env_path is None:
        raise FileNotFoundError('.env dosyası bulunamadı. Lütfen dizini kontrol et.')

    load_dotenv(env_path)
    username = os.getenv("EPIAS_USERNAME") or os.getenv("EPTR_USERNAME")
    password = os.getenv("EPIAS_PASSWORD") or os.getenv("EPTR_PASSWORD")

    if not username or not password:
        raise ValueError('Kimlik bilgileri .env içinde eksik!')

    # --- 2. TGT (GİRİŞ BİLETİ) ALMA İŞLEMİ ---
    print("🔑 EPİAŞ Güvenlik Kapısı: TGT Bileti Alınıyor...")
    cas_url = "https://giris.epias.com.tr/cas/v1/tickets"
    
    cas_payload = {
        "username": username,
        "password": password
    }
    
    cas_headers = {
        "Accept": "text/plain",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    tgt_response = requests.post(cas_url, data=cas_payload, headers=cas_headers)
    
    if tgt_response.status_code == 201:
        tgt = tgt_response.text
        print(f"   ✅ Bilet Başarıyla Alındı! (TGT: {tgt[:15]}...)")
    else:
        print(f"   [-] HATA: TGT bileti alınamadı! Detay: {tgt_response.text}")
        return 

    # --- 3. AKTİF DOLULUK API UÇ NOKTASI ---
    # Senin bulduğun /data/ servisi (Doğrudan JSON döner)
    api_url = "https://seffaflik.epias.com.tr/electricity-service/v1/dams/data/active-fullness"
    
    aylik_periyotlar = pd.date_range(start="2024-01-01", end="2026-07-01", freq="MS")
    
    ana_klasor = "epias_aktif_doluluk_data"
    os.makedirs(ana_klasor, exist_ok=True)
    
    print("\n⚡ Doluluk Botu Başlatıldı: Baraj Aktif Doluluk Oranları Çekiliyor ⚡\n")

    for i in range(len(aylik_periyotlar)):
        start_dt = aylik_periyotlar[i]
        end_dt = start_dt + pd.offsets.MonthEnd(1)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        klasor_adi = f"{ana_klasor}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(klasor_adi, exist_ok=True)
        
        print(f"🚀 Çekiliyor: {start_str} - {end_str}")
        
        # /data/ servisi olduğu için exportType: CSV yazmıyoruz!
        payload = {
            "startDate": f"{start_str}T00:00:00+03:00",
            "endDate": f"{end_str}T23:59:59+03:00"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "TGT": tgt 
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                # Veri zaten tertemiz JSON geliyor, direkt kaydediyoruz
                veri = response.json()
                
                dosya_yolu = f"{klasor_adi}/aktif_doluluk.json"
                
                with open(dosya_yolu, "w", encoding="utf-8") as f:
                    json.dump(veri, f, ensure_ascii=False, indent=4)
                    
                print(f"   ✅ Veri başarıyla kaydedildi.")
                
            else:
                print(f"   [-] HATA: Sunucu {response.status_code} kodu döndürdü. Detay: {response.text}")
                
        except Exception as e:
            print(f"   [!] HATA - Bağlantı sorunu oluştu: {e}")
        
        time.sleep(2) 

    print("\n✅ Sistemden çıkış yapıldı. Aktif doluluk verileri sorunsuz arşivlendi!")

if __name__ == "__main__":
    main()