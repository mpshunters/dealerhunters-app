from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI
import json
import os

load_dotenv()

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

# Maps signal rule weight (1-3) to a human-readable confidence score (75-95)
WEIGHT_TO_SCORE = {1: 75, 2: 83, 3: 92}


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


def _pick_best(rows, city, state):
    """Among multiple candidates, prefer city+state match."""
    if len(rows) == 1:
        return rows[0]

    def score(row):
        s = 0
        if city and row.get("city") and city.lower() == row["city"].lower():
            s += 2
        if state and row.get("state") and state.upper() == (row["state"] or "").upper():
            s += 1
        return s

    return max(rows, key=score)


def find_matching_dealership(name, city=None, state=None):
    if not name or name == "Unnamed Dealership":
        return None

    name_clean = name.strip()

    # Pass 1 — forward: DB name contains extracted name
    # e.g. extracted="AutoNation" matches DB="AutoNation Ford Mobile"
    try:
        rows = supabase.table("dealerships") \
            .select("dealership_name, city, state, phone, website, franchise") \
            .ilike("dealership_name", f"%{name_clean}%") \
            .limit(10) \
            .execute().data or []
        if rows:
            best = _pick_best(rows, city, state)
            qual = "exact" if best["dealership_name"].lower() == name_clean.lower() else "partial"
            print(f"    [DB match - {qual}] '{best['dealership_name']}'")
            return best
    except Exception as e:
        print(f"    Dealership lookup pass 1 failed: {e}")

    # Pass 2 — reverse: extracted name contains DB name
    # e.g. extracted="Grieger's Chrysler Dodge Jeep Ram" matches DB="Grieger's"
    # Query by first significant word (≥4 chars), then filter in Python.
    words = [w for w in name_clean.split() if len(w) >= 4]
    first_word = words[0] if words else name_clean.split()[0]
    try:
        candidates = supabase.table("dealerships") \
            .select("dealership_name, city, state, phone, website, franchise") \
            .ilike("dealership_name", f"%{first_word}%") \
            .limit(50) \
            .execute().data or []
        reverse = [
            r for r in candidates
            if r.get("dealership_name")
            and len(r["dealership_name"]) >= 5
            and r["dealership_name"].lower() in name_clean.lower()
        ]
        if reverse:
            best = _pick_best(reverse, city, state)
            print(f"    [DB match - partial] '{best['dealership_name']}' (reverse contains)")
            return best
    except Exception as e:
        print(f"    Dealership lookup pass 2 failed: {e}")

    # Pass 3 — first word + state: last resort when name is too generic
    # e.g. "AutoNation" + "CA" avoids cross-state false positives
    if state:
        try:
            rows = supabase.table("dealerships") \
                .select("dealership_name, city, state, phone, website, franchise") \
                .ilike("dealership_name", f"%{first_word}%") \
                .eq("state", state.upper()) \
                .limit(5) \
                .execute().data or []
            if rows:
                best = _pick_best(rows, city, state)
                print(f"    [DB match - first word] '{best['dealership_name']}' via '{first_word}' + {state}")
                return best
        except Exception as e:
            print(f"    Dealership lookup pass 3 failed: {e}")

    return None


matches = supabase.table("signal_matches") \
    .select("*") \
    .or_("processed.is.false,processed.is.null") \
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

    dealer = extract_dealer_info(raw_text)

    if not dealer["dealership_name"] or dealer["dealership_name"] == "Unnamed Dealership":
        print(f"Skipped: no dealership identified in article ({source.get('source_name', 'unknown')})")
        supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()
        continue

    ai_summary, pitch_angle = generate_ai_content(
        raw_text,
        match["signal_type"],
        source.get("source_name", "unknown source"),
    )

    matched = find_matching_dealership(dealer["dealership_name"], dealer.get("city"), dealer.get("state"))

    record = {
        "signal_id":        match["id"],
        "dealership_name":  dealer["dealership_name"],
        "city":             dealer["city"],
        "state":            dealer["state"],
        "opportunity_type": match["signal_type"],
        "fit_score":        match["fit_score"],
        "confidence_score": WEIGHT_TO_SCORE.get(match["fit_score"], 75),
        "status":           "new",
        "ai_summary":       ai_summary,
        "pitch_angle":      pitch_angle,
        "source_name":      source.get("source_name"),
        "source_url":       source.get("article_url"),
    }

    if matched:
        record["city"]      = matched["city"]     or dealer["city"]
        record["state"]     = matched["state"]    or dealer["state"]
        record["phone"]     = matched.get("phone")
        record["website"]   = matched.get("website")
        record["franchise"] = matched.get("franchise")
        print(f"  [DB match] Found location: {record['city']}, {record['state']}")
    else:
        print(f"  [No DB match] Using extracted location: {dealer['city']}, {dealer['state']}")

    # Dedup + hot lead: only one 'new' opportunity per dealership (keep highest score).
    # A second signal for the same dealer marks both records as is_hot_lead=True.
    existing = supabase.table("opportunities") \
        .select("id, fit_score") \
        .eq("dealership_name", dealer["dealership_name"]) \
        .eq("status", "new") \
        .execute()

    is_hot_lead = False

    if existing.data:
        is_hot_lead    = True
        existing_id    = existing.data[0]["id"]
        existing_score = existing.data[0].get("fit_score") or 0
        new_score      = record.get("fit_score") or 0

        if new_score > existing_score:
            # Delete the weaker record; new insert below carries the hot flag
            supabase.table("opportunities").delete().eq("id", existing_id).execute()
            print(f"  [Dedup] Replacing lower score ({existing_score}→{new_score}) for {dealer['dealership_name']} 🔥 hot lead")
        else:
            # Existing wins — mark it hot and skip inserting this one
            supabase.table("opportunities").update({"is_hot_lead": True}).eq("id", existing_id).execute()
            print(f"  [Dedup] Skipped lower score ({new_score}≤{existing_score}), marked existing as hot lead for {dealer['dealership_name']}")
            supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()
            continue

    record["is_hot_lead"] = is_hot_lead
    supabase.table("opportunities").insert(record).execute()

    supabase.table("signal_matches").update({"processed": True}).eq("id", match["id"]).execute()

    created += 1
    print(f"Created: {dealer['dealership_name']} | {record['city']}, {record['state']} | {match['signal_type']}")

print(f"Opportunity creation complete. {created} created.")
