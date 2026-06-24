from supabase import create_client
import os

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

opportunities = [
    {
        "dealership_name": "Cedar Valley Ford",
        "city": "Waterloo",
        "state": "IA",
        "signal_type": "Ownership Change",
        "source_name": "DealerHunters Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "Ownership change may create marketing vendor review opportunities.",
        "pitch_angle": "Grand reopening campaign",
        "confidence_score": 95,
        "status": "new"
    },
    {
        "dealership_name": "Midwest Honda",
        "city": "Minneapolis",
        "state": "MN",
        "signal_type": "Marketing Hire",
        "source_name": "DealerHunters Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "New marketing leader may be evaluating agency and advertising partners.",
        "pitch_angle": "90-day traffic generation plan",
        "confidence_score": 88,
        "status": "new"
    }
]

for opp in opportunities:
    existing = (
        supabase.table("opportunities")
        .select("id")
        .eq("dealership_name", opp["dealership_name"])
        .execute()
    )

    if existing.data:
        print(f"Already exists: {opp['dealership_name']}")
        continue

    supabase.table("opportunities").insert(opp).execute()
    print(f"Inserted: {opp['dealership_name']}")

print("Opportunity seeding complete")
