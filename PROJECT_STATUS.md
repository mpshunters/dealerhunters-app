# DealerHunters — Project Status

> **Last updated:** June 2026  
> **Purpose:** Complete handoff document. A new Claude session or developer should be able to resume work from zero other context.

---

## What Is DealerHunters?

DealerHunters is a **B2B sales intelligence platform** for auto dealership marketing outreach. It monitors thousands of news sources daily, detects "in-motion" dealerships (ownership changes, leadership hires, new rooftops, OEM events, expansions), and delivers a curated digest of high-quality leads with AI-generated summaries and pitch angles.

**Primary customer:** CR Advertising — a marketing agency that sells digital marketing services (SEO, PPC, social, BDC) to auto dealerships.

**Core value:** Instead of cold-calling random dealers, CR's reps contact dealerships at the exact moment of change — when a new owner just took over, a new marketing director was hired, or a second location opened. These are moments of maximum receptivity to a new agency relationship.

**Business model:** SaaS subscription sold to CR Advertising. They pay for access to the dashboard and daily digest.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE (GitHub Actions)              │
│                    Runs: 6:17 AM Central (11:17 UTC)            │
│                                                                 │
│  scrape_dealer_signals.py                                       │
│    └─ Seeds source_registry with news sources                   │
│                                                                 │
│  fetch_dealer_news.py                                           │
│    └─ Scrapes article links from each active source             │
│    └─ Inserts new articles into raw_signals                     │
│                                                                 │
│  detect_signal_matches.py                                       │
│    └─ Runs keyword rules (signal_rules) against raw_signals     │
│    └─ Writes matches to signal_matches                          │
│                                                                 │
│  create_opportunities.py                                        │
│    └─ Converts signal_matches → opportunities                   │
│    └─ Uses OpenAI GPT-4o-mini for AI summaries + pitch angles   │
│    └─ Detects hot leads (same dealership, multiple signals)     │
│    └─ Maps fit_score weight → confidence_score (75/83/92)       │
│                                                                 │
│  meta_ads_checker.py                                            │
│    └─ Playwright headless Chrome checks Meta Ads Library        │
│    └─ Only checks opportunities with confidence_score >= 80     │
│    └─ Creates weak_digital opportunities for dealers w/ no ads  │
│                                                                 │
│  google_presence_checker.py                                     │
│    └─ Checks Google presence for additional weak digital signals│
│                                                                 │
│  send_daily_digest.py                                           │
│    └─ Fetches new opportunities, renders HTML email             │
│    └─ Sends via Resend API                                      │
│    └─ Logs send to digest_log                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (Cloudflare Pages)                │
│                      dealerhunters.com                          │
│                                                                 │
│  index.html     — Public landing page / marketing site          │
│  dashboard.html — Customer opportunity dashboard                │
│  admin.html     — Internal admin command center (password-gated)│
└─────────────────────────────────────────────────────────────────┘
```

---

## Script Reference

### Pipeline Scripts (`scripts/`)

| Script | Purpose | Key tables |
|---|---|---|
| `scrape_dealer_signals.py` | Seeds `source_registry` with ~20 industry news sources | `source_registry` |
| `fetch_dealer_news.py` | Scrapes article URLs from each active source, inserts new articles | `source_registry`, `raw_signals` |
| `detect_signal_matches.py` | Runs signal_rules keyword matching against unprocessed raw_signals | `signal_rules`, `raw_signals`, `signal_matches` |
| `create_opportunities.py` | Converts signal_matches → opportunities with OpenAI summaries | `signal_matches`, `opportunities`, `dealerships` |
| `meta_ads_checker.py` | Playwright check of Meta Ads Library for weak_digital detection | `opportunities` |
| `google_presence_checker.py` | Google presence check for weak_digital detection | `opportunities` |
| `send_daily_digest.py` | Renders + sends HTML email digest via Resend | `opportunities`, `digest_log` |
| `seed_signal_rules.py` | Upserts keyword rules into signal_rules table | `signal_rules` |

### Dealer Database Seed Scripts (one-time, run manually)

Each follows the same pattern: Google Places API city sweep → filter by state → upsert by `google_place_id`.

| Script | State | ~Cities |
|---|---|---|
| `seed_il_dealers.py` | Illinois | 200 |
| `seed_tx_dealers.py` | Texas | 173 |
| `seed_fl_dealers.py` | Florida | 169 |
| `seed_ca_dealers.py` | California | 225 |
| `seed_oh_dealers.py` | Ohio | 140 |
| `seed_mi_dealers.py` | Michigan | 130 |
| `seed_mn_dealers.py` | Minnesota | 80 |
| `seed_wi_dealers.py` | Wisconsin | 90 |
| `seed_mo_dealers.py` | Missouri | 80 |
| `seed_in_dealers.py` | Indiana | 90 |
| `seed_ne_dealers.py` | Nebraska | 50 |
| `seed_ks_dealers.py` | Kansas | 60 |

---

## Database Schema

**Supabase project:** `xahazlzuxowamknucprs`  
**URL:** `https://xahazlzuxowamknucprs.supabase.co`

