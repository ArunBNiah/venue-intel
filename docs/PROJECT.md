# Venue Intelligence & Distribution Prioritisation System

**Version**: 0.1.0
**Status**: Phase 1 — Foundations
**Last Updated**: 2025-12-29

---

## 1. Executive Summary

### What This Is
A decision-support system that answers:

> "Which venues in a given city should be prioritised for distribution of a specific brand — and in what order?"

### What This Is Not
- Not an AI demo
- Not a black-box scoring system
- Not a replacement for commercial judgement

### Core Principle
**AI is an augmentation layer, not the source of truth.**

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [PROJECT.md](PROJECT.md) | This document — master reference |
| [subscription-model.md](subscription-model.md) | Commercial packaging, pricing tiers, unit economics |
| [data-freshness.md](data-freshness.md) | Refresh strategy, staleness rules, caching |
| [mvp-ui.md](mvp-ui.md) | Minimal viable UI components and design |
| [costed-data-plan.md](costed-data-plan.md) | API costs, fetch strategy, budget controls |
| [relevance-rubric.md](relevance-rubric.md) | M signal definition, scoring logic, theme weights |

---

## 2. Learning Context

This project serves a dual purpose:
1. **Deliver a real, sellable product** — a polished MVP for commercial teams
2. **Develop practical AI expertise** — through building, not theory

### Learning Pillars

| Pillar | Focus |
|--------|-------|
| A. AI Systems Design | Workflow decomposition, orchestration, guardrails |
| B. Data Engineering for AI | Structured vs unstructured, data contracts, ephemeral patterns |
| C. Explainability & Trust | Score breakdowns, confidence tiers, human override points |
| D. Productisation | Configuration over custom logic, repeatable pipelines |
| E. Evaluation & Governance | Failure modes, drift awareness, when AI should defer |

### Philosophy
- Build first, optimise later
- Deterministic before probabilistic
- Explainable before impressive
- Reuse over reinvention

---

## 3. Target User

**Commercial / route-to-market teams in large beverage companies.**

Characteristics:
- Time-poor
- Commercially focused
- Spreadsheet-literate
- Sceptical of black-box AI

**Implication**: Every output must be clear, explainable, actionable, and defensible.

---

## 4. Core Output (v1)

For a given **city + brand category**, the system produces:

| Output | Description |
|--------|-------------|
| Ranked venue list | Ordered by Distribution Fit Score |
| Distribution Fit Score | Deterministic, explainable score (0–100) |
| Confidence Tier | High / Medium / Low based on data quality |
| Plain-English Rationale | Why this venue ranked where it did |

**Export formats**: CSV, Excel

---

## 5. Scope

### In Scope (v1)
- Google Places API (official, paid)
- Review-based signals (themes, sentiment via controlled extraction)
- Deterministic scoring logic with configurable weights
- CSV/Excel exports
- Single brand category: **Premium Spirits** (configurable for future categories)

### Explicitly Out of Scope (v1)
- Image recognition
- Menu OCR or web scraping
- Instagram/social media scraping
- CRM integration
- Real-time monitoring
- Sales or ROI prediction
- Post-distribution tracking

---

## 6. Scoring System

### The Three Signals

#### V — Volume/Activity Signal
**Question**: Is this venue busy enough to matter?

| Input | Source | Logic |
|-------|--------|-------|
| `userRatingCount` | Place Details | Proxy for footfall |
| Recency | Review timestamps | Still active? (optional v1) |

**Calculation**: Percentile rank within city dataset (log-scaled for outliers)

---

#### R — Quality Signal
**Question**: Is this a quality venue worth brand association?

| Input | Source | Logic |
|-------|--------|-------|
| `rating` | Place Details | Google star rating (1–5) |
| `userRatingCount` | Place Details | Confidence adjustment |

**Calculation**: Confidence-adjusted rating
```
R = rating × min(1, userRatingCount / confidence_threshold)
```
Where `confidence_threshold` = 50 (configurable)

---

#### M — Relevance Signal
**Question**: Is this venue a fit for premium spirits?

##### Tier 1: Deterministic (no AI)

| Signal | Source | Premium Spirits Logic |
|--------|--------|----------------------|
| `types` | Place Details | **+ve**: bar, cocktail_bar, wine_bar. **-ve**: fast_food, convenience_store, night_club |
| `priceLevel` | Place Details | **+ve**: 3–4. **Neutral**: 2. **-ve**: 0–1 |
| `editorialSummary` | Place Details | Keyword presence: cocktail, spirits, whisky, gin, mixology, craft |

