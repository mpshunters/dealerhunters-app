from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
import requests
import os
import time

load_dotenv()

print("DealerHunters Meta Ads checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
META_TOKEN   = os.environ.get("META_ADS_API_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

if not META_TOKEN:
    raise Exception(
        "Missing META_ADS_API_TOKEN — get a free token at "
        "https://developers.facebook.com (create an app, then generate a "
        "User Access Token with ads_read permission)"
    )

supabase    = create_client(SUPABASE_URL, SUPABASE_KEY)
META_URL    = "https://graph.facebook.com/v21.0/ads_archive"
LOOKBACK    = 30   # days back to scan for recent opportunities
API_DELAY   = 1.2  # seconds between requests to avoid rate limits


def check_active_ads(dealership_name: str) -> dict:
    """Return active Meta ad count for a dealership. Returns None on API error."""
    params = {
        "search_terms":         dealership_name,
        "ad_type":              "ALL",
        "ad_active_status":     "ACTIVE",
        "ad_reached_countries": '["US"]',
        "fields":               "id,page_name,ad_delivery_start_time",
        "access_token":         META_TOKEN,
        "limit":                25,
    }
    try:
        resp = requests.get(META_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise ValueError(data["error"].get("message", "Unknown Meta API error"))
        ads = data.get("data", [])
        return {"ad_count": len(ads), "ads_found": len(ads) > 0}
    except Exception as e:
        print(f"  Meta API error: {e}")
        return None


# ── Gather unique dealerships from recent opportunities ──────────────────────
since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK)).isoformat()

recent = supabase.table("opportunities") \
    .select("dealership_name, city, state") \
    .gte("created_at", since) \
    .neq("opportunity_type", "weak_digital") \
    .execute()

seen = set()
dealerships = []
for row in recent.data:
    name = (row.get("dealership_name") or "").strip()
    if name and name not in seen:
        seen.add(name)
        dealerships.append(row)

print(f"Found {len(dealerships)} unique dealerships from the last {LOOKBACK} days\n")

checked             = 0
weak_digital_added  = 0
ads_running         = 0
errors              = 0

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
        print(f"  Already has weak_digital opportunity — skipping")
        checked += 1
        time.sleep(API_DELAY)
        continue

    result = check_active_ads(name)
    time.sleep(API_DELAY)

    if result is None:
        errors += 1
        checked += 1
        continue

    ad_count  = result["ad_count"]
    ads_found = result["ads_found"]

    if not ads_found:
        record = {
            "dealership_name":  name,
            "city":             city or None,
            "state":            state or None,
            "opportunity_type": "weak_digital",
            "fit_score":        82,
            "status":           "new",
            "source_name":      "Meta Ad Library",
            "ai_summary":       (
                f"{name} has zero active ads in the Meta Ad Library (Facebook/Instagram). "
                "This dealership is not currently running any paid social advertising."
            ),
            "pitch_angle":      (
                "Pitch a Meta advertising package — this dealer has no active social ads "
                "and is invisible to in-market shoppers on Facebook and Instagram."
            ),
        }
        supabase.table("opportunities").insert(record).execute()
        print(f"  → 0 active ads — inserted weak_digital opportunity")
        weak_digital_added += 1
    else:
        print(f"  → {ad_count} active ad(s) found — no signal needed")
        ads_running += 1

    checked += 1

print(
    f"\nMeta Ads check complete. "
    f"{checked} checked | "
    f"{weak_digital_added} weak_digital opportunities created | "
    f"{ads_running} already running ads | "
    f"{errors} API errors"
)
