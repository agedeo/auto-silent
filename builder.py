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
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/2.1',
    'Referer': 'https://github.com/' 
}

QUERY = """
[out:json][timeout:180];
area["name"="Nederland"]["admin_level"="2"]->.searchArea;
(
  nwr["amenity"="place_of_worship"](area.searchArea);
  nwr["amenity"="theatre"](area.searchArea);
  nwr["amenity"="cinema"](area.searchArea);
  nwr["amenity"="library"](area.searchArea);
);
out center;
"""

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def fetch_osm_data():
    print("⏳ Data ophalen bij OpenStreetMap...")
    try:
        response = requests.post(OVERPASS_URL, data={'data': QUERY}, headers=HEADERS)
        response.raise_for_status()
        return response.json()['elements']
    except Exception as e:
        print(f"❌ Fout: {e}")
        exit(1)

def map_category(osm_tag):
    if osm_tag == "place_of_worship": return "church"
    if osm_tag == "theatre": return "theater"
    if osm_tag == "cinema": return "cinema"
    if osm_tag == "library": return "library"
    return "church" 

def create_database(elements):
    print(f"🔨 Database aanmaken met {len(elements)} items...")
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- HIER ZIT DE FIX: NOT NULL TOEGEVOEGD ---
    cursor.execute('''
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            category TEXT NOT NULL
        )
    ''')

    count = 0
    for el in elements:
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        
        if not lat or not lon: continue

        tags = el.get('tags', {})
        name = tags.get('name', 'Naamloos')
        amenity = tags.get('amenity', '')
        app_category = map_category(amenity)

        cursor.execute('INSERT INTO locations VALUES (?, ?, ?, ?, ?)', 
                       (el.get('id'), name, lat, lon, app_category))
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ Database '{DB_FILENAME}' klaar: {count} locaties.")
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
