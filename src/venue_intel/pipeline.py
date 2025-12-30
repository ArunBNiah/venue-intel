"""Main pipeline for venue discovery, scoring, and export.

This script orchestrates the full workflow:
1. Discover venues (Text Search)
2. Filter already-scored venues (skip to save API cost)
3. Fetch details for new venues
4. Score and store
5. Export ranked results

Usage:
    python -m venue_intel.pipeline --city london --query "cocktail bars"
    python -m venue_intel.pipeline --city london --export-only
"""

import argparse
from datetime import datetime, timezone

from venue_intel.fetch import discover_venues, get_venue_details_batch, estimate_cost
from venue_intel.scoring import create_venue_records
from venue_intel.storage import (
    get_known_place_ids,
    save_venues,
    log_discovery,
    get_ranked_venues,
    get_venue_count,
)
from venue_intel.export import export_to_excel, export_to_csv


def run_discovery(
    city: str,
    query: str,
    max_results: int = 20,
    max_details: int = 20,
    brand_category: str = "premium_spirits",
) -> dict:
    """Run discovery pipeline for a single query.

    Args:
        city: City name (for storage/export)
        query: Search query
        max_results: Max venues from discovery
        max_details: Max detail calls (cost control)
        brand_category: Brand category for scoring

    Returns:
        Summary dict with counts and costs
    """
    print("=" * 60)
    print(f"VIDPS Discovery Pipeline")
    print(f"City: {city.title()} | Query: {query}")
    print("=" * 60)

    # Check what we already have
    known_ids = get_known_place_ids(city)
    print(f"\nAlready scored: {len(known_ids)} venues")

    # Stage 1: Discovery
    print(f"\n[Stage 1] Discovery: {query}")
    print("-" * 40)

    discovered = discover_venues(query, max_results=max_results)
    print(f"Found: {len(discovered)} venues")

    # Log discovery
    log_discovery(city, query, [v.place_id for v in discovered])

    # Filter out already-scored venues
    new_venues = [v for v in discovered if v.place_id not in known_ids]
    skipped = len(discovered) - len(new_venues)

    if skipped > 0:
        print(f"Skipping: {skipped} already scored")

    if not new_venues:
        print("No new venues to process.")
        return {
            "discovered": len(discovered),
            "skipped": skipped,
            "new": 0,
            "scored": 0,
            "cost_usd": estimate_cost(1, 0),
        }

    print(f"New venues: {len(new_venues)}")

    # Stage 2: Fetch details (limited)
    print(f"\n[Stage 2] Fetching details (max {max_details})")
    print("-" * 40)

    place_ids = [v.place_id for v in new_venues[:max_details]]
    detailed = get_venue_details_batch(place_ids, max_calls=max_details)

    print(f"Fetched: {len(detailed)} venues")

    # Score and create permanent records
    print(f"\n[Scoring & Storage]")
    print("-" * 40)

    records = create_venue_records(detailed, city=city, brand_category=brand_category)

    # Store to permanent database
    saved = save_venues(records)
    print(f"Saved: {saved} venues to permanent storage")

    # Summary
    cost = estimate_cost(1, len(detailed))
    print(f"\nEstimated cost: ${cost:.2f}")

    return {
        "discovered": len(discovered),
        "skipped": skipped,
        "new": len(new_venues),
        "scored": len(records),
        "cost_usd": cost,
    }


def run_multi_query_discovery(
    city: str,
    queries: list[str],
    max_results_per_query: int = 20,
    max_total_details: int = 100,
    brand_category: str = "premium_spirits",
) -> dict:
    """Run discovery with multiple queries.

    Args:
        city: City name
        queries: List of search queries
        max_results_per_query: Max venues per query
        max_total_details: Total detail calls budget
        brand_category: Brand category

    Returns:
        Summary dict
    """
    print("=" * 60)
    print(f"VIDPS Multi-Query Discovery")
    print(f"City: {city.title()} | Queries: {len(queries)}")
    print("=" * 60)

    known_ids = get_known_place_ids(city)
    print(f"\nAlready scored: {len(known_ids)} venues")

    all_discovered = []
    all_new_place_ids = set()

    # Stage 1: Run all discovery queries
    print(f"\n[Stage 1] Discovery")
    print("-" * 40)

    for query in queries:
        print(f"  Query: {query}")
        discovered = discover_venues(query, max_results=max_results_per_query)
        log_discovery(city, query, [v.place_id for v in discovered])

        for v in discovered:
            if v.place_id not in known_ids and v.place_id not in all_new_place_ids:
                all_discovered.append(v)
                all_new_place_ids.add(v.place_id)

        print(f"    Found: {len(discovered)}, New unique: {len(all_new_place_ids)}")

    print(f"\nTotal unique new venues: {len(all_discovered)}")

    if not all_discovered:
        print("No new venues to process.")
        return {
            "queries": len(queries),
            "discovered": 0,
            "new": 0,
            "scored": 0,
            "cost_usd": estimate_cost(len(queries), 0),
        }

    # Stage 2: Fetch details (limited)
    to_fetch = min(len(all_discovered), max_total_details)
    print(f"\n[Stage 2] Fetching details ({to_fetch} of {len(all_discovered)})")
    print("-" * 40)

    place_ids = [v.place_id for v in all_discovered[:to_fetch]]
    detailed = get_venue_details_batch(place_ids, max_calls=to_fetch)

    # Score and store to permanent database
    print(f"\n[Scoring & Storage]")
    print("-" * 40)

    records = create_venue_records(detailed, city=city, brand_category=brand_category)
    saved = save_venues(records)
    print(f"Saved: {saved} venues to permanent storage")

    cost = estimate_cost(len(queries), len(detailed))
    print(f"\nEstimated cost: ${cost:.2f}")

    return {
        "queries": len(queries),
        "discovered": len(all_discovered),
        "scored": len(records),
        "cost_usd": cost,
    }


def export_results(
    city: str,
    brand_category: str = "premium_spirits",
    limit: int = 100,
) -> None:
    """Export stored results to Excel and CSV."""
    print("=" * 60)
    print(f"VIDPS Export")
    print(f"City: {city.title()}")
    print("=" * 60)

    venues = get_ranked_venues(city, brand_category, limit)

    if not venues:
        print(f"\nNo scored venues found for {city}.")
        print("Run discovery first.")
        return

    print(f"\nVenues to export: {len(venues)}")

    # Export
    excel_path = export_to_excel(venues, city=city, brand_category=brand_category)
    csv_path = export_to_csv(venues, city=city)

    print(f"\nExported:")
    print(f"  Excel: {excel_path}")
    print(f"  CSV:   {csv_path}")

    # Show top 5
    print(f"\nTop 5 venues:")
    print("-" * 40)
    for i, v in enumerate(venues[:5], 1):
        print(f"  #{i} | {v.name} | {v.distribution_fit_score}/100 | {v.confidence_tier.value}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="VIDPS Pipeline")
    parser.add_argument("--city", default="london", help="City name")
    parser.add_argument("--query", help="Single search query")
    parser.add_argument("--export-only", action="store_true", help="Only export existing data")
    parser.add_argument("--max-details", type=int, default=20, help="Max detail API calls")

    args = parser.parse_args()

    if args.export_only:
        export_results(args.city)
    elif args.query:
        run_discovery(args.city, args.query, max_details=args.max_details)
        export_results(args.city)
    else:
        # Default: single test query
        run_discovery(args.city, "cocktail bars in London", max_details=10)
        export_results(args.city)


if __name__ == "__main__":
    main()
