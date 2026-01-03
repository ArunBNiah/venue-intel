# Venue Intelligence Project Review

**Last Updated:** 2025-01-02
**Status:** MVP Live (v1.1)
**App URL:** https://venue-intel-9tbkizjkdji3cdm5l8ljot.streamlit.app/
**Repo:** https://github.com/ArunBNiah/venue-intel

---

## Project Overview

### Purpose
A decision-support system for beverage companies to answer: **"Which venues in a given city should be prioritised for distribution of a specific brand — and in what order?"**

### Target Users
- Commercial teams at beverage brands (brand managers, sales teams)
- Spreadsheet-literate, skeptical of black-box AI
- Need ranked lists, filters, exports

### Learning Goals
This project was built as a practical AI learning exercise with principles:
- Build real, sellable products
- Deterministic before probabilistic
- Explainable scoring
- Commercial viability from day one

---

## Technical Architecture

### Stack
- **Language:** Python 3.11+
- **Database:** SQLite (venue_intelligence.db)
- **Web Framework:** Streamlit
- **Data Validation:** Pydantic
- **Deployment:** Streamlit Community Cloud
- **Version Control:** GitHub

### Directory Structure
```
venue-intel/
├── app/
│   ├── venue_intel_app.py      # Streamlit MVP
│   └── README.md               # Deployment guide
├── data/
│   ├── processed/
│   │   └── venue_intelligence.db  # 20MB, 39,489 venues
│   ├── raw/                    # Historical CSVs (gitignored)
│   └── exports/                # User exports (gitignored)
├── docs/
│   ├── PROJECT.md              # Master reference
│   ├── PROJECT-REVIEW.md       # This file
│   ├── costed-data-plan.md     # API cost analysis
│   ├── data-freshness.md       # Refresh strategy
│   ├── mvp-ui.md               # UI requirements
│   ├── relevance-rubric.md     # M-signal definition
│   └── subscription-model.md   # Commercial model
├── src/venue_intel/
│   ├── models.py               # Pydantic data contracts
│   ├── storage.py              # SQLite operations
│   ├── scoring.py              # V/R/M algorithm
│   ├── fetch.py                # Google Places API client
│   ├── pipeline.py             # Orchestration
│   ├── export.py               # CSV/Excel export
│   └── import_historical.py    # Bulk import script
├── .streamlit/
│   └── config.toml             # Theme configuration
├── requirements.txt
└── .gitignore
```

---

## Scoring Algorithm (V/R/M)

### Distribution Fit Score (0-100)
```
Score = (0.25 × V) + (0.25 × R) + (0.50 × M) × 100
```

### Signal Definitions

| Signal | Name | Weight | Source |
|--------|------|--------|--------|
| V | Volume/Visibility | 25% | Review count (log-scaled) |
| R | Quality/Reputation | 25% | Rating with confidence adjustment |
| M | Relevance/Match | 50% | Type + Price + Keywords + Attributes |

### M Sub-components
- **Type Score:** Venue type relevance (cocktail_bar=1.0, pub=0.5, cafe=0.3)
- **Price Score:** Price level alignment (premium=1.0, budget=0.1)
- **Keyword Score:** Editorial summary keyword matching
- **Attribute Score:** Boolean attributes (servesCocktails, reservable, etc.)

---

## Data Compliance (Google ToS)

### Key Principle
Store **derived tiers** (our categorisation), NOT raw Google values.

### What We Store (Compliant)
| Field | Example | Why Allowed |
|-------|---------|-------------|
| place_id | ChIJ... | Google explicitly permits |
| name | "Swift Soho" | Public information |
| address | "12 Old Compton St" | Public information |
| volume_tier | "high" | Our categorisation |
| quality_tier | "excellent" | Our categorisation |
| price_tier | "premium" | Our categorisation |
| distribution_fit_score | 81.5 | Our IP (computed score) |
| rationale | "Strong venue type fit..." | Our generated content |

### What We DON'T Store
| Field | Example | Why Excluded |
|-------|---------|--------------|
| rating | 4.6 | Raw Google data |
| user_rating_count | 1706 | Raw Google data |
| price_level | 3 | Raw Google data |
| reviews | [...] | Raw Google data |

### Tier Mappings
```python
# Volume Tier (from review count)
VERY_HIGH: 5000+ reviews
HIGH: 1000-4999
MEDIUM: 200-999
LOW: 50-199
VERY_LOW: <50

# Quality Tier (from rating)
EXCELLENT: 4.5+
GOOD: 4.0-4.4
AVERAGE: 3.5-3.9
BELOW_AVERAGE: 3.0-3.4
POOR: <3.0

# Price Tier (from price level)
PREMIUM: level 3-4
MID: level 2
BUDGET: level 0-1
UNKNOWN: no data
```

