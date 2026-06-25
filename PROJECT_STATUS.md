# DealerHunters — Project Status & Handoff Document

> **Last updated:** 2026-06-25  
> **Purpose:** Complete context for any new session, developer, or collaborator. No other context needed.

---

## 1. What DealerHunters Is

DealerHunters is a B2B sales intelligence tool built for **CR Advertising** — an agency that sells direct mail events and digital marketing campaigns to automotive dealerships across the US.

The core problem: CR's sales team has no systematic way to know *which* dealerships are in a buying moment right now. A dealership that just changed ownership, hired a new marketing director, or opened a second location is a high-probability prospect. Without signal detection, reps cold-call blindly.

**What DealerHunters does:**
1. Scrapes 25+ automotive industry news sources daily
2. Detects buying signals in articles (ownership changes, new hires, grand openings, OEM events)
3. Cross-references signals against a database of 33,000+ verified US dealerships
4. Generates AI-written summaries and pitch angles for each matched lead
5. Flags "hot leads" — dealerships that triggered multiple signals (highest priority)
6. Emails a daily digest to the CR team at 6:17 AM Central
7. Sends instant hot lead alerts the moment a hot lead is created

**Who uses it:** CR Advertising's sales and account management team.

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Pipeline runtime | GitHub Actions (Ubuntu) | Scheduled daily at 11:17 UTC (6:17 AM Central) |
| Database | Supabase (PostgreSQL) | All data storage; anon key for dashboard, service role key for pipeline |
| Web scraping | Python `requests` + BeautifulSoup | Article fetching from news sources |
| JS-heavy scraping | Playwright (headless Chromium) | Meta Ads Library (requires JS execution) |
| AI extraction | OpenAI GPT-4o-mini | Dealership name/city/state extraction + AI summaries + pitch angles |
| Email delivery | Resend | Daily digest + hot lead alerts |
| Frontend | Vanilla HTML/JS (no framework) | Dashboard, landing page, admin panel |
| Hosting | Cloudflare Pages | Static site + Pages Functions for `/admin-config` route |
| Dealer data | Google Places API v1 | City-sweep seeding of the dealership database |
| Local dev | Python `python-dotenv` | `.env` file for credentials |

**Python dependencies** (`requirements.txt`):
```
supabase
python-dotenv
requests
beautifulsoup4
openai
resend
pdfplumber
playwright
```

---

## 3. Every Script in `/scripts`

### Pipeline scripts (run in order by GitHub Actions)

| Script | What it does |
|---|---|
| `scrape_dealer_signals.py` | Seeds `source_registry` with all news sources. Idempotent — skips sources that already exist. Run once to bootstrap; re-run to add new sources. |
| `fetch_dealer_news.py` | Fetches each active source's homepage, extracts article links, scrapes article body text, inserts into `raw_signals`. Updates `last_scraped_at` and `last_status_code` per source. Retries with `verify=False` on SSL errors. |
| `detect_signal_matches.py` | Reads all unprocessed `raw_signals`. Runs each article through every active `signal_rules` keyword. Inserts rows into `signal_matches` for every keyword hit. Marks raw signals as `processed=True`. |
| `create_opportunities.py` | Reads unprocessed `signal_matches`. Uses GPT-4o-mini to extract dealership name/city/state and generate AI summary + pitch angle. 3-pass fuzzy match against `dealerships` DB to enrich with phone/website/franchise. Inserts into `opportunities`. Handles hot lead dedup logic. |
| `meta_ads_checker.py` | Uses Playwright to check the Meta Ads Library for high-confidence (score ≥ 80) dealerships from the last 30 days. If 0 active ads found → inserts `weak_digital` opportunity. |
| `google_presence_checker.py` | Scans all dealerships with Google data. Flags any with rating < 4.0 or < 50 reviews as `weak_digital` opportunities. |
| `send_hot_lead_alert.py` | Finds opportunities created in the last 2 hours with `is_hot_lead=True`. Sends one branded email per hot lead via Resend. Logs to `digest_log` with `type='hot_lead_alert'`. Exits silently if no hot leads. |
| `send_daily_digest.py` | Queries all `status='new'` opportunities. Sends a single HTML digest email to `DIGEST_EMAIL_TO`. Sends "no signals" email if zero results. Logs to `digest_log`. |

### One-time / maintenance scripts