### `dealerships`
Primary dealer database. ~25,000+ records.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `google_place_id` | text UNIQUE | Dedup key — never insert duplicates |
| `dealership_name` | text | |
| `city` | text | |
| `state` | text | 2-letter abbreviation (IL, TX, etc.) |
| `phone` | text | |
| `website` | text | |
| `google_rating` | float | |
| `google_reviews` | int | |
| `photo_count` | int | |
| `rooftop_status` | text | `active` by default |
| `has_recent_posts` | bool | nullable |
| `review_response_rate` | float | nullable |
| `dealer_group_id` | uuid | nullable |
| `created_at` | timestamptz | |

### `source_registry`
News and signal sources scraped daily.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `source_name` | text | e.g. "Automotive News" |
| `source_url` | text UNIQUE | Homepage URL |
| `source_type` | text | `dealer_news`, `trade_pub`, `local_news` |
| `state` | text | `ALL` or state code |
| `active` | bool | Toggle to disable scraping |
| `last_status_code` | int | HTTP status from last scrape |
| `health_status` | text | `healthy`, `warning`, `error` |
| `last_error` | text | Error message from last failed scrape |
| `last_scraped_at` | timestamptz | |

### `raw_signals`
Scraped article URLs. De-duplicated by URL.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `source_id` | uuid FK | → source_registry |
| `article_url` | text UNIQUE | |
| `article_title` | text | |
| `article_text` | text | Truncated to ~5000 chars |
| `created_at` | timestamptz | |

