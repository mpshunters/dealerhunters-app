from supabase import create_client
import os

print("DealerHunters scraper starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

print("Connected to Supabase")

response = supabase.table("source_registry").insert({
    "source_name": "DealerHunters Test",
    "source_url": "https://dealerhunters.com",
    "source_type": "system",
    "state": "ALL"
}).execute()

print("Test record inserted")
