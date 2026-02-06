#!/usr/bin/env python3
"""Get issue report summary statistics.

This script retrieves summary statistics of active issues across all components:
- Total counts by type (user/external/internal)
- Time-based counts (last hour, 24 hours, 7 days)
- Per-component breakdown
- Active vs total issue counts

Usage:
    python get_issue_summary.py

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def get_issue_summary(client: StatusPageClient) -> dict:
    """Get issue report summary statistics.

    Args:
        client: StatusPageClient instance.

    Returns:
        Issue summary statistics.
    """
    return client.get("/status-page/issues/summary")


def print_summary(result: dict) -> None:
    """Print issue summary in a readable format.

    Args:
        result: Issue summary result.
    """
    total_counts = result.get("totalCounts", {})

    print("\n📊 Overall Issue Statistics:")
    print("-" * 80)
    print(f"Total issues: {total_counts.get('total', 0)}")
    print(f"  User-reported: {total_counts.get('userCount', 0)}")
    print(f"  External systems: {total_counts.get('externalCount', 0)}")
    print(f"  Internal (Nobl9): {total_counts.get('internalCount', 0)}")

    print("\n⏰ Time-based Counts:")
    print(f"  Last hour: {total_counts.get('lastHour', 0)}")
    print(f"  Last 24 hours: {total_counts.get('last24h', 0)}")
    print(f"  Last 7 days: {total_counts.get('last7d', 0)}")

    components = result.get("components", [])
    if components:
        print(f"\n🔧 Per-Component Breakdown ({len(components)} components with active issues):")
        print("-" * 80)

        for comp in components:
            print(f"\n  Component: {comp.get('componentName')}")
            print(f"  ID: {comp.get('componentId')}")

            counts = comp.get("counts", {})
            print(f"  Total: {counts.get('total', 0)}")
            print(f"    User: {counts.get('userCount', 0)}")
            print(f"    External: {counts.get('externalCount', 0)}")
            print(f"    Internal: {counts.get('internalCount', 0)}")

            active_counts = comp.get("activeCounts", {})
            print(f"  Active: {active_counts.get('activeTotal', 0)}")
    else:
        print("\n✅ No components with active issues.")


def main():
    """Main function."""
    try:
        config = get_config()
        client = StatusPageClient(config)

        print("Fetching issue summary...")
        result = get_issue_summary(client)

        # Print formatted summary
        print_summary(result)

        # Print full JSON
        print("\n\nFull Issue Summary:")
        print("=" * 80)
        pretty_print(result)

    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
