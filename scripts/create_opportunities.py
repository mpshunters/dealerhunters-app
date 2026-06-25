from supabase import create_client
from openai import OpenAI
import json
import os

print("DealerHunters opportunity creation starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
openai_key = os.environ.get("OPENAI_API_KEY")

if not url or not key or not openai_key:
    raise Exception("Missing credentials: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY")

supabase = create_client(url, key)
ai_client = OpenAI(api_key=openai_key)

EXTRACT_PROMPT = (
    "You are extracting structured data from automotive industry news articles. "
    "Return JSON with these fields: dealership_name (the name of the specific dealership "
    "mentioned, or null if none), city (city where the dealership is located, or null), "
    "state (2-letter state abbreviation, or null). If multiple dealerships are mentioned, "
    "return the most prominently featured one."
)

SUMMARY_PROMPT = (
    "You are an analyst for CR Advertising, an agency that sells direct mail events "
    "and digital campaigns to automotive dealerships. Analyze this article and return "
    "JSON with two fields: ai_summary (2 sentences describing what is happening at this "
    "dealership) and pitch_angle (one specific sentence on how CR Advertising should "
    "pitch this dealer)."
)

PITCH_FALLBACK = {
    "ownership_change": "Grand reopening campaign",
    "new_rooftop":      "Local awareness campaign",
    "hiring":           "90-day traffic generation plan",
    "oem_event":        "Factory event campaign",
}


def extract_dealer_info(raw_text):
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": raw_text[:4000]},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "dealership_name": result.get("dealership_name") or "Unnamed Dealership",
            "city":            result.get("city"),
            "state":           result.get("state"),
        }
    except Exception as e:
        print(f"Dealer extraction failed ({e}), using fallback")
        return {"dealership_name": "Unnamed Dealership", "city": None, "state": None}


def generate_ai_content(raw_text, signal_type, source_name):
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": raw_text[:4000]},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        ai_summary = result.get("ai_summary") or f"{signal_type} detected from {source_name}"
        pitch_angle = result.get("pitch_angle") or PITCH_FALLBACK.get(signal_type, "Dealer growth campaign")
        return ai_summary, pitch_angle
    except Exception as e:
        print(f"OpenAI summary failed ({e}), using fallback")
        return (
            f"{signal_type} detected from {source_name}",
            PITCH_FALLBACK.get(signal_type, "Dealer growth campaign"),
        )


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
    raw_text = source.get("raw_text") or source.get("title") or ""

    dealer   = extract_dealer_info(raw_text)
    ai_summary, pitch_angle = generate_ai_content(
        raw_text,
        match["signal_type"],
        source.get("source_name", "unknown source"),
    )

    supabase.table("opportunities").insert({
        "signal_id":        match["id"],
        "dealership_name":  dealer["dealership_name"],
        "city":             dealer["city"],
        "state":            dealer["state"],
        "opportunity_type": match["signal_type"],
        "fit_score":        match["fit_score"],
        "ai_summary":       ai_summary,
        "pitch_angle":      pitch_angle,
    }).execute()

    supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()

    created += 1
    print(f"Created: {dealer['dealership_name']} | {dealer['city']}, {dealer['state']} | {match['signal_type']}")

print(f"Opportunity creation complete. {created} created.")
