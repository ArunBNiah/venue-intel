"""
Venue Intelligence MVP - Streamlit App

A simple interface for exploring and exporting venue data.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import pydeck as pdk
import yaml
from yaml.loader import SafeLoader
from datetime import datetime
from io import BytesIO

from venue_intel.storage import (
    get_connection,
    get_all_cities,
    get_venue_count,
    get_city_summary,
    get_venues_by_profile,
    get_available_profiles,
    BRAND_PROFILES,
)
from venue_intel.models import VolumeTier, QualityTier, PriceTier
from venue_intel.lookalike import find_lookalikes, AccountInput


# =============================================================================
# Page Config - Dark Mode
# =============================================================================

st.set_page_config(
    page_title="Venue Intelligence",
    page_icon="V",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================================================================
# Custom Dark Mode Styling
# =============================================================================

ACCENT_COLOR = "#FF520E"
ACCENT_LIGHT = "#FF7A45"
BG_DARK = "#0E1117"
BG_CARD = "#1A1D24"
BG_ELEVATED = "#262A33"
TEXT_PRIMARY = "#FAFAFA"
TEXT_SECONDARY = "#A0A0A0"
BORDER_COLOR = "#333842"

st.markdown(f"""
<style>
    /* Dark mode base */
    .stApp {{
        background-color: {BG_DARK};
    }}

    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background-color: {BG_CARD};
        border-right: 1px solid {BORDER_COLOR};
    }}

    [data-testid="stSidebar"] .stMarkdown {{
        color: {TEXT_PRIMARY};
    }}

    /* Headers */
    h1, h2, h3, h4, h5, h6 {{
        color: {TEXT_PRIMARY} !important;
    }}

    /* Accent color for key elements */
    .stButton > button[kind="primary"] {{
        background-color: {ACCENT_COLOR};
        border-color: {ACCENT_COLOR};
        color: white;
    }}

    .stButton > button[kind="primary"]:hover {{
        background-color: {ACCENT_LIGHT};
        border-color: {ACCENT_LIGHT};
    }}

    /* Metrics styling */
    [data-testid="stMetricValue"] {{
        color: {ACCENT_COLOR};
    }}

    [data-testid="stMetricLabel"] {{
        color: {TEXT_SECONDARY};
    }}

    /* Cards and containers */
    .metric-card {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 20px;
        margin: 8px 0;
    }}

    .metric-value {{
        font-size: 2.5rem;
        font-weight: 700;
        color: {ACCENT_COLOR};
        margin: 0;
    }}

    .metric-label {{
        font-size: 0.9rem;
        color: {TEXT_SECONDARY};
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* Home page cards */
    .feature-card {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 12px;
        padding: 24px;
        margin: 12px 0;
        transition: border-color 0.2s;
    }}

    .feature-card:hover {{
        border-color: {ACCENT_COLOR};
    }}

    .feature-title {{
        color: {ACCENT_COLOR};
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 8px;
    }}

    .feature-description {{
        color: {TEXT_SECONDARY};
        font-size: 0.95rem;
        line-height: 1.5;
    }}

    /* Confidence tier badges */
    .confidence-high {{
        background-color: #1B4D3E;
        color: #4ADE80;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 500;
    }}
    .confidence-medium {{
        background-color: #4A3728;
        color: #FBBF24;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 500;
    }}
    .confidence-low {{
        background-color: #4A2828;
        color: #F87171;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 500;
    }}

    /* Professional badges */
    .badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 500;
        margin-right: 6px;
    }}
    .badge-authority {{
        background-color: #2D1F0E;
        color: #FFD700;
        border: 1px solid #5C4A1E;
    }}
    .badge-premium {{
        background-color: {ACCENT_COLOR}22;
        color: {ACCENT_COLOR};
        border: 1px solid {ACCENT_COLOR}44;
    }}

    /* Map legend styling */
    .map-legend {{
        display: flex;
        gap: 16px;
        padding: 12px 0;
        font-size: 0.85em;
        color: {TEXT_SECONDARY};
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .legend-dot {{
        width: 12px;
        height: 12px;
        border-radius: 50%;
    }}

    /* Divider styling */
    hr {{
        border-color: {BORDER_COLOR};
    }}

    /* Table styling */
    .stDataFrame {{
        background-color: {BG_CARD};
    }}

    /* Export section */
    .export-section {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 20px;
        margin-top: 20px;
    }}

    .export-title {{
        color: {ACCENT_COLOR};
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 12px;
    }}

    /* Info boxes */
    .stAlert {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
    }}

    /* Welcome hero */
    .hero {{
        background: linear-gradient(135deg, {BG_CARD} 0%, {BG_ELEVATED} 100%);
        border: 1px solid {BORDER_COLOR};
        border-radius: 16px;
        padding: 40px;
        margin-bottom: 30px;
        text-align: center;
    }}

    .hero-title {{
        font-size: 2.5rem;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin-bottom: 12px;
    }}

    .hero-accent {{
        color: {ACCENT_COLOR};
    }}

    .hero-subtitle {{
        font-size: 1.2rem;
        color: {TEXT_SECONDARY};
        max-width: 600px;
        margin: 0 auto;
    }}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Authentication