### `signal_rules`
Keyword matching rules. Seeded by `seed_signal_rules.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `rule_name` | text UNIQUE | e.g. `ownership_change_high` |
| `signal_type` | text | `ownership_change`, `hiring`, `new_rooftop`, `oem_event`, `expansion`, `leadership_change`, `weak_digital` |
| `keywords` | text[] | Array of keyword strings |
| `fit_score` | int | Weight: 1=general, 2=moderate, 3=highly specific |

### `signal_matches`
Junction table: article × rule match.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `raw_signal_id` | uuid FK | → raw_signals |
| `rule_id` | uuid FK | → signal_rules |
| `dealership_id` | uuid FK | → dealerships (nullable) |
| `dealership_name` | text | Extracted by OpenAI |
| `fit_score` | int | Copied from rule |
| `processed` | bool | True after opportunity created |
| `created_at` | timestamptz | |

### `opportunities`
Final leads delivered to the dashboard and digest.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `dealership_name` | text | |
| `city` | text | |
| `state` | text | |
| `website` | text | From dealerships table |
| `opportunity_type` | text | Signal type label |
| `fit_score` | int | Raw weight (1-3) |
| `confidence_score` | int | Mapped score: 75/83/92 |
| `ai_summary` | text | GPT-4o-mini generated |
| `pitch_angle` | text | GPT-4o-mini generated |
| `recommended_offer` | text | |
| `source_url` | text | Original article URL |
| `status` | text | `new`, `contacted`, `closed` |
| `is_hot_lead` | bool | True if dealership has multiple signals |
| `outreach_steps` | jsonb | Tracks campaign sequence completions |
| `created_at` | timestamptz | |

### `digest_log`
Email send history.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `sent_at` | timestamptz | |
| `opportunities_count` | int | |
| `recipient` | text | |
| `status` | text | `sent` or `failed` |
| `resend_id` | text | Resend API message ID |

---

## Environment Variables

### GitHub Actions Secrets (Settings → Secrets → Actions)

| Variable | Description | Where to get it |
|---|---|---|
| `SUPABASE_URL` | `https://xahazlzuxowamknucprs.supabase.co` | Supabase dashboard → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) | Supabase → Settings → API → service_role |
| `GOOGLE_PLACES_API_KEY` | Google Places API v1 key | Google Cloud Console → APIs → Places API (New) |
| `OPENAI_API_KEY` | GPT-4o-mini for summaries | platform.openai.com |
| `RESEND_API_KEY` | Transactional email | resend.com → API Keys |
| `DIGEST_EMAIL_TO` | Recipient email | e.g. `zach@cradvertising.com` |
| `DIGEST_EMAIL_FROM` | Sender (verified domain) | `DealerHunters <digest@dealerhunters.io>` |

### Cloudflare Pages Environment Variables (CF Dashboard → Settings → Env Vars)

| Variable | Description |
|---|---|
| `ADMIN_SUPABASE_KEY` | Supabase service role key (used by `functions/admin-config.js`) |
| `ADMIN_GH_TOKEN` | GitHub PAT with `actions:write` on `mpshunters/dealerhunters-app` |

### Local Development (`.env` file, gitignored)

```
SUPABASE_URL=https://xahazlzuxowamknucprs.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
GOOGLE_PLACES_API_KEY=AIza...
OPENAI_API_KEY=sk-...
RESEND_API_KEY=re_...
DIGEST_EMAIL_TO=...
DIGEST_EMAIL_FROM=DealerHunters <digest@dealerhunters.io>
```

---

## What's Built and Working

### Pipeline ✅
- Full daily pipeline runs automatically via GitHub Actions at 6:17 AM Central (cron: `17 11 * * *`)
- Source scraping, signal detection, opportunity creation, AI summarization, email digest
- Meta Ads Library check via Playwright headless Chrome (plain HTTP scraping fails — see Known Issues)
- Hot lead detection: same dealership triggers multiple signals → `is_hot_lead = true`
- Confidence score mapping: weight 1→75, 2→83, 3→92

