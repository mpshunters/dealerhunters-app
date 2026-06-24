from supabase import create_client
import os

print("DealerHunters source seeding starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

sources = [
    {
        "source_name": "Auto Remarketing",
        "source_url": "https://www.autoremarketing.com/",
        "source_type": "dealer_news",
        "state": "ALL"
    },
    {
        "source_name": "Digital Dealer",
        "source_url": "https://digitaldealer.com/",
        "source_type": "dealer_news",
        "state": "ALL"
    },
    {
        "source_name": "Automotive News - Dealership News",
        "source_url": "https://www.autonews.com/dealers",
        "source_type": "dealer_news",
        "state": "ALL"
    },
    {
        "source_name": "CBT News",
        "source_url": "https://www.cbtnews.com/",
        "source_type": "dealer_news",
        "state": "ALL"
    },
    {
        "source_name": "Dealer Magazine",
        "source_url": "https://dealermagazine.com/",
        "source_type": "dealer_news",
        "state": "ALL"
    }
]

inserted = 0

for source in sources:
    existing = supabase.table("source_registry") \
        .select("id") \
        .eq("source_url", source["source_url"]) \
        .execute()

    if existing.data:
        print(f"Already exists: {source['source_name']}")
        continue

    supabase.table("source_registry").insert(source).execute()
    inserted += 1
    print(f"Inserted: {source['source_name']}")

print(f"Done. Inserted {inserted} new sources.")
