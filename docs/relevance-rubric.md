# VIDPS — Relevance Rubric (M Signal)

**Version**: 0.1.0
**Category**: Premium Spirits
**Last Updated**: 2025-12-29

---

## Purpose

This document defines how the **Relevance Signal (M)** is calculated for the "Premium Spirits" brand category.

The M signal answers: *"Is this venue a good fit for premium spirits distribution?"*

M is:
- Deterministic and auditable
- Configurable per brand category
- Derived primarily from cheap API data (Stages 1–2)
- Optionally enhanced with review themes (Stage 3, premium tier)

---

## M Signal Architecture

```
M = (w1 × type_score) + (w2 × price_score) + (w3 × attribute_score) + (w4 × keyword_score) + (w5 × theme_score*)

* theme_score only populated if Stage 3 enrichment is applied
```

### Default Weights (Premium Spirits)

| Component | Weight | Rationale |
|-----------|--------|-----------|
| `type_score` | 0.30 | Venue category is a strong signal |
| `price_score` | 0.25 | Premium spirits need premium venues |
| `attribute_score` | 0.20 | Boolean signals (cocktails, wine) |
| `keyword_score` | 0.10 | Editorial summary terms |
| `theme_score` | 0.15 | Review themes (when available) |

**Note**: If Stage 3 is not applied, weights are renormalised to exclude `theme_score`.

---

## Component 1: Type Score

Based on Google Places `types` and `primaryType` fields.

### Scoring Logic

| Category | Types | Score |
|----------|-------|-------|
| **Strong positive** | `cocktail_bar`, `wine_bar` | +1.0 |
| **Positive** | `bar`, `lounge` | +0.7 |
| **Neutral positive** | `restaurant` (with bar indicators) | +0.4 |
| **Neutral** | `hotel`, `resort` | +0.2 |
| **Neutral negative** | `cafe`, `pub` | 0.0 |
| **Negative** | `night_club`, `sports_bar` | −0.3 |
| **Strong negative** | `fast_food_restaurant`, `convenience_store` | −1.0 |

### Implementation

```python
def compute_type_score(types: list[str], primary_type: str) -> float:
    # Check primary type first
    if primary_type in STRONG_POSITIVE_TYPES:
        return 1.0
    if primary_type in STRONG_NEGATIVE_TYPES:
        return -1.0

    # Fall back to best match in types array
    # ... (see src/venue_intel/scoring.py)
```

### Type Classifications

```python
STRONG_POSITIVE_TYPES = {
    "cocktail_bar",
    "wine_bar",
}

POSITIVE_TYPES = {
    "bar",
    "lounge",
}

NEUTRAL_POSITIVE_TYPES = {
    "restaurant",
    "fine_dining_restaurant",
    "french_restaurant",
    "italian_restaurant",
    "japanese_restaurant",
    "steak_house",
}

NEUTRAL_TYPES = {
    "hotel",
    "resort_hotel",
    "boutique_hotel",
}

NEUTRAL_NEGATIVE_TYPES = {
    "cafe",
    "pub",
    "british_restaurant",
    "american_restaurant",
}

NEGATIVE_TYPES = {
    "night_club",
    "sports_bar",
    "karaoke",
    "dance_club",
}

STRONG_NEGATIVE_TYPES = {
    "fast_food_restaurant",
    "convenience_store",
    "liquor_store",
    "grocery_store",
}
```

---

## Component 2: Price Score

Based on Google Places `priceLevel` field (0–4 scale).

### Scoring Logic

| Price Level | Meaning | Score |
|-------------|---------|-------|
| 4 | Very Expensive | 1.0 |
| 3 | Expensive | 0.8 |
| 2 | Moderate | 0.4 |
| 1 | Inexpensive | 0.1 |
| 0 | Free | 0.0 |
| null | Unknown | 0.3 (neutral default) |

### Implementation

```python
PRICE_SCORES = {
    4: 1.0,
    3: 0.8,
    2: 0.4,
    1: 0.1,
    0: 0.0,
    None: 0.3,  # Unknown = cautious neutral
}

def compute_price_score(price_level: int | None) -> float:
    return PRICE_SCORES.get(price_level, 0.3)
```

---

## Component 3: Attribute Score

Based on Google Places boolean attributes (when available).

### Relevant Attributes

| Attribute | Premium Spirits Signal | Score Contribution |
|-----------|----------------------|-------------------|
| `servesCocktails` = True | Strong positive | +0.4 |
| `servesWine` = True | Positive | +0.2 |
| `servesBeer` = True | Neutral | +0.0 |
| `goodForGroups` = True | Occasion signal | +0.1 |
| `reservable` = True | Quality indicator | +0.1 |
| `servesDessert` = True | Dining venue | +0.05 |