---

## Database Contents

### Current State: 75,861 venues across 11 cities, 5 countries

| City | Country | Venues | W50B Bars |
|------|---------|--------|-----------|
| Tokyo | Japan | 28,725 | 8 |
| London | UK | 19,320 | 7 |
| Berlin | Germany | 7,718 | 1 |
| New York | USA | 5,505 | 7 |
| Paris | France | 5,443 | 3 |
| Chicago | USA | 2,143 | 1 |
| Marseille | France | 1,860 | - |
| Lyon | France | 1,755 | - |
| Düsseldorf | Germany | 1,611 | - |
| Toulouse | France | 956 | - |
| Bordeaux | France | 825 | - |

### By Country
| Country | Venues |
|---------|--------|
| Japan | 28,725 |
| UK | 19,320 |
| France | 10,839 |
| Germany | 9,329 |
| USA | 7,648 |

### Top Venue Types
| Type | Count |
|------|-------|
| Restaurant | 24,753 |
| Bar | 21,033 |
| Cafe | 5,442 |
| Pub | 3,856 |
| Izakaya | 3,248 |
| Cocktail Bar | 1,200+ |

### Authority Data
**43 bars** flagged from respected industry lists:

| List | Bars Matched | Coverage |
|------|-------------|----------|
| World's 50 Best Bars | 27 | 1-100 (global) |
| Asia's 50 Best Bars | 8 | 1-100 (Tokyo) |
| North America's 50 Best Bars | 15 | 1-50 (NYC, Chicago) |

- Authority tiers: `elite` (top 50 on any list), `notable` (51-100)
- Stored in: `on_worlds_50_best`, `on_asias_50_best`, `on_north_americas_50_best` (plus rank columns)

### Data Source
- **Historical import** from research data (CSV/XLSX files)
- Marked as `score_version = "1.0-historical"`
- Confidence capped at MEDIUM (unknown freshness)
- Place IDs banked for future API refresh (~60% cost savings)

---

## API Cost Structure

### Google Places API (New) Pricing
| API | Cost per 1k | Use |
|-----|-------------|-----|
| Text Search Pro | $32 | Discovery |
| Place Details Enterprise | $20 | Basic scoring |
| Place Details + Atmosphere | $25 | With reviews |

### Budget
- **Total budget:** $50
- **Spent:** ~$0.50 (test queries)
- **Remaining:** ~$49.50

### Cost per City (estimate)
- Small city (<1M pop): $50-100
- Medium city (1-5M pop): $100-200
- Large city (>5M pop): $200-400

---

## Streamlit MVP Features (v1.1)

### Pages
1. **Overview** - Database stats, venue counts by city/country, charts
2. **Explore Venues** - Multi-filter search with map visualization
3. **Export Data** - Download filtered results as CSV/Excel
4. **Validation Export** - Export top venues for manual review
5. **Request New City** - Cost estimate (API disabled by default)

### Filter Capabilities
- **City** - Dropdown with all 11 cities
- **Venue Types** - Multi-select, sorted by frequency, formatted display
- **Minimum Score** - Slider (0-100)
- **Premium Only** - Checkbox
- **World's 50 Best Only** - Checkbox
- **Beverage Signals** - Serves Cocktails, Serves Spirits, Great Cocktails
- **Venue Signals** - Upscale, Late Night
- **Advanced** - Volume tier, Quality tier, Max results

### Map Visualization
- **Markers View** - Color-coded by score (green=80+, red=<50)
- **Heatmap View** - Density visualization for hotspot identification
- Toggle between views with radio buttons

### Professional Styling
- No emojis - text-based badges throughout
- CSS-styled authority badges (W50B)
- Clean legend with colored dots

---

## Key Files for LLM Context

### To understand the data model:
- `src/venue_intel/models.py` - Pydantic models, tier enums, VenueRecord

### To understand scoring:
- `src/venue_intel/scoring.py` - V/R/M algorithm, create_venue_record()
- `docs/relevance-rubric.md` - M signal definition

### To understand storage:
- `src/venue_intel/storage.py` - SQLite operations, compliant schema

### To understand the app:
- `app/venue_intel_app.py` - Streamlit MVP

### To understand costs:
- `docs/costed-data-plan.md` - API pricing, budget strategy

---

## Decisions Made

