from supabase import create_client
import os

print("DealerHunters signal detection starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

raw_signals = supabase.table("raw_signals") \
    .select("id, title, raw_text, source_name") \
    .eq("processed", False) \
    .execute()

rules = supabase.table("signal_rules") \
    .select("id, rule_name, keywords, signal_type, fit_score") \
    .eq("active", True) \
    .execute()

print(f"Found {len(raw_signals.data)} unprocessed raw signals")
print(f"Found {len(rules.data)} active signal rules")

matches_found = 0

for signal in raw_signals.data:
    text = f"{signal.get('title', '')} {signal.get('raw_text', '')}".lower()

    for rule in rules.data:
        keywords = rule.get("keywords") or []

        for keyword in keywords:
            if keyword.lower() in text:
                existing = supabase.table("signal_matches") \
                    .select("id") \
                    .eq("raw_signal_id", signal["id"]) \
                    .eq("matched_keyword", keyword) \
                    .execute()

                if existing.data:
                    continue

                supabase.table("signal_matches").insert({
                    "raw_signal_id": signal["id"],
                    "signal_type": rule["signal_type"],
                    "matched_keyword": keyword,
                    "fit_score": rule["fit_score"]
                }).execute()

                matches_found += 1

                print(
                    f"Match found: {signal['source_name']} | "
                    f"{rule['signal_type']} | {keyword}"
                )

    supabase.table("raw_signals").update({
        "processed": True
    }).eq("id", signal["id"]).execute()

print(f"DealerHunters signal detection complete. Matches found: {matches_found}")