### Scoring Logic

```python
def compute_attribute_score(attributes: dict) -> float:
    score = 0.0

    if attributes.get("servesCocktails"):
        score += 0.4
    if attributes.get("servesWine"):
        score += 0.2
    if attributes.get("goodForGroups"):
        score += 0.1
    if attributes.get("reservable"):
        score += 0.1
    if attributes.get("servesDessert"):
        score += 0.05

    # Normalise to 0–1 range
    return min(score / 0.85, 1.0)
```

### Attribute Availability

**Important**: Boolean attributes are not available for all venues. If attributes are missing:
- Use `attribute_score = 0.3` (neutral default)
- Flag in confidence tier rationale

---

## Component 4: Keyword Score

Based on keyword presence in `editorialSummary` field.

### Positive Keywords (Premium Spirits)

| Category | Keywords |
|----------|----------|
| Cocktail focus | cocktail, mixology, mixologist, craft cocktails, signature drinks |
| Spirits depth | whisky, whiskey, bourbon, scotch, gin, tequila, mezcal, rum, cognac, spirits |
| Premium signals | premium, luxury, upscale, sophisticated, elegant, refined, curated |
| Occasion | tasting, pairing, sommelier, cellar, reserve, vintage |

### Negative Keywords

| Category | Keywords |
|----------|----------|
| Budget signals | cheap, budget, affordable, value, deal, discount |
| Volume signals | shots, shooters, all-you-can-drink, bottomless |
| Casual signals | sports, karaoke, student, dive |

### Scoring Logic

```python
POSITIVE_KEYWORDS = {
    "cocktail": 0.15,
    "mixology": 0.2,
    "whisky": 0.2,
    "whiskey": 0.2,
    "gin": 0.15,
    "spirits": 0.15,
    "premium": 0.1,
    "upscale": 0.1,
    "sophisticated": 0.1,
    "tasting": 0.15,
    "sommelier": 0.15,
}

NEGATIVE_KEYWORDS = {
    "cheap": -0.2,
    "budget": -0.15,
    "shots": -0.2,
    "student": -0.25,
    "dive": -0.2,
    "sports bar": -0.15,
    "karaoke": -0.15,
}

def compute_keyword_score(editorial_summary: str | None) -> float:
    if not editorial_summary:
        return 0.0  # No signal

    text = editorial_summary.lower()
    score = 0.0

    for keyword, weight in POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += weight

    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score += weight  # weight is negative

    # Clamp to -1 to 1, then normalise to 0-1
    return (max(-1, min(1, score)) + 1) / 2
```

---

## Component 5: Theme Score (Premium Enrichment)

Based on AI-extracted themes from review text. **Only available after Stage 3 enrichment.**

### Controlled Theme Labels

| Theme | Positive Indicators | Negative Indicators | Weight |
|-------|--------------------|--------------------|--------|
| `cocktail_focus` | "craft cocktails", "amazing drinks", "creative menu" | — | +0.25 |
| `spirits_depth` | "whisky selection", "gin menu", "rare bottles", "knowledgeable about spirits" | — | +0.30 |
| `upscale_atmosphere` | "elegant", "sophisticated", "special occasion", "impressive" | "dive bar", "sticky floors", "rowdy" | +0.20 |
| `service_quality` | "attentive", "knowledgeable bartender", "great recommendations" | "slow service", "rude staff" | +0.15 |
| `price_value_focus` | — | "cheap drinks", "great deals", "happy hour", "student prices" | −0.25 |

### Theme Extraction Prompt

```
Analyse these reviews for [venue_name] and classify against each theme.

Themes:
- cocktail_focus: Evidence of craft/creative cocktail programme
- spirits_depth: Evidence of extensive spirits selection or expertise
- upscale_atmosphere: Evidence of premium/sophisticated environment
- service_quality: Evidence of knowledgeable, attentive service
- price_value_focus: Evidence of budget/value positioning

For each theme, respond with:
- presence: "present" | "absent" | "unclear"
- supporting_quote: verbatim quote from reviews (if present)

Respond in JSON format only.
```

### Scoring Logic

