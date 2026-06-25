"""
Seed Illinois motor vehicle dealers via Google Places API.

Illinois does not publish a downloadable dealer roster (ILSOS apps block
programmatic access). Instead this script sweeps all significant IL cities
by querying Google Places for "car dealer" — giving us real licensed dealers
with Google ratings/reviews already populated.

Strategy: city sweep (up to 20 results per city) rather than brand×state so
we get broad geographic coverage across ~200 Illinois cities.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters Illinois city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Illinois cities with meaningful auto dealer presence
# Ordered roughly by metro size / dealer density to get best coverage first
IL_CITIES = [
    # Chicagoland metro
    "Chicago", "Aurora", "Naperville", "Joliet", "Rockford",
    "Springfield", "Elgin", "Peoria", "Champaign", "Waukegan",
    "Cicero", "Bloomington", "Arlington Heights", "Evanston",
    "Decatur", "Schaumburg", "Bolingbrook", "Palatine", "Skokie",
    "Des Plaines", "Orland Park", "Tinley Park", "Oak Lawn", "Berwyn",
    "Mount Prospect", "Normal", "Wheaton", "Downers Grove", "Hoffman Estates",
    "Oak Park", "Elmhurst", "Glenview", "Lombard", "Buffalo Grove",
    "Bartlett", "Crystal Lake", "Plainfield", "Streamwood", "Carol Stream",
    "Romeoville", "Hanover Park", "Carpentersville", "Wheeling", "Park Ridge",
    "Addison", "Calumet City", "Northbrook", "Elk Grove Village", "Oswego",
    "Mundelein", "Gurnee", "Lake in the Hills", "Niles", "St. Charles",
    "Geneva", "Moline", "Belleville", "East St. Louis", "Rockford",
    # Collar counties
    "Joliet", "Kankakee", "Galesburg", "Quincy", "Carbondale",
    "Danville", "Urbana", "Rock Island", "Elgin", "Batavia",
    "North Aurora", "Montgomery", "Oswego", "Yorkville", "Minooka",
    "Shorewood", "Crest Hill", "Lockport", "New Lenox", "Frankfort",
    "Mokena", "Homer Glen", "Lemont", "Woodridge", "Lisle",
    "Westmont", "Darien", "Burr Ridge", "Hinsdale", "LaGrange",
    "Palos Heights", "Orland Hills", "Matteson", "Richton Park", "Homewood",
    "Lansing", "Harvey", "Blue Island", "Oak Forest", "Midlothian",
    "Crestwood", "Alsip", "Worth", "Evergreen Park", "Chicago Ridge",
    # Downstate metro areas
    "Peoria", "East Peoria", "Pekin", "Morton", "Washington",
    "Springfield", "Sherman", "Rochester", "Chatham", "Auburn",
    "Champaign", "Urbana", "Savoy", "Rantoul", "Mahomet",
    "Bloomington", "Normal", "Gibson City", "Pontiac", "Chenoa",
    "Decatur", "Forsyth", "Macon", "Taylorville", "Mount Zion",
    "Moline", "East Moline", "Milan", "Rock Island", "Silvis",
    "Galesburg", "Macomb", "Monmouth", "Kewanee",
    "Belleville", "O'Fallon", "Shiloh", "Collinsville", "Fairview Heights",
    "Edwardsville", "Glen Carbon", "Maryville", "Troy", "Highland",
    "Carbondale", "Marion", "Herrin", "Murphysboro", "West Frankfort",
    "Kankakee", "Bradley", "Bourbonnais", "Manteno", "Momence",
    "Ottawa", "Streator", "Peru", "LaSalle", "Marseilles",
    "Joliet", "Shorewood", "Channahon", "Minooka", "Morris",
    "Elgin", "South Elgin", "Carpentersville", "Hampshire", "Algonquin",
    "Aurora", "Batavia", "Geneva", "St. Charles", "Dundee",
    "Waukegan", "North Chicago", "Lake Forest", "Libertyville", "Gurnee",
    "Alton", "Jerseyville", "Granite City", "Wood River", "Bethalto",
    "Danville", "Hoopeston", "Georgetown", "Catlin",
    "Freeport", "Sterling", "Dixon", "Rochelle", "DeKalb",
    "Sycamore", "Sandwich", "Plano", "Yorkville", "Plano",
    "Jacksonville", "Carlinville", "Litchfield", "Virden", "Staunton",
    "Centralia", "Salem", "Mount Vernon", "Benton", "McLeansboro",
    "Effingham", "Vandalia", "Olney", "Flora", "Lawrenceville",
    "Robinson", "Mattoon", "Charleston", "Paris", "Marshall",
    "Macomb", "Bushnell", "Carthage", "Beardstown",
    "Quincy", "Hannibal", "Pittsfield", "Rushville",
    "Rockford", "Machesney Park", "Loves Park", "Belvidere", "Roscoe",
    "Loves Park", "South Beloit", "Winnebago",
]

# Deduplicate city list while preserving order
seen = set()
CITIES = []
for c in IL_CITIES:
    if c.lower() not in seen:
        seen.add(c.lower())
        CITIES.append(c)

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
    "places.photos",
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
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": f"car dealer {city} Illinois",
        "includedType": "car_dealer",
        "maxResultCount": 20,
    }
    resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("places", [])


# Fetch existing Illinois dealerships to build skip set (by google_place_id)
existing = supabase.table("dealerships") \
    .select("google_place_id") \
    .eq("state", "IL") \
    .execute()

existing_place_ids = {
    row["google_place_id"]
    for row in existing.data
    if row.get("google_place_id")
}
print(f"Found {len(existing_place_ids)} existing IL dealerships in DB\n")
print(f"Sweeping {len(CITIES)} Illinois cities...\n")

total_added   = 0
total_skipped = 0
total_errors  = 0
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
                components = place.get("addressComponents", [])
                p_city, p_state, _ = parse_address_components(components)

                # Only keep dealers whose resolved state is IL
                if p_state and p_state != "IL":
                    total_skipped += 1
                    continue

                record = {
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "IL",
                    "phone":           place.get("nationalPhoneNumber"),
                    "website":         place.get("websiteUri"),
                    "google_rating":   place.get("rating"),
                    "google_reviews":  place.get("userRatingCount"),
                    "photo_count":     len(place.get("photos", [])),
                    "has_recent_posts":     None,
                    "review_response_rate": None,
                    "dealer_group_id": None,
                    "rooftop_status":  "active",
                }

                supabase.table("dealerships").upsert(
                    record, on_conflict="google_place_id"
                ).execute()

                seen_this_run.add(place_id)
                city_added += 1
                total_added += 1

            except Exception as e:
                name = place.get("displayName", {}).get("text", "?")
                print(f"    Skipped {name}: {e}")
                total_errors += 1

        print(f"  [{i}/{len(CITIES)}] {city}: +{city_added} new dealers")

    except Exception as e:
        print(f"  ERROR [{city}]: {e}")
        total_errors += 1

    time.sleep(API_DELAY)

print(
    f"\nIllinois city-sweep complete.\n"
    f"  {total_added} new dealers added\n"
    f"  {total_skipped} already in DB (skipped)\n"
    f"  {total_errors} errors"
)

result = supabase.table("dealerships").select("id", count="exact").eq("state", "IL").execute()
print(f"  Total IL dealerships in DB: {result.count}")