# =============================================================================

def load_auth_config():
    """Load auth config from Streamlit secrets or local YAML file."""
    # Try Streamlit secrets first (for cloud deployment)
    if hasattr(st, 'secrets') and 'credentials' in st.secrets:
        # Convert from Streamlit secrets format to dict
        config = {
            'credentials': {
                'usernames': dict(st.secrets['credentials']['usernames'])
            },
            'cookie': dict(st.secrets['cookie']),
            'preauthorized': dict(st.secrets.get('preauthorized', {'emails': []}))
        }
        # Convert nested user data
        for username in config['credentials']['usernames']:
            config['credentials']['usernames'][username] = dict(
                st.secrets['credentials']['usernames'][username]
            )
        return config

    # Fall back to local YAML file (for local development)
    auth_path = Path(__file__).parent.parent / "config" / "auth.yaml"
    if auth_path.exists():
        with open(auth_path) as file:
            return yaml.load(file, Loader=SafeLoader)

    return None

auth_config = load_auth_config()

if auth_config:
    authenticator = stauth.Authenticate(
        auth_config['credentials'],
        auth_config['cookie']['name'],
        auth_config['cookie']['key'],
        auth_config['cookie']['expiry_days'],
        auth_config.get('preauthorized', {})
    )

    # Login widget
    name, authentication_status, username = authenticator.login('main')

    if authentication_status == False:
        st.error('Username/password is incorrect')
        st.stop()
    elif authentication_status == None:
        # Show login page with branding
        st.markdown(f"""
        <div style="text-align: center; padding: 60px 20px;">
            <div style="font-size: 3rem; font-weight: 700; margin-bottom: 10px;">
                <span style="color: {TEXT_PRIMARY};">Venue</span>
                <span style="color: {ACCENT_COLOR};">Intel</span>
            </div>
            <p style="color: {TEXT_SECONDARY}; font-size: 1.1rem; margin-bottom: 40px;">
                Distribution Intelligence Platform
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.info('Please enter your username and password')
        st.stop()

    # User is authenticated - show logout in sidebar later
    user_role = auth_config['credentials']['usernames'].get(username, {}).get('role', 'viewer')
else:
    # No auth config - allow access (for development)
    authentication_status = True
    name = "Developer"
    username = "dev"
    user_role = "admin"
    authenticator = None


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

    # Authority sources
    stats["authority_count"] = conn.execute(
        "SELECT COUNT(*) FROM venues WHERE on_worlds_50_best = 1 OR on_asias_50_best = 1 OR on_north_americas_50_best = 1"
    ).fetchone()[0]

    conn.close()
    return stats


@st.cache_data(ttl=60)
def get_venues_filtered(
    city: str | None = None,
    venue_types: list[str] | None = None,
    min_score: float = 0,
    premium_only: bool = False,
    volume_tier: str | None = None,
    quality_tier: str | None = None,
    limit: int = 100,
    serves_cocktails: bool | None = None,
    serves_spirits: bool | None = None,
    has_great_cocktails: bool | None = None,
    is_upscale: bool | None = None,
    is_late_night: bool | None = None,
    on_any_authority_list: bool | None = None,
):
    """Get filtered venues from database."""
    conn = get_connection()

    query = "SELECT * FROM venues WHERE 1=1"
    params = []

    if city and city != "All":
        query += " AND city = ?"
        params.append(city.lower())

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

    if on_any_authority_list:
        query += " AND (on_worlds_50_best = 1 OR on_asias_50_best = 1 OR on_north_americas_50_best = 1)"

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
    """Format venue_type for display."""
    return venue_type.replace("_", " ").title()


def get_venue_type_options():
    """Get venue type options formatted for display."""
    types_df = get_venue_types_with_counts()
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

def score_to_color(score: float) -> list:
    """Convert distribution fit score to RGB color."""
    if score >= 80:
        return [39, 174, 96, 200]
    elif score >= 70:
        return [46, 204, 113, 200]
    elif score >= 60:
        return [241, 196, 15, 200]
    elif score >= 50:
        return [230, 126, 34, 200]
    else:
        return [231, 76, 60, 200]


def create_venue_map(df: pd.DataFrame, map_type: str = "markers") -> pdk.Deck:
    """Create a pydeck map with venue markers or heatmap."""
    map_df = df[["name", "latitude", "longitude", "distribution_fit_score", "venue_type"]].copy()
    map_df = map_df.dropna(subset=["latitude", "longitude"])

    center_lat = map_df["latitude"].mean()
    center_lon = map_df["longitude"].mean()

    if map_type == "heatmap":
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
                [255, 255, 178],
                [254, 204, 92],
                [253, 141, 60],
                [240, 59, 32],
                [189, 0, 38],
            ],
        )
        tooltip = None
        zoom = 10
    else:
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
                "backgroundColor": "#1A1D24",
                "color": "#FAFAFA",
                "fontSize": "12px",
                "padding": "8px",
                "border": "1px solid #333842"
            }
        }
        zoom = 11

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
        map_style="mapbox://styles/mapbox/dark-v10",
    )


def get_m_confidence_note(m_score: float, venue_type: str) -> str:
    """Generate a confidence note for M score."""
    strong_types = ["cocktail_bar", "wine_bar"]
    moderate_types = ["bar", "lounge", "pub"]

    if venue_type in strong_types:
        return "Strong evidence (venue type)"
    elif venue_type in moderate_types:
        return "Moderate evidence (venue type)"
    else:
        return "Limited evidence - interpret with caution"


# =============================================================================
# Check for Admin Mode
# =============================================================================

# Admin mode if user role is admin OR query param is set
admin_mode = user_role == "admin" or st.query_params.get("admin", "false").lower() == "true"


# =============================================================================
# Sidebar Navigation
# =============================================================================

st.sidebar.markdown(f"""
<div style="padding: 10px 0 20px 0;">
    <span style="font-size: 1.8rem; font-weight: 700; color: {TEXT_PRIMARY};">Venue</span>
    <span style="font-size: 1.8rem; font-weight: 700; color: {ACCENT_COLOR};">Intel</span>
</div>
""", unsafe_allow_html=True)

# User info and logout
st.sidebar.markdown(f"""
<div style="background-color: {BG_ELEVATED}; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
    <div style="color: {TEXT_SECONDARY}; font-size: 0.8rem; margin-bottom: 4px;">Logged in as</div>
    <div style="color: {TEXT_PRIMARY}; font-weight: 600;">{name}</div>
</div>
""", unsafe_allow_html=True)

if authenticator:
    authenticator.logout('Logout', 'sidebar')

st.sidebar.divider()

# Build navigation options
nav_options = ["Home", "Explore", "Expansion Planner", "Request City"]
if admin_mode:
    nav_options.append("Validation (Admin)")

# Initialize session state for navigation
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# Get default index from session state
default_index = nav_options.index(st.session_state.current_page) if st.session_state.current_page in nav_options else 0

page = st.sidebar.radio(
    "Navigate",
    nav_options,
    index=default_index,
    key="nav_radio",
    label_visibility="collapsed",
)

# Update session state when radio changes
st.session_state.current_page = page

st.sidebar.divider()

# Model info
st.sidebar.markdown(f"""
<div style="color: {TEXT_SECONDARY}; font-size: 0.85rem;">
    <div style="margin-bottom: 8px;"><strong style="color: {TEXT_PRIMARY};">Model</strong></div>
    <div>Version: v1.0-historical</div>
    <div>Type: V/R/M Weighted</div>
</div>
""", unsafe_allow_html=True)

if admin_mode:
    st.sidebar.markdown(f"""
    <div style="background-color: {ACCENT_COLOR}22; border: 1px solid {ACCENT_COLOR}44;
                border-radius: 4px; padding: 8px; margin-top: 16px; text-align: center;">
        <span style="color: {ACCENT_COLOR}; font-weight: 600;">ADMIN MODE</span>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# HOME PAGE
# =============================================================================

if page == "Home":
    # Hero section
    st.markdown(f"""
    <div class="hero">
        <div class="hero-title">
            Welcome to <span class="hero-accent">Venue Intelligence</span>
        </div>
        <div class="hero-subtitle">
            Prioritise your distribution with data-driven venue rankings.
            Find the right accounts, in the right markets, for your brand.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick stats
    stats = get_database_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{stats['total_venues']:,}</p>
            <p class="metric-label">Venues</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{len(stats['by_city'])}</p>
            <p class="metric-label">Cities</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{len(stats['by_country'])}</p>
            <p class="metric-label">Countries</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{stats['authority_count']}</p>
            <p class="metric-label">50 Best Bars</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature cards
    st.markdown(f"### What would you like to do?")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div class="feature-card">
            <div class="feature-title">Explore & Export Venues</div>
            <div class="feature-description">
                Browse our database of scored venues. Filter by city, venue type,
                brand profile, and quality signals. See why each venue ranks where
                it does, then export your target list.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Explore", type="primary", use_container_width=True):
            st.session_state.current_page = "Explore"
            st.rerun()

    with col2:
        st.markdown(f"""
        <div class="feature-card">
            <div class="feature-title">Expansion Planner</div>
            <div class="feature-description">
                Already winning in one market? Upload your top accounts and we'll
                find similar venues in a new market. Transfer your success pattern
                without starting from scratch.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Expansion Planner", type="primary", use_container_width=True):
            st.session_state.current_page = "Expansion Planner"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Coverage breakdown
    with st.expander("View Coverage by City"):
        city_df = stats["by_city"].copy()
        city_df["city"] = city_df["city"].str.title()
        city_df["country"] = city_df["country"].str.upper()
        city_df.columns = ["City", "Country", "Venues"]
        st.dataframe(city_df, use_container_width=True, hide_index=True)


# =============================================================================
# EXPLORE PAGE (Combined Overview + Explore + Export)
# =============================================================================

elif page == "Explore":
    st.title("Explore Venues")

    # Top-line metrics
    stats = get_database_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Venues", f"{stats['total_venues']:,}")
    with col2:
        st.metric("Cities", len(stats["by_city"]))
    with col3:
        st.metric("Countries", len(stats["by_country"]))
    with col4:
        st.metric("50 Best Bars", stats["authority_count"])

    # Coverage breakdown (collapsible)
    with st.expander("Coverage by City"):
        city_df = stats["by_city"].copy()
        city_df["city"] = city_df["city"].str.title()
        st.dataframe(city_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Filters Section ---
    venue_type_options = get_venue_type_options()
    venue_type_display_list = [opt['display'] for opt in venue_type_options]
    venue_type_value_map = {opt['display']: opt['value'] for opt in venue_type_options}

    profile_options = list(get_available_profiles().keys())
    profile_labels = {k: v for k, v in get_available_profiles().items()}

    col1, col2, col3 = st.columns(3)

    with col1:
        city = st.selectbox(
            "City",
            get_cities(),
            index=0,
            help="Select a city to filter venues"
        )

    with col2:
        brand_profile = st.selectbox(
            "Brand Profile",
            options=profile_options,
            index=0,
            format_func=lambda x: x.replace("_", " ").title(),
            help="Different profiles re-rank venues for your brand"
        )

    with col3:
        selected_types_display = st.multiselect(
            "Venue Types",
            options=venue_type_display_list,
            default=[],
            placeholder="All types",
            help="Filter by venue type"
        )
        selected_venue_types = [venue_type_value_map[d] for d in selected_types_display]

    st.caption(f"**{brand_profile.replace('_', ' ').title()}:** {profile_labels[brand_profile]}")

    col1, col2, col3 = st.columns(3)

    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 0)

    with col2:
        premium_only = st.checkbox("Premium Only")

    with col3:
        filter_authority_bars = st.checkbox("50 Best Bars Only")

    # Signal filters
    with st.expander("Beverage & Venue Signals"):
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
    if brand_profile != "premium_spirits":
        profile_data = get_venues_by_profile(
            city=city if city != "All" else "london",
            profile=brand_profile,
            limit=2000,
        )
        df = pd.DataFrame(profile_data)

        if selected_venue_types:
            df = df[df["venue_type"].isin(selected_venue_types)]
        if min_score > 0:
            df = df[df["distribution_fit_score"] >= min_score]
        if premium_only:
            df = df[df.get("is_premium_indicator", False) == True]
        if volume_tier != "All":
            df = df[df["volume_tier"] == volume_tier]
        if quality_tier != "All":
            df = df[df["quality_tier"] == quality_tier]

        df = df.head(limit)
    else:
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
            on_any_authority_list=filter_authority_bars if filter_authority_bars else None,
        )

    st.divider()

    # --- Results Section ---
    if len(df) > 0:
        st.subheader(f"Results ({len(df)} venues)")

        # Format for display
        base_cols = ["name", "city", "venue_type", "distribution_fit_score",
                     "volume_tier", "quality_tier", "confidence_tier"]
        base_names = ["Name", "City", "Type", "Score", "Volume", "Quality", "Confidence"]

        if "is_premium_indicator" in df.columns:
            base_cols.append("is_premium_indicator")
            base_names.append("Premium")

        display_df = df[[c for c in base_cols if c in df.columns]].copy()
        display_df.columns = base_names[:len(display_df.columns)]

        display_df["City"] = display_df["City"].str.title()
        display_df["Type"] = display_df["Type"].str.replace("_", " ").str.title()
        display_df["Volume"] = display_df["Volume"].str.replace("_", " ").str.title()
        display_df["Quality"] = display_df["Quality"].str.replace("_", " ").str.title()
        display_df["Confidence"] = display_df["Confidence"].str.title()
        if "Premium" in display_df.columns:
            display_df["Premium"] = display_df["Premium"].map({1: "Yes", 0: "", True: "Yes", False: ""})

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Quick stats row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Score", f"{df['distribution_fit_score'].mean():.1f}")
        with col2:
            st.metric("Max Score", f"{df['distribution_fit_score'].max():.1f}")
        with col3:
            st.metric("Premium", df["is_premium_indicator"].sum())
        with col4:
            high_conf = (df["confidence_tier"] == "medium").sum()
            st.metric("Medium+ Confidence", high_conf)

        # --- Export Section (immediately after results) ---
        st.markdown(f"""
        <div class="export-section">
            <div class="export-title">Export Your Selection</div>
        </div>
        """, unsafe_allow_html=True)

        # Build export dataframe
        export_columns = [
            "name", "city", "country", "address",
            "venue_type", "distribution_fit_score",
            "v_score", "r_score", "m_score",
            "volume_tier", "quality_tier", "price_tier",
            "confidence_tier", "is_premium_indicator",
            "serves_cocktails", "serves_spirits", "serves_wine", "serves_beer",
            "has_great_cocktails", "has_great_beer", "has_great_wine",
            "is_upscale", "is_late_night",
        ]
        export_names = [
            "Name", "City", "Country", "Address",
            "Venue Type", "Distribution Fit Score",
            "V (Volume)", "R (Rating)", "M (Match)",
            "Volume Tier", "Quality Tier", "Price Tier",
            "Confidence", "Premium",
            "Serves Cocktails", "Serves Spirits", "Serves Wine", "Serves Beer",
            "Great Cocktails", "Great Beer", "Great Wine",
            "Upscale", "Late Night",
        ]

        if "on_worlds_50_best" in df.columns:
            export_columns.extend([
                "on_worlds_50_best", "worlds_50_best_rank",
                "on_asias_50_best", "asias_50_best_rank",
                "on_north_americas_50_best", "north_americas_50_best_rank",
            ])
            export_names.extend([
                "World's 50 Best", "W50B Rank",
                "Asia's 50 Best", "A50B Rank",
                "NA's 50 Best", "NA50B Rank",
            ])

        export_columns.extend(["rationale", "place_id", "latitude", "longitude"])
        export_names.extend(["Rationale", "Place ID", "Latitude", "Longitude"])

        export_df = df[[c for c in export_columns if c in df.columns]].copy()
        export_df.columns = export_names[:len(export_df.columns)]

        st.caption(f"Export includes {len(export_df)} venues with all scores, signals, and metadata.")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"venue_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )

        with col2:
            buffer = BytesIO()
            export_df.to_excel(buffer, index=False, sheet_name="Venues")
            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name=f"venue_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # Map view
        st.divider()
        st.subheader("Map")

        col1, col2 = st.columns([1, 4])
        with col1:
            map_type = st.radio(
                "Style",
                ["Markers", "Heatmap"],
                horizontal=True,
            )

        if map_type == "Markers":
            st.markdown("""
            <div class="map-legend">
                <div class="legend-item"><div class="legend-dot" style="background:#27ae60"></div> 80+</div>
                <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div> 70-79</div>
                <div class="legend-item"><div class="legend-dot" style="background:#f1c40f"></div> 60-69</div>
                <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div> 50-59</div>
                <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div> &lt;50</div>
            </div>
            """, unsafe_allow_html=True)

        try:
            venue_map = create_venue_map(df, map_type="heatmap" if map_type == "Heatmap" else "markers")

            if map_type == "Markers":
                map_event = st.pydeck_chart(
                    venue_map,
                    use_container_width=True,
                    selection_mode="single-object",
                    on_select="rerun",
                    key="venue_map"
                )

                if map_event and map_event.selection:
                    objects = map_event.selection.get("objects", {})
                    if objects:
                        for layer_data in objects.values():
                            if layer_data and len(layer_data) > 0:
                                clicked_name = layer_data[0].get("name")
                                if clicked_name:
                                    st.session_state["map_selected_venue"] = clicked_name
                            break
            else:
                st.pydeck_chart(venue_map, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display map: {e}")
            st.map(df[["latitude", "longitude"]].dropna())

        # Venue detail section
        st.divider()
        st.subheader("Venue Detail")

        venue_names = df["name"].tolist()
        map_selected = st.session_state.get("map_selected_venue")
        default_index = None
        if map_selected and map_selected in venue_names:
            default_index = venue_names.index(map_selected)

        selected_venue = st.selectbox(
            "Select Venue",
            venue_names,
            index=default_index,
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

                st.markdown("#### Score Components")

                st.markdown(f"**V (Volume):** {venue_row['v_score']:.2f}")
                st.progress(venue_row['v_score'])
                st.caption(f"Volume tier: {venue_row['volume_tier'].replace('_', ' ').title()}")

                st.markdown(f"**R (Rating):** {venue_row['r_score']:.2f}")
                st.progress(venue_row['r_score'])
                st.caption(f"Quality tier: {venue_row['quality_tier'].replace('_', ' ').title()}")

                st.markdown(f"**M (Match):** {venue_row['m_score']:.2f}")
                st.progress(venue_row['m_score'])
                m_note = get_m_confidence_note(venue_row['m_score'], venue_row['venue_type'])
                st.caption(f"Brand profile: Premium Spirits | {m_note}")

            with col2:
                st.markdown("#### Summary")
                st.metric("Distribution Fit", f"{venue_row['distribution_fit_score']:.1f}/100")

                conf = venue_row['confidence_tier'].title()
                if conf == "High":
                    st.success(f"Confidence: {conf}")
                elif conf == "Medium":
                    st.warning(f"Confidence: {conf}")
                else:
                    st.error(f"Confidence: {conf}")

                if venue_row['is_premium_indicator']:
                    st.markdown('<span class="badge badge-premium">PREMIUM</span>', unsafe_allow_html=True)

                authority_badges = []
                if venue_row.get('on_worlds_50_best') == 1:
                    rank = venue_row.get('worlds_50_best_rank')
                    authority_badges.append(f'W50B #{rank}' if rank else 'W50B')
                if venue_row.get('on_asias_50_best') == 1:
                    rank = venue_row.get('asias_50_best_rank')
                    authority_badges.append(f'A50B #{rank}' if rank else 'A50B')
                if venue_row.get('on_north_americas_50_best') == 1:
                    rank = venue_row.get('north_americas_50_best_rank')
                    authority_badges.append(f'NA50B #{rank}' if rank else 'NA50B')

                for badge in authority_badges:
                    st.markdown(f'<span class="badge badge-authority">{badge}</span>', unsafe_allow_html=True)

                st.markdown("#### Data")
                st.text(f"Scored: {venue_row['last_scored_at'][:10]}")
                st.text(f"Version: {venue_row['score_version']}")

            st.divider()
            st.markdown("#### Rationale")
            st.info(venue_row['rationale'])

    else:
        st.info("No venues match your filters. Try adjusting your criteria.")


# =============================================================================
# EXPANSION PLANNER PAGE
# =============================================================================

elif page == "Expansion Planner":
    st.title("Expansion Planner")
    st.markdown("**Find prospects in a new market similar to your best accounts**")

    st.info("""
    Upload your top-performing accounts from one market, and we'll find similar
    venues in your target market - based on venue type, price tier, quality, and
    brand relevance patterns.
    """)

    st.divider()

    # Step 1: Market Selection
    st.subheader("1. Select Markets")

    col1, col2 = st.columns(2)

    with col1:
        source_market = st.selectbox(
            "Source Market (where your accounts are)",
            [c for c in get_cities() if c != "All"],
            index=0,
            key="source_market"
        )

    with col2:
        target_options = [c for c in get_cities() if c != "All" and c.lower() != source_market.lower()]
        target_market = st.selectbox(
            "Target Market (where to find prospects)",
            target_options,
            index=0,
            key="target_market"
        )

    st.divider()

    # Step 2: Account Input
    st.subheader("2. Enter Your Top Accounts")

    input_method = st.radio(
        "How would you like to enter accounts?",
        ["Manual Entry", "CSV Upload"],
        horizontal=True
    )

    accounts_to_process = []

    if input_method == "Manual Entry":
        st.caption(f"Enter your top accounts in **{source_market}** (one per line)")

        account_text = st.text_area(
            "Account Names",
            placeholder="The Connaught Bar\nSatan's Whiskers\nTayēr + Elementary\nSwift Soho\n...",
            height=200,
            help="Enter venue names exactly as they appear. We'll match them to our database."
        )

        if account_text:
            lines = [line.strip() for line in account_text.split("\n") if line.strip()]
            accounts_to_process = [
                AccountInput(name=name, city=source_market.lower())
                for name in lines
            ]
            st.caption(f"{len(accounts_to_process)} accounts entered")

    else:
        st.caption("Upload a CSV with columns: `name` (required), `place_id` (optional)")

        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type="csv",
            help="CSV should have at least a 'name' column"
        )

        if uploaded_file:
            try:
                csv_df = pd.read_csv(uploaded_file)
                if "name" not in csv_df.columns:
                    st.error("CSV must have a 'name' column")
                else:
                    for _, row in csv_df.iterrows():
                        accounts_to_process.append(AccountInput(
                            name=row["name"],
                            city=source_market.lower(),
                            place_id=row.get("place_id"),
                            address=row.get("address"),
                        ))
                    st.success(f"Loaded {len(accounts_to_process)} accounts from CSV")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    st.divider()

    # Step 3: Run Analysis
    st.subheader("3. Find Similar Venues")

    col1, col2 = st.columns(2)

    with col1:
        result_limit = st.selectbox("Max results", [25, 50, 100, 200], index=1)

    with col2:
        min_confidence = st.selectbox(
            "Minimum confidence",
            [None, "medium", "high"],
            format_func=lambda x: "All" if x is None else x.title()
        )

    if st.button("Generate Target List", type="primary", disabled=len(accounts_to_process) < 5):
        if len(accounts_to_process) < 5:
            st.warning("Please enter at least 5 accounts to build a reliable profile")
        else:
            with st.spinner(f"Analyzing {len(accounts_to_process)} accounts and finding matches in {target_market}..."):
                result = find_lookalikes(
                    source_accounts=accounts_to_process,
                    source_market=source_market.lower(),
                    target_market=target_market.lower(),
                    limit=result_limit,
                    min_confidence=min_confidence,
                )

            if "error" in result:
                st.error(result["error"])
            else:
                st.session_state["lookalike_results"] = result

    # Display Results
    if "lookalike_results" in st.session_state:
        result = st.session_state["lookalike_results"]

        st.divider()

        res = result["resolution_report"]
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Accounts Matched", f"{res['resolved']}/{res['total_input']}")
        with col2:
            st.metric("Resolution Rate", f"{res['resolution_rate']:.0%}")
        with col3:
            if res["unmatched_details"]:
                with st.expander(f"View {len(res['unmatched_details'])} unmatched"):
                    for u in res["unmatched_details"]:
                        st.text(f"• {u['name']}")

        st.divider()

        # Success Profile
        st.subheader(f"Your {source_market} Success Profile")

        prof = result["success_profile"]

        if prof["concentration_warning"]:
            st.warning(f"⚠️ {prof['concentration_warning']} - results may be narrow")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Venue Type Mix**")
            type_df = pd.DataFrame([
                {"Type": k.replace("_", " ").title(), "Share": f"{v:.0%}"}
                for k, v in sorted(prof["type_distribution"].items(), key=lambda x: -x[1])
            ])
            st.dataframe(type_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("**Price Tier Mix**")
            price_df = pd.DataFrame([
                {"Tier": k.title(), "Share": f"{v:.0%}"}
                for k, v in sorted(prof["price_tier_distribution"].items(), key=lambda x: -x[1])
            ])
            st.dataframe(price_df, hide_index=True, use_container_width=True)

            if prof["authority_prevalence"] > 0:
                st.markdown(f"**Authority Venues:** {prof['authority_prevalence']:.0%} of accounts")

        st.divider()

        # Results Table
        st.subheader(f"Top {target_market} Prospects")
        st.caption(f"Ranked by similarity to your {source_market} success profile")

        results_data = result["results"]

        if results_data:
            display_rows = []
            for r in results_data:
                display_rows.append({
                    "Rank": r["rank"],
                    "Venue": r["name"],
                    "Type": r["venue_type"].replace("_", " ").title(),
                    "Similarity": r["similarity_score"],
                    "Confidence": r["confidence"].title(),
                    "Why Similar": ", ".join(r["matched_on"][:3]) if r["matched_on"] else "-",
                    "VIDPS Score": r["context"]["distribution_fit_score"],
                })

            results_df = pd.DataFrame(display_rows)
            st.dataframe(results_df, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("**Venue Detail**")

            venue_names = [r["name"] for r in results_data]
            selected_name = st.selectbox("Select venue for details", venue_names)

            if selected_name:
                selected = next(r for r in results_data if r["name"] == selected_name)

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"### {selected['name']}")
                    st.markdown(f"*{selected['venue_type'].replace('_', ' ').title()}* · {selected['address']}")
                    st.markdown(f"**{selected['rationale']}**")

                with col2:
                    st.metric("Similarity Score", f"{selected['similarity_score']:.0f}/100")
                    st.metric("VIDPS Score", f"{selected['context']['distribution_fit_score']:.0f}")

                st.markdown("**Score Breakdown**")
                breakdown = selected["score_breakdown"]

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Type Match", f"{breakdown['type']:.0f}/30")
                with col2:
                    st.metric("Tier Match", f"{breakdown['tiers']:.0f}/30")
                with col3:
                    st.metric("Relevance", f"{breakdown['relevance']:.0f}/30")
                with col4:
                    st.metric("Authority", f"{breakdown['authority']:.0f}/10")

            # Export
            st.divider()
            st.subheader("Export Results")

            export_df = pd.DataFrame([
                {
                    "Rank": r["rank"],
                    "Name": r["name"],
                    "Type": r["venue_type"],
                    "Address": r["address"],
                    "Similarity Score": r["similarity_score"],
                    "Confidence": r["confidence"],
                    "Matched On": "; ".join(r["matched_on"]),
                    "Rationale": r["rationale"],
                    "VIDPS Score": r["context"]["distribution_fit_score"],
                    "Price Tier": r["context"]["price_tier"],
                    "Quality Tier": r["context"]["quality_tier"],
                    "Place ID": r["place_id"],
                }
                for r in results_data
            ])

            col1, col2 = st.columns(2)

            with col1:
                csv = export_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    file_name=f"lookalike_{target_market}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    type="primary",
                )

            with col2:
                buffer = BytesIO()
                export_df.to_excel(buffer, index=False, sheet_name="Prospects")
                st.download_button(
                    "Download Excel",
                    buffer.getvalue(),
                    file_name=f"lookalike_{target_market}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        else:
            st.info("No matching venues found. Try adjusting your source accounts or confidence filter.")

    elif len(accounts_to_process) > 0 and len(accounts_to_process) < 5:
        st.warning(f"Enter at least 5 accounts (currently {len(accounts_to_process)})")


# =============================================================================
# REQUEST CITY PAGE
# =============================================================================

elif page == "Request City":
    st.title("Request New City")

    st.write("""
    Don't see the city you need? Request data for a new city.
    We'll fetch venue data from Google Places API and score it using our algorithm.
    """)

    new_city = st.text_input("City Name", placeholder="e.g., New York, Amsterdam, Tokyo")
    country = st.selectbox("Country", ["USA", "UK", "France", "Germany", "Netherlands", "Japan", "Other"])

    if new_city:
        st.subheader("Cost Estimate")

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

        discovery_cost = (est_venues[1] / 1000) * 32
        details_cost = (est_venues[1] / 1000) * 20
        total_cost = discovery_cost + details_cost

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Est. Venues", f"{est_venues[0]:,} - {est_venues[1]:,}")

        with col2:
            st.metric("Est. Cost", f"${total_cost:.2f}")

        with col3:
            st.metric("Time", "2-5 minutes")

        st.warning(f"**Budget Check:** This would cost approximately ${total_cost:.2f}.")

        st.divider()

        if st.button("Request City Data", disabled=True):
            st.info("City requests are currently disabled. Contact admin to enable.")

        st.caption("City requests are currently disabled to manage API costs.")

    st.divider()
    st.subheader("Currently Available Cities")

    cities_df = get_database_stats()["by_city"]
    cities_df["city"] = cities_df["city"].str.title()
    st.dataframe(cities_df, use_container_width=True, hide_index=True)


# =============================================================================
# VALIDATION PAGE (Admin Only)
# =============================================================================

elif page == "Validation (Admin)":
    st.title("Validation Export")
    st.caption("Admin tool for model validation")

    st.markdown("""
    Export top venues for manual validation. Use this to:
    - Review if rankings make sense
    - Identify false positives / false negatives
    - Build a "Golden Set" for sanity checks
    """)

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        val_city = st.selectbox("City", get_cities(), key="val_city")

    with col2:
        val_type = st.selectbox(
            "Venue Type",
            ["All", "Cocktail Bar", "Wine Bar", "Bar", "Pub", "Restaurant"],
            key="val_type",
        )
        val_type_raw = val_type.lower().replace(" ", "_") if val_type != "All" else None

    with col3:
        val_count = st.selectbox("Top N venues", [10, 20, 50, 100], index=1)

    val_df = get_venues_filtered(
        city=val_city if val_city != "All" else None,
        venue_types=[val_type_raw] if val_type_raw else None,
        min_score=0,
        premium_only=False,
        limit=val_count,
    )

    if len(val_df) > 0:
        st.subheader(f"Top {len(val_df)} Venues for Validation")

        val_export = val_df[[
            "name", "city", "venue_type",
            "distribution_fit_score", "v_score", "r_score", "m_score",
            "volume_tier", "quality_tier", "confidence_tier",
            "rationale", "address"
        ]].copy()

        val_export["Human Agree (Y/N)"] = ""
        val_export["Notes"] = ""
        val_export["Suggested Rank"] = ""

        val_export.columns = [
            "Name", "City", "Type",
            "Score", "V (Volume)", "R (Rating)", "M (Match)",
            "Volume Tier", "Quality Tier", "Confidence",
            "Rationale", "Address",
            "Human Agree (Y/N)", "Notes", "Suggested Rank"
        ]

        st.dataframe(val_export.head(10), use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("### Instructions")
        st.markdown("""
        1. Download the Excel file
        2. For each venue, fill in:
           - **Human Agree (Y/N)**: Does this ranking make sense?
           - **Notes**: Why disagree? What's missing?
           - **Suggested Rank**: Where should this venue be?
        3. Focus on obvious errors first
        """)

        buffer = BytesIO()
        val_export.to_excel(buffer, index=False, sheet_name="Validation")

        st.download_button(
            label="Download Validation Template",
            data=buffer.getvalue(),
            file_name=f"validation_{val_city}_{val_type}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.info("No venues match your criteria.")
