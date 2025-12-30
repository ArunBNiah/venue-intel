"""Data contract models for Venue Intelligence system.

These Pydantic models define the strict schema for data as it moves
through the pipeline: API → Processing → Scoring → Output.

This is Artefact 2: The Data Contract.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class ConfidenceTier(str, Enum):
    """Data quality confidence tier.

    Determined by two dimensions:
    - Data volume: userRatingCount thresholds (LOW <30, MEDIUM 30-99, HIGH ≥100)
    - Data freshness: days since last refresh (HIGH <30d, MEDIUM 30-90d, LOW >90d)

    Combined logic:
    - If volume = LOW → Confidence = LOW (regardless of freshness)
    - Else if freshness > 90 days → Confidence = max(MEDIUM, volume_tier)
    - Else → Confidence = volume_tier
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FetchStage(str, Enum):
    """Which fetch stage the venue has reached."""

    DISCOVERY = "discovery"  # Stage 1: basic metadata only
    SCORED = "scored"  # Stage 2: full details for scoring
    ENRICHED = "enriched"  # Stage 3: reviews fetched for top N


class ThemeLabel(str, Enum):
    """Controlled theme labels for review extraction."""

    COCKTAIL_FOCUS = "cocktail_focus"
    SPIRITS_DEPTH = "spirits_depth"
    UPSCALE_ATMOSPHERE = "upscale_atmosphere"
    SERVICE_QUALITY = "service_quality"
    PRICE_VALUE_FOCUS = "price_value_focus"  # Negative signal


class ThemePresence(str, Enum):
    """Theme extraction result."""

    PRESENT = "present"
    ABSENT = "absent"
    UNCLEAR = "unclear"


class VolumeTier(str, Enum):
    """Volume/visibility tier based on review count.

    Our derived categorisation, not raw Google data.
    """

    VERY_HIGH = "very_high"  # 5000+ reviews
    HIGH = "high"            # 1000-4999 reviews
    MEDIUM = "medium"        # 200-999 reviews
    LOW = "low"              # 50-199 reviews
    VERY_LOW = "very_low"    # <50 reviews


class QualityTier(str, Enum):
    """Quality tier based on rating.

    Our derived categorisation, not raw Google data.
    """

    EXCELLENT = "excellent"  # 4.5+
    GOOD = "good"            # 4.0-4.4
    AVERAGE = "average"      # 3.5-3.9
    BELOW_AVERAGE = "below_average"  # 3.0-3.4
    POOR = "poor"            # <3.0


class PriceTier(str, Enum):
    """Price tier based on Google price level.

    Our derived categorisation, not raw Google data.
    """

    PREMIUM = "premium"      # Price level 3-4
    MID = "mid"              # Price level 2
    BUDGET = "budget"        # Price level 0-1
    UNKNOWN = "unknown"      # No price data


# =============================================================================
# Stage 1: Discovery Data (from Text Search)
# =============================================================================


class VenueDiscovery(BaseModel):
    """Minimal venue data from Stage 1 discovery search."""

    place_id: str = Field(..., description="Google Places unique identifier")
    name: str
    latitude: float
    longitude: float
    types: list[str] = Field(default_factory=list, description="Google place types")
    rating: float | None = Field(None, ge=1.0, le=5.0)
    user_rating_count: int | None = Field(None, ge=0)
    price_level: int | None = Field(None, ge=0, le=4)

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    search_query: str = Field(..., description="Query that found this venue")


# =============================================================================
# Stage 2: Scoring Data (from Place Details)
# =============================================================================


class VenueDetails(BaseModel):
    """Full venue details from Stage 2 for scoring."""

    # Identity
    place_id: str
    name: str
    formatted_address: str | None = None
    latitude: float
    longitude: float

    # Core signals
    types: list[str] = Field(default_factory=list)
    rating: float | None = Field(None, ge=1.0, le=5.0)
    user_rating_count: int | None = Field(None, ge=0)
    price_level: int | None = Field(None, ge=0, le=4)

    # Additional details
    website_uri: str | None = None
    phone_number: str | None = None
    editorial_summary: str | None = Field(
        None, description="Google's editorial description"
    )

    # Opening hours (simplified)
    open_now: bool | None = None
    weekday_hours: list[str] | None = Field(
        None, description="Opening hours text per weekday"
    )

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    fetch_stage: FetchStage = FetchStage.SCORED


# =============================================================================
# Stage 3: Review Data (from Place Details + Atmosphere)
# =============================================================================


class Review(BaseModel):
    """Single review from Google Places."""

    author_name: str
    rating: int = Field(..., ge=1, le=5)
    text: str
    relative_time_description: str  # e.g., "2 months ago"
    time: datetime | None = None  # Unix timestamp converted


