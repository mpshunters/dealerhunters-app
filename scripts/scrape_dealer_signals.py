import requests

print("DealerHunters scraper starting...")

sources = [
    "https://www.autoremarketing.com",
    "https://digitaldealer.com"
]

for source in sources:
    try:
        r = requests.get(source, timeout=20)
        print(f"{source}: {r.status_code}")
    except Exception as e:
        print(f"{source}: {e}")
