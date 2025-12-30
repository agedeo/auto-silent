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

# 1. Identificatie (Cruciaal! Anders blokkeert Overpass je)
HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/1.0 (github-action-test)',
    'Referer': 'https://github.com/jouwnaam/silent-app' 
}

# De query
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="NL"]["admin_level"="2"]->.searchArea;
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
    print(f"   Target URL: {OVERPASS_URL}")
    
    # We voegen de HEADERS toe aan het verzoek
    response = requests.post(OVERPASS_URL, data={'data': QUERY}, headers=HEADERS)
    
    if response.status_code == 200:
        try:
            return response.json()['elements']
        except json.JSONDecodeError:
            print("❌ FOUT: Server gaf geen geldige JSON terug.")
            print(f"Inhoud: {response.text[:500]}") # Print eerste 500 tekens
            raise Exception("Ongeldige JSON response")
    else:
        # DIT is wat we moeten zien als het fout gaat:
        print(f"❌ HTTP Fout {response.status_code}")
        print("🔍 Server antwoord (De reden):")
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
    print(f"✅ Database klaar: {count} locaties opgeslagen.")
    return count

def create_metadata(count):
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
        if not data:
            print("⚠️ Geen data gevonden! Check de query.")
            exit(1)
        count = create_database(data)
        create_metadata(count)
    except Exception as e:
        print(f"❌ Script gestopt door fout: {e}")
        exit(1)