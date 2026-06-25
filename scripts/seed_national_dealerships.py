from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
    "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
    "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

BRANDS = [
    "Ford", "Toyota", "Chevrolet", "Honda", "Nissan",
    "Jeep", "RAM", "Hyundai", "Kia", "Subaru",
    "Volkswagen", "BMW", "Mercedes", "Lexus", "Dodge",
]

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
])


def parse_address_components(components):
    city = state = zip_code = None
    for comp in components:
        types = comp.get("types", [])
        if "locality" in types:
            city = comp.get("longText")
        elif "administrative_area_level_1" in types:
            state = comp.get("shortText")  # 2-letter abbreviation
        elif "postal_code" in types:
            zip_code = comp.get("longText")
    return city, state, zip_code


def search_dealerships(brand, state_name):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": f"{brand} dealership in {state_name}",
        "includedType": "car_dealer",
        "maxResultCount": 20,
    }
    resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("places", [])


print("DealerHunters national dealership seeding starting...")
print(f"Searching {len(BRANDS)} brands × {len(STATES)} states = {len(BRANDS) * len(STATES)} queries\n")

total_upserted = 0

for state_idx, state_name in enumerate(STATES, 1):
    for brand in BRANDS:
        try:
            places = search_dealerships(brand, state_name)
            count = 0

            for place in places:
                try:
                    components = place.get("addressComponents", [])
                    city, state_abbr, zip_code = parse_address_components(components)

                    record = {
                        "google_place_id": place["id"],
                        "name":            place.get("displayName", {}).get("text", ""),
                        "address":         place.get("formattedAddress", ""),
                        "city":            city,
                        "state":           state_abbr,
                        "zip":             zip_code,
                        "brand":           brand,
                        "phone":           place.get("nationalPhoneNumber"),
                        "website":         place.get("websiteUri"),
                        "google_rating":   place.get("rating"),
                        "google_reviews":  place.get("userRatingCount"),
                    }

                    supabase.table("dealerships").upsert(
                        record, on_conflict="google_place_id"
                    ).execute()
                    count += 1

                except Exception as e:
                    name = place.get("displayName", {}).get("text", "?")
                    print(f"    Skipped {name}: {e}")

            print(f"  State {state_idx}/50 [{state_name}]: {count} results for {brand}")
            total_upserted += count

        except Exception as e:
            print(f"  ERROR [{state_name}] {brand}: {e}")

        time.sleep(0.5)

print(f"\nDone. {total_upserted} dealerships upserted across all states and brands.")

# Final count from DB
result = supabase.table("dealerships").select("id", count="exact").execute()
print(f"Total dealerships in database: {result.count}")
