"""Google Places API client for venue discovery and details.

This module implements the 3-stage fetch strategy:
- Stage 1: Discovery (Text Search) - find candidate venues
- Stage 2: Scoring (Place Details Basic) - get scoring inputs
- Stage 3: Enrichment (Place Details + Reviews) - optional, for top N only

Cost controls are built in. See docs/costed-data-plan.md for details.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from venue_intel.models import (
    FetchStage,
    VenueDiscovery,
    VenueDetails,
)

# Load API key from config/.env
_config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(_config_path)

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
BASE_URL = "https://places.googleapis.com/v1/places"


# =============================================================================
# Stage 1: Discovery (Text Search)
# =============================================================================

STAGE_1_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.location",
    "places.types",
    "places.primaryType",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
])


def discover_venues(
    query: str,
    max_results: int = 20,
) -> list[VenueDiscovery]:
    """Stage 1: Discover venues via Text Search.

    Cost: ~$0.032 per query (returns up to 20 results)

    Args:
        query: Search query, e.g., "cocktail bars in London"
        max_results: Maximum results to return (max 20 per query)

    Returns:
        List of VenueDiscovery objects with basic metadata
    """
    if not API_KEY:
        raise ValueError("GOOGLE_PLACES_API_KEY not set in config/.env")

    url = f"{BASE_URL}:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": STAGE_1_FIELD_MASK,
    }

    payload = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    data = response.json()
    places = data.get("places", [])

    venues = []
    for place in places:
        venue = VenueDiscovery(
            place_id=place.get("id", ""),
            name=place.get("displayName", {}).get("text", "Unknown"),
            latitude=place.get("location", {}).get("latitude", 0.0),
            longitude=place.get("location", {}).get("longitude", 0.0),
            types=place.get("types", []),
            rating=place.get("rating"),
            user_rating_count=place.get("userRatingCount"),
            price_level=_parse_price_level(place.get("priceLevel")),
            fetched_at=datetime.now(timezone.utc),
            search_query=query,
        )
        venues.append(venue)

    return venues


# =============================================================================
# Stage 2: Place Details (Basic/Advanced)
# =============================================================================

STAGE_2_FIELD_MASK = ",".join([
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "types",
    "primaryType",
    "rating",
    "userRatingCount",
    "priceLevel",
    "regularOpeningHours",
    "websiteUri",
    "nationalPhoneNumber",
    "editorialSummary",
    # Boolean attributes (may not be present for all venues)
    "servesCocktails",
    "servesWine",
    "servesBeer",
    "goodForGroups",
    "reservable",
])


def get_venue_details(place_id: str) -> VenueDetails | None:
    """Stage 2: Get detailed venue information for scoring.

    Cost: ~$0.017-0.020 per call (Basic/Advanced tier)

    Args:
        place_id: Google Places ID from Stage 1

    Returns:
        VenueDetails object with full scoring inputs, or None if failed
    """
    if not API_KEY:
        raise ValueError("GOOGLE_PLACES_API_KEY not set in config/.env")

    url = f"{BASE_URL}/{place_id}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": STAGE_2_FIELD_MASK,
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Warning: Failed to fetch {place_id}: {response.status_code}")
        return None

    place = response.json()

    # Parse opening hours
    hours = place.get("regularOpeningHours", {})
    weekday_hours = hours.get("weekdayDescriptions", [])
    open_now = hours.get("openNow")

    venue = VenueDetails(
        place_id=place.get("id", place_id),
        name=place.get("displayName", {}).get("text", "Unknown"),
        formatted_address=place.get("formattedAddress"),
        latitude=place.get("location", {}).get("latitude", 0.0),
        longitude=place.get("location", {}).get("longitude", 0.0),
        types=place.get("types", []),
        rating=place.get("rating"),
        user_rating_count=place.get("userRatingCount"),
        price_level=_parse_price_level(place.get("priceLevel")),
        website_uri=place.get("websiteUri"),
        phone_number=place.get("nationalPhoneNumber"),
        editorial_summary=place.get("editorialSummary", {}).get("text"),
        open_now=open_now,
        weekday_hours=weekday_hours if weekday_hours else None,
        fetched_at=datetime.now(timezone.utc),
        fetch_stage=FetchStage.SCORED,
    )

    # Store boolean attributes as extra data (for M signal)
    venue._attributes = {
        "servesCocktails": place.get("servesCocktails"),
        "servesWine": place.get("servesWine"),
        "servesBeer": place.get("servesBeer"),
        "goodForGroups": place.get("goodForGroups"),
        "reservable": place.get("reservable"),
    }

    return venue


def get_venue_details_batch(
    place_ids: list[str],
    max_calls: int = 20,
) -> list[VenueDetails]:
    """Stage 2: Get details for multiple venues with cost control.

    Args:
        place_ids: List of Google Places IDs
        max_calls: Maximum API calls to make (cost control)

    Returns:
        List of VenueDetails objects
    """
    venues = []

    for i, place_id in enumerate(place_ids[:max_calls]):
        print(f"Fetching details {i+1}/{min(len(place_ids), max_calls)}: {place_id[:20]}...")
        venue = get_venue_details(place_id)
        if venue:
            venues.append(venue)

    return venues


# =============================================================================
# Helpers
# =============================================================================

def _parse_price_level(price_level_str: str | None) -> int | None:
    """Convert Google's price level string to integer."""
    if price_level_str is None:
        return None

    mapping = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }

    return mapping.get(price_level_str)


def estimate_cost(discovery_queries: int, detail_calls: int) -> float:
    """Estimate API cost before running.

    Returns:
        Estimated cost in USD
    """
    discovery_cost = discovery_queries * 0.032
    details_cost = detail_calls * 0.020
    return discovery_cost + details_cost


# =============================================================================
# Test function
# =============================================================================

def test_single_query():
    """Run a minimal test: 1 discovery query + 10 detail calls.

    Estimated cost: ~$0.20
    """
    print("=" * 60)
    print("VIDPS Fetch Test - Single Query")
    print("=" * 60)
    print(f"Estimated cost: ${estimate_cost(1, 10):.2f}")
    print()

    # Stage 1: Discovery
    print("Stage 1: Discovery")
    print("-" * 40)
    query = "cocktail bars in London"
    print(f"Query: {query}")

    venues = discover_venues(query, max_results=20)
    print(f"Found: {len(venues)} venues")
    print()

    # Show sample
    for v in venues[:5]:
        print(f"  - {v.name} ({v.rating}★, {v.user_rating_count} reviews)")
    if len(venues) > 5:
        print(f"  ... and {len(venues) - 5} more")
    print()

    # Stage 2: Details (limited to 10)
    print("Stage 2: Place Details")
    print("-" * 40)

    place_ids = [v.place_id for v in venues[:10]]
    detailed_venues = get_venue_details_batch(place_ids, max_calls=10)
    print(f"Fetched details for: {len(detailed_venues)} venues")
    print()

    # Show sample with details
    print("Sample output:")
    print("-" * 40)
    for v in detailed_venues[:3]:
        print(f"Name: {v.name}")
        print(f"  Address: {v.formatted_address}")
        print(f"  Rating: {v.rating}★ ({v.user_rating_count} reviews)")
        print(f"  Price: {'$' * (v.price_level or 0)} ({v.price_level})")
        print(f"  Types: {', '.join(v.types[:3])}")
        if v.editorial_summary:
            print(f"  Summary: {v.editorial_summary[:100]}...")
        print()

    return venues, detailed_venues


if __name__ == "__main__":
    test_single_query()
