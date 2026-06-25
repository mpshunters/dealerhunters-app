"""
Seed Iowa licensed motor vehicle dealers from the Iowa DOT dealer roster PDF.
Source: https://iowadot.gov/media/1177/download?inline=
Effective: June 1, 2026 | Columns: Name, License#, County, Address, Status

Filters to Active dealers only; excludes powersports/motorsports by name.
Skips any dealership already in DB matched by (dealership_name, city).
"""

from dotenv import load_dotenv
from supabase import create_client
import pdfplumber
import requests
import re
import os

load_dotenv()

print("DealerHunters Iowa DOT dealer seed starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ROSTER_URL = "https://iowadot.gov/media/1177/download?inline="

# Exclude dealers whose names clearly indicate non-auto vehicle types
EXCLUDED_NAME_KEYWORDS = [
    "powersport", "motorsport", "motorcycle", "motor sport",
    "marine", "boat", "rv ", " rv,", "rvs", "trailer",
    "atv", "snowmobile", "golf cart", "mobile home", "manufactured home",
    "salvage", "recycl", "parts only", "powersycle",
]

# Iowa cities that are two or three words — needed to parse addresses correctly
IOWA_MULTI_WORD_CITIES = {
    # 3-word
    "WEST DES MOINES", "NORTH SIOUX CITY",
    # 2-word
    "DES MOINES", "CEDAR RAPIDS", "IOWA CITY", "COUNCIL BLUFFS",
    "SIOUX CITY", "IOWA FALLS", "CEDAR FALLS", "FORT DODGE",
    "MASON CITY", "FORT MADISON", "NORTH LIBERTY", "WEST BRANCH",
    "LE MARS", "CLEAR LAKE", "STORM LAKE", "MOUNT PLEASANT",
    "MOUNT VERNON", "WEST LIBERTY", "LAKE VIEW", "LAKE MILLS",
    "LAKE CITY", "LAKE PARK", "NORTH ENGLISH", "NEW LONDON",
    "NEW HAMPTON", "NEW MARKET", "NEW SHARON", "NEW VIENNA",
    "NEW ALBIN", "NEW HARTFORD", "SAINT ANSGAR", "SAINT CHARLES",
    "SAINT DONATUS", "ROCK RAPIDS", "ROCK VALLEY", "RED OAK",
    "CENTER POINT", "PLEASANT HILL", "PLEASANT VALLEY",
    "WEST UNION", "SPIRIT LAKE", "WEBSTER CITY", "EAGLE GROVE",
    "ELDRIDGE", "COUNCIL BLUFFS", "COLUMBUS JUNCTION",
    "LE CLAIRE", "DE WITT", "EL DORA", "CLARION JUNCTION",
    "MT PLEASANT", "MT VERNON", "MT AYR",
}


def is_excluded(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in EXCLUDED_NAME_KEYWORDS)


def parse_iowa_address(raw: str):
    """
    Parse Iowa DOT address format 'STREET CITY IA ZIP' into components.
    Returns (street, city, zip5) — all strings or None.
    """
    raw = raw.strip()
    m = re.match(r'^(.+?)\s+IA\s+(\d{5})\d*\s*$', raw, re.IGNORECASE)
    if not m:
        return None, None, None

    pre_state = m.group(1).strip().upper()
    zip5      = m.group(2)
    words     = pre_state.split()

    # Try longest city match first (3 words → 2 words → 1 word)
    for n in (3, 2):
        if len(words) >= n + 1:          # need at least one word left for street
            candidate = " ".join(words[-n:])
            if candidate in IOWA_MULTI_WORD_CITIES:
                city   = candidate.title()
                street = " ".join(words[:-n]).title()
                return street, city, zip5

    # Default: single last word is the city
    city   = words[-1].title()
    street = " ".join(words[:-1]).title()
    return street, city, zip5


# ── Download PDF ──────────────────────────────────────────────────────────────
print(f"Downloading Iowa DOT dealer roster from {ROSTER_URL}...")
resp = requests.get(ROSTER_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
resp.raise_for_status()
pdf_bytes = resp.content
print(f"Downloaded {len(pdf_bytes):,} bytes ({len(pdf_bytes) // 1024} KB)\n")

# ── Parse PDF ────────────────────────────────────────────────────────────────
import io
dealers_raw = []

with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    print(f"Parsing {len(pdf.pages)} pages...")
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if not row or not row[0]:
                    continue
                if "Name" in str(row[0]):   # skip header rows
                    continue
                name    = (row[0] or "").strip()
                license_num = (row[1] or "").strip()
                county  = (row[2] or "").strip()
                address = (row[3] or "").strip()
                status  = (row[4] or "").strip() if len(row) > 4 else ""

                if status != "Active":
                    continue
                if not name or is_excluded(name):
                    continue

                street, city, zip5 = parse_iowa_address(address)
                if not city:
                    continue

                dealers_raw.append({
                    "dealership_name": name,
                    "license_number":  license_num,
                    "county":          county,
                    "address":         street,
                    "city":            city,
                    "state":           "IA",
                    "zip":             zip5,
                    "rooftop_status":  "active",
                })

print(f"Parsed {len(dealers_raw)} active auto dealers from roster\n")

# ── Fetch existing dealerships in Iowa to build skip set ─────────────────────
existing = supabase.table("dealerships") \
    .select("dealership_name, city") \
    .eq("state", "IA") \
    .execute()

existing_set = {
    (row["dealership_name"].strip().lower(), (row["city"] or "").strip().lower())
    for row in existing.data
}
print(f"Found {len(existing_set)} existing Iowa dealerships in DB\n")

# ── Upsert loop ───────────────────────────────────────────────────────────────
added   = 0
skipped = 0
errors  = 0
total   = len(dealers_raw)

for i, dealer in enumerate(dealers_raw, 1):
    key = (dealer["dealership_name"].lower(), dealer["city"].lower())

    if key in existing_set:
        skipped += 1
        continue

    record = {
        "dealership_name": dealer["dealership_name"],
        "city":            dealer["city"],
        "state":           "IA",
        "rooftop_status":  "active",
    }

    try:
        supabase.table("dealerships").insert(record).execute()
        existing_set.add(key)   # prevent duplicates within this run
        added += 1
        if added % 50 == 0:
            print(f"  Progress: added {added} new dealers so far ({i}/{total} processed)")
    except Exception as e:
        print(f"  Error inserting {dealer['dealership_name']} ({dealer['city']}): {e}")
        errors += 1

print(
    f"\nIowa DOT seed complete.\n"
    f"  {added} new dealers added\n"
    f"  {skipped} already in DB (skipped)\n"
    f"  {errors} errors\n"
    f"  {total} total active dealers in roster"
)