##### Tier 2: Review-based (AI-assisted, Stage 3 only)

Controlled theme extraction with explicit labels:

| Theme Label | Positive Indicators | Negative Indicators |
|-------------|--------------------|--------------------|
| `cocktail_focus` | craft cocktails, mixology, signature drinks | — |
| `spirits_depth` | whisky selection, gin menu, rare bottles, tasting | — |
| `upscale_atmosphere` | elegant, sophisticated, special occasion | dive bar, rowdy, sticky floors |
| `service_quality` | knowledgeable bartender, recommendations | slow service, inexperienced |
| `price_value_focus` | — | cheap, deals, happy hour, student night |

**M Calculation**:
```
M = (type_score × w1) + (price_score × w2) + (keyword_score × w3) + (theme_score × w4)
```

---

### Combined Score

```
Distribution Fit Score = (wV × V) + (wR × R) + (wM × M)
```

**Default weights (Premium Spirits hypothesis)**:
- wV = 0.25 — volume matters but isn't dominant
- wR = 0.25 — quality matters
- wM = 0.50 — relevance is the differentiator

All weights are configurable and documented.

---

### Confidence Tiers

Confidence reflects **data quality**, not score certainty.

Confidence is determined by two dimensions:

| Dimension | High | Medium | Low |
|-----------|------|--------|-----|
| Data volume | ≥100 reviews | 30–99 reviews | <30 reviews |
| Data freshness | <30 days | 30–90 days | >90 days |

**Combined logic**:
```
If data_volume = LOW → Confidence = LOW (regardless of freshness)
Else if data_freshness > 90 days → Confidence = max(MEDIUM, volume_tier)
Else → Confidence = volume_tier
```

**Examples**:
- 500 reviews, refreshed 2 weeks ago → **High**
- 500 reviews, refreshed 4 months ago → **Medium** (freshness caps it)
- 25 reviews, refreshed yesterday → **Low** (volume floor)

**Rule**: Low-confidence venues are flagged, not hidden.

See [Data Freshness Strategy](data-freshness.md) for full refresh logic.

---

## 7. Data Strategy

### 3-Stage Fetch (Cost-Optimised)

| Stage | Purpose | Endpoint | Cost (USD/1k) |
|-------|---------|----------|---------------|
| 1. Discovery | Candidate place IDs | Text Search Pro | $32 |
| 2. Scoring | Deterministic inputs (V, R, base M) | Place Details Enterprise | $20 |
| 3. Explanations | Review text for top N | Place Details Enterprise + Atmosphere | $25 |

### Cost Model (London test run)

| Stage | Volume | Cost |
|-------|--------|------|
| Discovery | ~20 searches → 2,000 IDs | ~$0.65 |
| Scoring | ~600 venues (post-filter) | ~$12.00 |
| Explanations | Top 150 venues | ~$3.75 |
| **Total** | | **~$16–17 (~£13)** |

### Budget Control
- Adjust N in Stage 3 to control spend
- Phase 1 budget: £50 (allows 3–4 full runs)

### Constraints
- Google returns max 5 reviews per venue
- Reviews are supporting evidence, not primary signal
- M must work without reviews (Tier 1 signals only)

### Data Principles

| Principle | Implementation |
|-----------|----------------|
| Data Contract | Strict schemas for API → logic → output |
| Minimum Data Threshold | Venues below floor are not scored |
| Pass-Through Pattern | Fetch → Analyse → Summarise → Purge raw content |
| Ephemeral Raw Data | Third-party content not persisted long-term |

---

## 8. AI Constraints

### AI May
- Summarise review themes into controlled labels
- Generate venue profiles from structured data
- Explain scoring outcomes in plain English

### AI Must Not
- Independently decide rankings
- Replace deterministic logic
- Invent facts not in source data
- Hide uncertainty
- Provide "confidence" based on self-assessment

---

## 9. Technical Stack

### Phase 1 (Current)
- Python 3.11+
- Jupyter notebooks (exploration only)
- SQLite / Parquet (local persistence)
- Pydantic (data contracts)
- ruff (lint/format)
- uv or pip-tools (dependency management)

### Phase 2+ (When core logic proven)
- FastAPI (API layer)
- PostgreSQL (production database)
- Streamlit (MVP interface)
- Later: Next.js frontend if needed

### Principles
- Notebooks are for exploration; graduate to `/src` quickly
- No premature scaling assumptions
- Configuration over custom logic

