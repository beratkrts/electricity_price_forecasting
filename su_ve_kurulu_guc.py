import os
import time
import requests
import pandas as pd
import io
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

    # --- 3. SADECE SU ENERJİSİ API UÇ NOKTASI ---
    su_api_url = "https://seffaflik.epias.com.tr/electricity-service/v1/dams/export/water-energy-provision"
    
    aylik_periyotlar = pd.date_range(start="2024-01-01", end="2026-07-01", freq="MS")
    
    ana_klasor = "epias_su_enerjisi_data"
    os.makedirs(ana_klasor, exist_ok=True)
    
    print("\n⚡ Su Botu Başlatıldı: Baraj Verileri Çekilip JSON'a Çevriliyor ⚡\n")

    for i in range(len(aylik_periyotlar)):
        start_dt = aylik_periyotlar[i]
        end_dt = start_dt + pd.offsets.MonthEnd(1)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        
        klasor_adi = f"{ana_klasor}/{start_dt.strftime('%Y-%m')}"
        os.makedirs(klasor_adi, exist_ok=True)
        
        print(f"🚀 Çekiliyor: {start_str} - {end_str}")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "TGT": tgt 
        }
        
        payload_su = {
            "startDate": f"{start_str}T00:00:00+03:00",
            "endDate": f"{end_str}T23:59:59+03:00",
            "exportType": "CSV" 
        }
        
        try:
            res_su = requests.post(su_api_url, json=payload_su, headers=headers)
            
            if res_su.status_code == 200:
                res_su.encoding = 'utf-8-sig'
                # EPİAŞ virgül yerine noktalı virgül (;) kullanır
                df_su = pd.read_csv(io.StringIO(res_su.text), sep=";")
                
                # CSV'yi havada JSON'a çevir ve kaydet
                df_su.to_json(f"{klasor_adi}/su_enerjisi.json", orient="records", force_ascii=False, indent=4)
                print("   ✅ Su verisi 'su_enerjisi.json' olarak başarıyla kaydedildi.")
                
            else:
                print(f"   [-] HATA: Sunucu {res_su.status_code} kodu döndürdü. Detay: {res_su.text}")
                
        except Exception as e:
            print(f"   [!] HATA - Bağlantı veya Dönüşüm sorunu: {e}")
            
        time.sleep(2) # Ban yememek için 2 saniye mola

    print("\n✅ İşlem Tamam! Tüm ayların Su Enerjisi verileri sorunsuz arşivlendi.")

if __name__ == "__main__":
    main()