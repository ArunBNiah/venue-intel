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
import pydeck as pdk
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
    page_icon="V",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# Custom Styling
# =============================================================================

st.markdown("""
<style>
    /* Confidence tier badges */
    .confidence-high {
        background-color: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .confidence-medium {
        background-color: #ffc107;
        color: black;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .confidence-low {
        background-color: #dc3545;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }

    /* Score breakdown bars */
    .score-bar {
        height: 8px;
        border-radius: 4px;
        margin: 4px 0;
    }

    /* Data freshness warning */
    .freshness-warning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
    }

    /* Professional badges */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 500;
        margin-right: 4px;
    }
    .badge-authority {
        background-color: #1a472a;
        color: #ffd700;
    }
    .badge-premium {
        background-color: #2c3e50;
        color: white;
    }
    .badge-signal {
        background-color: #e8e8e8;
        color: #333;
    }

    /* Map legend styling */
    .map-legend {
        display: flex;
        gap: 16px;
        padding: 8px 0;
        font-size: 0.85em;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)


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

    # Score version distribution
    stats["score_versions"] = pd.read_sql_query(
        "SELECT score_version, COUNT(*) as count FROM venues GROUP BY score_version ORDER BY count DESC",
        conn
    )

    # Confidence distribution
    stats["confidence_dist"] = pd.read_sql_query(
        "SELECT confidence_tier, COUNT(*) as count FROM venues GROUP BY confidence_tier",
        conn
    )

    conn.close()
    return stats


@st.cache_data(ttl=60)
def get_venues_filtered(
    city: str | None = None,
    venue_types: list[str] | None = None,  # Changed to list for multi-select
    min_score: float = 0,
    premium_only: bool = False,
    volume_tier: str | None = None,
    quality_tier: str | None = None,
    limit: int = 100,
    # Signal filters
    serves_cocktails: bool | None = None,
    serves_spirits: bool | None = None,
    has_great_cocktails: bool | None = None,
    is_upscale: bool | None = None,
    is_late_night: bool | None = None,
    # Authority filters
    on_worlds_50_best: bool | None = None,
):
    """Get filtered venues from database."""
    conn = get_connection()

    query = "SELECT * FROM venues WHERE 1=1"
    params = []

    if city and city != "All":
        query += " AND city = ?"
        params.append(city.lower())

    # Handle multiple venue types
    if venue_types and len(venue_types) > 0:
        placeholders = ",".join(["?" for _ in venue_types])
        query += f" AND venue_type IN ({placeholders})"
        params.extend(venue_types)

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

    # Signal filters
    if serves_cocktails:
        query += " AND serves_cocktails = 1"

    if serves_spirits:
        query += " AND serves_spirits = 1"

    if has_great_cocktails:
        query += " AND has_great_cocktails = 1"

    if is_upscale:
        query += " AND is_upscale = 1"

    if is_late_night:
        query += " AND is_late_night = 1"

    # Authority filters
    if on_worlds_50_best:
        query += " AND on_worlds_50_best = 1"

    query += " ORDER BY distribution_fit_score DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    return df


@st.cache_data(ttl=60)
def get_venue_types_with_counts():
    """Get all venue types with counts, sorted by frequency."""
    conn = get_connection()
    types_df = pd.read_sql_query(
        """SELECT venue_type, COUNT(*) as count
           FROM venues
           GROUP BY venue_type
           ORDER BY count DESC""",
        conn
    )
    conn.close()
    return types_df

def format_venue_type(venue_type: str) -> str:
    """Format venue_type for display: 'adult_entertainment_club' -> 'Adult Entertainment Club'"""
    return venue_type.replace("_", " ").title()

def get_venue_type_options():
    """Get venue type options formatted for display, sorted by count."""
    types_df = get_venue_types_with_counts()
    # Return list of tuples: (display_name, raw_value, count)
    options = []
    for _, row in types_df.iterrows():
        display = format_venue_type(row['venue_type'])
        options.append({
            'display': f"{display} ({row['count']:,})",
            'value': row['venue_type'],
            'count': row['count']
        })
    return options


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
# Helper Functions
# =============================================================================

def render_confidence_badge(confidence: str) -> str:
    """Render confidence tier as colored badge."""
    conf_lower = confidence.lower()
    if conf_lower == "high":
        return '<span class="confidence-high">HIGH</span>'
    elif conf_lower == "medium":
        return '<span class="confidence-medium">MEDIUM</span>'
    else:
        return '<span class="confidence-low">LOW</span>'


def render_score_bar(score: float, max_score: float = 1.0, color: str = "#4CAF50") -> str:
    """Render a score as a progress bar."""
    pct = min(100, (score / max_score) * 100)
    return f'<div class="score-bar" style="background: linear-gradient(to right, {color} {pct}%, #e0e0e0 {pct}%);"></div>'


def get_m_confidence_note(m_score: float, venue_type: str) -> str:
    """Generate a confidence note for M score based on available evidence."""
    # M score is high confidence if venue type is strongly positive
    strong_types = ["cocktail_bar", "wine_bar"]
    moderate_types = ["bar", "lounge", "pub"]

    if venue_type in strong_types:
        return "Strong evidence (venue type)"
    elif venue_type in moderate_types:
        return "Moderate evidence (venue type)"
    else:
        return "Limited evidence - interpret with caution"


def score_to_color(score: float) -> list:
    """Convert distribution fit score to RGB color.

    High scores (80+) = Green
    Medium scores (60-80) = Yellow/Orange
    Low scores (<60) = Red
    """
    if score >= 80:
        # Green
        return [39, 174, 96, 200]
    elif score >= 70:
        # Light green
        return [46, 204, 113, 200]
    elif score >= 60:
        # Yellow
        return [241, 196, 15, 200]
    elif score >= 50:
        # Orange
        return [230, 126, 34, 200]
    else:
        # Red
        return [231, 76, 60, 200]


def create_venue_map(df: pd.DataFrame, map_type: str = "markers") -> pdk.Deck:
    """Create a pydeck map with venue markers or heatmap.

    Args:
        df: DataFrame with venue data
        map_type: "markers" for scatter plot, "heatmap" for density heatmap
    """
    # Prepare map data
    map_df = df[["name", "latitude", "longitude", "distribution_fit_score", "venue_type"]].copy()
    map_df = map_df.dropna(subset=["latitude", "longitude"])

    # Calculate center point
    center_lat = map_df["latitude"].mean()
    center_lon = map_df["longitude"].mean()

    if map_type == "heatmap":
        # Heatmap layer for density visualization
        layer = pdk.Layer(
            "HeatmapLayer",
            data=map_df,
            get_position=["longitude", "latitude"],
            get_weight="distribution_fit_score",
            aggregation="SUM",
            radius_pixels=50,
            intensity=1,
            threshold=0.1,
            color_range=[
                [255, 255, 178],   # Light yellow
                [254, 204, 92],    # Yellow
                [253, 141, 60],    # Orange
                [240, 59, 32],     # Red-orange
                [189, 0, 38],      # Dark red
            ],
        )
        tooltip = None  # Heatmap doesn't support tooltips
        zoom = 10
    else:
        # Scatter plot with colored markers
        map_df["color"] = map_df["distribution_fit_score"].apply(score_to_color)

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position=["longitude", "latitude"],
            get_color="color",
            get_radius=100,
            radius_min_pixels=5,
            radius_max_pixels=15,
            pickable=True,
        )

        tooltip = {
            "html": "<b>{name}</b><br/>Score: {distribution_fit_score}<br/>Type: {venue_type}",
            "style": {
                "backgroundColor": "steelblue",
                "color": "white",
                "fontSize": "12px",
                "padding": "8px"
            }
        }
        zoom = 11

    # Create the view
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=0,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="light",
    )


# =============================================================================
# Sidebar
# =============================================================================

st.sidebar.title("Venue Intelligence")
st.sidebar.caption("Distribution Prioritisation System")

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Explore Venues", "Export Data", "Validation Export", "Request New City"],
    index=0,
)

st.sidebar.divider()

# Score version and model info
st.sidebar.subheader("Model Info")
st.sidebar.markdown("""
**Score Version:** `v1.0-historical`
**Model:** V/R/M Weighted
**Status:** Current best model
""")

st.sidebar.caption("Scores represent current model output, not absolute truth. Validate with domain expertise.")

st.sidebar.divider()

# Data freshness warning
st.sidebar.subheader("Data Freshness")
st.sidebar.warning("Historical import - refresh recommended for production use.")


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

    # Data quality callout
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Confidence Distribution")
        conf_df = stats["confidence_dist"].copy()
        conf_df["confidence_tier"] = conf_df["confidence_tier"].str.title()
        st.dataframe(conf_df, use_container_width=True, hide_index=True)
        st.caption("Confidence reflects data volume. Historical imports capped at Medium.")

    with col2:
        st.subheader("Score Versions")
        version_df = stats["score_versions"].copy()
        st.dataframe(version_df, use_container_width=True, hide_index=True)
        st.caption("All data scored with same algorithm version.")

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

    # Get venue type options (sorted by count, formatted)
    venue_type_options = get_venue_type_options()
    venue_type_display_list = [opt['display'] for opt in venue_type_options]
    venue_type_value_map = {opt['display']: opt['value'] for opt in venue_type_options}

    # Primary filters
    col1, col2 = st.columns(2)

    with col1:
        city = st.selectbox(
            "City",
            get_cities(),
            index=0,
            help="Select a city to filter venues"
        )

    with col2:
        selected_types_display = st.multiselect(
            "Venue Types",
            options=venue_type_display_list,
            default=[],
            placeholder="All venue types - click to filter",
            help="Select one or more venue types (sorted by frequency)"
        )
        # Convert display names back to raw values
        selected_venue_types = [venue_type_value_map[d] for d in selected_types_display]

    col1, col2, col3 = st.columns(3)

    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 0)

    with col2:
        premium_only = st.checkbox("Premium Only")

    with col3:
        filter_worlds_50_best = st.checkbox("World's 50 Best Only")

    # Signal filters
    with st.expander("Beverage & Venue Signals"):
        st.caption("Filter by venue attributes")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            filter_serves_cocktails = st.checkbox("Serves Cocktails")

        with col2:
            filter_serves_spirits = st.checkbox("Serves Spirits")

        with col3:
            filter_great_cocktails = st.checkbox("Great Cocktails")

        with col4:
            filter_upscale = st.checkbox("Upscale Venue")

        with col5:
            filter_late_night = st.checkbox("Late Night")

    # Advanced filters
    with st.expander("Advanced Filters"):
        col1, col2, col3 = st.columns(3)

        with col1:
            volume_tier = st.selectbox(
                "Volume Tier",
                ["All", "very_high", "high", "medium", "low", "very_low"],
                format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All Volume Tiers"
            )

        with col2:
            quality_tier = st.selectbox(
                "Quality Tier",
                ["All", "excellent", "good", "average", "below_average", "poor"],
                format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All Quality Tiers"
            )

        with col3:
            limit = st.selectbox("Max Results", [50, 100, 250, 500, 1000], index=1)

    # Get filtered data
    df = get_venues_filtered(
        city=city,
        venue_types=selected_venue_types if selected_venue_types else None,
        min_score=min_score,
        premium_only=premium_only,
        volume_tier=volume_tier if volume_tier != "All" else None,
        quality_tier=quality_tier if quality_tier != "All" else None,
        limit=limit,
        serves_cocktails=filter_serves_cocktails if filter_serves_cocktails else None,
        serves_spirits=filter_serves_spirits if filter_serves_spirits else None,
        has_great_cocktails=filter_great_cocktails if filter_great_cocktails else None,
        is_upscale=filter_upscale if filter_upscale else None,
        is_late_night=filter_late_night if filter_late_night else None,
        on_worlds_50_best=filter_worlds_50_best if filter_worlds_50_best else None,
    )

    st.caption(f"Showing {len(df)} venues")

    if len(df) > 0:
        # Format for display - include freshness
        display_df = df[[
            "name", "city", "venue_type", "distribution_fit_score",
            "volume_tier", "quality_tier", "confidence_tier",
            "is_premium_indicator", "last_scored_at"
        ]].copy()

        display_df.columns = [
            "Name", "City", "Type", "Score",
            "Volume", "Quality", "Confidence",
            "Premium", "Last Scored"
        ]

        display_df["City"] = display_df["City"].str.title()
        display_df["Type"] = display_df["Type"].str.replace("_", " ").str.title()
        display_df["Volume"] = display_df["Volume"].str.replace("_", " ").str.title()
        display_df["Quality"] = display_df["Quality"].str.replace("_", " ").str.title()
        display_df["Confidence"] = display_df["Confidence"].str.title()
        display_df["Premium"] = display_df["Premium"].map({1: "Yes", 0: ""})
        display_df["Last Scored"] = pd.to_datetime(display_df["Last Scored"]).dt.strftime("%Y-%m-%d")

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Quick stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Score", f"{df['distribution_fit_score'].mean():.1f}")
        with col2:
            st.metric("Max Score", f"{df['distribution_fit_score'].max():.1f}")
        with col3:
            st.metric("Premium Count", df["is_premium_indicator"].sum())
        with col4:
            high_conf = (df["confidence_tier"] == "medium").sum()  # Historical max is medium
            st.metric("Medium+ Confidence", high_conf)

        # Map view
        st.divider()
        st.subheader("Venue Map")

        # Map controls
        col1, col2 = st.columns([1, 4])
        with col1:
            map_type = st.radio(
                "Map Style",
                ["Markers", "Heatmap"],
                horizontal=True,
                help="Markers show individual venues, Heatmap shows density"
            )

        # Legend for markers view
        if map_type == "Markers":
            st.markdown("""
            <div class="map-legend">
                <div class="legend-item"><div class="legend-dot" style="background:#27ae60"></div> Score 80+</div>
                <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div> Score 70-79</div>
                <div class="legend-item"><div class="legend-dot" style="background:#f1c40f"></div> Score 60-69</div>
                <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div> Score 50-59</div>
                <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div> Score &lt;50</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("Heatmap intensity reflects venue density and score concentration")

        # Display map
        try:
            venue_map = create_venue_map(df, map_type="heatmap" if map_type == "Heatmap" else "markers")
            st.pydeck_chart(venue_map)
            if map_type == "Markers":
                st.caption("Hover over markers to see venue details. Scroll to zoom.")
            else:
                st.caption("Brighter areas indicate higher concentration of high-scoring venues.")
        except Exception as e:
            st.warning(f"Could not display map: {e}")
            st.info("Showing simple map instead")
            st.map(df[["latitude", "longitude"]].dropna())

        # Venue detail expander
        st.divider()
        st.subheader("Venue Score Breakdown")
        st.caption("Select a venue to see detailed scoring components")

        venue_names = df["name"].tolist()
        selected_venue = st.selectbox(
            "Select Venue",
            venue_names,
            key="venue_detail",
            placeholder="Choose a venue..."
        )

        if selected_venue:
            venue_row = df[df["name"] == selected_venue].iloc[0]

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"### {venue_row['name']}")
                st.markdown(f"**{venue_row['address']}**")
                st.markdown(f"*{venue_row['venue_type'].replace('_', ' ').title()}* · {venue_row['city'].title()}, {venue_row['country']}")

                st.divider()

                # Score breakdown
                st.markdown("#### Score Components")

                # V Score
                st.markdown(f"**V (Volume):** {venue_row['v_score']:.2f}")
                st.progress(venue_row['v_score'])
                st.caption(f"Volume tier: {venue_row['volume_tier'].replace('_', ' ').title()}")

                # R Score
                st.markdown(f"**R (Quality):** {venue_row['r_score']:.2f}")
                st.progress(venue_row['r_score'])
                st.caption(f"Quality tier: {venue_row['quality_tier'].replace('_', ' ').title()}")

                # M Score with confidence note
                st.markdown(f"**M (Relevance):** {venue_row['m_score']:.2f}")
                st.progress(venue_row['m_score'])
                m_note = get_m_confidence_note(venue_row['m_score'], venue_row['venue_type'])
                st.caption(f"Evidence: {m_note}")

            with col2:
                st.markdown("#### Summary")
                st.metric("Distribution Fit", f"{venue_row['distribution_fit_score']:.1f}/100")

                # Confidence badge
                conf = venue_row['confidence_tier'].title()
                if conf == "High":
                    st.success(f"Confidence: {conf}")
                elif conf == "Medium":
                    st.warning(f"Confidence: {conf}")
                else:
                    st.error(f"Confidence: {conf}")

                # Premium indicator
                if venue_row['is_premium_indicator']:
                    st.markdown('<span class="badge badge-premium">PREMIUM</span>', unsafe_allow_html=True)

                # World's 50 Best badge
                if venue_row.get('on_worlds_50_best') == 1:
                    rank = venue_row.get('worlds_50_best_rank')
                    if rank:
                        st.markdown(f'<span class="badge badge-authority">W50B #{rank}</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge badge-authority">W50B Listed</span>', unsafe_allow_html=True)

                # Freshness
                st.markdown("#### Data Freshness")
                st.text(f"Scored: {venue_row['last_scored_at'][:10]}")
                st.text(f"Version: {venue_row['score_version']}")

            # Rationale
            st.divider()
            st.markdown("#### Rationale")
            st.info(venue_row['rationale'])

    else:
        st.info("No venues match your filters.")