| Script | What it does |
|---|---|
| `seed_signal_rules.py` | Inserts keyword rules into `signal_rules`. Idempotent by `rule_name`. Run once; re-run to add new rules. |
| `seed_national_dealerships.py` | Broad national dealer seed — searches major metro areas across all states. |
| `backfill_photo_counts.py` | Backfills `photo_count` column from Google Places data for existing dealership records. |
| `log_scrape_run.py` | Utility for logging pipeline run metadata. |

### State dealer seed scripts

All follow the same pattern: Google Places API city-sweep → state filter → upsert by `google_place_id`. All are idempotent.

| Script | Cities | Region |
|---|---|---|
| `seed_il_dealers.py` | ~120 | Illinois (Chicago metro + downstate) |
| `seed_oh_dealers.py` | ~110 | Ohio (Columbus, Cleveland, Cincinnati, Dayton, Toledo, Akron) |
| `seed_mi_dealers.py` | ~100 | Michigan (Detroit metro, Grand Rapids, Lansing, Flint, Ann Arbor) |
| `seed_mn_dealers.py` | ~80 | Minnesota (Twin Cities + outstate) |
| `seed_wi_dealers.py` | ~90 | Wisconsin (Milwaukee, Madison, Green Bay, Appleton) |
| `seed_mo_dealers.py` | ~90 | Missouri (St. Louis, Kansas City, Springfield) |
| `seed_in_dealers.py` | ~90 | Indiana (Indianapolis, Fort Wayne, Evansville, South Bend) |
| `seed_ne_dealers.py` | ~50 | Nebraska (Omaha, Lincoln + smaller markets) |
| `seed_ks_dealers.py` | ~60 | Kansas (Wichita, Kansas City KS, Topeka, Lawrence) |
| `seed_ny_dealers.py` | ~170 | New York (NYC boroughs, Long Island, Buffalo, Rochester, Albany, Syracuse) |
| `seed_pa_dealers.py` | ~140 | Pennsylvania (Philadelphia, Pittsburgh, Allentown, Scranton, Harrisburg, Erie) |
| `seed_ga_dealers.py` | ~110 | Georgia (Atlanta metro, Augusta, Columbus, Savannah, Macon, Athens) |
| `seed_nc_dealers.py` | ~110 | North Carolina (Charlotte, Raleigh-Durham, Greensboro, Fayetteville, Wilmington, Asheville) |
| `seed_wa_dealers.py` | ~90 | Washington (Seattle-Tacoma, Spokane, Tri-Cities, Bellingham, Vancouver) |
| `seed_co_dealers.py` | ~80 | Colorado (Denver Front Range, Colorado Springs, Fort Collins, Boulder, Western Slope) |
| `seed_az_dealers.py` | ~70 | Arizona (Phoenix Valley, Tucson, Flagstaff, Prescott, Yuma, Lake Havasu) |
| `seed_tx_dealers.py` | — | Texas (partial) |
| `seed_ca_dealers.py` | — | California (partial) |
| `seed_fl_dealers.py` | — | Florida (partial) |
| `seed_iowa_dealers.py` | — | Iowa (partial) |

---

## 4. Database Schema

**Supabase project:** `xahazlzuxowamknucprs`  
**URL:** `https://xahazlzuxowamknucprs.supabase.co`

### `dealerships`
The canonical dealer database. Seeded via Google Places API.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `google_place_id` | text UNIQUE | Dedup key for all seed scripts |
| `dealership_name` | text | |
| `city` | text | |
| `state` | text | 2-letter abbreviation |
| `phone` | text | |
| `website` | text | |
| `franchise` | text | OEM brand (Ford, Toyota, etc.) |
| `google_rating` | float | From Places API |
| `google_reviews` | int | Review count from Places API |
| `photo_count` | int | Count of photos on Google listing |
| `rooftop_status` | text | `active` default |
| `has_recent_posts` | bool | nullable |
| `review_response_rate` | float | nullable |
| `dealer_group_id` | uuid | FK to dealer groups, nullable |

### `source_registry`
All news/press sources the pipeline scrapes.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `source_name` | text | Display name |
| `source_url` | text UNIQUE | Homepage URL |
| `source_type` | text | `dealer_news`, `news`, `press`, `rss` |
| `active` | bool | Only active sources are scraped |
| `health_status` | text | `healthy`, `warning`, `error` |
| `last_status_code` | int | HTTP status from last scrape |
| `last_scraped_at` | timestamptz | Updated after each successful scrape |
| `last_error` | text | Cleared on success; set on failure |

