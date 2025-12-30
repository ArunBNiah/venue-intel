"""Scoring logic for venue prioritisation.

This module implements the Distribution Fit Score calculation:
- V signal: Volume/activity (userRatingCount)
- R signal: Quality (rating with confidence adjustment)
- M signal: Relevance (type, price, attributes, keywords)

See docs/relevance-rubric.md for full scoring logic.
"""

import math
from datetime import datetime, timezone

from venue_intel.models import (
    BrandCategory,
    ConfidenceTier,
    FetchStage,
    PriceTier,
    QualityTier,
    ScoredVenue,
    ScoringWeights,
    SignalScores,
    VenueDetails,
    VenueRecord,
    VolumeTier,
    compute_price_tier,
    compute_quality_tier,
    compute_volume_tier,
)


# =============================================================================
# Default Configurations
# =============================================================================

DEFAULT_WEIGHTS = ScoringWeights()

DEFAULT_BRAND = BrandCategory(
    name="premium_spirits",
    positive_types=["bar", "cocktail_bar", "wine_bar", "lounge"],
    neutral_types=["restaurant", "hotel", "resort_hotel"],
    negative_types=["night_club", "fast_food_restaurant", "convenience_store"],
    positive_keywords=[
        "cocktail", "mixology", "whisky", "whiskey", "gin", "spirits",
        "premium", "upscale", "sophisticated", "tasting", "sommelier",
    ],
    negative_keywords=[
        "cheap", "budget", "shots", "student", "dive", "sports bar", "karaoke",
    ],
)


# =============================================================================
# Type Scoring
# =============================================================================

# Type score mapping (more granular than BrandCategory)
TYPE_SCORES = {
    # Strong positive
    "cocktail_bar": 1.0,
    "wine_bar": 1.0,
    # Positive
    "bar": 0.7,
    "lounge": 0.7,
    # Neutral positive
    "restaurant": 0.4,
    "fine_dining_restaurant": 0.6,
    "french_restaurant": 0.5,
    "italian_restaurant": 0.5,
    "japanese_restaurant": 0.5,
    "steak_house": 0.5,
    # Neutral
    "hotel": 0.3,
    "resort_hotel": 0.3,
    "boutique_hotel": 0.4,
    # Neutral negative
    "cafe": 0.1,
    "pub": 0.2,
    "british_restaurant": 0.3,
    # Negative
    "night_club": -0.2,
    "sports_bar": -0.2,
    "karaoke": -0.3,
    # Strong negative
    "fast_food_restaurant": -0.8,
    "convenience_store": -1.0,
    "liquor_store": -0.5,
}


def compute_type_score(types: list[str]) -> float:
    """Compute type score from venue types.

    Returns:
        Score from -1.0 to 1.0
    """
    if not types:
        return 0.0

    # Find best matching type
    best_score = 0.0
    for venue_type in types:
        if venue_type in TYPE_SCORES:
            score = TYPE_SCORES[venue_type]
            # Prefer stronger signals
            if abs(score) > abs(best_score):
                best_score = score

    return best_score


# =============================================================================
# Price Scoring
# =============================================================================

PRICE_SCORES = {
    4: 1.0,   # Very expensive
    3: 0.8,   # Expensive
    2: 0.4,   # Moderate
    1: 0.1,   # Inexpensive
    0: 0.0,   # Free
    None: 0.3,  # Unknown = cautious neutral
}


def compute_price_score(price_level: int | None) -> float:
    """Compute price score from Google price level.

    Returns:
        Score from 0.0 to 1.0
    """
    return PRICE_SCORES.get(price_level, 0.3)


# =============================================================================
# Attribute Scoring
# =============================================================================

def compute_attribute_score(attributes: dict | None) -> float:
    """Compute attribute score from boolean venue attributes.

    Returns:
        Score from 0.0 to 1.0
    """
    if not attributes:
        return 0.3  # Neutral default when no data

    score = 0.0

    if attributes.get("servesCocktails"):
        score += 0.4
    if attributes.get("servesWine"):
        score += 0.2
    if attributes.get("goodForGroups"):
        score += 0.1
    if attributes.get("reservable"):
        score += 0.1

    # Normalise to 0-1 (max possible is 0.8)
    return min(score / 0.8, 1.0)


