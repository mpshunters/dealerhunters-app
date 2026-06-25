from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

print("DealerHunters Google presence checker starting...")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Thresholds for weak Google presence (photo_count excluded — Places API caps at 10)
RATING_THRESHOLD  = 4.0
REVIEWS_THRESHOLD = 50

dealers = supabase.table("dealerships") \
    .select("dealership_name, city, state, google_rating, google_reviews") \
    .execute()

print(f"Evaluating {len(dealers.data)} dealerships for weak Google presence\n")

flagged          = 0
skipped_no_data  = 0
skipped_existing = 0

for dealer in dealers.data:
    name = (dealer.get("dealership_name") or "").strip()
    if not name:
        continue

    rating  = dealer.get("google_rating")
    reviews = dealer.get("google_reviews")

    # Skip if no Google data at all
    if rating is None and reviews is None:
        skipped_no_data += 1
        continue

    # Determine if any threshold is breached
    reasons = []
    if rating is not None and rating < RATING_THRESHOLD:
        reasons.append(f"Google rating {rating}/5 (below {RATING_THRESHOLD})")
    if reviews is not None and reviews < REVIEWS_THRESHOLD:
        reasons.append(f"only {reviews} Google reviews (below {REVIEWS_THRESHOLD})")

    if not reasons:
        continue

    # Skip if a weak_digital opportunity already exists for this dealer
    existing = supabase.table("opportunities") \
        .select("id") \
        .eq("dealership_name", name) \
        .eq("opportunity_type", "weak_digital") \
        .execute()

    if existing.data:
        skipped_existing += 1
        continue

    city  = dealer.get("city")  or None
    state = dealer.get("state") or None
    reason_str = "; ".join(reasons)

    record = {
        "dealership_name":      name,
        "city":                 city,
        "state":                state,
        "opportunity_type":     "weak_digital",
        "fit_score":            78,
        "status":               "new",
        "source_name":          "Google Business Profile",
        "ai_summary": (
            f"{name} has a weak digital presence on Google: {reason_str}. "
            "This dealership is underinvesting in its online profile and losing "
            "in-market shoppers to better-reviewed competitors."
        ),
        "pitch_angle": (
            f"Pitch a Google reputation and visibility package — {reason_str}. "
            "A targeted campaign to drive reviews and showcase inventory can "
            "quickly close the gap against local competitors."
        ),
    }

    supabase.table("opportunities").insert(record).execute()
    label = f"{name} ({city}, {state})" if (city or state) else name
    print(f"  → Flagged: {label} | {reason_str}")
    flagged += 1

print(
    f"\nGoogle presence check complete. "
    f"{flagged} weak_digital opportunities created | "
    f"{skipped_existing} already had weak_digital record | "
    f"{skipped_no_data} skipped (no Google data)"
)
