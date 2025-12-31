import requests
import sqlite3
import os
import json
import time
from datetime import datetime

# --- INSTELLINGEN ---
OUTPUT_DIR = "public"
DB_FILENAME = "silent_locations.db"
JSON_FILENAME = "version.json"

# OPLOSSING 1: We gebruiken een 'Mirror' server. Deze is vaak sneller en minder streng.
# Alternatief als deze ook faalt: "https://lz4.overpass-api.de/api/interpreter"
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/3.0', 
    'Referer': 'https://github.com/'
}

# OPLOSSING 2: [maxsize:...] toegevoegd zodat hij meer geheugen mag gebruiken.
OVERPASS_QUERY = """
[out:json][timeout:900][maxsize:1073741824];
(
  // KERKEN (Religie)
  node["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);
  way["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);
  rel["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);

  // THEATERS
  node["amenity"="theatre"](50.7,3.3,53.7,7.3);
  way["amenity"="theatre"](50.7,3.3,53.7,7.3);
  rel["amenity"="theatre"](50.7,3.3,53.7,7.3);
   
  node["amenity"="arts_centre"](50.7,3.3,53.7,7.3);
  way["amenity"="arts_centre"](50.7,3.3,53.7,7.3);
  rel["amenity"="arts_centre"](50.7,3.3,53.7,7.3);

  // BIOSCOPEN
  node["amenity"="cinema"](50.7,3.3,53.7,7.3);
  way["amenity"="cinema"](50.7,3.3,53.7,7.3);
  rel["amenity"="cinema"](50.7,3.3,53.7,7.3);

  // BIBLIOTHEKEN
  node["amenity"="library"](50.7,3.3,53.7,7.3);
  way["amenity"="library"](50.7,3.3,53.7,7.3);
  rel["amenity"="library"](50.7,3.3,53.7,7.3);
);
out center;
"""

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def fetch_osm_data():
    print(f"⏳ Data ophalen bij {OVERPASS_URL}...")
    try:
        # We voegen hier ook een timeout toe aan requests zelf, voor de zekerheid
        response = requests.post(OVERPASS_URL, data={'data': OVERPASS_QUERY}, headers=HEADERS, timeout=900)
        
        if response.status_code == 429:
            print("❌ Te veel verzoeken (Rate Limit). Wacht even en probeer opnieuw.")
            exit(1)
        if response.status_code == 504:
            print("❌ Server Timeout. Probeer het script later opnieuw of gebruik een kleinere regio.")
            exit(1)
            
        response.raise_for_status()
        return response.json()['elements']
    except Exception as e:
        print(f"❌ Fout bij verbinding: {e}")
        exit(1)

def map_category(osm_tag):
    if osm_tag == "place_of_worship": return "church"
    if osm_tag == "theatre": return "theater"
    if osm_tag == "cinema": return "cinema"
    if osm_tag == "library": return "library"
    return "church" 

def construct_address(tags):
    street = tags.get('addr:street', '')
    number = tags.get('addr:housenumber', '')
    city = tags.get('addr:city', '')
    
    address = f"{street} {number}".strip()
    if address and city:
        return f"{address}, {city}"
    elif city:
        return city
    elif address:
        return address
    else:
        return "Adres onbekend"

def create_database(elements):
    print(f"🔨 Database aanmaken met {len(elements)} items...")
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL
        )
    ''')

    count = 0
    excluded_count = 0

    for el in elements:
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        
        if not lat or not lon: continue

        tags = el.get('tags', {})
        name = tags.get('name', 'Naamloos')
        amenity = tags.get('amenity', '')
        
        # --- KAPELLEN FILTER (Python Side) ---
        name_lower = name.lower()
        if 'kapel' in name_lower or 'chapel' in name_lower:
            excluded_count += 1
            continue
        # -------------------------------------

        app_category = map_category(amenity)
        full_address = construct_address(tags)

        cursor.execute('INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?)', 
                       (el.get('id'), name, lat, lon, app_category, full_address))
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ Database '{DB_FILENAME}' klaar: {count} locaties.")
    if excluded_count > 0:
        print(f"🧹 {excluded_count} kapellen succesvol gefilterd.")
    return count

def create_metadata(count):
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    file_size = os.path.getsize(db_path)
    
    metadata = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": int(time.time()),
        "regions": [{"id": "nl", "file": DB_FILENAME, "count": count, "size_bytes": file_size}]
    }
    
    with open(os.path.join(OUTPUT_DIR, JSON_FILENAME), 'w') as f:
        json.dump(metadata, f, indent=2)
    print("📄 Metadata bijgewerkt.")

if __name__ == "__main__":
    ensure_dir()
    data = fetch_osm_data()
    if data:
        count = create_database(data)
        create_metadata(count)
        print("\n🚀 KLAAR! Upload de map 'public' naar GitHub.")