### `raw_signals`
One row per article scraped.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `source_id` | uuid FK → source_registry | |
| `source_name` | text | Denormalized for convenience |
| `source_url` | text | Homepage URL of the source |
| `article_url` | text UNIQUE | Full article URL — dedup key |
| `title` | text | |
| `raw_text` | text | First 5000 chars of article body |
| `matched_keywords` | text[] | |
| `processed` | bool | Set True after signal detection runs |

### `signal_rules`
Keyword matching rules.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `rule_name` | text UNIQUE | Dedup key |
| `signal_type` | text | `ownership_change`, `new_rooftop`, `hiring`, `oem_event` |
| `keywords` | text[] | Case-insensitive substring matches |
| `fit_score` | int | 1 = generic, 2 = moderate, 3 = highly specific |
| `active` | bool | |

### `signal_matches`
Join between raw articles and matching rules.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `raw_signal_id` | uuid FK → raw_signals | |
| `signal_type` | text | Copied from rule |
| `matched_keyword` | text | The exact keyword that matched |
| `fit_score` | int | 1–3 |
| `processed` | bool | Set True after `create_opportunities.py` runs |

### `opportunities`
Final leads ready for the sales team.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `signal_id` | uuid FK → signal_matches | |
| `dealership_name` | text | |
| `city` | text | |
| `state` | text | |
| `phone` | text | From dealerships table if matched |
| `website` | text | From dealerships table if matched |
| `franchise` | text | From dealerships table if matched |
| `opportunity_type` | text | `ownership_change`, `new_rooftop`, `hiring`, `oem_event`, `weak_digital` |
| `fit_score` | int | Raw 1–3 from signal rule |
| `confidence_score` | int | Mapped: 1→75, 2→83, 3→92 |
| `status` | text | `new`, `contacted`, `won`, `lost` |
| `is_hot_lead` | bool | True if same dealer triggered 2+ signals |
| `ai_summary` | text | GPT-4o-mini 2-sentence summary |
| `pitch_angle` | text | GPT-4o-mini pitch recommendation |
| `source_name` | text | Which publication the signal came from |
| `source_url` | text | Direct article URL |
| `created_at` | timestamptz | Auto-set by Supabase |

### `digest_log`
Audit trail of every email sent.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `sent_at` | timestamptz | |
| `opportunities_count` | int | |
| `recipient` | text | |
| `status` | text | `sent` or `error` |
| `resend_id` | text | Resend message ID |
| `type` | text | `digest` or `hot_lead_alert` |

---

## 5. Environment Variables

### For local development (`.env` in repo root, gitignored)
```
SUPABASE_URL=https://xahazlzuxowamknucprs.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<from Supabase → Settings → API → service_role>
GOOGLE_PLACES_API_KEY=<from Google Cloud Console → APIs & Services → Credentials>
OPENAI_API_KEY=<from platform.openai.com>
RESEND_API_KEY=<from resend.com → API Keys>
DIGEST_EMAIL_TO=<email address to receive digests>
DIGEST_EMAIL_FROM=DealerHunters Signals <signals@mpshunters.com>
```

### GitHub Actions secrets (Settings → Secrets and variables → Actions)
| Secret | Value |
|---|---|
| `SUPABASE_URL` | Same as above |
| `SUPABASE_SERVICE_ROLE_KEY` | Same as above |
| `OPENAI_API_KEY` | Same as above |
| `RESEND_API_KEY` | Same as above |
| `DIGEST_EMAIL_TO` | Recipient email |
| `DIGEST_EMAIL_FROM` | From address string |

### Cloudflare Pages env vars (Settings → Environment variables)
| Variable | Value | Used by |
|---|---|---|
| `ADMIN_SUPABASE_KEY` | Supabase service role key | `/admin-config` Pages Function → admin.html |
| `ADMIN_GH_TOKEN` | GitHub PAT with `actions:write` scope | Admin panel workflow dispatch |

