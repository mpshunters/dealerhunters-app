from supabase import create_client
from bs4 import BeautifulSoup
import requests
import os

print("DealerHunters news fetch starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

sources = supabase.table("source_registry") \
    .select("id, source_name, source_url, source_type") \
    .eq("active", True) \
    .execute()

print(f"Found {len(sources.data)} active sources")

for source in sources.data:
    source_id = source["id"]
    source_name = source["source_name"]
    source_url = source["source_url"]

    try:
        response = requests.get(source_url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 DealerHuntersBot/1.0"
        })

        status_code = response.status_code
        print(f"{source_name}: {status_code}")

        supabase.table("source_registry").update({
            "last_status_code": status_code,
            "health_status": "healthy" if status_code == 200 else "warning"
        }).eq("id", source_id).execute()

        if status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else source_name

        existing = supabase.table("raw_signals") \
            .select("id") \
            .eq("article_url", source_url) \
            .execute()

        if existing.data:
            print(f"Already captured: {source_name}")
            continue

        supabase.table("raw_signals").insert({
            "source_id": source_id,
            "source_name": source_name,
            "source_url": source_url,
            "title": title,
            "article_url": source_url,
            "raw_text": soup.get_text(" ", strip=True)[:5000],
            "matched_keywords": []
        }).execute()

        print(f"Inserted raw signal: {source_name}")

    except Exception as e:
        print(f"{source_name} error: {e}")

        supabase.table("source_registry").update({
            "health_status": "error",
            "last_error": str(e)
        }).eq("id", source_id).execute()

print("DealerHunters news fetch complete")