# =============================================================================
# Keyword Scoring
# =============================================================================

POSITIVE_KEYWORDS = {
    "cocktail": 0.15,
    "cocktails": 0.15,
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
    "craft": 0.1,
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
    """Compute keyword score from editorial summary.

    Returns:
        Score from 0.0 to 1.0
    """
    if not editorial_summary:
        return 0.5  # Neutral when no data

    text = editorial_summary.lower()
    score = 0.0

    for keyword, weight in POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += weight

    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score += weight  # weight is already negative

    # Clamp to -1 to 1, then normalise to 0-1
    clamped = max(-1.0, min(1.0, score))
    return (clamped + 1.0) / 2.0


# =============================================================================
# Signal Calculations
# =============================================================================

def compute_v_score(
    user_rating_count: int | None,
    city_max: int = 5000,
) -> float:
    """Compute Volume signal (V).

    Uses log scale to handle outliers (some venues have 10,000+ reviews).

    Args:
        user_rating_count: Number of reviews
        city_max: Expected max reviews in city (for normalisation)

    Returns:
        Score from 0.0 to 1.0
    """
    if not user_rating_count or user_rating_count <= 0:
        return 0.0

    # Log scale normalisation
    log_count = math.log1p(user_rating_count)
    log_max = math.log1p(city_max)

    return min(log_count / log_max, 1.0)


def compute_r_score(
    rating: float | None,
    user_rating_count: int | None,
    confidence_threshold: int = 50,
) -> float:
    """Compute Quality signal (R).

    Applies confidence adjustment: low review counts discount the rating.

    Args:
        rating: Google star rating (1-5)
        user_rating_count: Number of reviews
        confidence_threshold: Reviews needed for full confidence

    Returns:
        Score from 0.0 to 1.0
    """
    if not rating:
        return 0.0

    # Normalise rating to 0-1
    rating_normalised = (rating - 1.0) / 4.0  # 1-5 -> 0-1

    # Confidence adjustment
    count = user_rating_count or 0
    confidence = min(1.0, count / confidence_threshold)

    return rating_normalised * confidence


def compute_m_score(
    types: list[str],
    price_level: int | None,
    attributes: dict | None,
    editorial_summary: str | None,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> tuple[float, float, float, float, float]:
    """Compute Relevance signal (M) with sub-components.

    Returns:
        Tuple of (m_score, type_score, price_score, attribute_score, keyword_score)
    """
    type_score = compute_type_score(types)
    price_score = compute_price_score(price_level)
    attribute_score = compute_attribute_score(attributes)
    keyword_score = compute_keyword_score(editorial_summary)

    # Normalise type_score from (-1, 1) to (0, 1) for weighted sum
    type_score_normalised = (type_score + 1.0) / 2.0

    # Combined M score (without theme score for now)
    # Renormalise weights since we're not using theme_score
    total_weight = (
        weights.m_type_weight +
        weights.m_price_weight +
        weights.m_keyword_weight +
        0.20  # attribute weight (not in config yet)
    )

    m_score = (
        (weights.m_type_weight / total_weight) * type_score_normalised +
        (weights.m_price_weight / total_weight) * price_score +
        (0.20 / total_weight) * attribute_score +
        (weights.m_keyword_weight / total_weight) * keyword_score
    )

    return m_score, type_score, price_score, attribute_score, keyword_score


# =============================================================================
# Confidence Tier
# =============================================================================

def compute_confidence_tier(
    user_rating_count: int | None,
    price_level: int | None,
    data_refreshed_at: datetime,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> ConfidenceTier:
    """Compute confidence tier based on data quality.

    Two dimensions:
    - Volume: userRatingCount thresholds
    - Freshness: days since refresh

    Returns:
        ConfidenceTier enum value
    """
    count = user_rating_count or 0

    # Volume tier
    if count >= weights.high_confidence_floor:
        volume_tier = ConfidenceTier.HIGH
    elif count >= weights.medium_confidence_floor:
        volume_tier = ConfidenceTier.MEDIUM
    else:
        volume_tier = ConfidenceTier.LOW

    # If volume is LOW, confidence is LOW regardless of freshness
    if volume_tier == ConfidenceTier.LOW:
        return ConfidenceTier.LOW

    # Check freshness
    now = datetime.now(timezone.utc)
    if data_refreshed_at.tzinfo is None:
        # Handle naive datetime
        days_old = (now.replace(tzinfo=None) - data_refreshed_at).days
    else:
        days_old = (now - data_refreshed_at).days

    # Freshness caps confidence
    if days_old > weights.freshness_medium_days:
        # Very stale data caps at MEDIUM
        if volume_tier == ConfidenceTier.HIGH:
            return ConfidenceTier.MEDIUM
    elif days_old > weights.freshness_high_days:
        # Moderately stale, keep volume tier but could add flag
        pass

    return volume_tier


# =============================================================================
# Rationale Generation
# =============================================================================

def generate_rationale(
    venue: VenueDetails,
    signal_scores: SignalScores,
    confidence_tier: ConfidenceTier,
) -> str:
    """Generate plain-English rationale for the score.

    Returns:
        1-2 sentence explanation
    """
    parts = []

    # Type signal
    type_score = signal_scores.m_type_score
    if type_score >= 0.7:
        parts.append("Strong venue type fit (cocktail/wine bar)")
    elif type_score >= 0.3:
        parts.append("Good venue type")
    elif type_score < 0:
        parts.append("Venue type may not align with premium positioning")

    # Volume
    v_score = signal_scores.v_score
    if v_score >= 0.7:
        parts.append(f"high visibility ({venue.user_rating_count}+ reviews)")
    elif v_score >= 0.4:
        parts.append("moderate visibility")

    # Quality
    if venue.rating and venue.rating >= 4.5:
        parts.append(f"excellent rating ({venue.rating}★)")
    elif venue.rating and venue.rating >= 4.0:
        parts.append(f"good rating ({venue.rating}★)")

    # Price
    if venue.price_level and venue.price_level >= 3:
        parts.append("premium price point")

    # Editorial summary hint
    if venue.editorial_summary:
        summary_lower = venue.editorial_summary.lower()
        if "cocktail" in summary_lower or "whisky" in summary_lower:
            parts.append("cocktail/spirits focus noted")

    # Confidence caveat
    if confidence_tier == ConfidenceTier.LOW:
        parts.append("(low data confidence)")

    if not parts:
        return "Limited signals available for assessment."

    # Join into readable sentence
    rationale = parts[0].capitalize()
    if len(parts) > 1:
        rationale += "; " + "; ".join(parts[1:])
    rationale += "."

    return rationale


# =============================================================================
# Main Scoring Function
# =============================================================================

def score_venue(
    venue: VenueDetails,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> ScoredVenue:
    """Score a single venue and return ScoredVenue object.

    Args:
        venue: VenueDetails from Stage 2 fetch
        weights: Scoring weights configuration

    Returns:
        ScoredVenue with scores, confidence, and rationale
    """
    # Get attributes if stored
    attributes = getattr(venue, "_attributes", None)

    # Compute signals
    v_score = compute_v_score(venue.user_rating_count)
    r_score = compute_r_score(
        venue.rating,
        venue.user_rating_count,
        weights.confidence_threshold,
    )
    m_score, type_score, price_score, attr_score, keyword_score = compute_m_score(
        venue.types,
        venue.price_level,
        attributes,
        venue.editorial_summary,
        weights,
    )

    # Combined score (0-100 scale)
    combined = (
        weights.w_volume * v_score +
        weights.w_quality * r_score +
        weights.w_relevance * m_score
    )
    distribution_fit_score = round(combined * 100, 1)

    # Signal scores object
    signal_scores = SignalScores(
        v_score=round(v_score, 3),
        r_score=round(r_score, 3),
        m_score=round(m_score, 3),
        m_type_score=round(type_score, 3),
        m_price_score=round(price_score, 3),
        m_keyword_score=round(keyword_score, 3),
        m_theme_score=None,  # No Stage 3 yet
    )

    # Confidence tier
    confidence_tier = compute_confidence_tier(
        venue.user_rating_count,
        venue.price_level,
        venue.fetched_at,
        weights,
    )

    # Rationale
    rationale = generate_rationale(venue, signal_scores, confidence_tier)

    return ScoredVenue(
        place_id=venue.place_id,
        name=venue.name,
        formatted_address=venue.formatted_address,
        latitude=venue.latitude,
        longitude=venue.longitude,
        types=venue.types,
        rating=venue.rating,
        user_rating_count=venue.user_rating_count,
        price_level=venue.price_level,
        editorial_summary=venue.editorial_summary,
        distribution_fit_score=distribution_fit_score,
        signal_scores=signal_scores,
        confidence_tier=confidence_tier,
        rationale=rationale,
        themes=[],
        rank=None,
        scored_at=datetime.now(timezone.utc),
        data_refreshed_at=venue.fetched_at,
        fetch_stage=venue.fetch_stage,
    )


def score_venues(
    venues: list[VenueDetails],
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> list[ScoredVenue]:
    """Score multiple venues and return ranked list.

    Args:
        venues: List of VenueDetails from Stage 2
        weights: Scoring weights configuration

    Returns:
        List of ScoredVenue objects, sorted by score descending, with ranks assigned
    """
    scored = [score_venue(v, weights) for v in venues]

    # Sort by score descending
    scored.sort(key=lambda x: x.distribution_fit_score, reverse=True)

    # Assign ranks
    for i, venue in enumerate(scored):
        venue.rank = i + 1

    return scored


# =============================================================================
# VenueRecord Creation (Permanent Compliant Storage)
# =============================================================================

def _determine_primary_type(types: list[str]) -> str:
    """Determine the primary venue type from Google types list.

    Returns the most relevant type for our purposes.
    """
    if not types:
        return "unknown"

    # Priority order for premium spirits relevance
    priority_types = [
        "cocktail_bar", "wine_bar", "bar", "lounge",
        "fine_dining_restaurant", "restaurant",
        "hotel", "boutique_hotel", "resort_hotel",
        "night_club", "pub", "cafe",
    ]

    for ptype in priority_types:
        if ptype in types:
            return ptype

    # Fall back to first type
    return types[0]


def _is_premium_indicator(
    types: list[str],
    price_level: int | None,
    rating: float | None,
    editorial_summary: str | None,
) -> bool:
    """Determine if venue shows premium signals.

    Our assessment based on multiple signals.
    """
    premium_signals = 0

    # Premium types
    if any(t in types for t in ["cocktail_bar", "wine_bar", "fine_dining_restaurant", "boutique_hotel"]):
        premium_signals += 1

    # High price point
    if price_level and price_level >= 3:
        premium_signals += 1

    # Excellent rating
    if rating and rating >= 4.5:
        premium_signals += 1

    # Premium keywords in editorial
    if editorial_summary:
        summary_lower = editorial_summary.lower()
        if any(kw in summary_lower for kw in ["upscale", "sophisticated", "premium", "craft", "fine"]):
            premium_signals += 1

    return premium_signals >= 2


def create_venue_record(
    venue: VenueDetails,
    city: str,
    brand_category: str = "premium_spirits",
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> VenueRecord:
    """Create a VenueRecord for permanent compliant storage.

    This converts ephemeral Google data into our permanent format:
    - Raw values → Derived tiers (our categorisation)
    - Computes our proprietary scores
    - Generates our rationale

    Args:
        venue: VenueDetails from Stage 2 fetch
        city: City name (for storage organisation)
        brand_category: Brand category for scoring context
        weights: Scoring weights configuration

    Returns:
        VenueRecord ready for permanent storage
    """
    # Get attributes if stored
    attributes = getattr(venue, "_attributes", None)

    # Compute signals
    v_score = compute_v_score(venue.user_rating_count)
    r_score = compute_r_score(
        venue.rating,
        venue.user_rating_count,
        weights.confidence_threshold,
    )
    m_score, type_score, price_score, attr_score, keyword_score = compute_m_score(
        venue.types,
        venue.price_level,
        attributes,
        venue.editorial_summary,
        weights,
    )

    # Combined score (0-100 scale)
    combined = (
        weights.w_volume * v_score +
        weights.w_quality * r_score +
        weights.w_relevance * m_score
    )
    distribution_fit_score = round(combined * 100, 1)

    # Signal scores object (for rationale generation)
    signal_scores = SignalScores(
        v_score=round(v_score, 3),
        r_score=round(r_score, 3),
        m_score=round(m_score, 3),
        m_type_score=round(type_score, 3),
        m_price_score=round(price_score, 3),
        m_keyword_score=round(keyword_score, 3),
        m_theme_score=None,
    )

    # Confidence tier
    confidence_tier = compute_confidence_tier(
        venue.user_rating_count,
        venue.price_level,
        venue.fetched_at,
        weights,
    )

    # Rationale
    rationale = generate_rationale(venue, signal_scores, confidence_tier)

    # Compute derived tiers (our categorisation, not raw Google data)
    volume_tier = compute_volume_tier(venue.user_rating_count)
    quality_tier = compute_quality_tier(venue.rating)
    price_tier = compute_price_tier(venue.price_level)

    # Determine venue type and premium indicator
    venue_type = _determine_primary_type(venue.types)
    is_premium = _is_premium_indicator(
        venue.types,
        venue.price_level,
        venue.rating,
        venue.editorial_summary,
    )

    now = datetime.now(timezone.utc)

    return VenueRecord(
        # Identifier (permanent)
        place_id=venue.place_id,
        # Venue identity (public info)
        name=venue.name,
        city=city.lower(),
        country="UK",  # TODO: derive from address
        address=venue.formatted_address,
        latitude=venue.latitude,
        longitude=venue.longitude,
        # Our derived tiers (NOT raw Google data)
        volume_tier=volume_tier,
        quality_tier=quality_tier,
        price_tier=price_tier,
        # Venue classification (our assessment)
        venue_type=venue_type,
        is_premium_indicator=is_premium,
        # Our scores (100% our IP)
        distribution_fit_score=distribution_fit_score,
        v_score=round(v_score, 3),
        r_score=round(r_score, 3),
        m_score=round(m_score, 3),
        confidence_tier=confidence_tier,
        # Our generated content
        rationale=rationale,
        # Metadata
        brand_category=brand_category,
        first_seen_at=now,
        last_scored_at=now,
        score_version="1.0",
    )


def create_venue_records(
    venues: list[VenueDetails],
    city: str,
    brand_category: str = "premium_spirits",
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> list[VenueRecord]:
    """Create VenueRecords for a batch of venues.

    Args:
        venues: List of VenueDetails from Stage 2
        city: City name
        brand_category: Brand category
        weights: Scoring weights

    Returns:
        List of VenueRecord objects, sorted by score descending
    """
    records = [
        create_venue_record(v, city, brand_category, weights)
        for v in venues
    ]

    # Sort by score descending
    records.sort(key=lambda x: x.distribution_fit_score, reverse=True)

    return records


# =============================================================================
# Test Function
# =============================================================================

def test_scoring():
    """Test scoring with mock data."""
    from venue_intel.fetch import discover_venues, get_venue_details_batch

    print("=" * 60)
    print("VIDPS Scoring Test")
    print("=" * 60)

    # Fetch real data (uses cached if available)
    print("\nFetching venues...")
    discovered = discover_venues("cocktail bars in London", max_results=10)
    place_ids = [v.place_id for v in discovered]
    detailed = get_venue_details_batch(place_ids, max_calls=10)

    print(f"\nScoring {len(detailed)} venues...")
    scored = score_venues(detailed)

    print("\n" + "=" * 60)
    print("RANKED RESULTS")
    print("=" * 60)

    for v in scored:
        print(f"\n#{v.rank} | {v.name}")
        print(f"    Score: {v.distribution_fit_score}/100 | Confidence: {v.confidence_tier.value}")
        print(f"    V={v.signal_scores.v_score:.2f} R={v.signal_scores.r_score:.2f} M={v.signal_scores.m_score:.2f}")
        print(f"    Rationale: {v.rationale}")

    return scored


if __name__ == "__main__":
    test_scoring()
