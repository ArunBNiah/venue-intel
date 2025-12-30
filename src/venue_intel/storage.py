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
    return conn


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
            rationale, brand_category, first_seen_at, last_scored_at, score_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
# Helpers
# =============================================================================

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
