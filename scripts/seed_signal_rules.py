from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

print("DealerHunters signal rule seeding starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

# weight 1 = generic term, 2 = moderately specific, 3 = highly specific to dealers
rules = [
    # --- ownership_change ---
    {
        "rule_name": "ownership_change_high",
        "signal_type": "ownership_change",
        "keywords": ["new dealer principal", "under new ownership"],
        "fit_score": 3,
        "active": True,
    },
    {
        "rule_name": "ownership_change_mid",
        "signal_type": "ownership_change",
        "keywords": ["new owner", "acquired", "acquisition", "new GM", "sold to"],
        "fit_score": 2,
        "active": True,
    },

    # --- new_rooftop ---
    {
        "rule_name": "new_rooftop_high",
        "signal_type": "new_rooftop",
        "keywords": ["new dealership"],
        "fit_score": 3,
        "active": True,
    },
    {
        "rule_name": "new_rooftop_mid",
        "signal_type": "new_rooftop",
        "keywords": ["grand opening", "new location"],
        "fit_score": 2,
        "active": True,
    },
    {
        "rule_name": "new_rooftop_low",
        "signal_type": "new_rooftop",
        "keywords": ["expansion", "opened"],
        "fit_score": 1,
        "active": True,
    },

    # --- hiring ---
    {
        "rule_name": "hiring_high",
        "signal_type": "hiring",
        "keywords": ["marketing director", "BDC manager", "internet manager"],
        "fit_score": 3,
        "active": True,
    },
    {
        "rule_name": "hiring_mid",
        "signal_type": "hiring",
        "keywords": ["digital marketing"],
        "fit_score": 2,
        "active": True,
    },

    # --- oem_event ---
    {
        "rule_name": "oem_event_high",
        "signal_type": "oem_event",
        "keywords": ["model year clearance", "factory incentive"],
        "fit_score": 3,
        "active": True,
    },
    {
        "rule_name": "oem_event_mid",
        "signal_type": "oem_event",
        "keywords": ["buyback", "holiday event"],
        "fit_score": 2,
        "active": True,
    },

    # ── New keywords ──────────────────────────────────────────────────────────

    # ownership_change
    {
        "rule_name": "ownership_change_high_v2",
        "signal_type": "ownership_change",
        "keywords": ["changes hands", "new ownership", "new principal"],
        "fit_score": 3,
        "active": True,
    },
    {
        "rule_name": "ownership_change_mid_v2",
        "signal_type": "ownership_change",
        "keywords": ["family sold", "dealer group acquires", "announces acquisition", "purchased by", "sold its"],
        "fit_score": 2,
        "active": True,
    },

    # hiring
    {
        "rule_name": "hiring_high_v2",
        "signal_type": "hiring",
        "keywords": ["sales manager", "finance manager", "general sales manager",
                     "fixed ops director", "service director", "parts manager"],
        "fit_score": 3,
        "active": True,
    },

    # oem_event
    {
        "rule_name": "oem_event_mid_v2",
        "signal_type": "oem_event",
        "keywords": ["year-end clearance", "model year end", "summer sales event",
                     "presidents day sale", "black friday", "end of year event"],
        "fit_score": 2,
        "active": True,
    },

    # new_rooftop / expansion
    {
        "rule_name": "new_rooftop_mid_v2",
        "signal_type": "new_rooftop",
        "keywords": ["second location", "third location", "new facility",
                     "ground breaking", "ribbon cutting", "new store"],
        "fit_score": 2,
        "active": True,
    },
]

inserted = 0
skipped = 0

for rule in rules:
    existing = (
        supabase.table("signal_rules")
        .select("id")
        .eq("rule_name", rule["rule_name"])
        .execute()
    )

    if existing.data:
        print(f"Already exists: {rule['rule_name']}")
        skipped += 1
        continue

    supabase.table("signal_rules").insert(rule).execute()
    keyword_count = len(rule["keywords"])
    print(f"Inserted: {rule['rule_name']} ({keyword_count} keywords, weight {rule['fit_score']})")
    inserted += 1

total_keywords = sum(len(r["keywords"]) for r in rules)
print(f"\nDone. {inserted} rules inserted, {skipped} skipped. {total_keywords} total keywords across all rules.")