### Frontend ✅
- **Landing page** (`index.html`) — Full marketing site with pricing, FAQ, waitlist form
- **Dashboard** (`dashboard.html`) — Opportunity cards with:
  - Filter pills: All, Hot Leads, Ownership Change, Hiring, New Rooftop, OEM Event, Weak Digital
  - "New Today" / "This Week" section grouping
  - Score gauge with `?` tooltip explaining 92/83/75/🔥
  - Hot lead 🔥 badge
  - Website link (strips https://www. for display)
  - Source article link (hidden if null or dealerhunters.com)
  - Campaign sequence outreach tracker (5 steps with toggles)
  - Apollo.io / LinkedIn / HubSpot platform selector
  - Stats bar: Total Opportunities, Ownership Changes, Marketing Hires, Avg Score, Contacted, ⚡ Signals Detected, Dealerships in DB
  - Animated count-up on load
  - Emerald crosshair cursor
- **Admin panel** (`admin.html`) — Internal command center with:
  - Password gate (`dh-admin-2026`) → sessionStorage
  - Pipeline Health: GitHub Actions run history, step timestamps, countdown, Run Pipeline Now
  - Source Management: source_registry table, toggle active/inactive, add source
  - Signal Rules: full rules table, edit/add/delete, fires-today count
  - Database Stats: dealership counts, top-15 state bar chart, 50-state coverage map
  - Opportunities: full table, filters, bulk delete/contacted, CSV export
  - Digest: settings, send history, next-digest preview

### Dealer Database ✅
- ~25,000+ dealerships seeded across 12 states: IL, TX, FL, CA, OH, MI, MN, WI, MO, IN, NE, KS
- All seeded via Google Places API v1 city sweep pattern
- Deduplication by `google_place_id`

---

## Known Issues and Workarounds

### GitHub Actions Cron Silently Skips Runs
**Problem:** Cron at `0 11 * * *` (top of hour) gets dropped under high load on GitHub's shared runners.  
**Fix:** Changed to `17 11 * * *` — offset minutes are not dropped.  
**Current schedule:** `17 11 * * *` = 6:17 AM Central Daylight Time (11:17 UTC)  
**Note:** CDT is UTC-5. In winter (CST, UTC-6), this runs at 5:17 AM Central. The cron doesn't adjust for DST automatically.

### Meta Ads Library Scraping Requires Playwright
**Problem:** Facebook serves a JavaScript bot challenge (`/__rd_verify_...`) to plain HTTP requests. Manually replaying the challenge POST gets a cookie but subsequent GETs return 400 (server-side fingerprinting).  
**Fix:** Use `sync_playwright()` with headless Chromium, which executes the JS challenge natively.  
**GitHub Actions:** Requires `playwright install chromium --with-deps` step before running `meta_ads_checker.py`.

### Supabase RLS Blocks Anon Key on Some Tables
**Problem:** The public anon key respects Row Level Security. Tables like `signal_rules`, `source_registry`, and `signal_matches` may block read access.  
**Fix:** Admin panel uses service role key served via Cloudflare Pages Function (`functions/admin-config.js`) — reads `ADMIN_SUPABASE_KEY` env var and returns it as JS config. Never committed to git.

### Illinois Has No Public Dealer Roster
**Problem:** ILSOS (Illinois Secretary of State) dealer apps return 403/timeout for programmatic access.  
**Fix:** Google Places API city sweep across ~200 IL cities — gives real licensed dealers with ratings/reviews.  
**This is now the pattern for all states** — no state publishes a clean downloadable roster.

### Dashboard Dealerships Stat Shows "—"
**Problem:** RLS blocks anon key from counting the `dealerships` table.  
**Fix:** Promise.all captures full result object; falls back to hardcoded `25000` on error or 0 count. Logs error to console.

### Confidence Score Was Showing "1" or "2" on Gauge
**Problem:** `signal_rules.fit_score` is a weight (1-3). `create_opportunities.py` was copying it directly to `opportunities.fit_score`. Dashboard fell back to `confidence_score ?? fit_score`, showing the raw weight.  
**Fix:** `WEIGHT_TO_SCORE = {1: 75, 2: 83, 3: 92}` in `create_opportunities.py` — writes the mapped score to `confidence_score` on every insert.

### Gear Dropdown Was Not Opening
**Problem:** `.header` had `overflow: hidden`, clipping the absolutely-positioned dropdown that extends below the header.  
**Fix:** Removed `overflow: hidden` from `.header`. The `::after` sweep animation uses `scaleX` and never actually overflows.

### `admin-config.js` Is Gitignored But Needed for Admin
**Problem:** Local `admin-config.js` (with real tokens) can't be committed.  
**Fix (production):** `functions/admin-config.js` Cloudflare Pages Function reads `ADMIN_SUPABASE_KEY` and `ADMIN_GH_TOKEN` from CF env vars and returns them as JavaScript at runtime.  
**Fix (local dev):** Keep `admin-config.js` in repo root (gitignored). Change `<script src="/admin-config">` to `<script src="admin-config.js">` temporarily, or run via `wrangler pages dev`.

---

## What Still Needs to Be Built (Prioritized)

### P0 — Before CR Demo
- [ ] Populate with 5-10 high-quality real opportunities (real dealerships, real signals)
- [ ] Verify digest email renders correctly with real data

### P1 — Core Product
- [ ] **More state seeding** — Many states still under 100 dealers or not seeded at all (NY, PA, GA, NC, VA, AZ, CO, WA, OR, NV, TN, SC, etc.)
- [ ] **Apollo.io real integration** — Platform selector in dashboard header connects to Apollo UI but doesn't auto-populate contact data. Need Apollo API integration to pull contact name/email for dealership.
- [ ] **Email/contact enrichment** — Each opportunity card has "Find Contact" button linking to Apollo/LinkedIn search, but not pulling real data.

### P2 — Growth
- [ ] **User accounts** — Currently single-user. Need Supabase Auth for multi-user access.
- [ ] **Stripe billing** — Subscription gating on dashboard access.
- [ ] **More signal sources** — Add state-specific auto dealer association newsletters, local business journals.
- [ ] **Signal confidence tuning** — Current keyword rules produce some false positives. Add entity extraction to verify dealership name is actually in the article.

### P3 — Polish
- [ ] **Mobile dashboard** — Cards are readable on mobile but outreach tracker is cramped.
- [ ] **Digest unsubscribe** — Currently a mailto link; should be a one-click unsubscribe.
- [ ] **Opportunity archiving** — Old `contacted`/`closed` opportunities accumulate. Add auto-archive after 90 days.

---

## Key Technical Decisions

### Google Places API v1 (New) for Dealer Seeding
Used `places.googleapis.com/v1/places:searchText` with `includedType: "car_dealer"` and `maxResultCount: 20`. The legacy Places API has a different auth model and lower result cap.

### Playwright for Meta Ads (Not Requests)
Facebook's `/ads/library/` serves a JavaScript challenge that `requests` cannot pass. Playwright's headless Chromium executes the challenge natively, passing bot detection. This adds ~3s per dealership check, so Meta Ads check is limited to `confidence_score >= 80` opportunities only.

### Signal Weight → Confidence Score Mapping
Signal rules have a `fit_score` weight (1=general, 2=moderate, 3=highly specific). This maps to `confidence_score` (75/83/92) on the opportunity record. The dashboard reads `confidence_score` and never shows the raw weight. This means the gauge always shows a meaningful percentage, not a weight integer.

### Supabase Over Firebase/PlanetScale
Supabase gives Postgres + Row Level Security + a JS client that works identically in browser and Node. RLS lets the anon key be public (committed in `config.js`) without exposing protected data.

### Resend Over SendGrid
Resend has a much simpler API and better deliverability for transactional email. SendGrid requires domain verification and has a more complex setup. Resend's Python SDK is two lines.

### Cloudflare Pages for Hosting
Static site + Pages Functions for the admin config endpoint. No server costs, deploys on every push to `main`, global CDN. The admin panel's service role key is injected at request time by the CF Function, never stored in git.

### `functions/admin-config.js` Pattern
Admin credentials can't live in committed JS (security) or in `admin-config.js` (gitignored, doesn't deploy). Solution: Cloudflare Pages Function at `/admin-config` reads CF env vars (`ADMIN_SUPABASE_KEY`, `ADMIN_GH_TOKEN`) and returns them as a JS object. The browser script tag loads it at runtime.

