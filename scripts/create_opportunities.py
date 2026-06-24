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
    .or_("processed.eq.false,processed.is.null") \
    .execute()

print(f"Found {len(matches.data)} unprocessed signal matches")

created = 0

for match in matches.data:
    raw = supabase.table("raw_signals") \
        .select("*") \
        .eq("id", match["raw_signal_id"]) \
        .single() \
        .execute()

    if not raw.data:
        supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()
        continue

    source = raw.data

    pitch = {
        "ownership_change": "Grand reopening campaign",
        "new_rooftop":      "Local awareness campaign",
        "hiring":           "90-day traffic generation plan",
        "oem_event":        "Factory event campaign",
    }.get(match["signal_type"], "Dealer growth campaign")

    supabase.table("opportunities").insert({
        "signal_id":        match["id"],
        "opportunity_type": match["signal_type"],
        "fit_score":        match["fit_score"],
        "ai_summary":       f"{match['signal_type']} detected from {source.get('source_name')}",
        "pitch_angle":      pitch,
    }).execute()

    supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()

    created += 1
    print(f"Created opportunity: {match['signal_type']} | {source.get('source_name')}")

print(f"Opportunity creation complete. {created} created.")