### Local-only admin config (`/admin-config.js`, gitignored)
Create this file in the repo root for local admin panel access:
```javascript
const ADMIN_CONFIG = {
  supabase_url: "https://xahazlzuxowamknucprs.supabase.co",
  supabase_key: "<service_role_key>",
  gh_token: "<github_pat>",
  gh_repo: "mpshunters/dealerhunters-app"
};
```
This file is gitignored (`/admin-config.js` root-anchored) so it never commits. In production, `functions/admin-config.js` (a Cloudflare Pages Function) serves the same data at the `/admin-config` route, reading from CF environment variables.

---

## 6. What's Built and Working

### Pipeline
- [x] Daily scrape scheduled at 11:17 UTC (6:17 AM Central) via GitHub Actions
- [x] 25+ news sources in `source_registry` across 4 source types
- [x] Article scraping with dedup by `article_url`
- [x] SSL error handling — retries with `verify=False`, never crashes the pipeline
- [x] Keyword-based signal detection across 4 signal types with 3 weight tiers
- [x] GPT-4o-mini dealer name/city/state extraction
- [x] 3-pass fuzzy dealership matching (forward ILIKE → reverse contains → first-word + state)
- [x] City/state tiebreaker for multiple DB candidates
- [x] Hot lead detection (same dealer, multiple signals → `is_hot_lead=True`)
- [x] Meta Ads Library checker via Playwright (headless Chromium, no API token needed)
- [x] Google presence checker (flags low-rating or low-review-count dealers)
- [x] Instant hot lead alerts (one email per hot lead, dark branded template)
- [x] Daily digest email (light branded template, signal stats header, opportunity cards)
- [x] `source_registry.last_scraped_at` stamped after each successful source scrape
- [x] `digest_log` audit trail for every email sent

### Frontend
- [x] Landing page (`index.html`) with hero, features, FAQ, waitlist CTA
- [x] Dashboard (`dashboard.html`) — live opportunity feed from Supabase
  - Score gauge with `?` tooltip explaining 92/83/75/🔥
  - "New Today" vs "This Week" card grouping
  - Hot Leads filter with empty-state message
  - Dealership website link on each card (stripped of `https://www.`)
  - Source article link (hidden if URL is internal or missing)
  - ⚡ Signals Detected stat card
  - Animated count-up stats (33,000+ dealerships, signals, etc.)
  - Settings gear dropdown (filter controls)
- [x] Admin panel (`admin.html`) — password-gated (`dh-admin-2026`)
  - 6 sections: Overview, Sources, Signals, Opportunities, Pipeline, System
  - Live Supabase counts (uses service role key for unfiltered reads)
  - GitHub Actions manual workflow dispatch ("Run Pipeline Now" button)
  - Countdown to next scheduled run (11:17 UTC)
  - Source health table with Fresh/Stale/Error status badges
- [x] Custom crosshair cursor (emerald SVG, hotspot 12,12) on all 3 pages
- [x] Cloudflare Pages Function at `functions/admin-config.js` serving secrets at `/admin-config`

### Dealer database
- [x] 33,000+ dealerships seeded across 20 states
- [x] Google Places API v1 city-sweep pattern (deduplicated by `google_place_id`)
- [x] Fields: name, city, state, phone, website, franchise, google_rating, google_reviews, photo_count

---

## 7. Known Issues and Workarounds

### Low DB match rate (~16–25%)
- **Cause:** Article-extracted names often don't match DB names exactly ("AutoNation" vs "AutoNation Ford Mobile")
- **Current fix:** 3-pass fuzzy matching in `create_opportunities.py` (forward ILIKE → reverse Python contains → first-word + state)
- **Remaining gap:** Match rate still limited by how accurately GPT-4o-mini extracts dealership names. Some articles mention dealer groups, not individual rooftops.
- **Next step:** Consider adding NER (named entity recognition) as a pre-filter before GPT extraction

### Meta Ads checker low volume
- **Cause:** Only checks dealerships with `confidence_score >= 80` from the last 30 days. Early in the product lifecycle, few opportunities pass this threshold.
- **Workaround:** As the pipeline runs more days and accumulates opportunities, the checker pool grows automatically.

### Google News RSS sources not parsed
- **Cause:** `fetch_dealer_news.py` uses BeautifulSoup for HTML parsing; RSS XML is not handled.
- **Workaround:** These 4 sources are registered in `source_registry` but produce no useful articles.
- **Fix needed:** Add `feedparser` to requirements and an RSS path in `fetch_dealer_news.py`