class ThemeExtraction(BaseModel):
    """AI-extracted theme from reviews."""

    label: ThemeLabel
    presence: ThemePresence
    supporting_quote: str | None = Field(
        None, description="Verbatim quote from review if present"
    )


class VenueEnriched(VenueDetails):
    """Venue with reviews and extracted themes (Stage 3)."""

    reviews: list[Review] = Field(default_factory=list, max_length=5)
    themes: list[ThemeExtraction] = Field(default_factory=list)
    fetch_stage: FetchStage = FetchStage.ENRICHED


# =============================================================================
# Scoring Output
# =============================================================================


class SignalScores(BaseModel):
    """Individual signal scores before weighting."""

    v_score: float = Field(..., ge=0, le=1, description="Volume/activity signal")
    r_score: float = Field(..., ge=0, le=1, description="Quality signal")
    m_score: float = Field(..., ge=0, le=1, description="Relevance signal")

    # M sub-components for explainability
    m_type_score: float = Field(..., ge=-1, le=1)
    m_price_score: float = Field(..., ge=0, le=1)
    m_keyword_score: float = Field(..., ge=0, le=1)
    m_theme_score: float | None = Field(
        None, ge=-1, le=1, description="Only populated after Stage 3"
    )


class ScoredVenue(BaseModel):
    """Final scored venue ready for output."""

    # Identity
    place_id: str
    name: str
    formatted_address: str | None = None
    latitude: float
    longitude: float

    # Raw data summary
    types: list[str]
    rating: float | None
    user_rating_count: int | None
    price_level: int | None
    editorial_summary: str | None = None

    # Scores
    distribution_fit_score: float = Field(..., ge=0, le=100)
    signal_scores: SignalScores
    confidence_tier: ConfidenceTier

    # Explainability
    rationale: str = Field(..., description="Plain-English explanation of score")
    themes: list[ThemeExtraction] = Field(default_factory=list)

    # Ranking
    rank: int | None = Field(None, ge=1, description="Position in ranked list")

    # Metadata
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    data_refreshed_at: datetime = Field(
        ..., description="When venue data was last fetched from API"
    )
    fetch_stage: FetchStage


# =============================================================================
# Configuration
# =============================================================================


class ScoringWeights(BaseModel):
    """Configurable weights for score calculation."""

    # Top-level signal weights (must sum to 1.0)
    w_volume: float = Field(0.25, ge=0, le=1)
    w_quality: float = Field(0.25, ge=0, le=1)
    w_relevance: float = Field(0.50, ge=0, le=1)

    # M sub-component weights
    m_type_weight: float = Field(0.30, ge=0, le=1)
    m_price_weight: float = Field(0.25, ge=0, le=1)
    m_keyword_weight: float = Field(0.20, ge=0, le=1)
    m_theme_weight: float = Field(0.25, ge=0, le=1)

    # Volume thresholds (userRatingCount)
    confidence_threshold: int = Field(
        50, description="userRatingCount threshold for R confidence adjustment"
    )
    high_confidence_floor: int = Field(
        100, description="userRatingCount for HIGH confidence tier"
    )
    medium_confidence_floor: int = Field(
        30, description="userRatingCount for MEDIUM confidence tier"
    )
    minimum_data_threshold: int = Field(
        10, description="Below this, venue is not scored"
    )

    # Freshness thresholds (days since refresh)
    freshness_high_days: int = Field(
        30, description="Data <30 days old = HIGH freshness"
    )
    freshness_medium_days: int = Field(
        90, description="Data 30-90 days old = MEDIUM freshness"
    )
    # Data >90 days old = LOW freshness (caps confidence at MEDIUM)


class BrandCategory(BaseModel):
    """Brand/category configuration for relevance scoring."""

    name: str = Field(..., description="e.g., 'premium_spirits', 'craft_beer'")

    # Type scoring
    positive_types: list[str] = Field(
        default_factory=lambda: ["bar", "cocktail_bar", "wine_bar"]
    )
    neutral_types: list[str] = Field(default_factory=lambda: ["restaurant"])
    negative_types: list[str] = Field(
        default_factory=lambda: ["fast_food_restaurant", "convenience_store", "night_club"]
    )

    # Keyword matching (for editorial summary)
    positive_keywords: list[str] = Field(
        default_factory=lambda: [
            "cocktail",
            "spirits",
            "whisky",
            "whiskey",
            "gin",
            "mixology",
            "craft",
            "premium",
            "signature drinks",
        ]
    )
    negative_keywords: list[str] = Field(
        default_factory=lambda: [
            "fast food",
            "takeaway",
            "cheap",
            "budget",
        ]
    )

    # Theme weights (which themes matter for this category)
    theme_weights: dict[ThemeLabel, float] = Field(
        default_factory=lambda: {
            ThemeLabel.COCKTAIL_FOCUS: 1.0,
            ThemeLabel.SPIRITS_DEPTH: 1.0,
            ThemeLabel.UPSCALE_ATMOSPHERE: 0.8,
            ThemeLabel.SERVICE_QUALITY: 0.5,
            ThemeLabel.PRICE_VALUE_FOCUS: -1.0,  # Negative signal
        }
    )


