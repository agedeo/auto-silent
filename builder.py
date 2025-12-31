import requests
import sqlite3
import os
import json
import time
from datetime import datetime

# --- INSTELLINGEN ---
OUTPUT_DIR = "public"
# LET OP: De naam moet exact matchen met wat in MainActivity.kt staat!
DB_FILENAME = "silent_locations.db" 
JSON_FILENAME = "version.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Headers om blokkades te voorkomen
HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/2.0',
    'Referer': 'https://github.com/' 
}

# De query - Nu inclusief Bibliotheken!
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
    print("⏳ Data ophalen bij OpenStreetMap (kan even duren)...")
    try:
        response = requests.post(OVERPASS_URL, data={'data': QUERY}, headers=HEADERS)
        response.raise_for_status() # Check op HTTP fouten
        data = response.json()
        return data['elements']
    except Exception as e:
        print(f"❌ Fout bij ophalen data: {e}")
        if 'response' in locals():
            print(f"Server response: {response.text[:200]}...")
        exit(1)

def map_category(osm_tag):
    """Vertaalt OSM tags naar de categorieën van jouw Android App"""
    if osm_tag == "place_of_worship": return "church"
    if osm_tag == "theatre": return "theater"
    if osm_tag == "cinema": return "cinema"
    if osm_tag == "library": return "library"
    return "church" # Fallback voor zekerheid

def create_database(elements):
    print(f"🔨 Database aanmaken met {len(elements)} items...")
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    
    # Oude verwijderen voor een schone lei
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # DE NIEUWE SCHEMA (Exact zoals in SilentLocation.kt)
    cursor.execute('''
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY,
            name TEXT,
            lat REAL,
            lon REAL,
            category TEXT
        )
    ''')

    count = 0
    for el in elements:
        # 1. Locatie bepalen (Node of Way)
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        
        if not lat or not lon:
            continue

        # 2. Gegevens ophalen
        tags = el.get('tags', {})
        name = tags.get('name', 'Naamloos')
        amenity = tags.get('amenity', '')
        
        # 3. Categorie vertalen (zodat checkboxes in app werken)
        app_category = map_category(amenity)

        # 4. Opslaan
        cursor.execute('INSERT INTO locations VALUES (?, ?, ?, ?, ?)', 
                       (el.get('id'), name, lat, lon, app_category))
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ Database '{DB_FILENAME}' klaar: {count} locaties opgeslagen.")
    return count

def create_metadata(count):
    db_path = os.path.join(OUTPUT_DIR, DB_FILENAME)
    file_size = os.path.getsize(db_path)
    
    # Metadata voor de UpdateManager in Android
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
    print("📄 Metadata (version.json) bijgewerkt.")

if __name__ == "__main__":
    ensure_dir()
    data = fetch_osm_data()
    if data:
        count = create_database(data)
        create_metadata(count)
        print("\n🚀 KLAAR! Upload de inhoud van de map 'public' naar GitHub.")
