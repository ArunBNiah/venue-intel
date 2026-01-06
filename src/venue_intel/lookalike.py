"""Cross-Market Lookalike Prospecting for Venue Intelligence.

"Find Berlin prospects similar to our best London accounts"

This module enables clients to:
1. Upload their top accounts in Market A (e.g., London)
2. Generate a ranked list of similar venues in Market B (e.g., Berlin)

Core principle: Transfer PATTERNS, not numbers.
- Use relative ranks within local market (percentiles, tiers)
- Match on role similarity (venue type/vibe)
- Compare brand fit patterns (M substructure)
"""

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

# =============================================================================
# Data Models
# =============================================================================


@dataclass
class AccountInput:
    """Client account input for matching."""
    name: str
    city: str
    place_id: str | None = None  # Preferred if available
    address: str | None = None   # For fuzzy matching fallback
    tier: str | None = None      # Client's own tier (Top/Mid/Low)


@dataclass
class ResolvedAccount:
    """Account matched to a VIDPS venue record."""
    input: AccountInput
    place_id: str
    venue_name: str
    match_confidence: Literal["exact", "high", "medium", "low"]
    match_method: str  # "place_id", "name_exact", "name_fuzzy"

    # Venue features (pulled from VIDPS)
    venue_type: str
    price_tier: str
    quality_tier: str
    volume_tier: str
    m_type_score: float
    m_price_score: float
    m_attribute_score: float
    is_authority: bool


@dataclass
class SuccessProfile:
    """Profile representing what "good accounts" look like for a client.

    Built from resolved source accounts. This is the "signature" we match against.
    """
    # Source metadata
    source_market: str
    account_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Type distribution (e.g., {"cocktail_bar": 0.4, "restaurant": 0.3, ...})
    type_distribution: dict[str, float] = field(default_factory=dict)

    # Tier distributions
    price_tier_distribution: dict[str, float] = field(default_factory=dict)
    quality_tier_distribution: dict[str, float] = field(default_factory=dict)
    volume_tier_distribution: dict[str, float] = field(default_factory=dict)

    # M-component signature (average values)
    avg_m_type_score: float = 0.5
    avg_m_price_score: float = 0.5
    avg_m_attribute_score: float = 0.5

    # Authority prevalence
    authority_prevalence: float = 0.0  # % of accounts with authority badges

    # Profile confidence
    profile_confidence: Literal["high", "medium", "low"] = "medium"
    concentration_warning: str | None = None  # e.g., "80% are cocktail bars"


@dataclass
class MarketNorms:
    """Local market norms for calibration.

    Used to interpret target market data relative to local context.
    """
    market: str
    venue_count: int

    # Type prevalence (what % of market is each type)
    type_prevalence: dict[str, float] = field(default_factory=dict)

    # Tier distributions in this market
    price_tier_distribution: dict[str, float] = field(default_factory=dict)
    quality_tier_distribution: dict[str, float] = field(default_factory=dict)
    volume_tier_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class SimilarityResult:
    """Similarity score for a candidate venue."""
    place_id: str
    name: str
    city: str
    address: str
    venue_type: str

    # Overall similarity
    similarity_score: float  # 0-100

    # Component scores (for explainability)
    type_score: float      # 0-30
    tier_score: float      # 0-30
    relevance_score: float # 0-30
    authority_score: float # 0-10

    # Cross-market confidence
    confidence: Literal["high", "medium", "low"]

    # Explainability
    matched_on: list[str] = field(default_factory=list)  # e.g., ["cocktail_bar", "premium price"]
    rationale: str = ""

    # Context (original VIDPS scores)
    distribution_fit_score: float = 0.0
    price_tier: str = ""
    quality_tier: str = ""
    volume_tier: str = ""


# =============================================================================
# Database Connection
# =============================================================================

DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "venue_intelligence.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# Fuzzy Matching
# =============================================================================

# Common words to ignore in matching (low signal)
STOP_WORDS = {
    "the", "a", "an", "and", "&", "at", "of", "in", "on",
    "bar", "bars", "restaurant", "lounge", "club", "pub",
    "nyc", "london", "berlin", "tokyo", "paris", "chicago",
}


