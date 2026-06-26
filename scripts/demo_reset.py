from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

deleted  = supabase.table("opportunities").delete().neq("id", 0).execute()
reset    = supabase.table("signal_matches").update({"processed": False}).neq("id", 0).execute()
cleared  = supabase.table("digest_log").delete().neq("id", 0).execute()

opp_count    = len(deleted.data)  if deleted.data  else 0
sig_count    = len(reset.data)    if reset.data    else 0
digest_count = len(cleared.data)  if cleared.data  else 0

print("Demo reset complete.")
print(f"{opp_count} opportunities deleted")
print(f"{sig_count} signal_matches reset")
print(f"{digest_count} digest_log entries cleared")
print("Run pipeline from GitHub Actions to regenerate.")
