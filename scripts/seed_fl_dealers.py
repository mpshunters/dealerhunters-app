"""
Seed Florida motor vehicle dealers via Google Places API city sweep.
Florida is the #2 US auto market by registration volume.
Sweeps ~180 cities; deduplicates by google_place_id; only keeps state=FL.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters Florida city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FL_CITIES = [
    # Major metros
    "Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg",
    "Hialeah", "Tallahassee", "Fort Lauderdale", "Port St. Lucie", "Cape Coral",
    "Pembroke Pines", "Hollywood", "Gainesville", "Miramar", "Coral Springs",
    "Miami Gardens", "West Palm Beach", "Clearwater", "Palm Bay", "Pompano Beach",
    "Lakeland", "Davie", "Miami Beach", "Sunrise", "Plantation",
    "Boca Raton", "Deltona", "Palm Coast", "Largo", "Deerfield Beach",
    "Melbourne", "Boynton Beach", "Lauderhill", "Fort Myers", "Palm Beach Gardens",
    "Homestead", "Daytona Beach", "Delray Beach", "Kissimmee", "Ocala",
    "Port Orange", "Sanford", "Pensacola", "St. Cloud", "Jupiter",
    "Margate", "Coconut Creek", "Tamarac", "North Miami Beach", "Weston",
    # Miami metro
    "Doral", "Aventura", "Kendall", "Cutler Bay", "Palmetto Bay",
    "Pinecrest", "Coral Gables", "South Miami", "Opa-locka", "North Miami",
    "Hialeah Gardens", "Miami Lakes", "Medley", "Florida City", "Homestead",
    "Key Biscayne", "Sunny Isles Beach", "Bal Harbour", "Surfside",
    # Fort Lauderdale metro (Broward)
    "Pompano Beach", "Deerfield Beach", "Coral Springs", "Margate", "Coconut Creek",
    "Tamarac", "Lauderdale Lakes", "Oakland Park", "Wilton Manors", "Hallandale Beach",
    "Miramar", "Pembroke Pines", "Hollywood", "Dania Beach", "Davie",
    "Cooper City", "Southwest Ranches", "Weston", "Sunrise", "Plantation",
    # Palm Beach metro
    "West Palm Beach", "Boca Raton", "Delray Beach", "Boynton Beach", "Lake Worth",
    "Wellington", "Greenacres", "Royal Palm Beach", "Belle Glade", "Riviera Beach",
    "Palm Beach Gardens", "Jupiter", "Tequesta", "Loxahatchee", "Pahokee",
    # Orlando metro
    "Kissimmee", "Sanford", "Altamonte Springs", "Casselberry", "Winter Park",
    "Oviedo", "Lake Mary", "Longwood", "Apopka", "Winter Garden",
    "Clermont", "Ocoee", "Winter Springs", "Deltona", "DeLand",
    "Leesburg", "Tavares", "Mount Dora", "Ocala", "The Villages",
    # Tampa Bay metro
    "St. Petersburg", "Clearwater", "Largo", "Dunedin", "Tarpon Springs",
    "Safety Harbor", "Oldsmar", "Palm Harbor", "New Port Richey", "Port Richey",
    "Holiday", "Zephyrhills", "Plant City", "Brandon", "Riverview",
    "Valrico", "Ruskin", "Sun City Center", "Apollo Beach", "Bradenton",
    "Sarasota", "Venice", "North Port", "Punta Gorda", "Englewood",
    # Northeast Florida
    "Jacksonville", "Orange Park", "Fleming Island", "St. Augustine", "Palatka",
    "Fernandina Beach", "Yulee", "Macclenny", "Lake City", "Starke",
    # Northwest Florida (Panhandle)
    "Pensacola", "Gulf Breeze", "Navarre", "Fort Walton Beach", "Destin",
    "Niceville", "Crestview", "Milton", "Panama City", "Lynn Haven",
    "Panama City Beach", "Marianna", "Chipley", "Tallahassee",
    # Southwest Florida
    "Fort Myers", "Cape Coral", "Bonita Springs", "Naples", "Marco Island",
    "Estero", "Lehigh Acres", "Immokalee", "Fort Myers Beach", "Punta Gorda",
    "Port Charlotte", "Arcadia",
    # Central / Space Coast
    "Melbourne", "Palm Bay", "Titusville", "Cocoa", "Rockledge",
    "Merritt Island", "Cape Canaveral", "Vero Beach", "Sebastian",
    "Fort Pierce", "Stuart", "Okeechobee",
    # Gainesville / North Central
    "Gainesville", "Ocala", "Crystal River", "Inverness", "Chiefland",
    "Trenton", "Newberry", "Archer", "Hawthorne",
]

seen_cities: set[str] = set()
CITIES = []
for c in FL_CITIES:
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
        json={"textQuery": f"car dealer {city} Florida", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "FL").execute()
seen_ids: set[str] = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(seen_ids)} existing FL dealerships in DB\n")
print(f"Sweeping {len(CITIES)} Florida cities...\n")

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
                if p_state and p_state != "FL":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "FL",
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

print(f"\nFlorida sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "FL").execute()
print(f"  Total FL dealerships in DB: {result.count}")