# =============================================================================
# Permanent Venue Record (Our IP - safe to store indefinitely)
# =============================================================================


class VenueRecord(BaseModel):
    """Permanent venue record storing only compliant data.

    This model represents our intellectual property:
    - place_id: Google allows permanent storage
    - Venue identity: Public information (name, location)
    - Derived tiers: Our categorisation, not raw Google data
    - Our scores: 100% our calculations

    Raw Google data (exact ratings, review counts) is NOT stored.
    """

    # Identifier (Google allows permanent storage of place_id)
    place_id: str = Field(..., description="Google Places ID - permanent storage OK")

    # Venue identity (public information, not Google's IP)
    name: str = Field(..., description="Venue's own name")
    city: str = Field(..., description="City name")
    country: str = Field(default="UK", description="Country code")
    address: str | None = Field(None, description="Display address")
    latitude: float
    longitude: float

    # Our derived tiers (transformations, not raw Google data)
    volume_tier: VolumeTier = Field(..., description="Our categorisation of review volume")
    quality_tier: QualityTier = Field(..., description="Our categorisation of rating")
    price_tier: PriceTier = Field(..., description="Our categorisation of price level")

    # Venue type summary (our categorisation)
    venue_type: str = Field(..., description="Primary venue type, e.g., 'cocktail_bar'")
    is_premium_indicator: bool = Field(
        False, description="Our assessment: shows premium signals"
    )

    # Our scores (100% our IP)
    distribution_fit_score: float = Field(..., ge=0, le=100)
    v_score: float = Field(..., ge=0, le=1, description="Volume signal")
    r_score: float = Field(..., ge=0, le=1, description="Quality signal")
    m_score: float = Field(..., ge=0, le=1, description="Relevance signal")
    confidence_tier: ConfidenceTier

    # Our generated content
    rationale: str = Field(..., description="Our explanation of the score")

    # Binary signals (our derived flags from attribute presence)
    serves_cocktails: bool | None = Field(None, description="Venue serves cocktails")
    serves_wine: bool | None = Field(None, description="Venue serves wine")
    serves_beer: bool | None = Field(None, description="Venue serves beer")
    serves_spirits: bool | None = Field(None, description="Venue serves hard liquor/spirits")
    has_great_cocktails: bool | None = Field(None, description="Highlighted for great cocktails")
    has_great_beer: bool | None = Field(None, description="Highlighted for great beer selection")
    has_great_wine: bool | None = Field(None, description="Highlighted for great wine list")
    is_upscale: bool | None = Field(None, description="Upscale atmosphere")
    is_late_night: bool | None = Field(None, description="Open past midnight")

    # Metadata
    brand_category: str = Field(default="premium_spirits")
    first_seen_at: datetime = Field(..., description="When we first discovered this venue")
    last_scored_at: datetime = Field(..., description="When we last scored this venue")
    score_version: str = Field(default="1.0", description="Scoring algorithm version")


# =============================================================================
# Tier Computation Helpers
# =============================================================================


def compute_volume_tier(user_rating_count: int | None) -> VolumeTier:
    """Compute volume tier from review count."""
    if user_rating_count is None:
        return VolumeTier.VERY_LOW
    if user_rating_count >= 5000:
        return VolumeTier.VERY_HIGH
    if user_rating_count >= 1000:
        return VolumeTier.HIGH
    if user_rating_count >= 200:
        return VolumeTier.MEDIUM
    if user_rating_count >= 50:
        return VolumeTier.LOW
    return VolumeTier.VERY_LOW


def compute_quality_tier(rating: float | None) -> QualityTier:
    """Compute quality tier from rating."""
    if rating is None:
        return QualityTier.AVERAGE  # Neutral default
    if rating >= 4.5:
        return QualityTier.EXCELLENT
    if rating >= 4.0:
        return QualityTier.GOOD
    if rating >= 3.5:
        return QualityTier.AVERAGE
    if rating >= 3.0:
        return QualityTier.BELOW_AVERAGE
    return QualityTier.POOR


def compute_price_tier(price_level: int | None) -> PriceTier:
    """Compute price tier from Google price level."""
    if price_level is None:
        return PriceTier.UNKNOWN
    if price_level >= 3:
        return PriceTier.PREMIUM
    if price_level == 2:
        return PriceTier.MID
    return PriceTier.BUDGET
