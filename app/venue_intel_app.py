"""
Venue Intelligence MVP - Streamlit App

A simple interface for exploring and exporting venue data.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
import pandas as pd
from datetime import datetime

from venue_intel.storage import (
    get_connection,
    get_all_cities,
    get_venue_count,
    get_city_summary,
)
from venue_intel.models import VolumeTier, QualityTier, PriceTier


# =============================================================================
# Page Config
# =============================================================================

st.set_page_config(
    page_title="Venue Intelligence",
    page_icon="🍸",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# Database Queries
# =============================================================================

@st.cache_data(ttl=60)
def get_database_stats():
    """Get overall database statistics."""
    conn = get_connection()

    stats = {}

    # Total venues
    stats["total_venues"] = conn.execute(
        "SELECT COUNT(*) FROM venues"
    ).fetchone()[0]

    # By country
    stats["by_country"] = pd.read_sql_query(
        "SELECT country, COUNT(*) as venues FROM venues GROUP BY country ORDER BY venues DESC",
        conn
    )

    # By city
    stats["by_city"] = pd.read_sql_query(
        "SELECT city, country, COUNT(*) as venues FROM venues GROUP BY city, country ORDER BY venues DESC",
        conn
    )

    # Premium venues
    stats["premium_count"] = conn.execute(
        "SELECT COUNT(*) FROM venues WHERE is_premium_indicator = 1"
    ).fetchone()[0]

    # Top venue types
    stats["top_types"] = pd.read_sql_query(
        "SELECT venue_type, COUNT(*) as count FROM venues GROUP BY venue_type ORDER BY count DESC LIMIT 10",
        conn
    )

    conn.close()
    return stats


@st.cache_data(ttl=60)
def get_venues_filtered(
    city: str | None = None,
    venue_type: str | None = None,
    min_score: float = 0,
    premium_only: bool = False,
    volume_tier: str | None = None,
    quality_tier: str | None = None,
    limit: int = 100,
):
    """Get filtered venues from database."""
    conn = get_connection()

    query = "SELECT * FROM venues WHERE 1=1"
    params = []

    if city and city != "All":
        query += " AND city = ?"
        params.append(city.lower())

    if venue_type and venue_type != "All":
        query += " AND venue_type = ?"
        params.append(venue_type)

    if min_score > 0:
        query += " AND distribution_fit_score >= ?"
        params.append(min_score)

    if premium_only:
        query += " AND is_premium_indicator = 1"

    if volume_tier and volume_tier != "All":
        query += " AND volume_tier = ?"
        params.append(volume_tier)

    if quality_tier and quality_tier != "All":
        query += " AND quality_tier = ?"
        params.append(quality_tier)

    query += " ORDER BY distribution_fit_score DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    return df


@st.cache_data(ttl=60)
def get_venue_types():
    """Get all venue types in database."""
    conn = get_connection()
    types = pd.read_sql_query(
        "SELECT DISTINCT venue_type FROM venues ORDER BY venue_type",
        conn
    )
    conn.close()
    return ["All"] + types["venue_type"].tolist()


@st.cache_data(ttl=60)
def get_cities():
    """Get all cities in database."""
    conn = get_connection()
    cities = pd.read_sql_query(
        "SELECT DISTINCT city FROM venues ORDER BY city",
        conn
    )
    conn.close()
    return ["All"] + [c.title() for c in cities["city"].tolist()]


# =============================================================================
# Sidebar
# =============================================================================

st.sidebar.title("Venue Intelligence")
st.sidebar.caption("Distribution Prioritisation System")

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Explore Venues", "Export Data", "Request New City"],
    index=0,
)

st.sidebar.divider()
st.sidebar.caption("v1.0-historical")
st.sidebar.caption("Data may require refresh")


# =============================================================================
# Overview Page
# =============================================================================

if page == "Overview":
    st.title("Database Overview")

    stats = get_database_stats()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Venues", f"{stats['total_venues']:,}")

    with col2:
        st.metric("Cities", len(stats["by_city"]))

    with col3:
        st.metric("Countries", len(stats["by_country"]))

    with col4:
        st.metric("Premium Venues", f"{stats['premium_count']:,}")

    st.divider()

    # By city
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Venues by City")
        city_df = stats["by_city"].copy()
        city_df["city"] = city_df["city"].str.title()
        st.dataframe(city_df, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Top Venue Types")
        types_df = stats["top_types"].copy()
        types_df["venue_type"] = types_df["venue_type"].str.replace("_", " ").str.title()
        st.dataframe(types_df, use_container_width=True, hide_index=True)

    # Chart
    st.subheader("Venue Distribution")
    chart_df = stats["by_city"].copy()
    chart_df["city"] = chart_df["city"].str.title()
    st.bar_chart(chart_df.set_index("city")["venues"])


# =============================================================================
# Explore Page
# =============================================================================

elif page == "Explore Venues":
    st.title("Explore Venues")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        city = st.selectbox("City", get_cities())

    with col2:
        venue_type = st.selectbox("Venue Type", get_venue_types())

    with col3:
        min_score = st.slider("Min Score", 0, 100, 0)

    with col4:
        premium_only = st.checkbox("Premium Only")

    # Advanced filters
    with st.expander("Advanced Filters"):
        col1, col2, col3 = st.columns(3)

        with col1:
            volume_tier = st.selectbox(
                "Volume Tier",
                ["All", "very_high", "high", "medium", "low", "very_low"]
            )

        with col2:
            quality_tier = st.selectbox(
                "Quality Tier",
                ["All", "excellent", "good", "average", "below_average", "poor"]
            )

        with col3:
            limit = st.selectbox("Max Results", [50, 100, 250, 500, 1000], index=1)

    # Get filtered data
    df = get_venues_filtered(
        city=city,
        venue_type=venue_type,
        min_score=min_score,
        premium_only=premium_only,
        volume_tier=volume_tier if 'volume_tier' in dir() else None,
        quality_tier=quality_tier if 'quality_tier' in dir() else None,
        limit=limit if 'limit' in dir() else 100,
    )

    st.caption(f"Showing {len(df)} venues")

    if len(df) > 0:
        # Format for display
        display_df = df[[
            "name", "city", "venue_type", "distribution_fit_score",
            "volume_tier", "quality_tier", "confidence_tier",
            "is_premium_indicator", "address"
        ]].copy()

        display_df.columns = [
            "Name", "City", "Type", "Score",
            "Volume", "Quality", "Confidence",
            "Premium", "Address"
        ]

        display_df["City"] = display_df["City"].str.title()
        display_df["Type"] = display_df["Type"].str.replace("_", " ").str.title()
        display_df["Volume"] = display_df["Volume"].str.replace("_", " ").str.title()
        display_df["Quality"] = display_df["Quality"].str.replace("_", " ").str.title()
        display_df["Confidence"] = display_df["Confidence"].str.title()
        display_df["Premium"] = display_df["Premium"].map({1: "Yes", 0: "No"})

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Quick stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg Score", f"{df['distribution_fit_score'].mean():.1f}")
        with col2:
            st.metric("Max Score", f"{df['distribution_fit_score'].max():.1f}")
        with col3:
            st.metric("Premium Count", df["is_premium_indicator"].sum())
    else:
        st.info("No venues match your filters.")


# =============================================================================
# Export Page
# =============================================================================

elif page == "Export Data":
    st.title("Export Data")

    st.write("Download venue data for your analysis.")

    # Filters (same as explore)
    col1, col2, col3 = st.columns(3)

    with col1:
        city = st.selectbox("City", get_cities(), key="export_city")

    with col2:
        venue_type = st.selectbox("Venue Type", get_venue_types(), key="export_type")

    with col3:
        min_score = st.slider("Min Score", 0, 100, 0, key="export_score")

    col1, col2 = st.columns(2)

    with col1:
        premium_only = st.checkbox("Premium Only", key="export_premium")

    with col2:
        limit = st.selectbox("Max Rows", [100, 500, 1000, 5000, "All"], key="export_limit")

    # Get data
    export_limit = 50000 if limit == "All" else limit

    df = get_venues_filtered(
        city=city,
        venue_type=venue_type,
        min_score=min_score,
        premium_only=premium_only,
        limit=export_limit,
    )

    st.caption(f"{len(df)} venues match your criteria")

    if len(df) > 0:
        # Prepare export dataframe
        export_df = df[[
            "name", "city", "country", "address",
            "venue_type", "distribution_fit_score",
            "v_score", "r_score", "m_score",
            "volume_tier", "quality_tier", "price_tier",
            "confidence_tier", "is_premium_indicator",
            "rationale", "place_id",
            "latitude", "longitude"
        ]].copy()

        export_df.columns = [
            "Name", "City", "Country", "Address",
            "Venue Type", "Distribution Fit Score",
            "V Score", "R Score", "M Score",
            "Volume Tier", "Quality Tier", "Price Tier",
            "Confidence", "Premium",
            "Rationale", "Place ID",
            "Latitude", "Longitude"
        ]

        # Preview
        st.subheader("Preview")
        st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)

        # Download buttons
        col1, col2 = st.columns(2)

        with col1:
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"venue_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

        with col2:
            # Excel export
            from io import BytesIO
            buffer = BytesIO()
            export_df.to_excel(buffer, index=False, sheet_name="Venues")

            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name=f"venue_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# =============================================================================
# Request New City Page
# =============================================================================

elif page == "Request New City":
    st.title("Request New City")

    st.write("""
    Don't see the city you need? Request data for a new city.

    We'll fetch venue data from Google Places API and score it using our algorithm.
    """)

    # City input
    new_city = st.text_input("City Name", placeholder="e.g., New York, Amsterdam, Tokyo")
    country = st.selectbox("Country", ["USA", "UK", "France", "Germany", "Netherlands", "Japan", "Other"])

    # Estimate
    if new_city:
        st.subheader("Cost Estimate")

        # Rough estimates based on city size
        city_estimates = {
            "small": (500, 1000),
            "medium": (1000, 3000),
            "large": (3000, 8000),
        }

        city_size = st.radio(
            "Estimated city size",
            ["Small (< 1M pop)", "Medium (1-5M pop)", "Large (> 5M pop)"],
            horizontal=True,
        )

        if "Small" in city_size:
            est_venues = city_estimates["small"]
        elif "Medium" in city_size:
            est_venues = city_estimates["medium"]
        else:
            est_venues = city_estimates["large"]

        # Cost calculation
        discovery_cost = (est_venues[1] / 1000) * 32  # $32 per 1k discovery
        details_cost = (est_venues[1] / 1000) * 20    # $20 per 1k details
        total_cost = discovery_cost + details_cost

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Est. Venues", f"{est_venues[0]:,} - {est_venues[1]:,}")

        with col2:
            st.metric("Est. Cost", f"${total_cost:.2f}")

        with col3:
            st.metric("Time", "2-5 minutes")

        st.warning(f"""
        **Budget Check:** This would cost approximately ${total_cost:.2f}.

        Current project budget remaining: ~$49
        """)

        st.divider()

        # Request button (disabled for now)
        if st.button("Request City Data", disabled=True):
            st.info("City requests are currently disabled. Contact admin to enable.")

        st.caption("City requests are currently disabled to manage API costs.")

    # Show existing cities
    st.divider()
    st.subheader("Currently Available Cities")

    cities_df = get_database_stats()["by_city"]
    cities_df["city"] = cities_df["city"].str.title()
    st.dataframe(cities_df, use_container_width=True, hide_index=True)
