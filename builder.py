import requests
import sqlite3
import os
import json
import time
from datetime import datetime

# Instellingen
OUTPUT_DIR = "public"  # Map voor GitHub Pages
DB_FILENAME = "silent_locations_nl.db"
JSON_FILENAME = "version.json"
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# De query (NL)
QUERY = """
[out:json][timeout:180];
area["name"="Nederland"]["admin_level"="2"]->.searchArea;
(
  nwr["amenity"~"^(place_of_worship|theatre|cinema|crematorium|funeral_hall)$"](area.searchArea);
);
out center;
"""

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def fetch_osm_data():
    print("⏳ Data ophalen bij OpenStreetMap...")
    response = requests.post(OVERPASS_URL, data=QUERY)
    if response.status_code == 200:
        return response.json()['elements']
    else:
        raise Exception(f"Error fetching data: {response.status_code}")

def create_database(elements):
    print("🔨 Database aanmaken...")
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            lat REAL,
            lon REAL,
            type TEXT,
            name TEXT,
            region_id TEXT
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
    print(f"✅ Database klaar: {count} locaties.")
    return count

def create_metadata(count):
    # Maak een manifest bestandje voor de app
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
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
        print(f"❌ Fout: {e}")
        exit(1)