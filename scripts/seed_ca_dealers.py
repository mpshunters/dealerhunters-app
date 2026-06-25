"""
Seed California motor vehicle dealers via Google Places API city sweep.
California is the #1 US auto market by new vehicle registrations (~2M/yr).
Sweeps ~200 cities; deduplicates by google_place_id; only keeps state=CA.
"""

from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import os

load_dotenv()

print("DealerHunters California city-sweep seeder starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_PLACES_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CA_CITIES = [
    # LA metro
    "Los Angeles", "Long Beach", "Anaheim", "Santa Ana", "Irvine",
    "Glendale", "Huntington Beach", "Santa Clarita", "Garden Grove", "Oceanside",
    "Rancho Cucamonga", "Ontario", "Lancaster", "Palmdale", "Pomona",
    "Escondido", "Torrance", "Pasadena", "Orange", "Fullerton",
    "Corona", "Thousand Oaks", "Simi Valley", "Victorville", "El Monte",
    "Downey", "Costa Mesa", "Inglewood", "Carlsbad", "West Covina",
    "Norwalk", "Burbank", "Murrieta", "El Cajon", "Rialto",
    "South Gate", "Vista", "Compton", "Carson", "Westminster",
    "Jurupa Valley", "Temecula", "Santa Monica", "Whittier", "Santa Maria",
    "Hawthorne", "Lakewood", "Alhambra", "Buena Park", "Hemet",
    "San Bernardino", "Fontana", "Moreno Valley", "Riverside",
    "Chula Vista", "Oxnard", "Ventura", "Camarillo", "Santa Barbara",
    "San Luis Obispo", "Bakersfield", "Visalia",
    # LA suburbs (San Gabriel / San Fernando valleys)
    "Burbank", "Glendale", "Pasadena", "Monrovia", "Arcadia",
    "El Monte", "Baldwin Park", "Covina", "West Covina", "Azusa",
    "Glendora", "San Dimas", "La Verne", "Pomona", "Chino",
    "Chino Hills", "Upland", "Montclair", "Ontario", "Rancho Cucamonga",
    "San Fernando", "Van Nuys", "Canoga Park", "Chatsworth", "Northridge",
    "Reseda", "North Hollywood", "Studio City", "Sherman Oaks", "Encino",
    # Inland Empire
    "Riverside", "San Bernardino", "Fontana", "Moreno Valley", "Ontario",
    "Rancho Cucamonga", "Chino", "Chino Hills", "Rialto", "Colton",
    "Redlands", "Yucaipa", "Beaumont", "Banning", "Palm Springs",
    "Palm Desert", "Cathedral City", "Indio", "Coachella", "Victorville",
    "Apple Valley", "Hesperia", "Adelanto", "Barstow", "Twentynine Palms",
    # Orange County
    "Anaheim", "Santa Ana", "Irvine", "Orange", "Fullerton",
    "Garden Grove", "Huntington Beach", "Costa Mesa", "Westminster", "Buena Park",
    "Tustin", "Lake Forest", "Mission Viejo", "Aliso Viejo", "Laguna Niguel",
    "Dana Point", "San Clemente", "Laguna Hills", "Rancho Santa Margarita",
    "Yorba Linda", "Placentia", "Brea", "La Habra", "Cypress", "Stanton",
    # San Diego metro
    "San Diego", "Chula Vista", "El Cajon", "Escondido", "Oceanside",
    "Carlsbad", "Vista", "San Marcos", "Santee", "Poway",
    "La Mesa", "National City", "Spring Valley", "El Cajon", "Lemon Grove",
    "Encinitas", "Solana Beach", "Del Mar", "La Jolla",
    "Mission Valley", "Kearny Mesa",
    # Bay Area
    "San Jose", "San Francisco", "Oakland", "Fremont", "Santa Rosa",
    "Sunnyvale", "Concord", "Hayward", "Berkeley", "Richmond",
    "Antioch", "Daly City", "San Mateo", "Livermore", "Fairfield",
    "Vacaville", "Vallejo", "Napa", "Petaluma", "Rohnert Park",
    "Santa Cruz", "Watsonville", "Salinas", "Monterey", "Seaside",
    "Morgan Hill", "Gilroy", "Los Gatos", "Campbell", "Milpitas",
    "Santa Clara", "Cupertino", "Mountain View", "Palo Alto", "Redwood City",
    "San Mateo", "Burlingame", "South San Francisco", "San Bruno", "Foster City",
    "Walnut Creek", "Danville", "San Ramon", "Pleasanton", "Dublin",
    "Union City", "Newark", "San Leandro", "Alameda", "Emeryville",
    "Pinole", "Hercules", "Martinez", "Pittsburg", "Brentwood",
    # Sacramento metro
    "Sacramento", "Elk Grove", "Roseville", "Folsom", "Citrus Heights",
    "Rancho Cordova", "West Sacramento", "Davis", "Woodland", "Yuba City",
    "Marysville", "Auburn", "Lincoln", "Rocklin", "Granite Bay",
    "Lodi", "Stockton", "Modesto", "Turlock", "Merced",
    # Central Valley
    "Fresno", "Bakersfield", "Visalia", "Clovis", "Tulare",
    "Hanford", "Porterville", "Dinuba", "Reedley", "Selma",
    "Madera", "Merced", "Atwater", "Los Banos", "Chowchilla",
    "Stockton", "Modesto", "Turlock", "Ceres", "Manteca",
    "Tracy", "Lodi", "Pittsburg", "Antioch",
    # North / Far North
    "Redding", "Chico", "Oroville", "Paradise", "Red Bluff",
    "Eureka", "Arcata", "Ukiah",
]

seen_cities: set[str] = set()
CITIES = []
for c in CA_CITIES:
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
        json={"textQuery": f"car dealer {city} California", "includedType": "car_dealer", "maxResultCount": 20},
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


existing = supabase.table("dealerships").select("google_place_id").eq("state", "CA").execute()
seen_ids: set[str] = {r["google_place_id"] for r in existing.data if r.get("google_place_id")}
print(f"Found {len(seen_ids)} existing CA dealerships in DB\n")
print(f"Sweeping {len(CITIES)} California cities...\n")

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
                if p_state and p_state != "CA":
                    total_skipped += 1
                    continue
                supabase.table("dealerships").upsert({
                    "google_place_id": place_id,
                    "dealership_name": place.get("displayName", {}).get("text", ""),
                    "city":            p_city,
                    "state":           p_state or "CA",
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

print(f"\nCalifornia sweep complete.\n  {total_added} added | {total_skipped} skipped | {total_errors} errors")
result = supabase.table("dealerships").select("id", count="exact").eq("state", "CA").execute()
print(f"  Total CA dealerships in DB: {result.count}")