### Why SQLite?
- Simple, portable, no server needed
- Database file can be committed to repo (20MB)
- Sufficient for MVP scale (40k venues)
- Easy to migrate to PostgreSQL later

### Why Streamlit?
- Python-only (no JS/HTML needed)
- Fast to build
- Free deployment on Community Cloud
- Good enough for MVP, can migrate later

### Why derived tiers instead of raw values?
- Google ToS compliance
- Values change over time anyway
- Tiers are more stable and actionable
- "High volume" is more useful than "1706 reviews"

### Why historical import before API?
- Zero cost to populate 39k venues
- Place IDs banked for future refresh
- Immediate coverage across 8 cities
- Validate scoring before spending budget

---

## Product Roadmap

### Guiding Principles
- Deterministic scoring remains the source of truth
- AI may interpret, but must not decide or override
- All new signals must be explainable, bounded, and reviewable
- Platform Terms of Service must be respected
- Variable costs must remain predictable and controllable

---

### Phase 1: Foundation & Explanation (Current Focus)

**Authority Signal Expansion**
- [x] World's 50 Best Bars (1-100)
- [x] Asia's 50 Best Bars (1-100) - 8 Tokyo bars matched
- [x] North America's 50 Best Bars (1-50) - 15 NYC/Chicago bars matched
- [ ] Tales of the Cocktail Spirited Awards
- [ ] Michelin Guide (for restaurant/bar overlap)
- [ ] Local "Best of" lists per city

**AI Explanation Layer**
- [ ] OpenAI integration for natural language queries
- [ ] "Explain this ranking" - Why is Venue A higher than B?
- [ ] "Compare venues" - Trade-offs between X and Y
- [ ] "Summarise patterns" - What defines top-tier venues in Paris?
- [ ] Cost controls: query caching, token limits, rate limiting

**Immediate Priorities**
- [ ] Validate scoring - export top 50 per city, manual review
- [ ] Enable new city requests - wire up API with cost confirmation
- [ ] Add authentication - user accounts for commercial use

---

### Phase 2: Momentum & Signals (Near-Term)

**Momentum Signals**
- [ ] Review velocity tracking (via periodic Places API refresh)
- [ ] Authority list delta (new additions vs last year)
- [ ] Directional classification: Rising / Stable / Declining / Unknown
- [ ] Momentum as context layer, not ranking input (initially)

**Brand Category Profiles**
- [x] M sub-component storage (type, price, attribute, keyword scores)
- [x] Type classifications (is_cocktail_focused, is_dining_focused, etc.)
- [x] Profile-based M recalculation (premium_spirits, craft_beer, fine_wine, budget_drinks)
- [ ] User-selectable brand lens in UI
- [ ] Custom profile creation

**AI Comparison Features**
- [ ] Multi-venue comparison tables
- [ ] Scenario exploration (not persona simulation)
- [ ] "What aspects align with premium positioning?"

**Data Quality**
- [ ] Refresh strategy - identify stale data, selective API refresh
- [ ] Data freshness indicators in UI
- [ ] Confidence tier improvements

---

### Phase 3: Advanced Intelligence (Conditional)

**Licensed Data Integration**
- [ ] Evaluate licensed social/media data sources
- [ ] Digital sophistication composite signal
- [ ] Only proceed if clear value and ToS compliance

**User-Defined Personas**
- [ ] Users upload own persona definitions (from real research)
- [ ] AI applies user's lens consistently across venues
- [ ] NOT pre-built synthetic personas (risk of misuse)

**Advanced Interpretive Queries**
- [ ] Complex multi-factor queries
- [ ] Historical trend analysis
- [ ] Cross-city pattern comparison

---

### Deprioritised / Deferred

| Feature | Reason |
|---------|--------|
| Social presence (has_instagram: Y/N) | Too weak without engagement metrics |
| Pre-built synthetic personas | Risk of users over-weighting fiction |
| Real-time social monitoring | ToS concerns, high cost |
| Affluence integration | Evaluate after core features stable |

---

### Commercial Packaging (Future)

**Core Subscription**
- Authority badges (all sources)
- AI-powered explanations & comparisons
- Full filter and export capabilities

**Premium Add-ons**
- Momentum signals
- Brand category profiles
- User-defined persona upload
- Advanced interpretive queries

---

## Future Feature: Keyword Search in Reviews

### Concept
Allow users to search for venues where Google reviews mention specific keywords (e.g., "whisky", "non-alcoholic", "craft gin").

