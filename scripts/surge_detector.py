import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

now = datetime.now(timezone.utc)
window_7d  = (now - timedelta(days=7)).isoformat()
window_30d = (now - timedelta(days=30)).isoformat()

print("Surge detector starting...")

# Pull all raw signals from last 30 days that have a linked opportunity
signals_30d = (
    supabase.table("raw_signals")
    .select("id, title, created_at, source_name")
    .gte("created_at", window_30d)
    .execute()
).data

# Pull all opportunities with dealership_name
opps = (
    supabase.table("opportunities")
    .select("id, dealership_name, surge_detected, confidence_score")
    .execute()
).data

surged = 0
checked = 0

for opp in opps:
    name = (opp.get("dealership_name") or "").strip().lower()
    if not name:
        continue

    checked += 1

    # Count mentions in last 7d and prior 30d for this dealership
    matches_7d  = [s for s in signals_30d if name in (s.get("title") or "").lower() and s["created_at"] >= window_7d]
    matches_30d = [s for s in signals_30d if name in (s.get("title") or "").lower()]

    count_7d  = len(matches_7d)
    count_30d = len(matches_30d)

    # Daily rates: 7d window vs prior 23d (30d minus 7d)
    rate_7d    = count_7d / 7
    prior_23d  = count_30d - count_7d
    rate_prior = prior_23d / 23 if prior_23d > 0 else 0

    # Velocity = ratio of recent rate vs baseline (floor at 1 to avoid div-by-zero)
    baseline  = max(rate_prior, 1 / 23)
    velocity  = rate_7d / baseline

    is_surge = velocity >= 2.0 and count_7d >= 2

    updates = {
        "mention_velocity": round(velocity, 2),
        "surge_detected": is_surge,
    }

    if is_surge:
        # Boost confidence by 8, capped at 100
        current_conf = opp.get("confidence_score") or 0
        updates["confidence_score"] = min(100, current_conf + 8)
        surged += 1
        print(f"Surge detected: {opp['dealership_name']} — velocity {velocity:.1f}x ({count_7d} mentions in 7d)")

    supabase.table("opportunities").update(updates).eq("id", opp["id"]).execute()

print(f"\nDone. Checked {checked} opportunities, {surged} surges detected.")