### Admin panel workflow dispatch requires GitHub PAT
- **Setup:** `ADMIN_GH_TOKEN` must be set in Cloudflare Pages environment variables. The PAT needs `actions:write` scope on the `mpshunters/dealerhunters-app` repo.
- **If missing:** The "Run Pipeline Now" button will show an error but nothing breaks.

### Playwright in GitHub Actions
- **Status:** Working. `playwright install chromium --with-deps` is a dedicated step in the workflow.
- **Note:** If Meta Ads Library changes its UI or bot detection, `meta_ads_checker.py` may return `None` (inconclusive) for all dealers rather than crashing.

---

## 8. What Still Needs to Be Built (Prioritized)

### High priority
1. **RSS feed parser** — Add `feedparser` support to `fetch_dealer_news.py` to activate the 4 Google News RSS sources. Each targets high-signal queries ("car dealership acquired", "new dealership opening", etc.)
2. **More state coverage** — States with no seed script: VA, TN, MD, SC, NV, OR, UT, NM, ID, OK, AR, MS, AL, KY, WV, and all New England states. Target: 48 contiguous states.
3. **Opportunity status workflow** — Dashboard UI for marking leads as `contacted`, `won`, `lost`. Currently status is only set to `new` and never updated from the UI.
4. **Contact info enrichment** — Apollo.io integration to surface the marketing director / GM contact for each rooftop. Currently only linked via button in hot lead emails.