# =============================================================================
# Export Page
# =============================================================================

elif page == "Export Data":
    st.title("Export Data")

    st.write("Download venue data for your analysis.")

    # Get venue type options (sorted by count, formatted)
    export_venue_type_options = get_venue_type_options()
    export_venue_type_display_list = [opt['display'] for opt in export_venue_type_options]
    export_venue_type_value_map = {opt['display']: opt['value'] for opt in export_venue_type_options}

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        city = st.selectbox("City", get_cities(), key="export_city")

    with col2:
        export_selected_types = st.multiselect(
            "Venue Types",
            options=export_venue_type_display_list,
            default=[],
            placeholder="All venue types - click to filter",
            key="export_types"
        )
        export_venue_types = [export_venue_type_value_map[d] for d in export_selected_types]

    col1, col2, col3 = st.columns(3)

    with col1:
        min_score = st.slider("Min Score", 0, 100, 0, key="export_score")

    with col2:
        premium_only = st.checkbox("Premium Only", key="export_premium")

    with col3:
        limit = st.selectbox("Max Rows", [100, 500, 1000, 5000, "All"], key="export_limit")

    # Get data
    export_limit = 50000 if limit == "All" else limit

    df = get_venues_filtered(
        city=city,
        venue_types=export_venue_types if export_venue_types else None,
        min_score=min_score,
        premium_only=premium_only,
        limit=export_limit,
    )

    st.caption(f"{len(df)} venues match your criteria")

    if len(df) > 0:
        # Build column list (handle optional authority columns)
        base_columns = [
            "name", "city", "country", "address",
            "venue_type", "distribution_fit_score",
            "v_score", "r_score", "m_score",
            "volume_tier", "quality_tier", "price_tier",
            "confidence_tier", "is_premium_indicator",
            "serves_cocktails", "serves_spirits", "serves_wine", "serves_beer",
            "has_great_cocktails", "has_great_beer", "has_great_wine",
            "is_upscale", "is_late_night",
        ]
        base_names = [
            "Name", "City", "Country", "Address",
            "Venue Type", "Distribution Fit Score",
            "V Score", "R Score", "M Score",
            "Volume Tier", "Quality Tier", "Price Tier",
            "Confidence", "Premium",
            "Serves Cocktails", "Serves Spirits", "Serves Wine", "Serves Beer",
            "Great Cocktails", "Great Beer", "Great Wine",
            "Upscale", "Late Night",
        ]

        # Add authority columns if available
        if "on_worlds_50_best" in df.columns:
            base_columns.extend(["on_worlds_50_best", "worlds_50_best_rank", "authority_tier"])
            base_names.extend(["World's 50 Best", "W50B Rank", "Authority Tier"])

        base_columns.extend(["rationale", "place_id", "latitude", "longitude", "last_scored_at", "score_version"])
        base_names.extend(["Rationale", "Place ID", "Latitude", "Longitude", "Last Scored", "Score Version"])

        # Prepare export dataframe with full details including signals
        export_df = df[[c for c in base_columns if c in df.columns]].copy()
        export_df.columns = base_names[:len(export_df.columns)]

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
# Validation Export Page
# =============================================================================

