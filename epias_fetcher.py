import os
import json
from datetime import datetime, timedelta
import pandas as pd
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

def get_date_chunks(start_date_str, end_date_str, max_days):
    """Büyük tarih aralığını EPİAŞ limitlerine göre küçük parçalara böler."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    current_date = start_date
    while current_date <= end_date:
        # EPİAŞ sınırını tam ucu ucuna aşmamak için max_days - 1 kullanıyoruz (Örn: 364 gün veya 89 gün)
        next_date = current_date + timedelta(days=max_days - 1)
        if next_date > end_date:
            next_date = end_date
        yield current_date.strftime("%Y-%m-%d"), next_date.strftime("%Y-%m-%d")
        current_date = next_date + timedelta(days=1)

def fetch_ml_hourly_features(start_date, end_date):
    # Paylaştığın log çıktısındaki kesin EPİAŞ limitlerine göre oluşturulmuş harita
    ml_calls = {
        "01_ptf": {"call_key": "mcp", "max_days": 365},
        "02_smf": {"call_key": "smp", "max_days": 365},
        "03_yuk_tahmini": {"call_key": "load-plan", "max_days": 365},
        "04_gerceklesen_tuketim": {"call_key": "rt-cons", "max_days": 365},
        "05_kgup_kaynak_bazli": {"call_key": "kgup", "max_days": 90},       # Logda dönen 3 MONTH sınırı
        "06_gerceklesen_uretim": {"call_key": "rt-gen", "max_days": 90},     # Logda dönen 3 MONTH sınırı
        "07_islem_hacmi": {"call_key": "dam-volume", "max_days": 365}
    }

    # Çıktıların kaydedileceği klasörü oluşturuyoruz
    os.makedirs("data", exist_ok=True)
    print(f"\n⚡ Processing ML Hourly Features for period: {start_date} to {end_date} ⚡\n")

    for file_prefix, config in ml_calls.items():
        call_key = config["call_key"]
        max_days = config["max_days"]
        
        print(f"-> Service [{file_prefix}] ({call_key}) is starting...")
        
        combined_data = []
        chunks = list(get_date_chunks(start_date, end_date, max_days))
        print(f"   [Info] Total chunks to fetch for this service: {len(chunks)}")

        # Tarih aralığını servisin limitine göre parçalayıp döngüyle çağırıyoruz
        for chunk_start, chunk_end in chunks:
            print(f"   Sending request for chunk: {chunk_start} to {chunk_end}...")
            try:
                res = eptr.call(call_key, start_date=chunk_start, end_date=chunk_end)
                
                if res is not None:
                    # Gelen veri Pandas DataFrame ise listeye (dict formatında) ekle
                    if hasattr(res, 'to_dict'):
                        if not res.empty:
                            combined_data.extend(res.to_dict(orient="records"))
                    # Gelen veri doğrudan liste veya dict ise ekle
                    elif isinstance(res, list):
                        combined_data.extend(res)
                    elif isinstance(res, dict):
                        combined_data.append(res)
                        
            except Exception as e:
                print(f"   [-] Error fetching chunk {chunk_start} - {chunk_end}: {e}")
                continue

        # Toplanan tüm parçaları tek bir JSON dosyası olarak kaydediyoruz
        if combined_data:
            file_path = f"data/{file_prefix}.json"
            try:
                df = pd.DataFrame(combined_data)
                df.to_json(file_path, orient="records", force_ascii=False, indent=4)
                print(f"   [+] Success! Total records combined: {len(df)}. Saved to: {file_path}")
            except Exception as e:
                print(f"   [-] Error saving combined file for {file_prefix}: {e}")
        else:
            print(f"   [-] No data could be collected for service [{file_prefix}].")

    print("\n✅ All operations completed. Data is structured in the 'data' directory for the ETL pipeline.")

if __name__ == "__main__":
    # Loglarındaki tam tarih aralığına göre çalıştırıyoruz
    fetch_ml_hourly_features("2020-07-01", "2026-07-19")