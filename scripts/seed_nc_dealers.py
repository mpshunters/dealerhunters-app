"""
Seed North Carolina motor vehicle dealers via Google Places API city sweep.
NC is a fast-growing auto market anchored by Charlotte, Raleigh-Durham,
and the Triad (Greensboro/Winston-Salem/High Point).
Sweeps ~110 cities; deduplicates by google_place_id; only keeps state=NC.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters North Carolina city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

NC_CITIES = [
    # Charlotte metro
    "Charlotte", "Concord", "Gastonia", "Huntersville", "Kannapolis",
    "Mooresville", "Statesville", "Monroe", "Matthews", "Mint Hill",
    "Harrisburg", "Cornelius", "Davidson", "Salisbury", "Albemarle",
    "Shelby", "Kings Mountain", "Belmont", "Mount Holly", "Cramerton",
    "Gastonia", "Cherryville", "Lincolnton", "Newton", "Hickory",
    "Conover", "Morganton", "Lenoir", "Taylorsville",
    # Raleigh-Durham Triangle
    "Raleigh", "Durham", "Chapel Hill", "Cary", "Apex",
    "Holly Springs", "Fuquay-Varina", "Morrisville", "Wake Forest",
    "Garner", "Clayton", "Smithfield", "Selma", "Sanford",
    "Pittsboro", "Hillsborough", "Mebane", "Graham", "Burlington",
    "Carrboro", "Siler City",
    # Triad — Greensboro / Winston-Salem / High Point
    "Greensboro", "Winston-Salem", "High Point", "Kernersville",
    "Asheboro", "Archdale", "Trinity", "Thomasville", "Lexington",
    "Salisbury", "Landis", "China Grove",
    # Fayetteville / Cape Fear
    "Fayetteville", "Hope Mills", "Spring Lake", "Lumberton",
    "Laurinburg", "Rockingham", "Hamlet", "Raeford",
    # Coastal / Eastern NC
    "Wilmington", "Jacksonville", "New Bern", "Goldsboro",
    "Greenville", "Rocky Mount", "Wilson", "Kinston",
    "Elizabeth City", "Edenton", "Washington",
    "Morehead City", "Beaufort", "Jacksonville",
    # Western NC / Mountains
    "Asheville", "Hendersonville", "Waynesville", "Brevard",
    "Boone", "Blowing Rock", "Watauga", "Marion",
    "Sylva", "Franklin", "Highlands", "Murphy",
    "Forest City", "Spindale", "Rutherfordton",
    # South Central
    "Monroe", "Wadesboro", "Troy", "Carthage", "Pinehurst",
    "Southern Pines", "Aberdeen",
]

seen = set()
CITIES = []
for c in NC_CITIES:
    if c.lower() not in seen:
        seen.add(c.lower())
        CITIES.append(c)

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.addressComponents", "places.nationalPhoneNumber",
    "places.websiteUri", "places.rating", "places.userRatingCount", "places.photos",
])
API_DELAY = 0.4


def parse_address_components(components):
    city = state = zip_code = None
    for comp in components:
        types = comp.get("types", [])
        if "locality" in types:
            city = comp.get("longText")
        elif "administrative_area_level_1" in types:
            state = comp.get("shortText")
        elif "postal_code" in types:
            zip_code = comp.get("longText")
    return city, state, zip_code


def search_dealers_in_city(city: str):
    resp = requests.post(
        PLACES_URL,
        json={"textQuery": f"car dealer {city} North Carolina", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "NC").execute()
existing_place_ids = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(existing_place_ids)} existing NC dealerships in DB\n")
print(f"Sweeping {len(CITIES)} North Carolina cities...\n")

total_added = total_skipped = total_errors = 0
seen_this_run = set(existing_place_ids)

for i, city in enumerate(CITIES, 1):
    try:
        places = search_dealers_in_city(city)
        city_added = 0
        for place in places:
            place_id = place.get("id")
            if not place_id or place_id in seen_this_run:
                total_skipped += 1
                continue
            try:
                p_city, p_state, _ = parse_address_components(place.get("addressComponents", []))
                if p_state and p_state != "NC":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "NC",
                    "phone":           place.get("nationalPhoneNumber"),
                    "website":         place.get("websiteUri"),
                    "google_rating":   place.get("rating"),
                    "google_reviews":  place.get("userRatingCount"),
                    "photo_count":     len(place.get("photos", [])),
                    "has_recent_posts": None, "review_response_rate": None,
                    "dealer_group_id": None, "rooftop_status": "active",
                }, on_conflict="google_place_id").execute()
                seen_this_run.add(place_id)
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

print(f"\nNorth Carolina sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "NC").execute()
print(f"  Total NC dealerships in DB: {result.count}")