elif page == "Validation Export":
    st.title("Validation Export")

    st.markdown("""
    Export top venues for manual validation. Use this to:
    - Review if rankings make sense
    - Identify false positives / false negatives
    - Build a "Golden Set" for sanity checks
    """)

    st.divider()

    # Validation parameters
    col1, col2, col3 = st.columns(3)

    with col1:
        val_city = st.selectbox("City", get_cities(), key="val_city")

    with col2:
        val_type = st.selectbox(
            "Venue Type",
            ["All", "Cocktail Bar", "Wine Bar", "Bar", "Pub", "Restaurant"],
            key="val_type",
            format_func=lambda x: x
        )
        # Convert display name to raw value
        val_type_raw = val_type.lower().replace(" ", "_") if val_type != "All" else None

    with col3:
        val_count = st.selectbox("Top N venues", [10, 20, 50, 100], index=1)

    # Get validation data
    val_df = get_venues_filtered(
        city=val_city if val_city != "All" else None,
        venue_types=[val_type_raw] if val_type_raw else None,
        min_score=0,
        premium_only=False,
        limit=val_count,
    )

    if len(val_df) > 0:
        st.subheader(f"Top {len(val_df)} Venues for Validation")

        # Create validation template
        val_export = val_df[[
            "name", "city", "venue_type",
            "distribution_fit_score", "v_score", "r_score", "m_score",
            "volume_tier", "quality_tier", "confidence_tier",
            "rationale", "address"
        ]].copy()

        # Add validation columns
        val_export["Human Agree (Y/N)"] = ""
        val_export["Notes"] = ""
        val_export["Suggested Rank"] = ""

        val_export.columns = [
            "Name", "City", "Type",
            "Score", "V", "R", "M",
            "Volume Tier", "Quality Tier", "Confidence",
            "Rationale", "Address",
            "Human Agree (Y/N)", "Notes", "Suggested Rank"
        ]

        # Display
        st.dataframe(val_export.head(10), use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("### Validation Instructions")
        st.markdown("""
        1. Download the Excel file
        2. For each venue, fill in:
           - **Human Agree (Y/N)**: Does this ranking make sense?
           - **Notes**: Why disagree? What's missing?
           - **Suggested Rank**: Where should this venue be?
        3. Focus on obvious errors first
        4. Save findings for model tuning
        """)

        # Download
        from io import BytesIO
        buffer = BytesIO()
        val_export.to_excel(buffer, index=False, sheet_name="Validation")

        st.download_button(
            label="Download Validation Template",
            data=buffer.getvalue(),
            file_name=f"validation_{val_city}_{val_type}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.caption("Template includes columns for human feedback.")
    else:
        st.info("No venues match your criteria.")


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
