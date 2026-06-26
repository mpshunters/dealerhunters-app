"""
Seed New Jersey motor vehicle dealers via Google Places API city sweep.
NJ is one of the densest auto markets in the US — suburban sprawl between
NYC and Philadelphia means high dealer concentration across the entire state.
Sweeps ~120 cities; deduplicates by google_place_id; only keeps state=NJ.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters New Jersey city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

NJ_CITIES = [
    # North NJ — NYC commuter belt (Bergen / Essex / Hudson / Passaic)
    "Newark", "Jersey City", "Paterson", "Clifton", "Elizabeth",
    "Bayonne", "Kearny", "East Orange", "Irvington", "Bloomfield",
    "Hackensack", "Paramus", "Teaneck", "Fort Lee", "Englewood",
    "Bergenfield", "Lodi", "Garfield", "Passaic", "Rutherford",
    "Lyndhurst", "North Bergen", "Secaucus", "Union City", "Hoboken",
    "West New York", "Guttenberg", "Fairview",
    # Morris / Sussex / Warren (NW NJ)
    "Morristown", "Dover", "Rockaway", "Denville", "Parsippany",
    "Mount Olive", "Wharton", "Butler", "Newton", "Sparta",
    "Hackettstown", "Washington", "Phillipsburg",
    # Somerset / Middlesex / Union (Central NJ north)
    "Somerset", "Bridgewater", "Bound Brook", "Somerville",
    "New Brunswick", "Edison", "Piscataway", "South Brunswick",
    "East Brunswick", "Old Bridge", "Woodbridge", "Perth Amboy",
    "Rahway", "Linden", "Plainfield", "Westfield", "Scotch Plains",
    "Cranford", "Clark", "Springfield", "Summit", "Millburn",
    "Short Hills", "Livingston", "West Orange", "Orange", "Maplewood",
    # Monmouth / Ocean (Jersey Shore)
    "Asbury Park", "Long Branch", "Eatontown", "Red Bank", "Freehold",
    "Howell", "Brick", "Toms River", "Lakewood", "Barnegat",
    "Manahawkin", "Seaside Heights", "Belmar", "Tinton Falls",
    "Neptune", "Wall Township", "Hazlet",
    # Burlington / Camden (South NJ — Philadelphia suburbs)
    "Cherry Hill", "Camden", "Voorhees", "Marlton", "Moorestown",
    "Mount Laurel", "Medford", "Evesham", "Lumberton", "Burlington",
    "Bordentown", "Pemberton", "Mount Holly",
    # Gloucester / Salem / Cumberland (Deep South NJ)
    "Vineland", "Millville", "Bridgeton", "Glassboro", "Washington Township",
    "Deptford", "Sewell", "Turnersville", "Woodbury", "Swedesboro",
    # Atlantic / Cape May
    "Atlantic City", "Egg Harbor Township", "Galloway", "Mays Landing",
    "Pleasantville", "Somers Point", "Ocean City", "Cape May",
    "Wildwood", "Rio Grande",
    # Mercer County (Trenton area)
    "Trenton", "Ewing", "Hamilton", "Lawrence", "Princeton",
    "Hightstown", "Robbinsville",
]

seen = set()
CITIES = []
for c in NJ_CITIES:
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
        json={"textQuery": f"car dealer {city} New Jersey", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "NJ").execute()
existing_place_ids = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(existing_place_ids)} existing NJ dealerships in DB\n")
print(f"Sweeping {len(CITIES)} New Jersey cities...\n")

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
                if p_state and p_state != "NJ":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "NJ",
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

print(f"\nNew Jersey sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "NJ").execute()
print(f"  Total NJ dealerships in DB: {result.count}")