### How It Works
1. User enters keywords and selects a city
2. System fetches reviews for **pre-filtered subset** (e.g., top 200 cocktail bars)
3. Searches review text in-memory for keyword matches
4. Returns venues ranked by mention count with snippets
5. Stores derived theme tags (compliant) - discards raw review text

### Cost Strategy (Option A - Pre-filter)
- Only fetch reviews for high-value, pre-filtered venues
- Example: Top 100 cocktail bars in London = ~$2.50
- NOT all 19k venues = ~$475

### Compliance
- Display review snippets with Google attribution ✅
- Store derived insights ("whisky_mentions": 3) ✅
- Do NOT store raw review text ❌

### API Details
- Uses Place Details + Atmosphere tier: $25/1k venues
- Returns up to 5 reviews per venue
- No native "search within reviews" - we filter in our code

---

## How to Continue This Project

### For an LLM assistant:
1. Read this file first for context
2. Check `src/venue_intel/models.py` for data structures
3. Check `app/venue_intel_app.py` for current UI
4. Budget constraint: $50 total, ~$49.50 remaining
5. Database is at `data/processed/venue_intelligence.db`

### Key commands:
```bash
# Run locally
cd ~/projects/venue-intel
streamlit run app/venue_intel_app.py

# Test imports
PYTHONPATH=src python -c "from venue_intel.storage import get_venue_count; print(get_venue_count())"

# Push changes
git add -A && git commit -m "message" && git push
```

### After pushing:
Streamlit Cloud auto-redeploys from main branch (takes ~1 min).

---

## Session Log (2024-12-30) - Initial Build

### What was accomplished:
1. Reviewed and refined project plan
2. Built data models with Pydantic (models.py)
3. Created Google Places API client (fetch.py)
4. Implemented V/R/M scoring algorithm (scoring.py)
5. Built compliant storage layer with derived tiers (storage.py)
6. Imported 39,489 historical venues (8 cities, 3 countries)
7. Created Streamlit MVP with 4 pages
8. Deployed to Streamlit Cloud
9. Set up GitHub repo

### Time: ~4 hours
### Cost: ~$0.50 API calls (testing)

---

## Session Log (2024-12-30) - US Cities & Binary Signals

### What was accomplished:

**Data Expansion:**
1. Imported New York (2,874 venues) and Chicago (2,156 venues)
2. Total database now: 44,518 venues across 10 cities, 4 countries

**Binary Signals (ToS-Compliant):**
Added 9 derived binary signal columns:
- `serves_cocktails`, `serves_wine`, `serves_beer`, `serves_spirits` (from Offerings)
- `has_great_cocktails`, `has_great_beer`, `has_great_wine` (from Highlights)
- `is_upscale` (from Atmosphere)
- `is_late_night` (derived from working hours)

Handled locale variations:
- US: "Hard liquor", "Upscale"
- UK/EU: "Spirits", "Upmarket"

**UI Improvements:**
1. Added interactive pydeck map with score color-coding
2. Added "Beverage & Venue Signals" filter panel (5 checkboxes)
3. Fixed map rendering (removed Mapbox token dependency)
4. Added signals to CSV/Excel exports

**Data Quality Fixes:**
- Removed incorrect Berlin/UK venue
- Normalized city names to lowercase
- Fixed Düsseldorf Unicode normalization

### Signal Coverage by City:
| City | Serves Spirits | Upscale | Late Night |
|------|----------------|---------|------------|
| New York | 76% | 16% | 65% |
| Chicago | 78% | 11% | 70% |
| London | 46% | 7% | 30% |
| Berlin | 62% | 6% | 43% |
| Paris | 63% | 9% | 35% |

### Cost: $0 (used historical data only)

---

## Session Log (2025-01-02) - Tokyo Import & UI Overhaul

### Data Expansion
1. Imported NYC boroughs (Brooklyn, Queens, Bronx) - 2,631 venues
2. New York total now 5,505 venues
3. Imported Tokyo metropolitan area - 28,725 venues
4. Fixed JSON parsing for Tokyo signals (json.loads vs ast.literal_eval)
5. Tokyo now largest city in database