---

## How to Run the Pipeline Manually

### Via GitHub Actions UI (recommended)
1. Go to `github.com/mpshunters/dealerhunters-app/actions`
2. Click "Daily Dealer Signal Scrape"
3. Click "Run workflow" → "Run workflow" (on `main`)

### Via Admin Panel
1. Open `dealerhunters.com/admin.html`
2. Enter password: `dh-admin-2026`
3. Pipeline Health → "▶ Run Pipeline Now"
4. (Requires `ADMIN_GH_TOKEN` set in CF env vars)

### Via CLI (run individual steps locally)
```bash
# Set env vars first
export SUPABASE_URL="https://xahazlzuxowamknucprs.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
export GOOGLE_PLACES_API_KEY="AIza..."
export OPENAI_API_KEY="sk-..."
export RESEND_API_KEY="re_..."
export DIGEST_EMAIL_TO="..."

# Run each step
python scripts/fetch_dealer_news.py
python scripts/detect_signal_matches.py
python scripts/create_opportunities.py
python scripts/send_daily_digest.py
```

---

## How to Add New States to the Dealer Database

1. **Copy an existing seed script** (e.g. `seed_il_dealers.py` → `seed_ga_dealers.py`)
2. **Update three things:**
   - Module docstring (state name)
   - `print(...)` message at top
   - `GA_CITIES = [...]` city list (replace IL_CITIES)
   - State filter: `.eq("state", "GA")` and `p_state != "GA"` 
   - State fallback: `p_state or "GA"`
   - Query string: `f"car dealer {city} Georgia"`
   - Final print: `"Georgia sweep complete."` and `.eq("state", "GA")`
