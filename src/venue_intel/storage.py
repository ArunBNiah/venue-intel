"""Permanent storage layer for venue intelligence.

This module stores ONLY compliant data:
- place_ids (allowed indefinitely per Google ToS)
- Venue identity (public info: name, address, location)
- Our derived tiers (transformations, not raw Google data)
- Our scores and rationales (100% our IP)

Raw Google API data (exact ratings, review counts) is NEVER stored.
See docs/data-freshness.md for refresh policy.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from venue_intel.models import (
    ConfidenceTier,
    PriceTier,
    QualityTier,
    VenueRecord,
    VolumeTier,
)


# =============================================================================
# Database Setup
# =============================================================================

DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "venue_intelligence.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection, creating tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    _migrate_add_binary_signals(conn)
    _migrate_add_authority_sources(conn)
    _migrate_add_brand_flexibility(conn)
    return conn


def _migrate_add_binary_signals(conn: sqlite3.Connection) -> None:
    """Add binary signal columns if they don't exist (migration)."""
    cursor = conn.execute("PRAGMA table_info(venues)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("serves_cocktails", "INTEGER"),
        ("serves_wine", "INTEGER"),
        ("serves_beer", "INTEGER"),
        ("serves_spirits", "INTEGER"),
        ("has_great_cocktails", "INTEGER"),
        ("has_great_beer", "INTEGER"),
        ("has_great_wine", "INTEGER"),
        ("is_upscale", "INTEGER"),
        ("is_late_night", "INTEGER"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE venues ADD COLUMN {col_name} {col_type}")

    conn.commit()


def _migrate_add_authority_sources(conn: sqlite3.Connection) -> None:
    """Add authority source columns if they don't exist (migration).

    Supports multiple authority lists:
    - World's 50 Best Bars (already exists)
    - Asia's 50 Best Bars
    - North America's 50 Best Bars
    """
    cursor = conn.execute("PRAGMA table_info(venues)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        # Asia's 50 Best Bars
        ("on_asias_50_best", "INTEGER"),
        ("asias_50_best_rank", "INTEGER"),
        # North America's 50 Best Bars
        ("on_north_americas_50_best", "INTEGER"),
        ("north_americas_50_best_rank", "INTEGER"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE venues ADD COLUMN {col_name} {col_type}")

    conn.commit()


def _migrate_add_brand_flexibility(conn: sqlite3.Connection) -> None:
    """Add columns for multi-brand profile support.

    Enables M score recalculation for different brand profiles without
    re-fetching Google data. Stores:
    1. Type classifications (our derived booleans)
    2. M sub-component scores (for reweighting)

    These are ToS-compliant as they're our derived assessments.
    """
    cursor = conn.execute("PRAGMA table_info(venues)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        # Type classifications (derived from venue_type)
        ("is_cocktail_focused", "INTEGER"),
        ("is_dining_focused", "INTEGER"),
        ("is_nightlife_focused", "INTEGER"),
        ("is_casual_drinking", "INTEGER"),

        # M sub-component scores (for reweighting)
        ("m_type_score", "REAL"),
        ("m_price_score", "REAL"),
        ("m_attribute_score", "REAL"),
        ("m_keyword_score", "REAL"),
    ]

    added_new = False
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE venues ADD COLUMN {col_name} {col_type}")
            added_new = True

    conn.commit()

    # If we added new columns, populate them from existing data
    if added_new:
        _populate_brand_flexibility_columns(conn)


def _populate_brand_flexibility_columns(conn: sqlite3.Connection) -> None:
    """Populate brand flexibility columns from existing data."""

    # Type classification mappings
    cocktail_types = ('cocktail_bar', 'wine_bar', 'bar', 'lounge')
    dining_types = ('restaurant', 'fine_dining_restaurant', 'french_restaurant',
                    'italian_restaurant', 'japanese_restaurant', 'steak_house',
                    'seafood_restaurant', 'indian_restaurant', 'chinese_restaurant')
    nightlife_types = ('night_club', 'karaoke', 'adult_entertainment_club')
    casual_types = ('pub', 'sports_bar', 'beer_garden', 'beer_hall', 'izakaya')

    # Update type classifications
    for types, column in [
        (cocktail_types, 'is_cocktail_focused'),
        (dining_types, 'is_dining_focused'),
        (nightlife_types, 'is_nightlife_focused'),
        (casual_types, 'is_casual_drinking'),
    ]:
        placeholders = ','.join(['?' for _ in types])
        conn.execute(f"""
            UPDATE venues SET {column} = CASE
                WHEN venue_type IN ({placeholders}) THEN 1
                ELSE 0
            END
        """, types)

    # Type score mapping (from scoring.py TYPE_SCORES)
    type_scores = {
        'cocktail_bar': 1.0, 'wine_bar': 1.0,
        'bar': 0.7, 'lounge': 0.7,
        'fine_dining_restaurant': 0.6,
        'french_restaurant': 0.5, 'italian_restaurant': 0.5,
        'japanese_restaurant': 0.5, 'steak_house': 0.5,
        'restaurant': 0.4, 'boutique_hotel': 0.4,
        'hotel': 0.3, 'resort_hotel': 0.3, 'british_restaurant': 0.3,
        'pub': 0.2, 'izakaya': 0.2,
        'cafe': 0.1,
        'night_club': -0.2, 'sports_bar': -0.2,
        'karaoke': -0.3, 'liquor_store': -0.5,
        'fast_food_restaurant': -0.8,
        'convenience_store': -1.0,
    }

    # Update m_type_score based on venue_type
    for venue_type, score in type_scores.items():
        # Normalise from (-1,1) to (0,1) for storage
        normalised = (score + 1.0) / 2.0
        conn.execute("""
            UPDATE venues SET m_type_score = ?
            WHERE venue_type = ? AND m_type_score IS NULL
        """, (normalised, venue_type))

    # Set default for unknown types
    conn.execute("""
        UPDATE venues SET m_type_score = 0.5
        WHERE m_type_score IS NULL
    """)

    # Price score from price_tier
    price_scores = {
        'premium': 0.9,
        'mid': 0.4,
        'budget': 0.1,
        'unknown': 0.3,
    }
    for tier, score in price_scores.items():
        conn.execute("""
            UPDATE venues SET m_price_score = ?
            WHERE price_tier = ?
        """, (score, tier))

    # Attribute score from binary signals
    # Formula: (0.4*cocktails + 0.2*wine + 0.1*spirits + 0.1*beer) / 0.8, capped at 1.0
    conn.execute("""
        UPDATE venues SET m_attribute_score =
            MIN(1.0, (
                COALESCE(serves_cocktails, 0) * 0.4 +
                COALESCE(serves_wine, 0) * 0.2 +
                COALESCE(serves_spirits, 0) * 0.1 +
                COALESCE(serves_beer, 0) * 0.1
            ) / 0.8)
    """)

    # Keyword score - set to neutral (0.5) since we don't have editorial summary
    conn.execute("""
        UPDATE venues SET m_keyword_score = 0.5
    """)

    conn.commit()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        -- Main venue intelligence table (permanent, compliant)
        CREATE TABLE IF NOT EXISTS venues (
            -- Identifier (Google allows permanent storage)
            place_id TEXT PRIMARY KEY,

            -- Venue identity (public information)
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT 'UK',
            address TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,

            -- Our derived tiers (NOT raw Google data)
            volume_tier TEXT NOT NULL,
            quality_tier TEXT NOT NULL,
            price_tier TEXT NOT NULL,

            -- Venue classification (our assessment)
            venue_type TEXT NOT NULL,
            is_premium_indicator INTEGER NOT NULL DEFAULT 0,

            -- Our scores (100% our IP)
            distribution_fit_score REAL NOT NULL,
            v_score REAL NOT NULL,
            r_score REAL NOT NULL,
            m_score REAL NOT NULL,
            confidence_tier TEXT NOT NULL,

            -- Our generated content
            rationale TEXT NOT NULL,

            -- Binary signals (our derived flags)
            serves_cocktails INTEGER,
            serves_wine INTEGER,
            serves_beer INTEGER,
            serves_spirits INTEGER,
            has_great_cocktails INTEGER,
            has_great_beer INTEGER,
            has_great_wine INTEGER,
            is_upscale INTEGER,
            is_late_night INTEGER,

            -- Metadata
            brand_category TEXT NOT NULL DEFAULT 'premium_spirits',
            first_seen_at TEXT NOT NULL,
            last_scored_at TEXT NOT NULL,
            score_version TEXT NOT NULL DEFAULT '1.0'
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_city ON venues(city);
        CREATE INDEX IF NOT EXISTS idx_score ON venues(distribution_fit_score DESC);
        CREATE INDEX IF NOT EXISTS idx_brand ON venues(brand_category);
        CREATE INDEX IF NOT EXISTS idx_volume_tier ON venues(volume_tier);
        CREATE INDEX IF NOT EXISTS idx_quality_tier ON venues(quality_tier);

        -- Discovery log (for tracking API usage)
        CREATE TABLE IF NOT EXISTS discovery_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            query TEXT NOT NULL,
            place_ids_found TEXT NOT NULL,
            discovered_at TEXT NOT NULL
        );
    """)
    conn.commit()


# =============================================================================
# Save Operations
# =============================================================================

def save_venue(
    venue: VenueRecord,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Save a venue record to permanent storage."""
    should_close = conn is None
    conn = conn or get_connection()

    # Check if venue exists (for first_seen_at preservation)
    existing = conn.execute(
        "SELECT first_seen_at FROM venues WHERE place_id = ?",
        (venue.place_id,)
    ).fetchone()

    first_seen = (
        existing["first_seen_at"] if existing
        else venue.first_seen_at.isoformat()
    )

    conn.execute("""
        INSERT OR REPLACE INTO venues (
            place_id, name, city, country, address, latitude, longitude,
            volume_tier, quality_tier, price_tier,
            venue_type, is_premium_indicator,
            distribution_fit_score, v_score, r_score, m_score, confidence_tier,
            rationale,
            serves_cocktails, serves_wine, serves_beer, serves_spirits,
            has_great_cocktails, has_great_beer, has_great_wine,
            is_upscale, is_late_night,
            brand_category, first_seen_at, last_scored_at, score_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        venue.place_id,
        venue.name,
        venue.city,
        venue.country,
        venue.address,
        venue.latitude,
        venue.longitude,
        venue.volume_tier.value,
        venue.quality_tier.value,
        venue.price_tier.value,
        venue.venue_type,
        1 if venue.is_premium_indicator else 0,
        venue.distribution_fit_score,
        venue.v_score,
        venue.r_score,
        venue.m_score,
        venue.confidence_tier.value,
        venue.rationale,
        1 if venue.serves_cocktails else (0 if venue.serves_cocktails is False else None),
        1 if venue.serves_wine else (0 if venue.serves_wine is False else None),
        1 if venue.serves_beer else (0 if venue.serves_beer is False else None),
        1 if venue.serves_spirits else (0 if venue.serves_spirits is False else None),
        1 if venue.has_great_cocktails else (0 if venue.has_great_cocktails is False else None),
        1 if venue.has_great_beer else (0 if venue.has_great_beer is False else None),
        1 if venue.has_great_wine else (0 if venue.has_great_wine is False else None),
        1 if venue.is_upscale else (0 if venue.is_upscale is False else None),
        1 if venue.is_late_night else (0 if venue.is_late_night is False else None),
        venue.brand_category,
        first_seen,
        venue.last_scored_at.isoformat(),
        venue.score_version,
    ))
    conn.commit()

    if should_close:
        conn.close()


def save_venues(venues: list[VenueRecord]) -> int:
    """Save multiple venue records. Returns count saved."""
    conn = get_connection()
    for venue in venues:
        save_venue(venue, conn)
    conn.close()
    return len(venues)


def log_discovery(
    city: str,
    query: str,
    place_ids: list[str],
) -> None:
    """Log a discovery query for tracking."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO discovery_log (city, query, place_ids_found, discovered_at)
        VALUES (?, ?, ?, ?)
    """, (
        city,
        query,
        json.dumps(place_ids),
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


# =============================================================================
# Read Operations
# =============================================================================

def get_venue(place_id: str) -> VenueRecord | None:
    """Get a venue by place_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM venues WHERE place_id = ?", (place_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    return _row_to_venue_record(row)


def get_known_place_ids(city: str | None = None) -> set[str]:
    """Get all place_ids we have stored."""
    conn = get_connection()
    if city:
        rows = conn.execute(
            "SELECT place_id FROM venues WHERE city = ?", (city.lower(),)
        ).fetchall()
    else:
        rows = conn.execute("SELECT place_id FROM venues").fetchall()
    conn.close()

    return {row["place_id"] for row in rows}


def get_ranked_venues(
    city: str,
    brand_category: str = "premium_spirits",
    limit: int = 100,
) -> list[VenueRecord]:
    """Get ranked venues for a city."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM venues
        WHERE city = ? AND brand_category = ?
        ORDER BY distribution_fit_score DESC
        LIMIT ?
    """, (city.lower(), brand_category, limit)).fetchall()
    conn.close()

    return [_row_to_venue_record(row) for row in rows]


def get_venues_by_tier(
    city: str,
    volume_tier: VolumeTier | None = None,
    quality_tier: QualityTier | None = None,
    price_tier: PriceTier | None = None,
    limit: int = 100,
) -> list[VenueRecord]:
    """Get venues filtered by tiers."""
    conn = get_connection()

    query = "SELECT * FROM venues WHERE city = ?"
    params = [city.lower()]

    if volume_tier:
        query += " AND volume_tier = ?"
        params.append(volume_tier.value)
    if quality_tier:
        query += " AND quality_tier = ?"
        params.append(quality_tier.value)
    if price_tier:
        query += " AND price_tier = ?"
        params.append(price_tier.value)

    query += " ORDER BY distribution_fit_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [_row_to_venue_record(row) for row in rows]


def get_venue_count(city: str | None = None) -> int:
    """Get count of stored venues."""
    conn = get_connection()
    if city:
        count = conn.execute(
            "SELECT COUNT(*) FROM venues WHERE city = ?", (city.lower(),)
        ).fetchone()[0]
    else:
        count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    conn.close()
    return count


def get_city_summary(city: str) -> dict:
    """Get summary statistics for a city."""
    conn = get_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM venues WHERE city = ?", (city.lower(),)
    ).fetchone()[0]

    if total == 0:
        conn.close()
        return {"city": city, "total": 0}

    # Volume tier distribution
    volume_dist = {}
    for tier in VolumeTier:
        count = conn.execute(
            "SELECT COUNT(*) FROM venues WHERE city = ? AND volume_tier = ?",
            (city.lower(), tier.value)
        ).fetchone()[0]
        volume_dist[tier.value] = count

    # Quality tier distribution
    quality_dist = {}
    for tier in QualityTier:
        count = conn.execute(
            "SELECT COUNT(*) FROM venues WHERE city = ? AND quality_tier = ?",
            (city.lower(), tier.value)
        ).fetchone()[0]
        quality_dist[tier.value] = count

    # Price tier distribution
    price_dist = {}
    for tier in PriceTier:
        count = conn.execute(
            "SELECT COUNT(*) FROM venues WHERE city = ? AND price_tier = ?",
            (city.lower(), tier.value)
        ).fetchone()[0]
        price_dist[tier.value] = count

    # Score stats
    stats = conn.execute("""
        SELECT
            AVG(distribution_fit_score) as avg_score,
            MAX(distribution_fit_score) as max_score,
            MIN(distribution_fit_score) as min_score
        FROM venues WHERE city = ?
    """, (city.lower(),)).fetchone()

    conn.close()

    return {
        "city": city,
        "total": total,
        "volume_distribution": volume_dist,
        "quality_distribution": quality_dist,
        "price_distribution": price_dist,
        "avg_score": round(stats["avg_score"], 1) if stats["avg_score"] else 0,
        "max_score": round(stats["max_score"], 1) if stats["max_score"] else 0,
        "min_score": round(stats["min_score"], 1) if stats["min_score"] else 0,
    }


# =============================================================================
# Brand Profile Calculations
# =============================================================================

# Pre-defined brand profiles with M sub-component weights
# Note: keyword scoring removed - we don't store editorial summary (ToS compliance)
# If client needs keyword-based matching, requires API re-fetch (~$20/1k venues)
BRAND_PROFILES = {
    "premium_spirits": {
        "description": "Premium cocktail bars and upscale venues",
        "weights": {"type": 0.45, "price": 0.35, "attribute": 0.20},
        "type_boost": {"is_cocktail_focused": 0.15, "is_casual_drinking": -0.10},
    },
    "craft_beer": {
        "description": "Craft beer focused venues and pubs",
        "weights": {"type": 0.30, "price": 0.15, "attribute": 0.55},
        "type_boost": {"is_casual_drinking": 0.20, "is_cocktail_focused": -0.05},
    },
    "fine_wine": {
        "description": "Wine bars and fine dining",
        "weights": {"type": 0.35, "price": 0.40, "attribute": 0.25},
        "type_boost": {"is_dining_focused": 0.15, "is_nightlife_focused": -0.15},
    },
    "budget_drinks": {
        "description": "High-volume budget-friendly venues",
        "weights": {"type": 0.25, "price": 0.15, "attribute": 0.60},
        "type_boost": {"is_casual_drinking": 0.20, "is_nightlife_focused": 0.10},
        "invert_price": True,  # Lower price = higher score
    },
}


def calculate_profile_m_score(
    m_type: float,
    m_price: float,
    m_attribute: float,
    is_cocktail_focused: bool,
    is_dining_focused: bool,
    is_nightlife_focused: bool,
    is_casual_drinking: bool,
    profile: str = "premium_spirits",
) -> float:
    """Calculate M score for a specific brand profile.

    Uses stored M sub-components and type classifications to compute
    a profile-specific M score without needing raw Google data.

    Components used:
    - Type score: How well venue type matches profile (cocktail_bar vs pub)
    - Price score: Price tier alignment (premium vs budget)
    - Attribute score: Beverage signals (serves_cocktails, serves_beer, etc.)

    Note: Keyword scoring not used - would require storing editorial summary.

    Args:
        m_type, m_price, m_attribute: Stored M sub-components
        is_*: Type classification booleans
        profile: Brand profile name

    Returns:
        M score (0-1) for the specified profile
    """
    if profile not in BRAND_PROFILES:
        profile = "premium_spirits"

    config = BRAND_PROFILES[profile]
    weights = config["weights"]

    # Invert price score if profile prefers budget
    price_score = m_price
    if config.get("invert_price"):
        price_score = 1.0 - m_price

    # Base weighted score (3 components)
    m_score = (
        weights["type"] * m_type +
        weights["price"] * price_score +
        weights["attribute"] * m_attribute
    )

    # Apply type boosts
    boosts = config.get("type_boost", {})
    if is_cocktail_focused and "is_cocktail_focused" in boosts:
        m_score += boosts["is_cocktail_focused"]
    if is_dining_focused and "is_dining_focused" in boosts:
        m_score += boosts["is_dining_focused"]
    if is_nightlife_focused and "is_nightlife_focused" in boosts:
        m_score += boosts["is_nightlife_focused"]
    if is_casual_drinking and "is_casual_drinking" in boosts:
        m_score += boosts["is_casual_drinking"]

    # Clamp to 0-1
    return max(0.0, min(1.0, m_score))


def get_venues_by_profile(
    city: str,
    profile: str = "premium_spirits",
    limit: int = 100,
) -> list[dict]:
    """Get venues ranked by a specific brand profile.

    Recalculates M and distribution_fit_score using stored sub-components.

    Args:
        city: City name
        profile: Brand profile name
        limit: Maximum results

    Returns:
        List of venue dicts with recalculated scores
    """
    conn = get_connection()

    rows = conn.execute("""
        SELECT *,
               m_type_score, m_price_score, m_attribute_score, m_keyword_score,
               is_cocktail_focused, is_dining_focused, is_nightlife_focused, is_casual_drinking
        FROM venues
        WHERE city = ?
    """, (city.lower(),)).fetchall()

    conn.close()

    # Recalculate scores for each venue
    results = []
    for row in rows:
        new_m = calculate_profile_m_score(
            m_type=row["m_type_score"] or 0.5,
            m_price=row["m_price_score"] or 0.3,
            m_attribute=row["m_attribute_score"] or 0.3,
            is_cocktail_focused=bool(row["is_cocktail_focused"]),
            is_dining_focused=bool(row["is_dining_focused"]),
            is_nightlife_focused=bool(row["is_nightlife_focused"]),
            is_casual_drinking=bool(row["is_casual_drinking"]),
            profile=profile,
        )

        # Recalculate distribution fit score with new M
        new_score = (0.25 * row["v_score"] + 0.25 * row["r_score"] + 0.50 * new_m) * 100

        results.append({
            "place_id": row["place_id"],
            "name": row["name"],
            "city": row["city"],
            "venue_type": row["venue_type"],
            "address": row["address"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "v_score": row["v_score"],
            "r_score": row["r_score"],
            "m_score": round(new_m, 3),
            "m_score_original": row["m_score"],
            "distribution_fit_score": round(new_score, 1),
            "original_score": row["distribution_fit_score"],
            "volume_tier": row["volume_tier"],
            "quality_tier": row["quality_tier"],
            "price_tier": row["price_tier"],
            "confidence_tier": row["confidence_tier"],
            "is_cocktail_focused": bool(row["is_cocktail_focused"]),
            "is_casual_drinking": bool(row["is_casual_drinking"]),
            "profile": profile,
        })

    # Sort by new score
    results.sort(key=lambda x: x["distribution_fit_score"], reverse=True)

    return results[:limit]


def get_available_profiles() -> dict:
    """Get available brand profiles with descriptions."""
    return {k: v["description"] for k, v in BRAND_PROFILES.items()}


# =============================================================================
# Helpers
# =============================================================================

def _int_to_bool(val: int | None) -> bool | None:
    """Convert SQLite integer to Python bool, preserving None."""
    if val is None:
        return None
    return bool(val)


def _row_to_venue_record(row: sqlite3.Row) -> VenueRecord:
    """Convert database row to VenueRecord."""
    return VenueRecord(
        place_id=row["place_id"],
        name=row["name"],
        city=row["city"],
        country=row["country"],
        address=row["address"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        volume_tier=VolumeTier(row["volume_tier"]),
        quality_tier=QualityTier(row["quality_tier"]),
        price_tier=PriceTier(row["price_tier"]),
        venue_type=row["venue_type"],
        is_premium_indicator=bool(row["is_premium_indicator"]),
        distribution_fit_score=row["distribution_fit_score"],
        v_score=row["v_score"],
        r_score=row["r_score"],
        m_score=row["m_score"],
        confidence_tier=ConfidenceTier(row["confidence_tier"]),
        rationale=row["rationale"],
        serves_cocktails=_int_to_bool(row["serves_cocktails"]) if "serves_cocktails" in row.keys() else None,
        serves_wine=_int_to_bool(row["serves_wine"]) if "serves_wine" in row.keys() else None,
        serves_beer=_int_to_bool(row["serves_beer"]) if "serves_beer" in row.keys() else None,
        serves_spirits=_int_to_bool(row["serves_spirits"]) if "serves_spirits" in row.keys() else None,
        has_great_cocktails=_int_to_bool(row["has_great_cocktails"]) if "has_great_cocktails" in row.keys() else None,
        has_great_beer=_int_to_bool(row["has_great_beer"]) if "has_great_beer" in row.keys() else None,
        has_great_wine=_int_to_bool(row["has_great_wine"]) if "has_great_wine" in row.keys() else None,
        is_upscale=_int_to_bool(row["is_upscale"]) if "is_upscale" in row.keys() else None,
        is_late_night=_int_to_bool(row["is_late_night"]) if "is_late_night" in row.keys() else None,
        brand_category=row["brand_category"],
        first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
        last_scored_at=datetime.fromisoformat(row["last_scored_at"]),
        score_version=row["score_version"],
    )


def clear_city_data(city: str) -> int:
    """Clear all data for a city. Returns count deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM venues WHERE city = ?", (city.lower(),))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# =============================================================================
# Database Info
# =============================================================================

def get_database_path() -> Path:
    """Get the path to the database file."""
    return DB_PATH


def get_all_cities() -> list[str]:
    """Get list of all cities in the database."""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT city FROM venues ORDER BY city").fetchall()
    conn.close()
    return [row["city"] for row in rows]
