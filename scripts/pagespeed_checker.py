"""
Check Google PageSpeed Insights scores for dealership websites.

Pulls recent high-confidence opportunities that have a website URL,
calls the free PageSpeed Insights API v5 (no API key required for
basic usage), and flags dealers with poor mobile scores as weak_digital.

Score thresholds:
  < 50 → Poor   (insert weak_digital opportunity)
  50–89 → Needs improvement (skip — not critical enough)
  90+  → Good (skip)
"""

from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
import requests
import time
import os
import re

load_dotenv()

print("DealerHunters PageSpeed checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
# Optional — increases rate limit from 25 req/100s to 400 req/100s
GOOGLE_API_KEY = os.environ.get("GOOGLE_PAGESPEED_API_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

LOOKBACK          = 30    # days back to consider
SCORE_POOR        = 50    # flag anything below this
API_DELAY         = 3     # seconds between API calls
PSI_URL           = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def get_pagespeed_score(url: str) -> int | None:
    """Return mobile performance score (0–100), or None on error."""
    params = {
        "url":      url,
        "strategy": "mobile",
        "category": "performance",
    }
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY

    try:
        resp = requests.get(PSI_URL, params=params, timeout=30)
        resp.raise_for_status()
        data  = resp.json()
        score = data.get("lighthouseResult", {}) \
                    .get("categories", {}) \
                    .get("performance", {}) \
                    .get("score")
        if score is None:
            return None
        return round(score * 100)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("  Rate limited by PageSpeed API — pausing 30s")
            time.sleep(30)
        else:
            print(f"  PageSpeed API error {e.response.status_code}: {e}")
        return None
    except Exception as e:
        print(f"  PageSpeed error: {e}")
        return None


def clean_website(raw: str) -> str | None:
    raw = raw.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    # strip query strings and trailing slashes
    return re.sub(r"[?#].*$", "", raw).rstrip("/")


# ── Gather unique dealerships with websites from recent opportunities ─────────
since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK)).isoformat()

recent = supabase.table("opportunities") \
    .select("dealership_name, city, state, website, confidence_score") \
    .gte("created_at", since) \
    .gte("confidence_score", 75) \
    .neq("opportunity_type", "weak_digital") \
    .execute()

seen          = set()
to_check      = []
for row in recent.data:
    name    = (row.get("dealership_name") or "").strip()
    website = row.get("website") or ""
    if name and website and name not in seen:
        seen.add(name)
        to_check.append(row)

print(f"Found {len(to_check)} dealerships with websites from last {LOOKBACK} days\n")

if not to_check:
    print("Nothing to check — exiting.")
    raise SystemExit(0)

checked   = 0
flagged   = 0
good      = 0
errors    = 0

for dealer in to_check:
    name    = dealer["dealership_name"]
    city    = dealer.get("city")  or ""
    state   = dealer.get("state") or ""
    website = clean_website(dealer.get("website", ""))
    label   = f"{name} ({city}, {state})" if (city or state) else name

    if not website:
        continue

    print(f"Checking: {label} — {website}")

    # Skip if weak_digital opportunity already exists for this dealer
    existing = supabase.table("opportunities") \
        .select("id") \
        .eq("dealership_name", name) \
        .eq("opportunity_type", "weak_digital") \
        .execute()

    if existing.data:
        print("  Already has weak_digital opportunity — skipping")
        checked += 1
        continue

    score = get_pagespeed_score(website)
    time.sleep(API_DELAY)

    if score is None:
        print("  Could not retrieve score — skipping")
        errors += 1
        checked += 1
        continue

    print(f"  Mobile score: {score}/100")

    if score >= SCORE_POOR:
        good += 1
        checked += 1
        continue

    # Poor score — create weak_digital signal
    record = {
        "dealership_name":  name,
        "city":             city or None,
        "state":            state or None,
        "opportunity_type": "weak_digital",
        "signal_type":      "weak_digital",
        "fit_score":        85,
        "confidence_score": 85,
        "status":           "new",
        "source_name":      "Google PageSpeed Insights",
        "website":          website,
        "ai_summary": (
            f"{name}'s website scores {score}/100 on Google PageSpeed Insights "
            f"(mobile). A score below 50 means slow load times, poor Core Web Vitals, "
            f"and significant loss of in-market shoppers who bounce before the page loads. "
            f"Dealers with slow websites lose an estimated 53% of mobile visitors."
        ),
        "suggested_pitch": (
            f"CR Advertising can pair a performance-optimized landing page with targeted "
            f"paid search campaigns, capturing the in-market buyers currently bouncing off "
            f"{name}'s slow site. Fast landing pages + Google Ads = lower cost-per-lead."
        ),
    }

    supabase.table("opportunities").insert(record).execute()
    print(f"  → Score {score} < {SCORE_POOR} — inserted weak_digital opportunity")
    flagged  += 1
    checked  += 1

print(
    f"\nPageSpeed check complete. "
    f"{checked} checked | "
    f"{flagged} weak_digital opportunities created | "
    f"{good} scored well | "
    f"{errors} errors"
)