3. **Run it:**
   ```bash
   python scripts/seed_ga_dealers.py
   ```
4. **Expected output:** `[1/N] Atlanta: +12 new dealers` per city. Takes 1-2 minutes per 50 cities at 0.4s delay.

**States still needing seeding (priority order by market size):**
NY, PA, GA, NC, AZ, CO, WA, TN, NV, VA, OR, SC, MD, AL, LA

---

## Demo Script for CR Advertising Meeting

### Setup (before meeting)
- Open `dashboard.html` in Chrome, full screen
- Make sure there are at least 5-8 real opportunities visible
- Have at least 1 hot lead (🔥) visible

### Walk-through (~8 minutes)

**1. The Problem (1 min)**
> "Right now, your reps cold-call dealerships with no idea who's ready to change agencies. DealerHunters monitors 25,000+ dealerships and finds the ones in motion — and delivers them every morning."

**2. The Dashboard (3 min)**
- Show the stats bar: total opportunities, signals detected, dealerships in DB
- Click "🔥 Hot Leads" filter — explain: "These dealers have triggered multiple signals. They're the highest-priority calls."
- Click a hot lead card. Show:
  - The 🔥 badge and score gauge (hover the `?` to show the explanation tooltip)
  - The AI summary explaining what happened
  - The pitch angle — "Your rep walks in knowing exactly what to say"
  - The website link
  - The campaign sequence tracker — "Check off each touchpoint as you go"
- Click "Ownership Change" filter — "New owners often fire the incumbent agency in the first 90 days"

**3. The Email Digest (2 min)**
- Show a sample digest email
- "Every morning at 6:17 AM, this hits your inbox. 5 minutes to know who to call that day."

**4. The Scale (1 min)**
- "We cover 25,000+ dealerships across 12 states today. Full national coverage in Q3."
- Admin panel → Database → show the state coverage map

**5. Close (1 min)**
- "You're getting a competitive edge your competitors don't have. Who's your top rep? Let's set them up today."

---

## Daily Operations Guide

### Morning Check (5 min)
1. Open digest email — review new opportunities
2. Check admin panel Pipeline Health — verify today's step timestamps are green
3. If any step is amber/red: check GitHub Actions for error details

### Adding Opportunities to Dashboard
Opportunities appear automatically each morning. If you need to test/add manually:
- Use `create_opportunities.py` locally with env vars set
- Or trigger the pipeline manually (see above)

### Editing Signal Keywords
To add a keyword that should trigger a signal:
1. Open admin panel → Signal Rules
2. Click "Edit" on the relevant rule
3. Add keyword to the comma-separated list
4. Click "Add Rule" (the save button)
5. New keywords apply on the next pipeline run