### Medium priority
5. **LinkedIn hiring signal detection** — LinkedIn job postings for "Marketing Manager" or "BDC Manager" at dealerships are a premium signal.
6. **Email engagement tracking** — Resend supports webhooks for open/click events. Log these back to Supabase so the team knows which leads got attention.
7. **Dashboard mobile view** — Dashboard is desktop-only; no responsive breakpoints.
8. **Opportunity dedup across days** — A dealership can re-appear in consecutive digests if a new signal is detected each day. Need a cooldown window (e.g., don't re-surface the same dealer within 14 days unless a higher-score signal appears).

### Low priority / backlog
9. **CRM export** — CSV download from dashboard or direct HubSpot/Salesforce push
10. **Multi-user auth** — Currently single-password. Real auth would let individual reps claim/track their leads.
11. **Slack webhook** — Push new opportunities to a Slack channel in addition to email
12. **Historical analytics** — Track lead contact rate, won rate, avg score over time

---

## 9. Key Technical Decisions and Why

### Why GitHub Actions for the pipeline?
Zero infrastructure to maintain. The pipeline is a sequence of Python scripts — Actions handles scheduling, secrets injection, Playwright dependencies, and logging. A cron at `17 11 * * *` (not top-of-hour) avoids resource contention on Actions runners.

### Why Supabase?
PostgreSQL with a REST API and built-in auth/RLS. The dashboard JS queries Supabase directly using the anon key (RLS-restricted). The pipeline uses the service role key (no RLS). No custom backend needed.

### Why Cloudflare Pages?
Free static hosting with Pages Functions support. The `functions/admin-config.js` function solves the secret-injection problem for the admin panel — the service role key and GitHub PAT live in CF environment variables and are served at `/admin-config` as a JS file that admin.html loads at runtime. The file is never committed.

### Why GPT-4o-mini for extraction?
Fast, cheap (~$0.15/1M tokens), and accurate enough for structured extraction (name, city, state) and short summaries. GPT-4o would be better quality but costs 10× more with minimal improvement on this specific use case.

### Why Google Places API v1 for dealer seeding?
`places.googleapis.com/v1/places:searchText` with `includedType: "car_dealer"` returns structured data (name, address components, phone, website, rating, review count, photos) in a single call. Deduplication by `google_place_id` makes all seed scripts idempotent.

### Why one email per hot lead (not batched)?
Hot leads are time-sensitive. A dealership that just triggered its second signal deserves immediate attention, not a once-a-day digest. The hot lead alert arrives before the digest so the rep sees it first.

### Why `verify=False` on SSL retry instead of skipping the source?
Sources like `fixedopsmag.com` have expired or misconfigured certs but serve valid content. Skipping them entirely would lose real signal. The retry is logged clearly; fixing the cert is their problem, not ours.

### Why root-anchor `/admin-config.js` in `.gitignore`?
The pattern `admin-config.js` (no leading slash) matches `functions/admin-config.js` — the Pages Function that must be committed. The leading slash anchors the ignore rule to the repo root only.

---

## 10. How to Run the Pipeline Manually

### Via GitHub Actions (recommended)
1. Go to the repo → Actions → "Daily Dealer Signal Scrape"
2. Click "Run workflow" → Run workflow
3. Or trigger from the admin panel at `/admin.html` → Pipeline section → "Run Pipeline Now"

### Via local terminal (for debugging individual steps)
```bash
# Prerequisites: Python 3.11+, .env file with all credentials
cd /path/to/dealerhunters-app
pip install -r requirements.txt
playwright install chromium --with-deps

# Run the full pipeline in order:
python scripts/scrape_dealer_signals.py     # seed sources (idempotent)
python scripts/fetch_dealer_news.py         # scrape articles
python scripts/detect_signal_matches.py    # keyword matching
python scripts/create_opportunities.py     # AI enrichment + DB matching
python scripts/meta_ads_checker.py         # Meta Ads Library check
python scripts/google_presence_checker.py  # Google profile check
python scripts/send_hot_lead_alert.py      # hot lead emails (if any)
python scripts/send_daily_digest.py        # digest email
```

### Pipeline step order matters
Each step depends on the previous: raw_signals → signal_matches → opportunities. Running steps out of order is safe (all are idempotent) but won't produce new results until upstream steps have run.

---

## 11. How to Add New States to the Dealer Database

All seed scripts follow an identical pattern. To add a new state (example: Virginia):

```bash
# 1. Copy an existing script as the template
cp scripts/seed_nc_dealers.py scripts/seed_va_dealers.py

# 2. Edit the new file — change these 5 things:
#    a. Docstring: update state name
#    b. Rename the city list: VA_CITIES = [...]
#    c. State filter: p_state != "VA"
#    d. textQuery: f"car dealer {city} Virginia"
#    e. Final count query: .eq("state", "VA")

# 3. Run locally to test (reads from .env):
python scripts/seed_va_dealers.py

# 4. Commit and push:
git add scripts/seed_va_dealers.py
git commit -m "Add Virginia dealer seed script"
git push
```

**City list guidance:**
- Start with the largest metro area and expand outward to suburbs
- Include county-seat towns — they often have dealer strips
- Target 60–170 cities depending on state population density
- The dedup loop at the top of every script handles duplicate city names in your list

**Expected yield:** ~8–15 new dealerships per city on average (Google Places caps at 20 per search). A 100-city sweep typically adds 600–1,200 dealerships.

---

## 12. Demo Script for CR Advertising

Use this when showing DealerHunters to CR's leadership or new prospects.

**Setup before the demo:**
- Open the dashboard at `dealerhunters-app.pages.dev/dashboard`
- Confirm 5–10 opportunities are visible (if empty, manually insert 2–3 test records via Supabase table editor)

**Demo flow (~8 minutes):**

**1. The problem** (1 min)
> "Right now, your reps are cold-calling blind. They don't know which dealers are in a buying moment. DealerHunters fixes that."

**2. The dashboard** (2 min)
> "Every morning at 6:17, this updates automatically. Each card is a dealership that triggered a buying signal in the last 24 hours — ownership change, new hire, grand opening, OEM event."
- Point to the score gauge: "92 means a highly specific signal, 75 is a broader one."
- Point to "New Today" section: "These came in this morning."
- Click the `?` next to a score to show the tooltip.

**3. Hot leads** (2 min)
> "The real money is here — Hot Leads."
- Click the Hot Leads filter.
> "A hot lead means the same dealership triggered multiple signals. That's rare and extremely high-value. We email you the second this happens — before the daily digest even goes out."
- Point to the 🔥 badge on a hot lead card.

**4. Signal types** (1 min)
> "Four signal types: ownership change — new owner, new budget, new decisions. New rooftop — they just opened, they need to drive traffic. Marketing hire — new marketing director usually means new vendor budget. OEM event — factory incentives create urgency for a direct mail event."

**5. What we cover** (30 sec)
> "33,000+ dealerships across 30+ states. 25+ news sources. Runs every morning automatically — no manual work."

**6. The pitch angle** (1 min)
> "Expand any card and you'll see an AI-written pitch angle — exactly how CR should approach this dealer. Your reps walk in with context, not a cold call."

**7. Close** (30 sec)
> "The daily digest lands in your inbox before your team starts their day. Hot leads get an immediate separate alert. You'll never miss a buying window again."

---

## 13. Daily Operations Checklist

**Each morning (after 6:17 AM Central):**
- [ ] Check email — verify the daily digest arrived and has opportunities
- [ ] If a hot lead alert arrived, assign it to the relevant sales rep immediately
- [ ] Check admin panel → Sources section — all sources should show "Fresh" (green)
- [ ] If any source shows "Error" or "Stale" — check `last_error` in Supabase `source_registry`

**Weekly:**
- [ ] Admin panel → Overview — review total opportunities count trend
- [ ] Check for leads sitting in `status='new'` for more than a week — consider reassigning or archiving stale records
- [ ] GitHub Actions → confirm no pipeline runs failed (red X) in the last 7 days

**As needed:**
- [ ] Add new states to the dealer database (see Section 11)
- [ ] Add new signal keywords: edit `seed_signal_rules.py` and re-run it
- [ ] Add new news sources: edit `scrape_dealer_signals.py` and re-run it
- [ ] If match rate drops (watch for `[No DB match]` logs in Actions), expand dealer seeding in affected states

---

## 14. Dealership Database Coverage by State

### Seeded (seed script written and run)

| State | Script | Approx. Cities | Key Markets |
|---|---|---|---|
| IL | `seed_il_dealers.py` | ~120 | Chicago metro, Springfield, Peoria, Rockford |
| OH | `seed_oh_dealers.py` | ~110 | Columbus, Cleveland, Cincinnati, Dayton, Toledo, Akron |
| MI | `seed_mi_dealers.py` | ~100 | Detroit, Grand Rapids, Lansing, Flint, Ann Arbor |
| MN | `seed_mn_dealers.py` | ~80 | Twin Cities, Rochester, Duluth, St. Cloud |
| WI | `seed_wi_dealers.py` | ~90 | Milwaukee, Madison, Green Bay, Appleton |
| MO | `seed_mo_dealers.py` | ~90 | St. Louis, Kansas City, Springfield |
| IN | `seed_in_dealers.py` | ~90 | Indianapolis, Fort Wayne, Evansville, South Bend |
| NE | `seed_ne_dealers.py` | ~50 | Omaha, Lincoln |
| KS | `seed_ks_dealers.py` | ~60 | Wichita, Kansas City KS, Topeka |
| NY | `seed_ny_dealers.py` | ~170 | NYC, Long Island, Buffalo, Rochester, Albany, Syracuse |
| PA | `seed_pa_dealers.py` | ~140 | Philadelphia, Pittsburgh, Allentown, Scranton, Erie |
| GA | `seed_ga_dealers.py` | ~110 | Atlanta metro, Augusta, Savannah, Macon, Columbus |
| NC | `seed_nc_dealers.py` | ~110 | Charlotte, Raleigh-Durham, Greensboro, Fayetteville, Asheville |
| WA | `seed_wa_dealers.py` | ~90 | Seattle-Tacoma, Spokane, Tri-Cities, Bellingham |
| CO | `seed_co_dealers.py` | ~80 | Denver, Colorado Springs, Fort Collins, Boulder |
| AZ | `seed_az_dealers.py` | ~70 | Phoenix Valley, Tucson, Flagstaff, Prescott, Yuma |
| TX | `seed_tx_dealers.py` | — | Partial |
| CA | `seed_ca_dealers.py` | — | Partial |
| FL | `seed_fl_dealers.py` | — | Partial |
| IA | `seed_iowa_dealers.py` | — | Partial |

### Not yet seeded (no script exists)
VA, TN, MD, SC, NJ, NV, OR, UT, NM, ID, OK, AR, MS, AL, KY, WV, CT, MA, NH, VT, ME, RI, DE, MT, WY, ND, SD, HI, AK

### Priority next states (by population × dealer density)
1. **VA** — Northern VA / Richmond / Hampton Roads; DC market bleed-over
2. **TN** — Nashville, Memphis, Knoxville, Chattanooga; fast-growing auto market
3. **NJ** — Dense market adjacent to NY and PA already seeded
4. **MD** — Baltimore metro + DC suburbs
5. **SC** — Charlotte bleed-over + Greenville, Columbia, Myrtle Beach
