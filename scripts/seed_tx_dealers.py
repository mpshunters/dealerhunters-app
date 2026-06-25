"""
Seed Texas motor vehicle dealers via Google Places API city sweep.
Texas has ~16,000+ licensed dealers — the largest US auto market by volume.
Sweeps ~200 cities; deduplicates by google_place_id; only keeps state=TX.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters Texas city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TX_CITIES = [
    # Major metros
    "Houston", "San Antonio", "Dallas", "Austin", "Fort Worth",
    "El Paso", "Arlington", "Corpus Christi", "Plano", "Lubbock",
    "Laredo", "Irving", "Garland", "Amarillo", "McKinney",
    "Frisco", "Grand Prairie", "Brownsville", "Pasadena", "Mesquite",
    "Killeen", "McAllen", "Waco", "Carrollton", "Denton",
    "Midland", "Odessa", "Tyler", "Beaumont", "Round Rock",
    "Abilene", "Wichita Falls", "Richardson", "Pearland", "College Station",
    "League City", "San Angelo", "Longview", "Sugar Land", "Edinburg",
    "Mission", "Bryan", "Baytown", "Pharr", "Temple",
    "Missouri City", "Flower Mound", "Harlingen", "Lewisville", "Allen",
    # DFW suburbs
    "Southlake", "Keller", "Grapevine", "Euless", "Bedford",
    "Hurst", "North Richland Hills", "Mansfield", "Cedar Hill", "Duncanville",
    "DeSoto", "Lancaster", "Rowlett", "Wylie", "Sachse",
    "Murphy", "Allen", "Rockwall", "Fate", "Forney",
    "Burleson", "Cleburne", "Weatherford", "Azle", "Waxahachie",
    "Ennis", "Corsicana", "Terrell", "Greenville", "Sherman",
    "Denison", "Gainesville", "Denton", "Lewisville", "Coppell",
    "Farmers Branch", "Addison", "Richardson", "Garland", "Mesquite",
    # Houston metro
    "The Woodlands", "Katy", "Sugar Land", "Pearland", "League City",
    "Friendswood", "Dickinson", "Texas City", "La Marque", "Galveston",
    "Baytown", "Deer Park", "La Porte", "Pasadena", "Humble",
    "Kingwood", "Conroe", "Spring", "Tomball", "Cypress",
    "Richmond", "Rosenberg", "Stafford", "Missouri City", "Pearland",
    "Angleton", "Lake Jackson", "Clute", "Alvin", "Manvel",
    # San Antonio metro
    "New Braunfels", "Seguin", "San Marcos", "Kyle", "Buda",
    "Schertz", "Cibolo", "Universal City", "Converse", "Selma",
    "Leon Valley", "Helotes", "Boerne", "Kerrville", "Fredericksburg",
    # Austin metro
    "Cedar Park", "Round Rock", "Georgetown", "Pflugerville", "Hutto",
    "Taylor", "Bastrop", "Lockhart", "Elgin", "Marble Falls",
    "Leander", "Liberty Hill", "Lakeway", "Dripping Springs", "Buda",
    # West Texas
    "Midland", "Odessa", "Big Spring", "Snyder", "Sweetwater",
    "San Angelo", "Abilene", "Lubbock", "Amarillo", "Plainview",
    "Pampa", "Borger", "Perryton", "Dalhart", "Childress",
    # East Texas
    "Tyler", "Longview", "Marshall", "Texarkana", "Nacogdoches",
    "Lufkin", "Huntsville", "Conroe", "Jacksonville", "Henderson",
    # South Texas
    "McAllen", "Edinburg", "Mission", "Pharr", "Weslaco",
    "Harlingen", "San Benito", "Brownsville", "Laredo", "Del Rio",
    "Eagle Pass", "Uvalde", "Carrizo Springs",
    # Gulf Coast
    "Corpus Christi", "Victoria", "Port Arthur", "Orange", "Beaumont",
    "Lufkin", "Nacogdoches", "Bay City", "El Campo", "Wharton",
    # Panhandle / North
    "Amarillo", "Lubbock", "Wichita Falls", "Vernon", "Mineral Wells",
    "Stephenville", "Granbury", "Glen Rose",
    # Central Texas
    "Waco", "Temple", "Killeen", "Belton", "Copperas Cove",
    "Harker Heights", "Georgetown", "Hillsboro", "Mexia", "Corsicana",
]

# Deduplicate city list
seen_cities: set[str] = set()
CITIES = []
for c in TX_CITIES:
    if c.lower() not in seen_cities:
        seen_cities.add(c.lower())
        CITIES.append(c)

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.addressComponents", "places.nationalPhoneNumber",
    "places.websiteUri", "places.rating", "places.userRatingCount", "places.photos",
])
API_DELAY = 0.4


def parse_address_components(components):
    city = state = None
    for comp in components:
        types = comp.get("types", [])
        if "locality" in types:
            city = comp.get("longText")
        elif "administrative_area_level_1" in types:
            state = comp.get("shortText")
    return city, state


def search_dealers_in_city(city: str):
    resp = requests.post(
        PLACES_URL,
        json={"textQuery": f"car dealer {city} Texas", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "TX").execute()
seen_ids: set[str] = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(seen_ids)} existing TX dealerships in DB\n")
print(f"Sweeping {len(CITIES)} Texas cities...\n")

total_added = total_skipped = total_errors = 0

for i, city in enumerate(CITIES, 1):
    try:
        places = search_dealers_in_city(city)
        city_added = 0
        for place in places:
            place_id = place.get("id")
            if not place_id or place_id in seen_ids:
                total_skipped += 1
                continue
            try:
                p_city, p_state = parse_address_components(place.get("addressComponents", []))
                if p_state and p_state != "TX":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "TX",
                    "phone":           place.get("nationalPhoneNumber"),
                    "website":         place.get("websiteUri"),
                    "google_rating":   place.get("rating"),
                    "google_reviews":  place.get("userRatingCount"),
                    "photo_count":     len(place.get("photos", [])),
                    "has_recent_posts": None, "review_response_rate": None,
                    "dealer_group_id": None, "rooftop_status": "active",
                }, on_conflict="google_place_id").execute()
                seen_ids.add(place_id)
                city_added += 1
                total_added += 1
            except Exception as e:
                print(f"    Skipped {place.get('displayName', {}).get('text', '?')}: {e}")
                total_errors += 1
        print(f"  [{i}/{len(CITIES)}] {city}: +{city_added} new dealers")
    except Exception as e:
        print(f"  ERROR [{city}]: {e}")
        total_errors += 1
    time.sleep(API_DELAY)

print(f"\nTexas sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "TX").execute()
print(f"  Total TX dealerships in DB: {result.count}")