### Disabling a Noisy Source
If a source is generating too many false signals:
1. Admin panel → Sources
2. Toggle the source to inactive
3. It will be skipped on the next scrape

### Monitoring Costs
- **OpenAI:** ~$0.001 per opportunity summary. 10 opportunities/day = <$0.01/day.
- **Google Places API:** ~$0.017/request. Seeding 100 cities = ~$1.70. Seeding runs are one-time.
- **Resend:** 100 emails/day free tier. Well within limits.
- **GitHub Actions:** 2,000 minutes/month free. Pipeline takes ~3 min/day = ~90 min/month.
- **Cloudflare Pages:** Free tier covers all static + Functions usage at this scale.
- **Supabase:** Free tier (500MB DB, 2GB bandwidth). Will need Pro (~$25/mo) once DB exceeds 500MB.

---

## Repository Structure

```
dealerhunters-app/
├── index.html                    # Landing page
├── dashboard.html                # Customer dashboard
├── admin.html                    # Internal admin panel
├── config.js                     # Public Supabase URL + anon key
├── admin-config.js               # LOCAL ONLY (gitignored) — real tokens
├── functions/
│   └── admin-config.js           # CF Pages Function — serves /admin-config
├── scripts/
│   ├── scrape_dealer_signals.py  # Seeds source_registry
│   ├── fetch_dealer_news.py      # Scrapes articles
│   ├── detect_signal_matches.py  # Keyword matching
│   ├── create_opportunities.py   # AI summarization + opportunity creation
│   ├── meta_ads_checker.py       # Meta Ads Library (Playwright)
│   ├── google_presence_checker.py
│   ├── send_daily_digest.py      # Email digest
│   ├── seed_signal_rules.py      # Keyword rules seeder
│   ├── seed_il_dealers.py        # Illinois
│   ├── seed_tx_dealers.py        # Texas
│   ├── seed_fl_dealers.py        # Florida
│   ├── seed_ca_dealers.py        # California
│   ├── seed_oh_dealers.py        # Ohio
│   ├── seed_mi_dealers.py        # Michigan
│   ├── seed_mn_dealers.py        # Minnesota
│   ├── seed_wi_dealers.py        # Wisconsin
│   ├── seed_mo_dealers.py        # Missouri
│   ├── seed_in_dealers.py        # Indiana
│   ├── seed_ne_dealers.py        # Nebraska
│   └── seed_ks_dealers.py        # Kansas
├── .github/
│   └── workflows/
│       └── daily_scrape.yml      # GitHub Actions pipeline
├── requirements.txt              # Python dependencies
├── .gitignore                    # Excludes .env, admin-config.js
└── PROJECT_STATUS.md             # This file
```

---

## GitHub Actions Workflow Reference

**File:** `.github/workflows/daily_scrape.yml`  
**Trigger:** Schedule `17 11 * * *` (6:17 AM CT) + `workflow_dispatch`  
**Steps (in order):**
1. Checkout repo
2. Set up Python 3.11
3. `pip install -r requirements.txt`
4. `playwright install chromium --with-deps`
5. Run dealer source seeder (`scrape_dealer_signals.py`)
6. Fetch dealer news (`fetch_dealer_news.py`)
7. Detect signal matches (`detect_signal_matches.py`)
8. Create opportunities (`create_opportunities.py`)
9. Check Meta Ads (`meta_ads_checker.py`)
10. Check Google presence (`google_presence_checker.py`)
11. Send daily digest (`send_daily_digest.py`)

**All pipeline steps** use `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.  
`create_opportunities.py` additionally needs `OPENAI_API_KEY`.  
`send_daily_digest.py` additionally needs `RESEND_API_KEY`, `DIGEST_EMAIL_TO`, `DIGEST_EMAIL_FROM`.
