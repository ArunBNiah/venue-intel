# Venue Intelligence Project Review

**Last Updated:** 2024-12-30
**Status:** MVP Live
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

### Current State: 39,489 venues across 8 cities

| City | Country | Venues | Premium |
|------|---------|--------|---------|
| London | UK | 19,320 | 1,236 |
| Berlin | Germany | 7,718 | 309 |
| Paris | France | 5,443 | 426 |
| Marseille | France | 1,860 | 61 |
| Lyon | France | 1,755 | 105 |
| Düsseldorf | Germany | 1,611 | 62 |
| Toulouse | France | 956 | 39 |
| Bordeaux | France | 825 | 76 |

### Top Venue Types
| Type | Count | Avg Score |
|------|-------|-----------|
| Restaurant | 18,552 | 62.8 |
| Cafe | 5,064 | 49.4 |
| Bar | 4,654 | 69.5 |
| Pub | 2,929 | 63.6 |
| Hotel | 1,730 | 56.7 |
| Cocktail Bar | 817 | 81.4 |
| Wine Bar | 374 | 77.9 |

### Data Source
- **Historical import** from user's previous research (8 CSV files)
- Marked as `score_version = "1.0-historical"`
- Confidence capped at MEDIUM (unknown freshness)
- Place IDs banked for future API refresh

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

## Streamlit MVP Features

### Pages
1. **Overview** - Database stats, venue counts by city, charts
2. **Explore Venues** - Filter by city, type, score, tiers, premium status
3. **Export Data** - Download filtered results as CSV/Excel
4. **Request New City** - Cost estimate (API disabled by default)

### Filters Available
- City (dropdown)
- Venue type (dropdown)
- Minimum score (slider)
- Premium only (checkbox)
- Volume tier (dropdown)
- Quality tier (dropdown)
- Max results (dropdown)

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

## Next Steps (Prioritised)

### High Priority
1. **Improve UI/UX** - Better styling, mobile responsive, clearer navigation
2. **Validate scoring** - Export top venues, review manually, tune weights
3. **Enable new city requests** - Wire up API with cost confirmation

### Medium Priority
4. **Add authentication** - User accounts for commercial use
5. **Brand category profiles** - Different scoring for whisky vs wine vs beer
6. **Refresh strategy** - Identify stale data, selective refresh
7. **Keyword search in reviews** - See details below

### Lower Priority
8. **Custom domain** - Professional URL
9. **Usage tracking** - Credits/subscription system
10. **Affluence integration** - Location intelligence overlay (see docs/relevance-rubric.md)

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

## Session Log (2024-12-30)

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

*This document is designed to be shared with LLM assistants to provide full context for continuing the project.*
