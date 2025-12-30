# VIDPS — Costed Data Plan

**Version**: 0.1.0
**Last Updated**: 2025-12-29

---

## Purpose

This document defines:
- What data VIDPS fetches from Google Places API
- How much each data tier costs
- The fetch strategy that optimises for cost and decision value
- Budget controls for Phase 1

---

## Core Insight

Most scoring signals come from **cheap API tiers**.

Review data (expensive) is only needed for:
- Rationale generation
- Hero venue identification
- Brand marketer use cases

Commercial teams — the primary v1 user — need universe coverage and volume/quality signals, which are available without fetching reviews.

---

## Google Places API (New) — Relevant Endpoints

### Text Search (Places)

**Use**: Stage 1 discovery — find candidate venues

**Cost**: $32 per 1,000 requests

**Fields available** (relevant subset):
| Field | Use |
|-------|-----|
| `place_id` | Unique identifier for subsequent calls |
| `displayName` | Venue name |
| `location` | Lat/lng coordinates |
| `types` | Array of place types (bar, restaurant, etc.) |
| `primaryType` | Main category |
| `rating` | Average star rating (1–5) |
| `userRatingCount` | Number of reviews (V signal) |
| `priceLevel` | Price tier (0–4) |

**Note**: A single Text Search can return up to 20 results. Use `pageToken` for pagination.

---

### Place Details

**Use**: Stage 2 scoring — fetch additional signals for candidates

**Cost tiers**:

| SKU | Cost (per 1k) | Includes |
|-----|---------------|----------|
| Basic | $17 | address, phone, website, hours |
| Advanced | $20 | + current opening status, UTC offset |
| Preferred | $25 | + reviews (up to 5), editorialSummary |

**Key fields for scoring**:

| Field | SKU Required | Use |
|-------|--------------|-----|
| `formattedAddress` | Basic | Location context |
| `postalCode` | Basic | Neighbourhood proxy |
| `regularOpeningHours` | Basic | Operating pattern |
| `websiteUri` | Basic | Venue legitimacy check |
| `editorialSummary` | Preferred | Keyword extraction for M signal |
| `servesCocktails` | Basic* | Direct relevance signal |
| `servesWine` | Basic* | Direct relevance signal |
| `servesBeer` | Basic* | Direct relevance signal |
| `goodForGroups` | Basic* | Occasion signal |
| `reviews` | Preferred | Theme extraction (optional) |

*Boolean attribute availability may vary by venue.

---

## Fetch Strategy

### Revised Model: 2 Stages + Optional Enrichment

Based on user research: commercial teams need coverage and prioritisation from cheap data. Review-based enrichment is a premium feature.

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: DISCOVERY (Cheap)                                     │
│  ─────────────────────────                                       │
│  Endpoint: Text Search                                           │
│  Cost: $32 / 1,000 requests                                      │
│                                                                  │
│  Queries: "cocktail bars in London", "wine bars in London", etc. │
│  Output: ~2,000 candidate place_ids                              │
│  Estimated calls: ~20 searches (with pagination)                 │
│  Estimated cost: ~$0.65                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FILTER: Minimum Viability                                       │
│  ─────────────────────────                                       │
│  - userRatingCount ≥ 30                                          │
│  - rating ≥ 3.5                                                  │
│  - types include bar, restaurant, or lodging                     │
│                                                                  │
│  Output: ~600–800 candidates                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: SCORING (Cheap)                                        │
│  ────────────────────────                                        │
│  Endpoint: Place Details (Basic or Advanced)                     │
│  Cost: $17–20 / 1,000 requests                                   │
│                                                                  │
│  Fields: address, postalCode, hours, website, boolean attributes │
│  Purpose: Complete V, R, M signals for deterministic scoring     │
│                                                                  │
│  Output: Scored and ranked venue list                            │
│  Estimated calls: ~600–800                                       │
│  Estimated cost: ~$10–16                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: Commercial Team Deliverable                             │
│  ───────────────────────────────────                             │
│  - Full ranked list of venues                                    │
│  - Distribution Fit Score                                        │
│  - Confidence tier                                               │
│  - Basic rationale (from deterministic signals)                  │
│                                                                  │
│  Cost so far: ~$11–17 per city (~£9–14)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (OPTIONAL)
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: ENRICHMENT (Premium — optional)                        │
│  ────────────────────────────────────────                        │
│  Endpoint: Place Details (Preferred)                             │
│  Cost: $25 / 1,000 requests                                      │
│                                                                  │
│  Triggered for: Top N venues only (e.g., N=50–100)               │
│  Purpose: Review text for hero venue identification              │
│                                                                  │
│  Output: Theme extraction, enhanced rationale                    │
│  Estimated calls: 50–100                                         │
│  Estimated cost: ~$1.25–2.50                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cost Summary

