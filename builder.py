import requests
import sqlite3
import os
import json
import time
from datetime import datetime

# Instellingen
OUTPUT_DIR = "public"
DB_FILENAME = "silent_locations_nl.db"
JSON_FILENAME = "version.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Headers om te voorkomen dat we geblokkeerd worden
HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/1.0',
    'Referer': 'https://github.com/' 
}

# De query - Simpelere versie die altijd werkt voor Nederland
QUERY = """
[out:json][timeout:180];
area["name"="Nederland"]["admin_level"="2"]->.searchArea;
(
  nwr["amenity"="place_of_worship"](area.searchArea);
  nwr["amenity"="theatre"](area.searchArea);
  nwr["amenity"="cinema"](area.searchArea);
  nwr["amenity"="crematorium"](area.searchArea);
  nwr["amenity"="funeral_hall"](area.searchArea);
);
out center;
"""

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def fetch_osm_data():
    print("⏳ Data ophalen bij OpenStreetMap...")
    print(f"   Target URL: {OVERPASS_URL}")
    
    # We sturen de data correct als form-data
    response = requests.post(OVERPASS_URL, data={'data': QUERY}, headers=HEADERS)
    
    if response.status_code == 200:
        try:
            data = response.json()
            return data['elements']
        except Exception as e:
            print("❌ De server gaf geen geldige JSON terug.")
            print(f"Server antwoord: {response.text[:200]}...") 
            raise Exception("Ongeldige response")
    else:
        # HIER printen we nu de echte fout
        print(f"❌ HTTP Fout {response.status_code}")
        print("🔍 Server antwoord (Lees dit goed):")
        print("------------------------------------------------")
        print(response.text) 
        print("------------------------------------------------")
        raise Exception(f"Fout bij ophalen data: {response.status_code}")

def create_database(elements):
    print(f"🔨 Database aanmaken met {len(elements)} items...")
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            type TEXT NOT NULL,
            name TEXT,
            region_id TEXT NOT NULL
        )
    ''')

    count = 0
    for el in elements:
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        tags = el.get('tags', {})
        
        if lat and lon:
            cursor.execute('INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?)', 
                           (el.get('id'), lat, lon, tags.get('amenity'), tags.get('name', 'Onbekend'), 'NL'))
            count += 1

    conn.commit()
    conn.close()
    print(f"✅ Database klaar: {count} locaties opgeslagen.")
    return count

def create_metadata(count):
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    if not os.path.exists(db_path):
        print("⚠️ Database bestand niet gevonden voor metadata!")
        return

    file_size = os.path.getsize(db_path)
    
    metadata = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": int(time.time()),
        "regions": [
            {
                "id": "nl",
                "file": DB_FILENAME,
                "count": count,
                "size_bytes": file_size
            }
        ]
    }
    
    with open(os.path.join(OUTPUT_DIR, JSON_FILENAME), 'w') as f:
        json.dump(metadata, f, indent=2)
    print("📄 Metadata (version.json) aangemaakt.")

if __name__ == "__main__":
    try:
        ensure_dir()
        data = fetch_osm_data()
        count = create_database(data)
        create_metadata(count)
    except Exception as e:
        print(f"❌ Script gestopt: {e}")
        exit(1)