```python
THEME_WEIGHTS = {
    ThemeLabel.COCKTAIL_FOCUS: 0.25,
    ThemeLabel.SPIRITS_DEPTH: 0.30,
    ThemeLabel.UPSCALE_ATMOSPHERE: 0.20,
    ThemeLabel.SERVICE_QUALITY: 0.15,
    ThemeLabel.PRICE_VALUE_FOCUS: -0.25,
}

def compute_theme_score(themes: list[ThemeExtraction]) -> float:
    score = 0.0
    for theme in themes:
        if theme.presence == ThemePresence.PRESENT:
            score += THEME_WEIGHTS.get(theme.label, 0)

    # Normalise to 0-1 (theoretical range is -0.25 to 0.90)
    return (score + 0.25) / 1.15
```

---

## Combined M Calculation

### With Stage 3 (Full Enrichment)

```python
def compute_m_score_full(
    type_score: float,
    price_score: float,
    attribute_score: float,
    keyword_score: float,
    theme_score: float,
) -> float:
    return (
        0.30 * type_score +
        0.25 * price_score +
        0.20 * attribute_score +
        0.10 * keyword_score +
        0.15 * theme_score
    )
```

### Without Stage 3 (Base Scoring)

```python
def compute_m_score_base(
    type_score: float,
    price_score: float,
    attribute_score: float,
    keyword_score: float,
) -> float:
    # Renormalise weights (0.30 + 0.25 + 0.20 + 0.10 = 0.85)
    return (
        (0.30 / 0.85) * type_score +      # ≈ 0.35
        (0.25 / 0.85) * price_score +     # ≈ 0.29
        (0.20 / 0.85) * attribute_score + # ≈ 0.24
        (0.10 / 0.85) * keyword_score     # ≈ 0.12
    )
```

---

## Configuration for Other Categories

The rubric is designed to be swappable. For other brand categories:

### Craft Beer

| Change | Adjustment |
|--------|------------|
| Type scoring | Elevate `pub`, `brewery`, `beer_garden` |
| Positive keywords | Add: "craft", "IPA", "local brewery", "tap list" |
| Negative keywords | Remove: none specific |
| Theme weights | Reduce `spirits_depth`, add `beer_focus` |

### Ready-to-Drink (RTD)

| Change | Adjustment |
|--------|------------|
| Type scoring | Elevate `night_club`, `music_venue`, neutral on `bar` |
| Positive keywords | Add: "party", "club", "late night", "energy" |
| Price scoring | Flatten (RTD spans price points) |
| Theme weights | Add `high_energy`, `youth_focus` |

---

## Validation Approach

### Top-10 Sanity Check

For each city run, manually review:
1. Are obvious premium cocktail bars in the top 20?
2. Are fast food / convenience stores excluded or bottom-ranked?
3. Do the M scores correlate with intuition?

### Golden Set

Maintain a list of 10 "known good" venues per city:
- 5 should rank in top 20 (true positives)
- 5 should rank in bottom 50% (true negatives)

Use for regression testing when weights are adjusted.

---

## Future Enhancements (v1.1+)

### Location Intelligence (v1.1)

**Source**: Existing affluence model project (`/Users/mike/Desktop/affluence_model_thailand`)

**Available data**:
- UK: IMD (Index of Multiple Deprivation) at LSOA level
- Thailand: Meta RWI (Relative Wealth Index)
- USA: Census ACS median income
- Tourism density: OpenStreetMap POI analysis
- Nightlife density: Venue clustering analysis
- Pre-computed London coverage: 19,297 venues, H3 hexagon maps

**Integration approach**:
1. Use `postalCode` from Google Places Stage 2
2. Lookup in IMD/RWI data → get affluence decile
3. Add `location_score` as optional M component
4. Tourism score available as separate dimension

**Critical design principle**:

> **Affluence is informational, not a filter.**

Location data should **contextualise**, not **exclude**. Experience shows that:
- Great "on-trend" venues are often in up-and-coming, less affluent areas
- Using affluence as a screen risks missing emerging hotspots
- Brand marketers value location context, but commercial teams need full coverage

**Recommended implementation**:
- Display affluence/tourism as **metadata** in venue detail drawer
- Allow filtering **by user choice**, not by default
- Flag "high score + low affluence" as **emerging opportunity**, not anomaly
- Consider inverse signal: venues succeeding despite location = strong fundamentals

**M signal adjustment (if enabled)**:
```
location_score weight: 0.10–0.15 (informational, not dominant)
```

---

### Other Enhancements

| Enhancement | Value | Complexity | Priority |
|-------------|-------|------------|----------|
| Opening hours scoring | Late-night premium for spirits | Low | High |
| Seasonal weighting | Summer terrace, winter cosy | Low | Medium |
| Competitor signals | "Serves [competitor brand]" detection | High | Low |
| Chain detection | Flag chains vs independents | Medium | Medium |

---

## Guiding Principle

> **Relevance is evidence-based, not vibes-based.**