### Per-City Cost (London baseline)

| Stage | Calls | Cost (USD) | Cost (GBP) |
|-------|-------|------------|------------|
| 1. Discovery | ~100 | ~$3.20 | ~£2.50 |
| 2. Scoring | ~700 | ~$14.00 | ~£11.00 |
| **Base total** | | **~$17** | **~£13.50** |
| 3. Enrichment (optional) | ~75 | ~$1.90 | ~£1.50 |
| **Full total** | | **~$19** | **~£15.00** |

### Phase 1 Budget

| Item | Amount |
|------|--------|
| Budget cap | £50 |
| Full runs (with enrichment) | ~3 runs |
| Base runs (no enrichment) | ~4 runs |
| Recommended approach | 2 base runs, 1 enriched run |

---

## Caching Policy

| Data | Cache Duration | Rationale |
|------|----------------|-----------|
| `place_id` list | 30 days | Venue existence changes slowly |
| Stage 2 details | Per refresh cycle | Core scoring data |
| Stage 3 reviews | 7 days or ephemeral | Raw content not persisted long-term |
| Scored output | Until next refresh | Reused across sessions |

### Cache Key Structure

```
{city}:{place_id}:{fetch_stage}:{fetched_date}
```

Example: `london:ChIJdd4hrwug2EcRmSrV3Vo6llI:scored:2025-12-29`

---

## Field Masks

Using field masks reduces response size and can affect billing (some fields are free, others count toward SKU pricing).

### Stage 1 (Text Search)

```
fields=places.id,places.displayName,places.location,places.types,places.primaryType,places.rating,places.userRatingCount,places.priceLevel
```

### Stage 2 (Place Details — Basic/Advanced)

```
fields=id,displayName,formattedAddress,addressComponents,location,types,rating,userRatingCount,priceLevel,regularOpeningHours,websiteUri,nationalPhoneNumber,servesCocktails,servesWine,servesBeer,goodForGroups
```

### Stage 3 (Place Details — Preferred)

```
fields=id,reviews,editorialSummary
```

---

## Query Strategy for London

### Discovery Queries (Stage 1)

| Query | Expected Results |
|-------|------------------|
| `cocktail bars in London` | ~200–400 |
| `wine bars in London` | ~100–200 |
| `whisky bars in London` | ~50–100 |
| `speakeasy London` | ~30–50 |
| `hotel bars in London` | ~100–150 |
| `rooftop bars in London` | ~50–100 |
| `upscale restaurants London` | ~200–400 |
| `fine dining London` | ~100–200 |

**Deduplication**: Use `place_id` as key. Same venue may appear in multiple queries.

**Estimated unique venues**: ~1,500–2,000 after deduplication.

---

## Budget Controls

### Hard Limits

| Control | Value |
|---------|-------|
| Max Stage 1 queries per city | 50 |
| Max Stage 2 calls per city | 1,000 |
| Max Stage 3 calls per city | 200 |
| Monthly API spend alert | £20 |

### Soft Limits (Configurable)

| Control | Default | Purpose |
|---------|---------|---------|
| `min_review_count` | 30 | Filter out low-signal venues |
| `min_rating` | 3.5 | Filter out poor-quality venues |
| `enrichment_top_n` | 75 | Limit expensive Stage 3 calls |

---

## User Segmentation & Cost Allocation

| User Type | Needs | Stages Required | Cost/City |
|-----------|-------|-----------------|-----------|
| Commercial team | Universe, prioritisation | 1 + 2 | ~£13 |
| Brand marketers | Hero venues, segmentation | 1 + 2 + 3 | ~£15 |

This informs subscription tier pricing — see [subscription-model.md](subscription-model.md).

---

## Error Handling

| Error | Response |
|-------|----------|
| Rate limit (429) | Exponential backoff, max 3 retries |
| Invalid place_id | Log and skip, do not retry |
| Missing fields | Score with available data, flag confidence |
| Budget exceeded | Halt fetch, notify user |

---

## Future Enhancements (v1.1+)

| Enhancement | Value | Complexity |
|-------------|-------|------------|
| Location/affluence scoring | Premium area detection | Medium (requires postcode data) |
| Competitor presence signals | Strategic gaps | High (requires brand-specific data) |
| Seasonal adjustment | Time-aware prioritisation | Medium |

---

## Guiding Principle

> **Fetch what you need for the decision — not everything available.**
