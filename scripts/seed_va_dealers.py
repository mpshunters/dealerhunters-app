"""
Seed Virginia motor vehicle dealers via Google Places API city sweep.
VA is anchored by Northern Virginia (DC suburbs), Richmond, and Hampton Roads,
with secondary markets in Charlottesville, Roanoke, and the Shenandoah Valley.
Sweeps ~110 cities; deduplicates by google_place_id; only keeps state=VA.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters Virginia city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

VA_CITIES = [
    # Northern Virginia — DC suburbs
    "Alexandria", "Arlington", "Fairfax", "Reston", "Herndon",
    "Chantilly", "Centreville", "Manassas", "Manassas Park", "Woodbridge",
    "Dale City", "Lake Ridge", "Dumfries", "Stafford", "Fredericksburg",
    "Spotsylvania", "Culpeper", "Warrenton", "Leesburg", "Ashburn",
    "Sterling", "Dulles", "Purcellville", "Lovettsville", "Haymarket",
    "Gainesville", "Bristow", "Nokesville", "Prince William",
    # Richmond metro
    "Richmond", "Henrico", "Chesterfield", "Midlothian", "Chester",
    "Colonial Heights", "Petersburg", "Hopewell", "Mechanicsville",
    "Ashland", "Hanover", "Glen Allen", "Short Pump", "Bon Air",
    "Highland Springs", "Sandston",
    # Hampton Roads
    "Virginia Beach", "Norfolk", "Chesapeake", "Portsmouth", "Suffolk",
    "Hampton", "Newport News", "Williamsburg", "James City",
    "York County", "Poquoson", "Smithfield", "Franklin",
    # Charlottesville
    "Charlottesville", "Crozet", "Waynesboro", "Staunton", "Harrisonburg",
    "Bridgewater", "Elkton",
    # Roanoke / Lynchburg
    "Roanoke", "Salem", "Vinton", "Lynchburg", "Bedford",
    "Christiansburg", "Radford", "Blacksburg", "Pulaski",
    # Shenandoah Valley / Western VA
    "Winchester", "Front Royal", "Woodstock", "Luray", "Strasburg",
    "Martinsville", "Henry County", "Danville", "South Boston",
    # Southwest VA
    "Bristol", "Abingdon", "Wytheville", "Galax", "Big Stone Gap",
    "Norton", "Wise", "Bluefield",
    # Eastern Shore / Northern Neck
    "Accomac", "Exmore", "Cape Charles", "Warsaw", "Tappahannock",
]

seen = set()
CITIES = []
for c in VA_CITIES:
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
        json={"textQuery": f"car dealer {city} Virginia", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "VA").execute()
existing_place_ids = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(existing_place_ids)} existing VA dealerships in DB\n")
print(f"Sweeping {len(CITIES)} Virginia cities...\n")

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
                if p_state and p_state != "VA":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "VA",
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

print(f"\nVirginia sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "VA").execute()
print(f"  Total VA dealerships in DB: {result.count}")
