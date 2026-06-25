"""
Check the Meta Ads Library for active dealer ads.

Uses Playwright (headless Chromium) to load the public Ads Library search page,
which requires JavaScript execution to pass Facebook's bot challenge and render
React results. No Meta API token or authentication needed.

No ads found → insert weak_digital opportunity.
Ads found → skip (dealer is already advertising on Facebook/Instagram).
"""

from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
import urllib.parse
import time
import os

load_dotenv()

print("DealerHunters Meta Ads checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase  = create_client(SUPABASE_URL, SUPABASE_KEY)
LOOKBACK  = 30   # days back to scan for recent opportunities
PAGE_WAIT = 3000 # ms to wait after networkidle for React to finish rendering

NO_ADS_PHRASES = [
    "no ads match your search",
    "no results found",
    "0 ads match",
]


def check_active_ads(page, dealership_name: str) -> bool | None:
    """
    Navigate to the Ads Library search for dealership_name.
    Returns True if active ads were found, False if none, None on error.
    """
    url = (
        "https://www.facebook.com/ads/library/"
        "?active_status=active&ad_type=all&country=US"
        f"&q={urllib.parse.quote(dealership_name)}&search_type=keyword_unordered"
    )
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(PAGE_WAIT)
        content = page.content()

        for phrase in NO_ADS_PHRASES:
            if phrase in content.lower():
                return False

        if "adArchiveID" in content or "ad_archive_id" in content:
            return True

        return None  # inconclusive — page loaded but neither signal found

    except Exception as e:
        print(f"  Browser error: {e}")
        return None


# ── Gather unique dealerships from recent opportunities ──────────────────────
since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK)).isoformat()

recent = supabase.table("opportunities") \
    .select("dealership_name, city, state, confidence_score") \
    .gte("created_at", since) \
    .gte("confidence_score", 80) \
    .neq("opportunity_type", "weak_digital") \
    .execute()

seen = set()
dealerships = []
for row in recent.data:
    name = (row.get("dealership_name") or "").strip()
    if name and name not in seen:
        seen.add(name)
        dealerships.append(row)

print(f"Found {len(dealerships)} high-confidence dealerships (score ≥ 80) from the last {LOOKBACK} days\n")

if not dealerships:
    print("Nothing to check — exiting.")
    exit(0)

checked            = 0
weak_digital_added = 0
ads_running        = 0
errors             = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/Chicago",
    )
    page = ctx.new_page()

    for dealer in dealerships:
        name  = dealer["dealership_name"]
        city  = dealer.get("city")  or ""
        state = dealer.get("state") or ""
        label = f"{name} ({city}, {state})" if (city or state) else name

        print(f"Checking: {label}")

        # Skip if a weak_digital opportunity already exists for this dealer
        existing = supabase.table("opportunities") \
            .select("id") \
            .eq("dealership_name", name) \
            .eq("opportunity_type", "weak_digital") \
            .execute()

        if existing.data:
            print("  Already has weak_digital opportunity — skipping")
            checked += 1
            continue

        ads_found = check_active_ads(page, name)
        time.sleep(3)

        if ads_found is None:
            print("  Inconclusive (page loaded but no clear signal) — skipping")
            errors += 1
        elif ads_found:
            print("  Active ads found — no signal needed")
            ads_running += 1
        else:
            record = {
                "dealership_name":  name,
                "city":             city or None,
                "state":            state or None,
                "opportunity_type": "weak_digital",
                "fit_score":        82,
                "status":           "new",
                "source_name":      "Meta Ad Library",
                "ai_summary": (
                    f"{name} has zero active ads in the Meta Ad Library "
                    "(Facebook/Instagram). This dealership is not running "
                    "any paid social advertising."
                ),
                "pitch_angle": (
                    "Pitch a Meta advertising package — this dealer has no active "
                    "social ads and is invisible to in-market shoppers on Facebook "
                    "and Instagram."
                ),
            }
            supabase.table("opportunities").insert(record).execute()
            print("  → 0 active ads — inserted weak_digital opportunity")
            weak_digital_added += 1

        checked += 1

    browser.close()

print(
    f"\nMeta Ads check complete. "
    f"{checked} checked | "
    f"{weak_digital_added} weak_digital opportunities created | "
    f"{ads_running} already running ads | "
    f"{errors} inconclusive"
)
