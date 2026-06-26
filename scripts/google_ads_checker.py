"""
Check Google Ads Transparency Center for active dealer search campaigns.

For each dealership in recent high-confidence opportunities, searches
Google for: site:adstransparency.google.com "[dealership name]"

No results found → dealer has no detected Google Ads presence →
insert a weak_digital opportunity.

Uses requests + BeautifulSoup with realistic headers and 3-second delays
to avoid rate limiting. Skips dealers that already have a weak_digital
opportunity.
"""

from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import requests
import time
import random
import os

load_dotenv()

print("DealerHunters Google Ads Transparency checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

LOOKBACK   = 30
API_DELAY  = 3   # seconds between Google searches (be polite)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def check_google_ads(dealership_name: str) -> bool | None:
    """
    Search Google for dealer on adstransparency.google.com.
    Returns True if ads found, False if none, None if blocked/inconclusive.
    """
    query = f'site:adstransparency.google.com "{dealership_name}"'
    url   = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)

        # Google sometimes returns 429 when rate-limited
        if resp.status_code == 429:
            print("  Google rate-limited — pausing 60s")
            time.sleep(60)
            return None

        if resp.status_code != 200:
            print(f"  Google returned {resp.status_code} — skipping")
            return None

        soup = resp.soup if hasattr(resp, 'soup') else BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()

        # Google shows "did not match any documents" or "No results found" for 0 results
        no_result_phrases = [
            "did not match any documents",
            "no results found for",
            "no results found",
            "your search did not match",
        ]
        for phrase in no_result_phrases:
            if phrase in text:
                return False

        # Check if adstransparency.google.com appears in result links
        links = soup.find_all("a", href=True)
        for link in links:
            if "adstransparency.google.com" in link["href"]:
                return True

        # Check for result count text indicating hits
        if "adstransparency.google.com" in text:
            return True

        return None  # inconclusive

    except requests.exceptions.Timeout:
        print("  Request timed out — skipping")
        return None
    except Exception as e:
        print(f"  Error checking Google Ads: {e}")
        return None


# ── Gather dealerships from recent high-confidence opportunities ──────────────
since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK)).isoformat()

recent = supabase.table("opportunities") \
    .select("dealership_name, city, state, website, confidence_score") \
    .gte("created_at", since) \
    .gte("confidence_score", 80) \
    .neq("opportunity_type", "weak_digital") \
    .execute()

seen     = set()
to_check = []
for row in recent.data:
    name = (row.get("dealership_name") or "").strip()
    if name and name not in seen:
        seen.add(name)
        to_check.append(row)

print(f"Found {len(to_check)} dealerships from last {LOOKBACK} days (score ≥ 80)\n")

if not to_check:
    print("Nothing to check — exiting.")
    raise SystemExit(0)

checked   = 0
flagged   = 0
ads_found = 0
skipped   = 0
errors    = 0

for dealer in to_check:
    name  = dealer["dealership_name"]
    city  = dealer.get("city")  or ""
    state = dealer.get("state") or ""
    label = f"{name} ({city}, {state})" if (city or state) else name

    print(f"Checking: {label}")

    # Skip if weak_digital opportunity already exists for this dealer
    existing = supabase.table("opportunities") \
        .select("id") \
        .eq("dealership_name", name) \
        .eq("opportunity_type", "weak_digital") \
        .execute()

    if existing.data:
        print("  Already has weak_digital opportunity — skipping")
        skipped += 1
        checked += 1
        continue

    has_ads = check_google_ads(name)
    # Randomize delay slightly to appear more human
    time.sleep(API_DELAY + random.uniform(0, 1.5))

    if has_ads is None:
        print("  Inconclusive — skipping")
        errors += 1
    elif has_ads:
        print("  Google Ads detected — no signal needed")
        ads_found += 1
    else:
        # No Google Ads presence found — create weak_digital signal
        city_state = f"{city}, {state}".strip(", ") if (city or state) else "their market"
        franchise  = ""  # not reliably available from opportunities table

        record = {
            "dealership_name":  name,
            "city":             city or None,
            "state":            state or None,
            "opportunity_type": "weak_digital",
            "signal_type":      "weak_digital",
            "fit_score":        80,
            "confidence_score": 80,
            "status":           "new",
            "source_name":      "Google Ads Transparency",
            "ai_summary": (
                f"{name} has no active Google Ads campaigns detected in the "
                f"Google Ads Transparency Center. Dealerships without paid search "
                f"miss high-intent car buyers actively searching for inventory in "
                f"{city_state}."
            ),
            "suggested_pitch": (
                f"CR Advertising can launch targeted Google search campaigns that "
                f"capture in-market buyers searching for dealers in {city_state} — "
                f"typically the highest-converting digital channel for automotive. "
                f"{name} has no paid search presence and is ceding that traffic to "
                f"competitors."
            ),
        }

        supabase.table("opportunities").insert(record).execute()
        print(f"  → No Google Ads detected — inserted weak_digital opportunity")
        flagged += 1

    checked += 1

print(
    f"\nGoogle Ads check complete. "
    f"{checked} checked | "
    f"{flagged} weak_digital opportunities created | "
    f"{ads_found} already running ads | "
    f"{skipped} skipped (existing signal) | "
    f"{errors} inconclusive"
)
