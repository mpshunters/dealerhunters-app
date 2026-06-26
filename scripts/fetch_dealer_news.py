from dotenv import load_dotenv
from supabase import create_client
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
import feedparser
import requests
import re
import os

load_dotenv()

print("DealerHunters article scrape starting...")

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise Exception("Missing Supabase credentials")

supabase = create_client(url, key)

HEADERS = {"User-Agent": "Mozilla/5.0 DealerHuntersBot/1.0"}
ARTICLE_PATTERN = re.compile(r'/news/|/dealers/|/retail/|/20\d{2}/')
MAX_ARTICLES = 10


def normalize_url(u):
    """Strip trailing slash and fragment for comparison."""
    return u.rstrip("/").split("#")[0]


def is_article_link(href, base_domain, source_url):
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc != base_domain:
        return False
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return False
    # Skip if the link resolves back to the source homepage itself
    if normalize_url(href) == normalize_url(source_url):
        return False
    path = parsed.path
    return bool(ARTICLE_PATTERN.search(href)) or len(path) > 40


def extract_article_links(soup, base_url):
    base_domain = urlparse(base_url).netloc
    seen = set()
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if href in seen:
            continue
        seen.add(href)
        if is_article_link(href, base_domain, base_url):
            links.append(href)
    return links[:MAX_ARTICLES]


def extract_body_text(soup):
    for tag in ("article", "main"):
        el = soup.find(tag)
        if el:
            return el.get_text(" ", strip=True)[:5000]

    divs = soup.find_all("div")
    if divs:
        best = max(divs, key=lambda d: len(d.find_all("p")))
        if len(best.find_all("p")) >= 2:
            return best.get_text(" ", strip=True)[:5000]

    return soup.get_text(" ", strip=True)[:5000]


sources = supabase.table("source_registry") \
    .select("id, source_name, source_url, source_type") \
    .eq("active", True) \
    .execute()

print(f"Found {len(sources.data)} active sources")

total_inserted = 0

for source in sources.data:
    source_id  = source["id"]
    source_name = source["source_name"]
    source_url  = source["source_url"]

    source_type = source.get("source_type") or "html"
    is_rss = (
        source_type == "rss"
        or "feeds.google.com" in source_url
        or "/rss" in source_url
        or "/feed" in source_url
        or "rss=" in source_url
    )
    print(f"\nScraping {source_name} [{'rss' if is_rss else source_type}]...")

    # ── RSS path ────────────────────────────────────────────────────
    if is_rss:
        try:
            feed = feedparser.parse(source_url)
            if feed.bozo and not feed.entries:
                raise ValueError(f"Feed parse error: {feed.bozo_exception}")

            display_name = feed.feed.get("title") or source_name
            entries = feed.entries[:MAX_ARTICLES]
            print(f"  Found {len(entries)} RSS entries (feed: {display_name})")

            supabase.table("source_registry").update({
                "health_status": "healthy",
            }).eq("id", source_id).execute()

        except Exception as e:
            print(f"  RSS fetch failed: {e}")
            supabase.table("source_registry").update({
                "health_status": "error",
                "last_error": str(e),
            }).eq("id", source_id).execute()
            continue

        inserted = 0
        for entry in entries:
            article_url = entry.get("link", "")
            if not article_url:
                continue

            existing = supabase.table("raw_signals") \
                .select("id") \
                .eq("article_url", article_url) \
                .execute()
            if existing.data:
                continue

            title = entry.get("title", display_name)
            raw_summary = entry.get("summary") or entry.get("description", "")
            body_text = BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True)[:5000] if raw_summary else ""

            try:
                supabase.table("raw_signals").insert({
                    "source_id":        source_id,
                    "source_name":      display_name,
                    "source_url":       source_url,
                    "title":            title,
                    "article_url":      article_url,
                    "raw_text":         body_text,
                    "matched_keywords": [],
                }).execute()
                inserted += 1
                print(f"  Inserted: {title[:70]}")
            except Exception as e:
                print(f"  Skipped {article_url}: {e}")

        supabase.table("source_registry").update({
            "last_scraped_at": datetime.now(timezone.utc).isoformat(),
            "last_error":      None,
        }).eq("id", source_id).execute()

        print(f"  {inserted} new articles from {display_name}")
        total_inserted += inserted
        continue
    # ── end RSS path ─────────────────────────────────────────────────

    verify_ssl = True

    try:
        try:
            resp = requests.get(source_url, timeout=20, headers=HEADERS)
        except requests.exceptions.SSLError:
            print(f"  SSL error — retrying with verify=False")
            verify_ssl = False
            resp = requests.get(source_url, timeout=20, headers=HEADERS, verify=False)
        supabase.table("source_registry").update({
            "last_status_code": resp.status_code,
            "health_status": "healthy" if resp.status_code == 200 else "warning"
        }).eq("id", source_id).execute()

        if resp.status_code != 200:
            print(f"  Homepage returned {resp.status_code}, skipping")
            continue

        homepage_soup = BeautifulSoup(resp.text, "html.parser")
        article_links = extract_article_links(homepage_soup, source_url)
        print(f"  Found {len(article_links)} article links")

    except Exception as e:
        print(f"  Homepage fetch failed: {e}")
        supabase.table("source_registry").update({
            "health_status": "error",
            "last_error": str(e)
        }).eq("id", source_id).execute()
        continue

    inserted = 0

    for article_url in article_links:
        existing = supabase.table("raw_signals") \
            .select("id") \
            .eq("article_url", article_url) \
            .execute()

        if existing.data:
            continue

        try:
            article_resp = requests.get(article_url, timeout=20, headers=HEADERS, verify=verify_ssl)
            if article_resp.status_code != 200:
                continue

            article_soup = BeautifulSoup(article_resp.text, "html.parser")

            h1 = article_soup.find("h1")
            title = h1.get_text(strip=True) if h1 else (
                article_soup.title.string.strip()
                if article_soup.title and article_soup.title.string
                else source_name
            )

            body_text = extract_body_text(article_soup)

            supabase.table("raw_signals").insert({
                "source_id":        source_id,
                "source_name":      source_name,
                "source_url":       source_url,
                "title":            title,
                "article_url":      article_url,
                "raw_text":         body_text,
                "matched_keywords": [],
            }).execute()

            inserted += 1
            print(f"  Inserted: {title[:70]}")

        except Exception as e:
            print(f"  Skipped {article_url}: {e}")
            continue

    supabase.table("source_registry").update({
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
        "last_error":      None,
    }).eq("id", source_id).execute()

    print(f"  {inserted} new articles from {source_name}")
    total_inserted += inserted

print(f"\nDone. {total_inserted} new articles inserted total.")
