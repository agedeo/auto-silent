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

# We gebruiken de Kumi Systems mirror voor betere performance
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

HEADERS = {
    'User-Agent': 'SilentModeAppBuilder/4.1', 
    'Referer': 'https://github.com/'
}

# QUERY UPDATE: Alle categorieën
OVERPASS_QUERY = """
[out:json][timeout:900][maxsize:1073741824];
(
  // 1. KERKEN (Religie) - Kapellen uitgesloten
  node["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);
  way["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);
  rel["amenity"="place_of_worship"]["building"!="chapel"]["building"!="shrine"]["building"!="wayside_shrine"]["amenity"!="wayside_shrine"]["historic"!="wayside_shrine"](50.7,3.3,53.7,7.3);

  // 2. CULTUUR (Theaters, Bioscopen, Arts Centres)
  node["amenity"~"^(theatre|cinema|arts_centre)$"](50.7,3.3,53.7,7.3);
  way["amenity"~"^(theatre|cinema|arts_centre)$"](50.7,3.3,53.7,7.3);
  rel["amenity"~"^(theatre|cinema|arts_centre)$"](50.7,3.3,53.7,7.3);

  // 3. BIBLIOTHEKEN
  node["amenity"="library"](50.7,3.3,53.7,7.3);
  way["amenity"="library"](50.7,3.3,53.7,7.3);
  rel["amenity"="library"](50.7,3.3,53.7,7.3);

  // 4. GEMEENSCHAPSHUIZEN (Buurthuizen)
  node["amenity"="community_centre"](50.7,3.3,53.7,7.3);
  way["amenity"="community_centre"](50.7,3.3,53.7,7.3);
  rel["amenity"="community_centre"](50.7,3.3,53.7,7.3);

  // 5. MUSEA
  node["tourism"="museum"](50.7,3.3,53.7,7.3);
  way["tourism"="museum"](50.7,3.3,53.7,7.3);
  rel["tourism"="museum"](50.7,3.3,53.7,7.3);

  // 6. ROUW & HERDENKING (Begraafplaatsen, Crematoria)
  node["landuse"="cemetery"](50.7,3.3,53.7,7.3);
  way["landuse"="cemetery"](50.7,3.3,53.7,7.3);
  rel["landuse"="cemetery"](50.7,3.3,53.7,7.3);
  
  node["amenity"~"^(funeral_hall|crematorium)$"](50.7,3.3,53.7,7.3);
  way["amenity"~"^(funeral_hall|crematorium)$"](50.7,3.3,53.7,7.3);
  rel["amenity"~"^(funeral_hall|crematorium)$"](50.7,3.3,53.7,7.3);

  // 7. ZIEKENHUIZEN
  node["amenity"="hospital"](50.7,3.3,53.7,7.3);
  way["amenity"="hospital"](50.7,3.3,53.7,7.3);
  rel["amenity"="hospital"](50.7,3.3,53.7,7.3);

  // 8. OVERHEID (Rechtbanken, Gemeentehuizen)
  node["amenity"~"^(courthouse|townhall)$"](50.7,3.3,53.7,7.3);
  way["amenity"~"^(courthouse|townhall)$"](50.7,3.3,53.7,7.3);
  rel["amenity"~"^(courthouse|townhall)$"](50.7,3.3,53.7,7.3);
);
out center;
"""

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def fetch_osm_data():
    print(f"⏳ Data ophalen bij {OVERPASS_URL}...")
    try:
        response = requests.post(OVERPASS_URL, data={'data': OVERPASS_QUERY}, headers=HEADERS, timeout=900)
        
        if response.status_code == 429:
            print("❌ Te veel verzoeken (Rate Limit). Wacht even en probeer opnieuw.")
            exit(1)
        if response.status_code == 504:
            print("❌ Server Timeout. Probeer het script later opnieuw.")
            exit(1)
            
        response.raise_for_status()
        return response.json()['elements']
    except Exception as e:
        print(f"❌ Fout bij verbinding: {e}")
        exit(1)

def map_category(tags):
    amenity = tags.get('amenity', '')
    tourism = tags.get('tourism', '')
    landuse = tags.get('landuse', '')
    
    # 1. Cultuur & Entertainment
    if amenity == "cinema": return "cinema"
    if amenity == "theatre" or amenity == "arts_centre": return "theater"
    if tourism == "museum": return "museum"
    if amenity == "library": return "library"

    # 2. Vereniging
    if amenity == "community_centre": return "community"

    # 3. Zorg & Rouw
    if amenity == "hospital": return "hospital"
    if landuse == "cemetery" or amenity in ["funeral_hall", "crematorium"]: return "cemetery"

    # 4. Overheid
    if amenity in ["courthouse", "townhall"]: return "government"

    # 5. Religie (Fallback)
    if amenity == "place_of_worship": return "church"
    
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
        
        # --- KAPELLEN FILTER ---
        name_lower = name.lower()
        if 'kapel' in name_lower or 'chapel' in name_lower:
            excluded_count += 1
            continue

        app_category = map_category(tags)
        full_address = construct_address(tags)

        # --- FIX VOOR UNIQUE ID ERROR ---
        # We maken het ID uniek door er een groot getal bij op te tellen
        # afhankelijk van het type (node, way, relation).
        osm_id = el.get('id')
        osm_type = el.get('type')
        
        unique_id = osm_id
        if osm_type == 'way':
            unique_id = osm_id + 10_000_000_000  # Way ID + 10 miljard
        elif osm_type == 'relation':
            unique_id = osm_id + 20_000_000_000  # Relation ID + 20 miljard
        
        # ---------------------------------

        try:
            cursor.execute('INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?)', 
                           (unique_id, name, lat, lon, app_category, full_address))
            count += 1
        except sqlite3.IntegrityError:
            # Als er ondanks de fix toch nog een dubbele is, slaan we hem over ipv crashen
            print(f"⚠️ Dubbel ID overgeslagen: {unique_id}")
            continue

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
