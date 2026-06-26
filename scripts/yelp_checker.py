"""
Check Yelp Fusion API for dealership ratings and review counts.

For each dealership in recent high-confidence opportunities, searches
Yelp for the business. If rating < 3.5 OR review_count < 20,
creates a weak_digital opportunity.

Requires YELP_API_KEY environment variable (free at yelp.com/developers,
500 req/day on free tier).
"""

from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
import requests
import time
import os

load_dotenv()

print("DealerHunters Yelp checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
YELP_API_KEY = os.environ.get("YELP_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
if not YELP_API_KEY:
    print("Missing YELP_API_KEY — skipping Yelp check.")
    raise SystemExit(0)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

LOOKBACK         = 30
RATING_THRESHOLD = 3.5
REVIEW_THRESHOLD = 20
API_DELAY        = 1
YELP_SEARCH_URL  = "https://api.yelp.com/v3/businesses/search"
HEADERS          = {"Authorization": f"Bearer {YELP_API_KEY}"}


def search_yelp(name: str, city: str, state: str) -> dict | None:
    location = f"{city}, {state}".strip(", ") if (city or state) else "United States"
    try:
        resp = requests.get(
            YELP_SEARCH_URL,
            headers=HEADERS,
            params={
                "term":       name,
                "location":   location,
                "categories": "auto,dealers",
                "limit":      1,
            },
            timeout=10,
        )
        if resp.status_code == 429:
            print("  Yelp rate-limited — pausing 30s")
            time.sleep(30)
            return None
        resp.raise_for_status()
        businesses = resp.json().get("businesses", [])
        return businesses[0] if businesses else None
    except Exception as e:
        print(f"  Yelp API error: {e}")
        return None


since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK)).isoformat()

recent = (
    supabase.table("opportunities")
    .select("dealership_name, city, state, confidence_score")
    .gte("created_at", since)
    .gte("confidence_score", 75)
    .neq("opportunity_type", "weak_digital")
    .execute()
)

seen     = set()
to_check = []
for row in recent.data:
    name = (row.get("dealership_name") or "").strip()
    if name and name not in seen:
        seen.add(name)
        to_check.append(row)

print(f"Found {len(to_check)} dealerships from last {LOOKBACK} days\n")

if not to_check:
    print("Nothing to check — exiting.")
    raise SystemExit(0)

checked = 0
flagged = 0
good    = 0
errors  = 0

for dealer in to_check:
    name  = dealer["dealership_name"]
    city  = dealer.get("city")  or ""
    state = dealer.get("state") or ""
    label = f"{name} ({city}, {state})" if (city or state) else name

    print(f"Checking: {label}")

    existing = (
        supabase.table("opportunities")
        .select("id")
        .eq("dealership_name", name)
        .eq("opportunity_type", "weak_digital")
        .execute()
    )
    if existing.data:
        print("  Already has weak_digital opportunity — skipping")
        checked += 1
        continue

    biz = search_yelp(name, city, state)
    time.sleep(API_DELAY)

    if biz is None:
        print("  Not found on Yelp — skipping")
        errors  += 1
        checked += 1
        continue

    rating  = biz.get("rating", 0)
    reviews = biz.get("review_count", 0)
    print(f"  Yelp: {rating}★ / {reviews} reviews")

    if rating >= RATING_THRESHOLD and reviews >= REVIEW_THRESHOLD:
        good    += 1
        checked += 1
        continue

    reasons = []
    if rating < RATING_THRESHOLD:  reasons.append(f"{rating}★ rating")
    if reviews < REVIEW_THRESHOLD: reasons.append(f"only {reviews} reviews")
    reason_str = " and ".join(reasons)

    record = {
        "dealership_name":  name,
        "city":             city or None,
        "state":            state or None,
        "opportunity_type": "weak_digital",
        "signal_type":      "weak_digital",
        "fit_score":        80,
        "confidence_score": 80,
        "status":           "new",
        "source_name":      "Yelp",
        "ai_summary": (
            f"{name} has a {rating}★ Yelp rating with only {reviews} reviews. "
            f"Poor Yelp presence costs dealerships an estimated 15–20% of potential "
            f"walk-in traffic as car shoppers check reviews before visiting."
        ),
        "suggested_pitch": (
            f"CR Advertising can help build {name}'s Yelp reputation through a "
            f"targeted review generation campaign alongside their digital advertising "
            f"strategy. More reviews + higher rating = more showroom traffic."
        ),
    }

    supabase.table("opportunities").insert(record).execute()
    print(f"  → Flagged ({reason_str}) — inserted weak_digital opportunity")
    flagged += 1
    checked += 1

print(
    f"\nYelp check complete. "
    f"{checked} checked | "
    f"{flagged} weak_digital opportunities created | "
    f"{good} scored well | "
    f"{errors} not found / errors"
)
