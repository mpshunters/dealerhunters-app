"""
Seed Ohio motor vehicle dealers via Google Places API city sweep.
Ohio has one of the largest dealer networks in the Midwest (~5,000+ franchised/independent).
Sweeps ~150 cities; deduplicates by google_place_id; only keeps state=OH.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters Ohio city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

OH_CITIES = [
    # Columbus metro
    "Columbus", "Dublin", "Westerville", "Hilliard", "Grove City",
    "Gahanna", "Reynoldsburg", "Newark", "Lancaster", "Pickerington",
    "Canal Winchester", "Delaware", "Marysville", "Marion", "Circleville",
    "Chillicothe", "London", "Washington Court House",
    # Cleveland metro
    "Cleveland", "Akron", "Parma", "Lorain", "Elyria",
    "Strongsville", "North Olmsted", "Middleburg Heights", "Brook Park", "Westlake",
    "North Royalton", "Mentor", "Willoughby", "Euclid", "Solon",
    "Beachwood", "Mayfield Heights", "Richmond Heights", "Lyndhurst", "South Euclid",
    "Lakewood", "Rocky River", "Bay Village", "Avon Lake", "Avon",
    "Medina", "Brunswick", "Wadsworth", "Barberton", "Norton",
    "Stow", "Tallmadge", "Cuyahoga Falls", "Fairlawn", "Kent",
    "Ravenna", "Aurora", "Twinsburg", "Macedonia", "Hudson",
    "Painesville", "Chardon", "Ashtabula", "Sandusky", "Fremont",
    # Cincinnati metro
    "Cincinnati", "Hamilton", "Middletown", "Fairfield", "Mason",
    "West Chester", "Blue Ash", "Loveland", "Milford", "Batavia",
    "Florence", "Covington", "Newport", "Erlanger", "Kenwood",
    "Springdale", "Forest Park", "Sharonville", "Norwood", "Mariemont",
    "Anderson Township", "Delhi Township", "Colerain Township",
    # Dayton metro
    "Dayton", "Kettering", "Beavercreek", "Huber Heights", "Fairborn",
    "Troy", "Piqua", "Miamisburg", "Springboro", "Franklin",
    "Xenia", "Centerville", "Trotwood", "Englewood", "Vandalia",
    "Moraine", "West Carrollton", "Riverside", "Oakwood",
    # Toledo metro
    "Toledo", "Perrysburg", "Maumee", "Sylvania", "Oregon",
    "Findlay", "Bowling Green", "Defiance", "Bryan", "Wauseon",
    "Fostoria", "Tiffin", "Fremont",
    # Other major cities
    "Youngstown", "Canton", "Massillon", "Alliance", "New Philadelphia",
    "Dover", "Wooster", "Ashland", "Mansfield", "Galion",
    "Lima", "Wapakoneta", "Celina", "Van Wert", "Defiance",
    "Portsmouth", "Ironton", "Gallipolis", "Jackson", "Waverly",
    "Athens", "Zanesville", "Cambridge", "Coshocton", "Steubenville",
    "Belmont", "St. Clairsville", "Martins Ferry", "Wheeling",
    "Springfield", "Urbana", "Bellefontaine", "Kenton", "Ada",
]

seen = set()
CITIES = []
for c in OH_CITIES:
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
        json={"textQuery": f"car dealer {city} Ohio", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "OH").execute()
existing_place_ids = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(existing_place_ids)} existing OH dealerships in DB\n")
print(f"Sweeping {len(CITIES)} Ohio cities...\n")

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
                if p_state and p_state != "OH":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "OH",
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

print(f"\nOhio sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "OH").execute()
print(f"  Total OH dealerships in DB: {result.count}")
