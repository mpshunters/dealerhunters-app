from supabase import create_client
import os

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

opportunities = [
    {
        "dealership_name": "Cedar Valley Ford",
        "city": "Waterloo",
        "state": "IA",
        "signal_type": "Ownership Change",
        "opportunity_type": "Direct Mail + Digital",
        "source_name": "DealerHunters Beta Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "Ownership changes often trigger vendor reviews, brand refreshes, and customer reactivation campaigns.",
        "pitch_angle": "Grand reopening campaign with direct mail, email, and digital retargeting.",
        "recommended_offer": "90-day traffic generation campaign",
        "fit_score": 95,
        "confidence_score": 95,
        "status": "new"
    },
    {
        "dealership_name": "Midwest Honda",
        "city": "Minneapolis",
        "state": "MN",
        "signal_type": "Marketing Hire",
        "opportunity_type": "Digital Advertising",
        "source_name": "DealerHunters Beta Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "A new marketing hire may be evaluating vendors, campaigns, and traffic-generation partners.",
        "pitch_angle": "Offer a quick audit and a 90-day digital traffic plan.",
        "recommended_offer": "Digital conquest and retargeting package",
        "fit_score": 88,
        "confidence_score": 88,
        "status": "new"
    },
    {
        "dealership_name": "Prairie Toyota",
        "city": "Des Moines",
        "state": "IA",
        "signal_type": "Poor Review Score",
        "opportunity_type": "Reputation + Digital",
        "source_name": "DealerHunters Beta Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "Lower review ratings can hurt shopper trust and reduce lead conversion.",
        "pitch_angle": "Position CR as a traffic and reputation recovery partner.",
        "recommended_offer": "Reputation recovery and review generation campaign",
        "fit_score": 91,
        "confidence_score": 91,
        "status": "new"
    },
    {
        "dealership_name": "North Star Chevrolet",
        "city": "Rochester",
        "state": "MN",
        "signal_type": "Facility Expansion",
        "opportunity_type": "Direct Mail",
        "source_name": "DealerHunters Beta Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "Facility expansions create local awareness and customer reactivation opportunities.",
        "pitch_angle": "Promote the upgraded facility with a targeted mailer and digital follow-up.",
        "recommended_offer": "Grand reopening direct mail campaign",
        "fit_score": 89,
        "confidence_score": 89,
        "status": "new"
    },
    {
        "dealership_name": "Lakeside CDJR",
        "city": "Madison",
        "state": "WI",
        "signal_type": "Buyback Opportunity",
        "opportunity_type": "Mailer Campaign",
        "source_name": "DealerHunters Beta Seed",
        "source_url": "https://dealerhunters.com",
        "ai_summary": "Buyback campaigns are highly aligned with CR Advertising's direct mail and dealership event experience.",
        "pitch_angle": "Lead with a buyback mailer tied to trade-in demand and digital retargeting.",
        "recommended_offer": "Buyback event mailer campaign",
        "fit_score": 96,
        "confidence_score": 96,
        "status": "new"
    }
]

inserted = 0

for opp in opportunities:
    existing = supabase.table("opportunities") \
        .select("id") \
        .eq("dealership_name", opp["dealership_name"]) \
        .execute()

    if existing.data:
        print(f"Already exists: {opp['dealership_name']}")
        continue

    supabase.table("opportunities").insert(opp).execute()
    inserted += 1
    print(f"Inserted: {opp['dealership_name']}")

print(f"Done. Inserted {inserted} opportunities.")
