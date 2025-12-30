"""Import historical venue data into compliant storage.

Reads CSV files from data/raw/ and converts to VenueRecords,
storing only derived tiers (not raw Google values).
"""

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from venue_intel.models import (
    ConfidenceTier,
    PriceTier,
    QualityTier,
    VenueRecord,
    VolumeTier,
    compute_price_tier,
    compute_quality_tier,
    compute_volume_tier,
)
from venue_intel.storage import save_venue, get_connection


# =============================================================================
# Country Code Mapping
# =============================================================================

COUNTRY_MAP = {
    "GB": "UK",
    "UK": "UK",
    "FR": "France",
    "DE": "Germany",
}


# =============================================================================
# Type Classification
# =============================================================================

def determine_venue_type(type_str: str, subtypes_str: str | None) -> str:
    """Determine primary venue type from historical data."""
    if pd.isna(type_str):
        return "unknown"

    # Normalise to lowercase for matching
    type_lower = type_str.lower().replace(" ", "_")

    # Map common types
    type_mapping = {
        "cocktail_bar": "cocktail_bar",
        "wine_bar": "wine_bar",
        "bar": "bar",
        "pub": "pub",
        "lounge": "lounge",
        "restaurant": "restaurant",
        "cafe": "cafe",
        "coffee_shop": "cafe",
        "hotel": "hotel",
        "night_club": "night_club",
        "nightclub": "night_club",
    }

    for key, value in type_mapping.items():
        if key in type_lower:
            return value

    return type_lower


def is_premium_indicator(
    venue_type: str,
    rating: float | None,
    subtypes: str | None,
) -> bool:
    """Determine if venue shows premium signals."""
    premium_signals = 0

    # Premium types
    if venue_type in ["cocktail_bar", "wine_bar", "fine_dining_restaurant"]:
        premium_signals += 1

    # Excellent rating
    if rating and rating >= 4.5:
        premium_signals += 1

    # Check subtypes for premium keywords
    if subtypes and not pd.isna(subtypes):
        subtypes_lower = subtypes.lower()
        if any(kw in subtypes_lower for kw in ["upscale", "fine dining", "luxury", "cocktail"]):
            premium_signals += 1

    return premium_signals >= 2


def compute_confidence_tier_historical(reviews: int | None) -> ConfidenceTier:
    """Compute confidence tier for historical data.

    Since we don't know the freshness, we cap at MEDIUM for stale data.
    """
    if reviews is None or reviews < 30:
        return ConfidenceTier.LOW
    elif reviews >= 100:
        return ConfidenceTier.MEDIUM  # Capped due to unknown freshness
    else:
        return ConfidenceTier.LOW


# =============================================================================
# Score Computation (Simplified for Historical Data)
# =============================================================================

def compute_historical_scores(
    rating: float | None,
    reviews: int | None,
    venue_type: str,
) -> tuple[float, float, float, float]:
    """Compute V/R/M scores and distribution fit from historical data.

    Returns:
        Tuple of (distribution_fit_score, v_score, r_score, m_score)
    """
    import math

    # V score (volume)
    if reviews and reviews > 0:
        log_count = math.log1p(reviews)
        log_max = math.log1p(5000)  # Normalise against 5000
        v_score = min(log_count / log_max, 1.0)
    else:
        v_score = 0.0

    # R score (quality with confidence adjustment)
    if rating:
        rating_normalised = (rating - 1.0) / 4.0
        confidence = min(1.0, (reviews or 0) / 50)
        r_score = rating_normalised * confidence
    else:
        r_score = 0.0

    # M score (simplified type-based relevance)
    type_scores = {
        "cocktail_bar": 0.9,
        "wine_bar": 0.85,
        "bar": 0.7,
        "lounge": 0.7,
        "pub": 0.5,
        "restaurant": 0.5,
        "hotel": 0.4,
        "cafe": 0.3,
        "night_club": 0.3,
    }
    m_score = type_scores.get(venue_type, 0.4)

    # Combined score
    distribution_fit = (0.25 * v_score + 0.25 * r_score + 0.50 * m_score) * 100

    return round(distribution_fit, 1), round(v_score, 3), round(r_score, 3), round(m_score, 3)


def generate_historical_rationale(
    venue_type: str,
    volume_tier: VolumeTier,
    quality_tier: QualityTier,
    confidence_tier: ConfidenceTier,
) -> str:
    """Generate rationale for historical import."""
    parts = []

    # Type
    type_display = venue_type.replace("_", " ").title()
    parts.append(f"Venue type: {type_display}")

    # Volume
    if volume_tier in [VolumeTier.VERY_HIGH, VolumeTier.HIGH]:
        parts.append("high visibility")
    elif volume_tier == VolumeTier.MEDIUM:
        parts.append("moderate visibility")
    else:
        parts.append("limited visibility")

    # Quality
    if quality_tier == QualityTier.EXCELLENT:
        parts.append("excellent rating tier")
    elif quality_tier == QualityTier.GOOD:
        parts.append("good rating tier")

    # Historical caveat
    parts.append("(historical import - refresh recommended)")

    return "; ".join(parts) + "."


