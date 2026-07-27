import os
import json
import time
import requests
import pandas as pd
from pathlib import Path

# --- 1. GEOCODING LOOKUP DICTIONARY FOR TURKEY PROVINCES ---
TURKEY_81_CITY_COORDINATES = {
    "ADANA": (36.9914, 35.3308),
    "ADIYAMAN": (37.7644, 38.2786),
    "AFYONKARAHİSAR": (38.7507, 30.5567),
    "AĞRI": (39.7192, 43.0503),
    "AKSARAY": (38.3687, 34.0370),
    "AMASYA": (40.6499, 35.8353),
    "ANKARA": (39.9334, 32.8597),
    "ANTALYA": (36.8969, 30.7133),
    "ARDAHAN": (41.1105, 42.7022),
    "ARTVİN": (41.1828, 41.8183),
    "AYDIN": (37.8450, 27.8416),
    "BALIKESİR": (39.6484, 27.8826),
    "BARTIN": (41.6358, 32.3375),
    "BATMAN": (37.8812, 41.1351),
    "BAYBURT": (40.2552, 40.2249),
    "BİLECİK": (40.1506, 29.9792),
    "BİNGÖL": (38.8854, 40.4980),
    "BİTLİS": (38.4006, 42.1095),
    "BOLU": (40.7392, 31.6089),
    "BURDUR": (37.7203, 30.2908),
    "BURSA": (40.1885, 29.0610),
    "ÇANAKKALE": (40.1553, 26.4142),
    "ÇANKIRI": (40.6013, 33.6134),
    "ÇORUM": (40.5506, 34.9556),
    "DENİZLİ": (37.7765, 29.0864),
    "DİYARBAKIR": (37.9144, 40.2306),
    "DÜZCE": (40.8438, 31.1565),
    "EDİRNE": (41.6772, 26.5557),
    "ELAZIĞ": (38.6810, 39.2264),
    "ERZİNCAN": (39.7500, 39.4925),
    "ERZURUM": (39.9043, 41.2679),
    "ESKİŞEHİR": (39.7667, 30.5256),
    "GAZİANTEP": (37.0662, 37.3833),
    "GİRESUN": (40.9128, 38.3895),
    "GÜMÜŞHANE": (40.4602, 39.4814),
    "HAKKARİ": (37.5833, 43.7333),
    "HATAY": (36.2023, 36.1613),
    "IĞDIR": (39.9237, 44.0450),
    "ISPARTA": (37.7648, 30.5566),
    "İSTANBUL": (41.0082, 28.9784),
    "İZMİR": (38.4192, 27.1287),
    "KAHRAMANMARAŞ": (37.5858, 36.9371),
    "KARABÜK": (41.2061, 32.6204),
    "KARAMAN": (37.1759, 33.2287),
    "KARS": (40.6013, 43.0975),
    "KASTAMONU": (41.3887, 33.7827),
    "KAYSERİ": (38.7312, 35.4787),
    "KIRIKKALE": (39.8453, 33.5153),
    "KIRKLARELİ": (41.7351, 27.2252),
    "KIRŞEHİR": (39.1425, 34.1709),
    "KİLİS": (36.7184, 37.1212),
    "KOCAELİ": (40.7654, 29.9408),
    "KONYA": (37.8746, 32.4932),
    "KÜTAHYA": (39.4167, 29.9833),
    "MALATYA": (38.3552, 38.3095),
    "MANİSA": (38.6191, 27.4289),
    "MARDİN": (37.3129, 40.7350),
    "MERSİN": (36.8000, 34.6333),
    "MUĞLA": (37.2153, 28.3636),
    "MUŞ": (38.7432, 41.5064),
    "NEVŞEHİR": (38.6244, 34.7144),
    "NİĞDE": (37.9667, 34.6833),
    "ORDU": (40.9839, 37.8764),
    "OSMANİYE": (37.0742, 36.2478),
    "RİZE": (41.0201, 40.5234),
    "SAKARYA": (40.7569, 30.3783),
    "SAMSUN": (41.2928, 36.3313),
    "SİİRT": (37.9333, 41.9500),
    "SİNOP": (42.0268, 35.1507),
    "SİVAS": (39.7477, 37.0179),
    "ŞANLIURFA": (37.1674, 38.7955),
    "ŞIRNAK": (37.5164, 42.4611),
    "TEKİRDAĞ": (40.9833, 27.5167),
    "TOKAT": (40.3167, 36.5500),
    "TRABZON": (41.0027, 39.7169),
    "TUNCELİ": (39.1083, 39.5401),
    "UŞAK": (38.6823, 29.4082),
    "VAN": (38.4942, 43.3800),
    "YALOVA": (40.6550, 29.2769),
    "YOZGAT": (39.8181, 34.8147),
    "ZONGULDAK": (41.4564, 31.7987)
}

