from supabase import create_client
import os

print("DealerHunters opportunity creation starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)


matches = supabase.table("signal_matches") \
    .select("*") \
    .execute()


print(f"Found {len(matches.data)} signal matches")


for match in matches.data:

    raw = supabase.table("raw_signals") \
        .select("*") \
        .eq("id", match["raw_signal_id"]) \
        .single() \
        .execute()

    if not raw.data:
        continue


    existing = supabase.table("opportunities") \
        .select("id") \
        .eq("signal_id", match["id"]) \
        .execute()


    if existing.data:
        continue


    source = raw.data


    pitch = {
        "Ownership Change": "Grand reopening campaign",
        "Marketing Hire": "90-day traffic generation plan",
        "Leadership Change": "New leadership growth strategy",
        "Expansion": "Local awareness campaign"
    }.get(
        match["signal_type"],
        "Dealer growth campaign"
    )


    supabase.table("opportunities").insert({

        "signal_id": match["id"],

        "opportunity_type": match["signal_type"],

        "fit_score": match["fit_score"],

        "ai_summary":
            f"{match['signal_type']} detected from {source.get('source_name')}",

        "pitch_angle":
            pitch

    }).execute()


    print(
        f"Created opportunity: {match['signal_type']}"
    )


print("Opportunity creation complete")