# =============================================================================
# Main Import Function
# =============================================================================

def import_city_file(filepath: Path, city_override: str | None = None) -> dict:
    """Import a single city CSV file.

    Args:
        filepath: Path to CSV file
        city_override: Override city name if needed

    Returns:
        Summary dict with counts
    """
    print(f"\nImporting: {filepath.name}")
    print("-" * 40)

    # Read CSV
    df = pd.read_csv(filepath)
    total_rows = len(df)
    print(f"Total rows: {total_rows}")

    # Get city name from filename if not overridden
    if city_override:
        city = city_override
    else:
        city = filepath.stem.replace("-Raw", "").lower()

    # Get database connection
    conn = get_connection()

    imported = 0
    skipped = 0
    errors = 0

    now = datetime.now(timezone.utc)

    for idx, row in df.iterrows():
        try:
            # Skip if no place_id
            if pd.isna(row.get("place_id")):
                skipped += 1
                continue

            place_id = str(row["place_id"])

            # Extract values
            name = str(row["name"]) if not pd.isna(row.get("name")) else "Unknown"
            rating = float(row["rating"]) if not pd.isna(row.get("rating")) else None
            reviews = int(row["reviews"]) if not pd.isna(row.get("reviews")) else None

            # Address
            address = str(row["full_address"]) if not pd.isna(row.get("full_address")) else None

            # Coordinates
            lat = float(row["latitude"]) if not pd.isna(row.get("latitude")) else 0.0
            lng = float(row["longitude"]) if not pd.isna(row.get("longitude")) else 0.0

            # Country
            country_code = str(row["country_code"]) if not pd.isna(row.get("country_code")) else "UK"
            country = COUNTRY_MAP.get(country_code, country_code)

            # Venue type
            venue_type = determine_venue_type(
                row.get("type"),
                row.get("subtypes"),
            )

            # Compute tiers (our derived categorisation)
            volume_tier = compute_volume_tier(reviews)
            quality_tier = compute_quality_tier(rating)

            # Price tier - try to extract from 'range' or 'about' fields
            price_tier = PriceTier.UNKNOWN  # Historical data may not have this

            # Premium indicator
            is_premium = is_premium_indicator(venue_type, rating, row.get("subtypes"))

            # Compute scores
            dist_score, v_score, r_score, m_score = compute_historical_scores(
                rating, reviews, venue_type
            )

            # Confidence tier
            confidence_tier = compute_confidence_tier_historical(reviews)

            # Rationale
            rationale = generate_historical_rationale(
                venue_type, volume_tier, quality_tier, confidence_tier
            )

            # Create VenueRecord
            record = VenueRecord(
                place_id=place_id,
                name=name,
                city=city,
                country=country,
                address=address,
                latitude=lat,
                longitude=lng,
                volume_tier=volume_tier,
                quality_tier=quality_tier,
                price_tier=price_tier,
                venue_type=venue_type,
                is_premium_indicator=is_premium,
                distribution_fit_score=dist_score,
                v_score=v_score,
                r_score=r_score,
                m_score=m_score,
                confidence_tier=confidence_tier,
                rationale=rationale,
                brand_category="all",  # Generic for historical import
                first_seen_at=now,
                last_scored_at=now,
                score_version="1.0-historical",
            )

            # Save to database
            save_venue(record, conn)
            imported += 1

            # Progress indicator
            if imported % 1000 == 0:
                print(f"  Imported: {imported}...")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error on row {idx}: {e}")

    conn.close()

    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

    return {
        "city": city,
        "total": total_rows,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }


def import_all_historical(raw_dir: Path | None = None) -> list[dict]:
    """Import all historical CSV files from raw directory.

    Returns:
        List of summary dicts per city
    """
    if raw_dir is None:
        raw_dir = Path(__file__).parent.parent.parent / "data" / "raw"

    print("=" * 60)
    print("VIDPS Historical Import")
    print("=" * 60)

    # Find all CSV files
    csv_files = sorted(raw_dir.glob("*-Raw.csv"))
    print(f"\nFound {len(csv_files)} city files")

    results = []

    for filepath in csv_files:
        result = import_city_file(filepath)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)

    total_imported = sum(r["imported"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    print(f"\n{'City':<15} {'Total':<10} {'Imported':<10} {'Errors':<10}")
    print("-" * 45)
    for r in results:
        print(f"{r['city'].title():<15} {r['total']:<10} {r['imported']:<10} {r['errors']:<10}")
    print("-" * 45)
    print(f"{'TOTAL':<15} {sum(r['total'] for r in results):<10} {total_imported:<10} {total_errors:<10}")

    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import_all_historical()