def tokenize(name: str) -> set[str]:
    """Convert venue name to a set of meaningful tokens.

    - Lowercases
    - Removes punctuation
    - Splits into words
    - Removes stop words

    Example: "The Connaught Bar" → {"connaught"}
    """
    # Lowercase and remove punctuation (keep alphanumeric and spaces)
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    # Split into words
    words = cleaned.split()
    # Remove stop words and very short words
    tokens = {w for w in words if w not in STOP_WORDS and len(w) > 1}
    return tokens


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings (0-1).

    Uses SequenceMatcher which is similar to Levenshtein but optimized.
    1.0 = identical, 0.0 = completely different
    """
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def token_match_score(input_tokens: set[str], venue_tokens: set[str], typo_threshold: float = 0.8) -> float:
    """Calculate match score between two token sets.

    Handles:
    - Exact token matches
    - Fuzzy token matches (typos) using Levenshtein

    Returns:
        Score from 0.0 to 1.0 (proportion of input tokens matched)
    """
    if not input_tokens:
        return 0.0

    matched = 0

    for input_token in input_tokens:
        # Check for exact match
        if input_token in venue_tokens:
            matched += 1
            continue

        # Check for fuzzy match on each venue token
        for venue_token in venue_tokens:
            if levenshtein_ratio(input_token, venue_token) >= typo_threshold:
                matched += 1
                break

    return matched / len(input_tokens)


def fuzzy_match_venue(
    input_name: str,
    candidates: list[sqlite3.Row],
    threshold: float = 0.6,
) -> tuple[sqlite3.Row | None, float, str]:
    """Find best fuzzy match for input name among candidates.

    Uses hybrid approach:
    1. Token-based matching for word overlap
    2. Levenshtein on tokens for typo tolerance
    3. Full string Levenshtein as tiebreaker

    Args:
        input_name: The venue name to match
        candidates: List of database rows to search
        threshold: Minimum score to consider a match (0-1)

    Returns:
        Tuple of (best_match_row, score, match_method)
        Returns (None, 0, "") if no match above threshold
    """
    input_tokens = tokenize(input_name)

    best_match = None
    best_score = 0.0
    best_method = ""
    best_token_score = 0.0
    best_string_score = 0.0

    for row in candidates:
        venue_name = row["name"]
        venue_tokens = tokenize(venue_name)

        # Calculate token match score (handles word overlap + typos)
        token_score = token_match_score(input_tokens, venue_tokens)

        # Calculate full string similarity as secondary signal
        string_score = levenshtein_ratio(input_name, venue_name)

        # Combined score: weight tokens heavily, string as tiebreaker
        combined_score = (token_score * 0.7) + (string_score * 0.3)

        if combined_score > best_score:
            best_score = combined_score
            best_match = row
            best_token_score = token_score
            best_string_score = string_score

            # Determine method description
            if token_score >= 0.9:
                best_method = "token_exact"
            elif token_score >= 0.6:
                best_method = "token_fuzzy"
            else:
                best_method = "string_fuzzy"

    # Apply threshold with additional validation
    if best_score >= threshold:
        # Prevent false positives: require either strong token match OR strong string match
        # This catches cases like "Totally Fake Bar" matching "Totally Gyro" on single word
        if best_token_score < 0.6 and best_string_score < 0.7:
            return None, 0.0, ""
        return best_match, best_score, best_method
    else:
        return None, 0.0, ""


# =============================================================================
# Account Resolution
# =============================================================================


def resolve_accounts(
    accounts: list[AccountInput],
) -> tuple[list[ResolvedAccount], list[dict]]:
    """Resolve client accounts to VIDPS venue records.

    Uses a cascade of matching strategies:
    1. Exact place_id match (if provided)
    2. Exact name match (case-insensitive)
    3. Hybrid fuzzy match (token overlap + Levenshtein for typos)

    Args:
        accounts: List of client account inputs

    Returns:
        Tuple of (resolved_accounts, unmatched_reports)
    """
    conn = get_connection()
    resolved = []
    unmatched = []

    for account in accounts:
        # TIER 1: Try place_id first (exact match)
        if account.place_id:
            row = conn.execute(
                "SELECT * FROM venues WHERE place_id = ?",
                (account.place_id,)
            ).fetchone()

            if row:
                resolved.append(_row_to_resolved(account, row, "exact", "place_id"))
                continue

        # TIER 2: Try exact name match in city
        row = conn.execute(
            "SELECT * FROM venues WHERE LOWER(name) = LOWER(?) AND LOWER(city) = LOWER(?)",
            (account.name, account.city)
        ).fetchone()

        if row:
            resolved.append(_row_to_resolved(account, row, "high", "name_exact"))
            continue

        # TIER 3: Hybrid fuzzy match (token + Levenshtein)
        # Get all venues in the city as candidates
        candidates = conn.execute(
            "SELECT * FROM venues WHERE LOWER(city) = LOWER(?)",
            (account.city,)
        ).fetchall()

        if candidates:
            match, score, method = fuzzy_match_venue(account.name, candidates, threshold=0.5)

            if match:
                # Determine confidence based on score
                if score >= 0.85:
                    confidence = "high"
                elif score >= 0.65:
                    confidence = "medium"
                else:
                    confidence = "low"

                resolved.append(_row_to_resolved(account, match, confidence, method))
                continue

        # No match found
        unmatched.append({
            "name": account.name,
            "city": account.city,
            "reason": "No matching venue found in VIDPS database"
        })

    conn.close()
    return resolved, unmatched


def _row_to_resolved(
    account: AccountInput,
    row: sqlite3.Row,
    confidence: str,
    method: str
) -> ResolvedAccount:
    """Convert database row to ResolvedAccount."""
    is_authority = (
        row["on_worlds_50_best"] == 1 or
        row["on_asias_50_best"] == 1 or
        row["on_north_americas_50_best"] == 1
    )

    return ResolvedAccount(
        input=account,
        place_id=row["place_id"],
        venue_name=row["name"],
        match_confidence=confidence,
        match_method=method,
        venue_type=row["venue_type"],
        price_tier=row["price_tier"],
        quality_tier=row["quality_tier"],
        volume_tier=row["volume_tier"],
        m_type_score=row["m_type_score"] or 0.5,
        m_price_score=row["m_price_score"] or 0.5,
        m_attribute_score=row["m_attribute_score"] or 0.5,
        is_authority=is_authority,
    )


# =============================================================================
# Profile Builder
# =============================================================================


def build_success_profile(
    resolved_accounts: list[ResolvedAccount],
    source_market: str,
) -> SuccessProfile:
    """Build a success profile from resolved source accounts.

    This creates the "signature" of what good accounts look like.
    """
    n = len(resolved_accounts)
    if n == 0:
        raise ValueError("Cannot build profile from zero accounts")

    # Count distributions
    type_counts: dict[str, int] = {}
    price_counts: dict[str, int] = {}
    quality_counts: dict[str, int] = {}
    volume_counts: dict[str, int] = {}
    authority_count = 0

    m_type_sum = 0.0
    m_price_sum = 0.0
    m_attr_sum = 0.0

    for acc in resolved_accounts:
        # Type distribution
        type_counts[acc.venue_type] = type_counts.get(acc.venue_type, 0) + 1

        # Tier distributions
        price_counts[acc.price_tier] = price_counts.get(acc.price_tier, 0) + 1
        quality_counts[acc.quality_tier] = quality_counts.get(acc.quality_tier, 0) + 1
        volume_counts[acc.volume_tier] = volume_counts.get(acc.volume_tier, 0) + 1

        # M-components
        m_type_sum += acc.m_type_score
        m_price_sum += acc.m_price_score
        m_attr_sum += acc.m_attribute_score

        # Authority
        if acc.is_authority:
            authority_count += 1

    # Convert to distributions (proportions)
    type_dist = {k: v / n for k, v in type_counts.items()}
    price_dist = {k: v / n for k, v in price_counts.items()}
    quality_dist = {k: v / n for k, v in quality_counts.items()}
    volume_dist = {k: v / n for k, v in volume_counts.items()}

    # Check for concentration warnings
    concentration_warning = None
    max_type_share = max(type_dist.values()) if type_dist else 0
    if max_type_share > 0.7:
        dominant_type = max(type_dist, key=type_dist.get)
        concentration_warning = f"{max_type_share:.0%} of accounts are {dominant_type.replace('_', ' ')}"

    # Determine profile confidence
    if n >= 20 and max_type_share < 0.8:
        confidence = "high"
    elif n >= 10:
        confidence = "medium"
    else:
        confidence = "low"

    return SuccessProfile(
        source_market=source_market,
        account_count=n,
        type_distribution=type_dist,
        price_tier_distribution=price_dist,
        quality_tier_distribution=quality_dist,
        volume_tier_distribution=volume_dist,
        avg_m_type_score=m_type_sum / n,
        avg_m_price_score=m_price_sum / n,
        avg_m_attribute_score=m_attr_sum / n,
        authority_prevalence=authority_count / n,
        profile_confidence=confidence,
        concentration_warning=concentration_warning,
    )


# =============================================================================
# Market Norms
# =============================================================================


def compute_market_norms(market: str) -> MarketNorms:
    """Compute local market norms for a target market.

    This is used to interpret target market data in local context.
    """
    conn = get_connection()

    # Get venue count
    count = conn.execute(
        "SELECT COUNT(*) FROM venues WHERE LOWER(city) = LOWER(?)",
        (market,)
    ).fetchone()[0]

    if count == 0:
        conn.close()
        raise ValueError(f"No venues found in market: {market}")

    # Type prevalence
    type_rows = conn.execute(
        """SELECT venue_type, COUNT(*) as cnt
           FROM venues WHERE LOWER(city) = LOWER(?)
           GROUP BY venue_type""",
        (market,)
    ).fetchall()
    type_prev = {row["venue_type"]: row["cnt"] / count for row in type_rows}

    # Tier distributions
    def get_tier_dist(column: str) -> dict[str, float]:
        rows = conn.execute(
            f"""SELECT {column}, COUNT(*) as cnt
                FROM venues WHERE LOWER(city) = LOWER(?)
                GROUP BY {column}""",
            (market,)
        ).fetchall()
        return {row[column]: row["cnt"] / count for row in rows}

    price_dist = get_tier_dist("price_tier")
    quality_dist = get_tier_dist("quality_tier")
    volume_dist = get_tier_dist("volume_tier")

    conn.close()

    return MarketNorms(
        market=market,
        venue_count=count,
        type_prevalence=type_prev,
        price_tier_distribution=price_dist,
        quality_tier_distribution=quality_dist,
        volume_tier_distribution=volume_dist,
    )


# =============================================================================
# Similarity Scoring
# =============================================================================

# Type compatibility matrix (for partial matches)
TYPE_COMPATIBILITY = {
    "cocktail_bar": ["bar", "wine_bar", "lounge"],
    "bar": ["cocktail_bar", "pub", "wine_bar"],
    "wine_bar": ["cocktail_bar", "bar", "restaurant"],
    "pub": ["bar", "sports_bar", "beer_garden"],
    "restaurant": ["fine_dining_restaurant", "wine_bar"],
    "lounge": ["cocktail_bar", "bar", "hotel"],
}


def compute_similarity(
    venue: sqlite3.Row,
    profile: SuccessProfile,
    target_norms: MarketNorms,
) -> SimilarityResult:
    """Compute similarity score between a venue and success profile.

    Scoring breakdown:
    - Type match: 0-30 points
    - Tier match: 0-30 points (price + quality + volume)
    - Relevance signature: 0-30 points (M-component similarity)
    - Authority overlay: 0-10 points

    Total: 0-100
    """
    matched_on = []

    # --- Type Score (0-30) ---
    venue_type = venue["venue_type"]
    type_score = 0.0

    if venue_type in profile.type_distribution:
        # Exact type match - score based on prevalence in profile
        type_weight = profile.type_distribution[venue_type]
        type_score = 30 * min(1.0, type_weight * 2)  # 50%+ prevalence = full score
        matched_on.append(venue_type.replace("_", " "))
    else:
        # Check compatible types
        for profile_type, weight in profile.type_distribution.items():
            compatible = TYPE_COMPATIBILITY.get(profile_type, [])
            if venue_type in compatible:
                type_score = max(type_score, 20 * weight)  # Partial credit
                if type_score > 10:
                    matched_on.append(f"similar to {profile_type.replace('_', ' ')}")
                break

    # --- Tier Score (0-30) ---
    tier_score = 0.0

    # Price tier (0-10)
    price_tier = venue["price_tier"]
    if price_tier in profile.price_tier_distribution:
        price_weight = profile.price_tier_distribution[price_tier]
        tier_score += 10 * min(1.0, price_weight * 2)
        if price_weight > 0.3:
            matched_on.append(f"{price_tier} price")

    # Quality tier (0-10)
    quality_tier = venue["quality_tier"]
    if quality_tier in profile.quality_tier_distribution:
        quality_weight = profile.quality_tier_distribution[quality_tier]
        tier_score += 10 * min(1.0, quality_weight * 2)
        if quality_weight > 0.3:
            matched_on.append(f"{quality_tier} quality")

    # Volume tier (0-10)
    volume_tier = venue["volume_tier"]
    if volume_tier in profile.volume_tier_distribution:
        volume_weight = profile.volume_tier_distribution[volume_tier]
        tier_score += 10 * min(1.0, volume_weight * 2)

    # --- Relevance Score (0-30) ---
    # Compare M-component signature
    venue_m_type = venue["m_type_score"] or 0.5
    venue_m_price = venue["m_price_score"] or 0.5
    venue_m_attr = venue["m_attribute_score"] or 0.5

    # Similarity = 1 - normalized distance
    m_type_diff = abs(venue_m_type - profile.avg_m_type_score)
    m_price_diff = abs(venue_m_price - profile.avg_m_price_score)
    m_attr_diff = abs(venue_m_attr - profile.avg_m_attribute_score)

    avg_diff = (m_type_diff + m_price_diff + m_attr_diff) / 3
    relevance_score = 30 * (1 - avg_diff)  # Closer = higher score

    if relevance_score > 20:
        matched_on.append("similar relevance profile")

    # --- Authority Score (0-10) ---
    authority_score = 0.0
    is_authority = (
        venue["on_worlds_50_best"] == 1 or
        venue["on_asias_50_best"] == 1 or
        venue["on_north_americas_50_best"] == 1
    )

    if is_authority and profile.authority_prevalence > 0.1:
        # Profile has authority venues, and this is one
        authority_score = 10
        matched_on.append("authority venue")
    elif is_authority:
        # Bonus even if profile doesn't have authority venues
        authority_score = 5

    # --- Total Score ---
    total_score = type_score + tier_score + relevance_score + authority_score

    # --- Confidence ---
    # Based on data quality and match strength
    if total_score > 70 and venue["confidence_tier"] in ("high", "medium"):
        confidence = "high"
    elif total_score > 50:
        confidence = "medium"
    else:
        confidence = "low"

    # --- Rationale ---
    if matched_on:
        rationale = f"Similar to your {profile.source_market} accounts: {', '.join(matched_on[:3])}"
    else:
        rationale = "Limited similarity signals"

    return SimilarityResult(
        place_id=venue["place_id"],
        name=venue["name"],
        city=venue["city"],
        address=venue["address"] or "",
        venue_type=venue_type,
        similarity_score=round(total_score, 1),
        type_score=round(type_score, 1),
        tier_score=round(tier_score, 1),
        relevance_score=round(relevance_score, 1),
        authority_score=round(authority_score, 1),
        confidence=confidence,
        matched_on=matched_on,
        rationale=rationale,
        distribution_fit_score=venue["distribution_fit_score"],
        price_tier=price_tier,
        quality_tier=quality_tier,
        volume_tier=volume_tier,
    )


# =============================================================================
# Main Pipeline
# =============================================================================


def find_lookalikes(
    source_accounts: list[AccountInput],
    source_market: str,
    target_market: str,
    exclude_place_ids: list[str] | None = None,
    limit: int = 100,
    min_confidence: str | None = None,
) -> dict:
    """Main pipeline: Find lookalike venues in target market.

    Args:
        source_accounts: Client's top accounts in source market
        source_market: Name of source market (e.g., "london")
        target_market: Name of target market (e.g., "berlin")
        exclude_place_ids: Place IDs to exclude (e.g., existing accounts)
        limit: Maximum results to return
        min_confidence: Minimum confidence tier ("high", "medium", or None)

    Returns:
        Dict with:
        - resolution_report: Account matching results
        - success_profile: Built profile
        - target_norms: Target market calibration
        - results: Ranked list of similar venues
    """
    # Step A: Resolve accounts
    resolved, unmatched = resolve_accounts(source_accounts)

    resolution_report = {
        "total_input": len(source_accounts),
        "resolved": len(resolved),
        "unmatched": len(unmatched),
        "unmatched_details": unmatched,
        "resolution_rate": len(resolved) / len(source_accounts) if source_accounts else 0,
    }

    if len(resolved) < 5:
        return {
            "error": f"Too few accounts resolved ({len(resolved)}). Need at least 5.",
            "resolution_report": resolution_report,
        }

    # Step B: Build success profile
    profile = build_success_profile(resolved, source_market)

    # Step C: Compute target market norms
    target_norms = compute_market_norms(target_market)

    # Step D: Get candidates from target market
    conn = get_connection()

    query = """
        SELECT * FROM venues
        WHERE LOWER(city) = LOWER(?)
        AND confidence_tier IN ('high', 'medium')
    """
    params = [target_market]

    if exclude_place_ids:
        placeholders = ",".join(["?" for _ in exclude_place_ids])
        query += f" AND place_id NOT IN ({placeholders})"
        params.extend(exclude_place_ids)

    candidates = conn.execute(query, params).fetchall()
    conn.close()

    # Step E: Score all candidates
    results = []
    for venue in candidates:
        result = compute_similarity(venue, profile, target_norms)

        # Apply confidence filter
        if min_confidence:
            conf_order = {"high": 3, "medium": 2, "low": 1}
            if conf_order.get(result.confidence, 0) < conf_order.get(min_confidence, 0):
                continue

        results.append(result)

    # Step F: Rank by similarity score
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    results = results[:limit]

    # Add ranks
    for i, result in enumerate(results):
        result.rank = i + 1

    return {
        "resolution_report": resolution_report,
        "success_profile": {
            "source_market": profile.source_market,
            "account_count": profile.account_count,
            "type_distribution": profile.type_distribution,
            "price_tier_distribution": profile.price_tier_distribution,
            "quality_tier_distribution": profile.quality_tier_distribution,
            "authority_prevalence": profile.authority_prevalence,
            "profile_confidence": profile.profile_confidence,
            "concentration_warning": profile.concentration_warning,
        },
        "target_market": {
            "name": target_market,
            "venue_count": target_norms.venue_count,
            "candidates_scored": len(candidates),
        },
        "results": [
            {
                "rank": r.rank,
                "name": r.name,
                "venue_type": r.venue_type,
                "address": r.address,
                "similarity_score": r.similarity_score,
                "confidence": r.confidence,
                "matched_on": r.matched_on,
                "rationale": r.rationale,
                "score_breakdown": {
                    "type": r.type_score,
                    "tiers": r.tier_score,
                    "relevance": r.relevance_score,
                    "authority": r.authority_score,
                },
                "context": {
                    "distribution_fit_score": r.distribution_fit_score,
                    "price_tier": r.price_tier,
                    "quality_tier": r.quality_tier,
                    "volume_tier": r.volume_tier,
                },
                "place_id": r.place_id,
            }
            for r in results
        ],
    }


# =============================================================================
# CLI for Testing
# =============================================================================

if __name__ == "__main__":
    # Test with mock London accounts looking for Berlin matches
    test_accounts = [
        AccountInput(name="The Connaught Bar", city="london"),
        AccountInput(name="Satan's Whiskers", city="london"),
        AccountInput(name="Tayēr + Elementary", city="london"),
        AccountInput(name="Swift Soho", city="london"),
        AccountInput(name="Nightjar", city="london"),
        AccountInput(name="Oriole", city="london"),
        AccountInput(name="Scarfes Bar", city="london"),
        AccountInput(name="American Bar at The Savoy", city="london"),
        AccountInput(name="Kwãnt", city="london"),
        AccountInput(name="Three Sheets", city="london"),
    ]

    print("=" * 70)
    print("CROSS-MARKET LOOKALIKE TEST")
    print("Source: London (10 accounts) → Target: Berlin")
    print("=" * 70)

    result = find_lookalikes(
        source_accounts=test_accounts,
        source_market="london",
        target_market="berlin",
        limit=20,
    )

    if "error" in result:
        print(f"\nError: {result['error']}")
    else:
        # Resolution report
        res = result["resolution_report"]
        print(f"\n📋 Resolution: {res['resolved']}/{res['total_input']} accounts matched")
        if res["unmatched_details"]:
            print(f"   Unmatched: {[u['name'] for u in res['unmatched_details']]}")

        # Profile summary
        prof = result["success_profile"]
        print(f"\n📊 Success Profile ({prof['profile_confidence']} confidence)")
        print(f"   Types: {prof['type_distribution']}")
        print(f"   Price: {prof['price_tier_distribution']}")
        if prof["concentration_warning"]:
            print(f"   ⚠️  {prof['concentration_warning']}")

        # Results
        print(f"\n🎯 Top Berlin Matches ({len(result['results'])} venues)")
        print("-" * 70)

        for r in result["results"][:10]:
            ctx = r["context"]
            print(f"\n#{r['rank']:2d} | {r['similarity_score']:5.1f} | {r['name']}")
            print(f"     Type: {r['venue_type']} | {ctx['price_tier']} | {ctx['quality_tier']}")
            print(f"     {r['rationale']}")
            print(f"     Scores: type={r['score_breakdown']['type']:.0f}, "
                  f"tiers={r['score_breakdown']['tiers']:.0f}, "
                  f"relevance={r['score_breakdown']['relevance']:.0f}, "
                  f"authority={r['score_breakdown']['authority']:.0f}")