### World's 50 Best Integration
- Fetched 1-100 list from theworlds50best.com
- Matched and flagged 27 bars across all cities
- Added columns: on_worlds_50_best, worlds_50_best_rank, authority_tier
- Tokyo: 8 bars (Bar Benfiddich #3, The SG Club #10, etc.)
- Clover Club (Brooklyn) added as #36

### UI Improvements
1. Multi-select venue type filter (can pick Bar + Pub + Cocktail Bar)
2. Venue types sorted by count (Restaurant: 24,753 at top)
3. Formatted display names (adult_entertainment_club → Adult Entertainment Club)
4. Added heatmap view alongside marker view
5. Removed all emojis - professional text badges
6. CSS-styled authority badges
7. Improved dropdown UX with placeholder text

### Cost: $0 (all historical data imports)

---

## Session Log (2025-01-03) - Authority Sources Expansion

### Authority Sources Added
1. Fetched Asia's 50 Best Bars 2024 (ranks 1-100)
2. Fetched North America's 50 Best Bars 2024 (ranks 1-50)
3. Added database columns for new authority sources
4. Matched and flagged bars across all lists

### Bars Matched
- **Tokyo (Asia's 50 Best):** 8 bars (#9 Bar Benfiddich through #99 The SG Club)
- **NYC (NA's 50 Best):** 11 bars (#2 Superbueno through #46 Dante)
- **Chicago (NA's 50 Best):** 4 bars (#10 Kumiko, #25 Best Intentions, #38 Meadowlark, #39 Bisous)
- Some bars appear on multiple lists (e.g., Bar Benfiddich: W50B #3, A50B #9)

### UI Updates
1. Filter renamed: "50 Best Bars Only" (covers all lists)
2. Authority badges show all applicable rankings (W50B, A50B, NA50B)
3. Overview page shows authority breakdown by source
4. Export includes all authority columns

### Cost: $0 (web scraping for authority lists)

---

## Session Log (2025-01-03) - Brand Profile Flexibility

### Problem Solved
M score was hardcoded for premium spirits. Recalculating for different brand profiles (e.g., craft beer, budget drinks) would require re-fetching Google data, violating ToS scalability.

### Solution Implemented
Store M sub-components and type classifications derived from existing data:

**New Columns Added:**
- Type classifications: `is_cocktail_focused`, `is_dining_focused`, `is_nightlife_focused`, `is_casual_drinking`
- M sub-components: `m_type_score`, `m_price_score`, `m_attribute_score`, `m_keyword_score`

**Pre-defined Brand Profiles:**
| Profile | Description | Effect |
|---------|-------------|--------|
| premium_spirits | Cocktail bars, upscale venues | Cocktail bars rank highest |
| craft_beer | Pubs, beer-focused venues | Pubs dominate rankings |
| fine_wine | Wine bars, fine dining | Dining venues boosted |
| budget_drinks | High-volume, budget-friendly | Price score inverted |

**Example - London Top 3:**
- Premium Spirits: Simmons Bar, Cahoots Underground, F1 Arcade
- Craft Beer: Old Shades, The Marquis Cornwallis, The Churchill Arms

### ToS Compliance
All new columns are our derived assessments, not raw Google data:
- Type classifications derived from stored `venue_type`
- M sub-components approximated from stored tiers and signals
- `m_keyword_score` set to neutral (0.5) as we don't store editorial summary

### Limitation
`m_keyword_score` cannot vary by profile (no editorial summary stored). To fully support keyword-based differentiation, would need to store editorial summary or re-fetch.

### Cost: $0 (derived from existing data)

---

## Current Database State

**75,861 venues across 11 cities, 5 countries:**
| City | Country | Venues | Authority Bars |
|------|---------|--------|----------------|
| Tokyo | Japan | 28,725 | 14 (W50B + A50B) |
| London | UK | 19,320 | 7 (W50B) |
| Berlin | Germany | 7,718 | 1 (W50B) |
| New York | USA | 5,505 | 14 (W50B + NA50B) |
| Paris | France | 5,443 | 3 (W50B) |
| Chicago | USA | 2,143 | 4 (W50B + NA50B) |
| Marseille | France | 1,860 | - |
| Lyon | France | 1,755 | - |
| Düsseldorf | Germany | 1,611 | - |
| Toulouse | France | 956 | - |
| Bordeaux | France | 825 | - |

**Total authority bars:** 43 (across 3 lists, some overlap)

---

## Recommended Next Steps (Immediate)

Based on current state and roadmap, recommended focus:

1. **Validate Scoring** - Export top 50 cocktail bars per major city, manual review with domain expert
2. **Tales of the Cocktail Spirited Awards** - Add winners from Best International Cocktail Bar, Best US Bar categories
3. **OpenAI Integration** - Build explanation layer with cost controls
4. **Enable API Refresh** - Wire up new city requests with cost confirmation

These deliver immediate value while setting foundation for Phase 2.

---

*This document is designed to be shared with LLM assistants to provide full context for continuing the project.*