def get_coordinates(city_name):
    """İl adından enlem ve boylam bulur (Önce static lookup, sonra Open-Meteo API)."""
    if city_name.upper() in TURKEY_81_CITY_COORDINATES:
        return TURKEY_81_CITY_COORDINATES[city_name.upper()]
        
    clean_name = city_name.replace('İ', 'I').replace('I', 'i').title()
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_name}&count=5&language=tr&format=json"
    try:
        res = requests.get(url, timeout=10).json()
        results = res.get("results", [])
        for r in results:
            if r.get("country_code") == "TR" or r.get("country") == "Turkey":
                return r["latitude"], r["longitude"]
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception as e:
        print(f"[!] Geocoding error for {city_name}: {e}")
    return None, None


# --- 2. CONFIG LOADER & WEIGHT NORMALIZER ---
def load_city_weights_and_coords(num_target_cities: int = 26):
    """
    Loads city percentages from config/city_percentages.json for top num_target_cities (default 26),
    normalizes their weights to sum to 1.0, and returns city metadata with coordinates.
    Also creates/updates config/city_coordinates.json cleanly without any missing cities.
    """
    config_dir = Path("config")
    coords_file = config_dir / "city_coordinates.json"
    percentages_file = config_dir / "city_percentages.json"

    if not percentages_file.exists():
        raise FileNotFoundError("config/city_percentages.json not found!")

    with open(percentages_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Slice the target N cities (default 26)
    target_cities = list(raw_data.items())[:num_target_cities]
    total_share_sum = sum(val for _, val in target_cities)

    if total_share_sum == 0:
        raise ValueError("Sum of target city percentages is 0!")

    normalized = {}
    for city, raw_val in target_cities:
        lat, lon = get_coordinates(city)
        if lat is None or lon is None:
            raise KeyError(f"Could not resolve coordinates for city: {city}")
            
        weight = raw_val / total_share_sum
        normalized[city] = {
            "lat": lat,
            "lon": lon,
            "raw_percentage": raw_val,
            "weight": round(weight, 8)
        }

    # Always write verified config/city_coordinates.json
    os.makedirs(config_dir, exist_ok=True)
    with open(coords_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=4)

    return normalized


# --- 3. OPEN-METEO ARCHIVE WEATHER FETCHER ---
def fetch_turkey_weighted_temperature(start_date_str: str, end_date_str: str, batch_size: int = 25):
    """
    Fetches hourly temperature for all weighted Turkish cities from Open-Meteo Historical Archive API,
    computes the consumption-weighted average hourly temperature for Turkey,
    and returns a clean Pandas DataFrame.
    """
    city_map = load_city_weights_and_coords()
    cities = list(city_map.keys())
    
    print(f"\n🌤️  Fetching Open-Meteo weather data for {len(cities)} cities from {start_date_str} to {end_date_str}...")

    # Split cities into chunks to avoid HTTP GET URL length limits
    city_chunks = [cities[i:i + batch_size] for i in range(0, len(cities), batch_size)]
    
    hourly_time = None
    weighted_temperature_sum = None

    total_weight_used = sum(city_map[c]["weight"] for c in cities)

    for idx, chunk in enumerate(city_chunks, start=1):
        lats = [str(city_map[c]["lat"]) for c in chunk]
        lons = [str(city_map[c]["lon"]) for c in chunk]

        archive_url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={','.join(lats)}&"
            f"longitude={','.join(lons)}&"
            f"start_date={start_date_str}&"
            f"end_date={end_date_str}&"
            f"hourly=temperature_2m"
        )

        try:
            res = requests.get(archive_url, timeout=60)
            res.raise_for_status()
            data = res.json()

            # Single location returns dict, multiple locations return list of dicts
            locations_data = data if isinstance(data, list) else [data]

            for city, loc_data in zip(chunk, locations_data):
                hourly = loc_data.get("hourly", {})
                time_series = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])

                if hourly_time is None and time_series:
                    hourly_time = time_series
                    weighted_temperature_sum = [0.0] * len(time_series)

                city_weight = city_map[city]["weight"]
                for i in range(len(temps)):
                    temp_val = temps[i] if temps[i] is not None else 0.0
                    weighted_temperature_sum[i] += temp_val * city_weight

            print(f"   [+] Processed batch {idx}/{len(city_chunks)} ({len(chunk)} cities)")

        except Exception as e:
            print(f"   [!] Error fetching batch {idx}: {e}")

        time.sleep(1)  # Respect API rate limits

    if hourly_time is None or weighted_temperature_sum is None:
        print("   [-] Could not collect weather data.")
        return pd.DataFrame()

    # Re-normalize by total weight used (should be 1.0)
    final_weighted_temp = [round(t / total_weight_used, 2) for t in weighted_temperature_sum]

    df_result = pd.DataFrame({
        "date_time": hourly_time,
        "turkey_weighted_temperature_c": final_weighted_temp
    })

    print(f"   ✅ Successfully computed weighted temperature series ({len(df_result)} hourly records).")
    return df_result


# --- 4. MAIN EXECUTION ---
if __name__ == "__main__":
    # Test fetch for 2024-01-01 to 2024-01-10
    df = fetch_turkey_weighted_temperature("2024-01-01", "2024-01-10")
    print(df.head())
    
    os.makedirs("data", exist_ok=True)
    output_path = "data/turkey_weighted_temperature_test.json"
    df.to_json(output_path, orient="records", force_ascii=False, indent=4)
    print(f"Saved test output to {output_path}")
