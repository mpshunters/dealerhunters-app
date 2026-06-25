from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters photo count backfill starting...")

SUPABASE_URL   = os.environ.get("SUPABASE_URL")
SUPABASE_KEY   = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.photos"
API_DELAY  = 0.5

# Fetch all dealerships missing photo_count
result = supabase.table("dealerships") \
    .select("id, dealership_name, city, state, google_place_id") \
    .is_("photo_count", "null") \
    .execute()

dealerships = result.data
total       = len(dealerships)
print(f"Found {total} dealerships with no photo_count\n")

updated = 0
errors  = 0

for i, dealer in enumerate(dealerships, 1):
    name          = dealer.get("dealership_name") or ""
    dealer_id     = dealer["id"]
    google_place_id = dealer.get("google_place_id")
    city          = dealer.get("city")  or ""
    state         = dealer.get("state") or ""
    label         = f"{name} ({city}, {state})" if (city or state) else name

    photo_count = 0

    try:
        if google_place_id:
            # Prefer direct Place Details lookup by place ID (cheaper, more accurate)
            detail_url = f"https://places.googleapis.com/v1/places/{google_place_id}"
            resp = requests.get(
                detail_url,
                headers={
                    "X-Goog-Api-Key":  GOOGLE_API_KEY,
                    "X-Goog-FieldMask": "photos",
                },
                timeout=15,
            )
            resp.raise_for_status()
            photo_count = len(resp.json().get("photos", []))
        else:
            # Fall back to text search if no place ID stored
            headers = {
                "Content-Type":   "application/json",
                "X-Goog-Api-Key": GOOGLE_API_KEY,
                "X-Goog-FieldMask": FIELD_MASK,
            }
            body = {
                "textQuery":      f"{name} dealership",
                "includedType":   "car_dealer",
                "maxResultCount": 1,
            }
            if city or state:
                body["textQuery"] = f"{name} dealership {city} {state}".strip()

            resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            places = resp.json().get("places", [])
            if places:
                photo_count = len(places[0].get("photos", []))

        supabase.table("dealerships") \
            .update({"photo_count": photo_count}) \
            .eq("id", dealer_id) \
            .execute()

        print(f"  Updated {i}/{total}: {label} — {photo_count} photos")
        updated += 1

    except Exception as e:
        print(f"  Error {i}/{total}: {label} — {e}")
        errors += 1

    time.sleep(API_DELAY)

print(
    f"\nBackfill complete. "
    f"{updated} updated | {errors} errors | {total} total"
)
