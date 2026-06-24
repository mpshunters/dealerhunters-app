from supabase import create_client
import os

print("DealerHunters scraper starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

print("Connected to Supabase")