---

## 10. Project Phases

### Phase 1 — Foundations (Current)
**Goal**: Build deterministic ingestion and scoring without AI.

**Artefacts**:
1. Costed Data Plan
2. Venue Object Data Contract (schema)
3. Relevance Rubric v0
4. Validation Loop v0

**Non-Goals**: No AI-generated insight, no weight optimisation

---

### Phase 2 — AI-Augmented Insight
**Goal**: Introduce AI for theme extraction and synthesis.

**Learn**: Prompt structuring, context shaping, hallucination risks

**Non-Goal**: No AI-driven decisions

---

### Phase 3 — Decision Support
**Goal**: Move from insight to recommendation.

**Learn**: Trust design, executive-facing AI UX, decision framing

**Non-Goal**: No black-box scoring

---

### Phase 4 — Productisation
**Goal**: Refactor for reuse and configuration.

**Learn**: Platform thinking, scope discipline, leverage creation

**Non-Goal**: No premature scaling

---

### Phase 5 — Evaluation & Governance
**Goal**: Add checks, reviews, documentation for enterprise readiness.

**Learn**: Reliability patterns, AI governance basics

---

## 11. Success Criteria

### v1 is successful when:
- A commercial user can act immediately on the output
- Scoring logic can be explained to Legal or Procurement
- Re-runs for new cities require minimal configuration change
- AI increases clarity and speed, not risk
- The system feels like a reusable asset, not an experiment

### Learning is successful when:
- The system can be explained end-to-end without referencing tools
- Design decisions are documented and intentional
- AI usage is constrained and defensible
- The architecture can be reused for other verticals
- Confidence comes from understanding, not tooling

---

## 12. Folder Structure

```
venue-intel/
├── docs/                    # Project documentation
│   ├── PROJECT.md           # This document (start here)
│   ├── subscription-model.md # Commercial packaging & pricing
│   ├── data-freshness.md    # Refresh strategy & staleness
│   ├── mvp-ui.md            # Minimal viable UI definition
│   ├── costed-data-plan.md  # API costs and fetch strategy (TODO)
│   ├── data-contract.md     # Venue object schema (TODO)
│   └── relevance-rubric.md  # M signal definition (TODO)
├── notebooks/               # Exploration only (not production)
│   └── 01-discovery.ipynb
├── src/
│   └── venue_intel/         # Production code
│       ├── __init__.py
│       ├── models.py        # Pydantic schemas
│       ├── fetch.py         # Google Places API client
│       ├── scoring.py       # V, R, M calculations
│       └── export.py        # CSV/Excel output
├── tests/                   # Unit and integration tests
├── data/
│   ├── raw/                 # Ephemeral API responses (gitignored)
│   ├── processed/           # Scored venue data
│   └── exports/             # Client-ready outputs
├── config/                  # Weight configurations, API keys (gitignored)
├── pyproject.toml           # Dependencies and project metadata
└── README.md                # Quick start guide
```

---

## 13. Next Actions

### Completed
- [x] Create `pyproject.toml` with Phase 1 dependencies
- [x] Define Pydantic models in `src/venue_intel/models.py`
- [x] Draft `docs/subscription-model.md` — commercial packaging
- [x] Draft `docs/data-freshness.md` — refresh strategy
- [x] Draft `docs/mvp-ui.md` — minimal UI definition
- [x] Draft `docs/costed-data-plan.md` — API costs, fetch strategy, budget controls
- [x] Draft `docs/relevance-rubric.md` — M signal definition, scoring logic

### Remaining (Phase 1)
1. [ ] Set up Google Cloud project and enable Places API (New)
2. [ ] Build Stage 1 fetch script (`src/venue_intel/fetch.py`)
3. [ ] Run first discovery query for London test
4. [ ] Build Stage 2 fetch logic (Place Details)
5. [ ] Build scoring logic (`src/venue_intel/scoring.py`)
6. [ ] Build export functionality (`src/venue_intel/export.py`)
7. [ ] Validate top-10 output manually
8. [ ] Create golden set (10 venues) for regression testing

---

## Appendix: LLM Design Partner Instructions

When assisting with this project, the LLM must:

**Priorities**:
- Learning by doing
- Incremental capability building
- Practical trade-offs over theory

**Constraints**:
- Challenge unnecessary complexity
- Flag risks early (scope, compliance, trust)
- Optimise for decision usefulness over technical elegance
- Every capability must be justified by product necessity

**Tone**:
- Practical
- Commercially grounded
- Precise
