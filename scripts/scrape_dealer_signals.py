from supabase import create_client
import os

print("DealerHunters source seeding starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

sources = [
    # ── Existing sources ───────────────────────────────────────────────────
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
    },

    # ── Trade publications ─────────────────────────────────────────────────
    {
        "source_name": "Fixed Ops Magazine",
        "source_url": "https://fixedopsmag.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "AutoSuccess Magazine",
        "source_url": "https://www.autosuccessonline.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Wards Auto - Dealers",
        "source_url": "https://www.wardsauto.com/dealers",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "F&I and Showroom Magazine",
        "source_url": "https://www.fi-magazine.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Auto Dealer Today",
        "source_url": "https://www.autodealertodaymagazine.com/news",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "ABRN - Automotive Body Repair News",
        "source_url": "https://www.abrn.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Vehicle Service Pros",
        "source_url": "https://www.vehicleservicepros.com/industry-news",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Car Dealership Guy News",
        "source_url": "https://news.dealershipguy.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },

    # ── Industry / dealer group blogs ──────────────────────────────────────
    {
        "source_name": "NADA Newsroom",
        "source_url": "https://www.nada.org/nada/news/press-releases",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "NCM Associates Blog",
        "source_url": "https://ncmassociates.com/about-us/up-to-speed-blog",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Reynolds and Reynolds Blog",
        "source_url": "https://www.reyrey.com/resources/blog",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "CDK Global Insights",
        "source_url": "https://www.cdkglobal.com/insights",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "DealerSocket / Solera Blog",
        "source_url": "https://www.solera.com/blog/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "DrivingSales",
        "source_url": "https://www.drivingsales.com/",
        "source_type": "news",
        "active": True,
        "state": "ALL"
    },

    # ── Press release wires ────────────────────────────────────────────────
    {
        "source_name": "PRNewswire - Automotive",
        "source_url": "https://www.prnewswire.com/news-releases/automotive-transportation-latest-news/automotive-list/",
        "source_type": "press",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "BusinessWire - Automotive",
        "source_url": "https://www.businesswire.com/newsroom/industry/automotive",
        "source_type": "press",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "GlobeNewswire - Automotive",
        "source_url": "https://www.globenewswire.com/news/consumer-products-services/automobiles-parts",
        "source_type": "press",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "GlobeNewswire - Dealer Search",
        "source_url": "https://www.globenewswire.com/en/search/tag/automotive",
        "source_type": "press",
        "active": True,
        "state": "ALL"
    },

    # ── Google News RSS feeds (need RSS parser — flagged for scraper upgrade)
    {
        "source_name": "Google News - Car Dealership Acquired",
        "source_url": "https://news.google.com/rss/search?q=car+dealership+acquired&hl=en-US&gl=US&ceid=US:en",
        "source_type": "rss",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Google News - New Dealership Opening",
        "source_url": "https://news.google.com/rss/search?q=new+dealership+opening&hl=en-US&gl=US&ceid=US:en",
        "source_type": "rss",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Google News - Automotive Dealer Marketing",
        "source_url": "https://news.google.com/rss/search?q=automotive+dealer+marketing&hl=en-US&gl=US&ceid=US:en",
        "source_type": "rss",
        "active": True,
        "state": "ALL"
    },
    {
        "source_name": "Google News - Dealership Ownership Change",
        "source_url": "https://news.google.com/rss/search?q=dealership+ownership+change&hl=en-US&gl=US&ceid=US:en",
        "source_type": "rss",
        "active": True,
        "state": "ALL"
    },
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
