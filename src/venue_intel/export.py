"""Export functionality for venue data.

Exports scored venues to CSV and Excel formats for client delivery.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from venue_intel.models import VenueRecord
from venue_intel.storage import get_ranked_venues


# =============================================================================
# Export Directory
# =============================================================================

EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "exports"


def _ensure_export_dir() -> Path:
    """Ensure export directory exists."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR


# =============================================================================
# DataFrame Conversion
# =============================================================================

def venues_to_dataframe(venues: list[VenueRecord]) -> pd.DataFrame:
    """Convert venue records to a pandas DataFrame.

    Note: VenueRecord stores derived tiers (our categorisation)
    instead of raw Google values for ToS compliance.
    """
    records = []

    for i, v in enumerate(venues):
        records.append({
            # Core identifiers
            "Rank": i + 1,  # Rank based on sorted position
            "Venue Name": v.name,
            "Address": v.address,

            # Scores (our IP)
            "Distribution Fit Score": v.distribution_fit_score,
            "Confidence": v.confidence_tier.value.title(),

            # Signal breakdown (our scores)
            "Volume Score (V)": round(v.v_score, 2),
            "Quality Score (R)": round(v.r_score, 2),
            "Relevance Score (M)": round(v.m_score, 2),

            # Derived tiers (our categorisation, NOT raw Google data)
            "Volume Tier": v.volume_tier.value.replace("_", " ").title(),
            "Quality Tier": v.quality_tier.value.replace("_", " ").title(),
            "Price Tier": v.price_tier.value.title(),

            # Venue assessment
            "Venue Type": v.venue_type.replace("_", " ").title(),
            "Premium Indicator": "Yes" if v.is_premium_indicator else "No",

            # Explanation (our content)
            "Rationale": v.rationale,

            # Location
            "City": v.city.title(),
            "Latitude": v.latitude,
            "Longitude": v.longitude,

            # Metadata
            "Place ID": v.place_id,
            "Scored At": v.last_scored_at.strftime("%Y-%m-%d %H:%M") if v.last_scored_at else "",
            "First Seen": v.first_seen_at.strftime("%Y-%m-%d") if v.first_seen_at else "",
        })

    return pd.DataFrame(records)


# =============================================================================
# CSV Export
# =============================================================================

def export_to_csv(
    venues: list[VenueRecord],
    filename: str | None = None,
    city: str = "london",
) -> Path:
    """Export venues to CSV file.

    Args:
        venues: List of venue records
        filename: Custom filename (optional)
        city: City name for default filename

    Returns:
        Path to exported file
    """
    _ensure_export_dir()

    if filename is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"{city}_venues_{timestamp}.csv"

    filepath = EXPORT_DIR / filename
    df = venues_to_dataframe(venues)
    df.to_csv(filepath, index=False)

    return filepath


# =============================================================================
# Excel Export
# =============================================================================

def export_to_excel(
    venues: list[VenueRecord],
    filename: str | None = None,
    city: str = "london",
    brand_category: str = "premium_spirits",
) -> Path:
    """Export venues to Excel file with formatting.

    Args:
        venues: List of venue records
        filename: Custom filename (optional)
        city: City name for default filename
        brand_category: Brand category for sheet naming

    Returns:
        Path to exported file
    """
    _ensure_export_dir()

    if filename is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"{city}_venues_{timestamp}.xlsx"

    filepath = EXPORT_DIR / filename
    df = venues_to_dataframe(venues)

    # Create Excel writer with formatting
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name="Ranked Venues", index=False)

        # Get workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets["Ranked Venues"]

        # Auto-adjust column widths (handles columns beyond Z)
        from openpyxl.utils import get_column_letter
        for i, column in enumerate(df.columns):
            max_length = max(
                df[column].astype(str).map(len).max(),
                len(column)
            )
            # Cap at 50 characters
            adjusted_width = min(max_length + 2, 50)
            col_letter = get_column_letter(i + 1)
            worksheet.column_dimensions[col_letter].width = adjusted_width

        # Add summary sheet with tier distributions
        summary_data = {
            "Metric": [
                "Total Venues",
                "High Confidence",
                "Medium Confidence",
                "Low Confidence",
                "Premium Indicators",
                "Average Score",
                "Top Score",
                "City",
                "Brand Category",
                "Export Date",
            ],
            "Value": [
                len(venues),
                sum(1 for v in venues if v.confidence_tier.value == "high"),
                sum(1 for v in venues if v.confidence_tier.value == "medium"),
                sum(1 for v in venues if v.confidence_tier.value == "low"),
                sum(1 for v in venues if v.is_premium_indicator),
                round(sum(v.distribution_fit_score for v in venues) / len(venues), 1) if venues else 0,
                max(v.distribution_fit_score for v in venues) if venues else 0,
                city.title(),
                brand_category.replace("_", " ").title(),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            ],
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

    return filepath


# =============================================================================
# Convenience Functions
# =============================================================================

def export_city(
    city: str,
    brand_category: str = "premium_spirits",
    limit: int = 100,
    format: str = "excel",
) -> Path:
    """Export ranked venues for a city from storage.

    Args:
        city: City to export
        brand_category: Brand category
        limit: Maximum venues to export
        format: "csv" or "excel"

    Returns:
        Path to exported file
    """
    venues = get_ranked_venues(city, brand_category, limit)

    if not venues:
        raise ValueError(f"No scored venues found for {city}")

    if format == "csv":
        return export_to_csv(venues, city=city)
    else:
        return export_to_excel(venues, city=city, brand_category=brand_category)


# =============================================================================
# Test Function
# =============================================================================

def test_export():
    """Test export with current data."""
    from venue_intel.storage import get_venue_count

    print("=" * 60)
    print("VIDPS Export Test")
    print("=" * 60)

    count = get_venue_count("london")
    print(f"\nVenues in storage: {count}")

    if count == 0:
        print("No venues in storage. Run scoring first.")
        return None

    # Export both formats
    print("\nExporting...")

    csv_path = export_city("london", format="csv")
    print(f"CSV: {csv_path}")

    excel_path = export_city("london", format="excel")
    print(f"Excel: {excel_path}")

    return excel_path


if __name__ == "__main__":
    test_export()
