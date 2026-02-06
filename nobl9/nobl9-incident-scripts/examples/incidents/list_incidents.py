#!/usr/bin/env python3
"""List incidents grouped by day.

This script retrieves incidents that are automatically derived from status changes
where components transition to non-operational states. Features:
- Incidents grouped by day
- Filter by ongoing or resolved status
- Incident details including duration, severity, and related issue reports

Incidents are created automatically when a component's status changes to
degradedPerformance or majorOutage, and resolved when it returns to operational.

Usage:
    python list_incidents.py [--ongoing | --resolved]

Options:
    --ongoing: Show only ongoing incidents
    --resolved: Show only resolved incidents
    (no flag): Show all incidents

Examples:
    python list_incidents.py
    python list_incidents.py --ongoing
    python list_incidents.py --resolved

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys
import argparse

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def list_incidents(client: StatusPageClient, ongoing: bool = None) -> dict:
    """List incidents.

    Args:
        client: StatusPageClient instance.
        ongoing: Filter by ongoing status (True/False/None for all).

    Returns:
        Incidents grouped by day.
    """
    params = {}
    if ongoing is not None:
        params["ongoing"] = str(ongoing).lower()

    return client.get("/status-page/incidents", params=params)


def print_incidents_summary(days: list) -> None:
    """Print incidents in a summary format.

    Args:
        days: List of day incident groups.
    """
    if not days:
        print("No incidents found.")
        return

    total_incidents = sum(day.get("count", 0) for day in days)
    print(f"\nTotal incidents: {total_incidents} across {len(days)} days")
    print("\nIncident Summary:")
    print("-" * 80)

    for day in days:
        print(f"\n📅 {day.get('date')}: {day.get('count')} incident(s)")

        for incident in day.get("incidents", []):
            severity_emoji = {
                "degradedPerformance": "⚠️",
                "majorOutage": "❌",
            }.get(incident.get("severity", ""), "❓")

            status_emoji = {
                "ongoing": "🔴",
                "resolved": "✅",
            }.get(incident.get("status", ""), "❓")

            print(f"\n  {severity_emoji} {incident.get('componentName')} - {status_emoji} {incident.get('status')}")
            print(f"     Started: {incident.get('startedAt')}")

            if incident.get("endedAt"):
                print(f"     Ended: {incident.get('endedAt')}")
                print(f"     Duration: {incident.get('duration')} seconds")
            else:
                print(f"     Duration: {incident.get('duration')} seconds (ongoing)")

            if incident.get("startComment"):
                print(f"     Comment: {incident.get('startComment')}")

            issue_count = incident.get("issueCount", 0)
            if issue_count > 0:
                print(f"     Issue reports: {issue_count}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="List incidents grouped by day")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ongoing", action="store_true", help="Show only ongoing incidents")
    group.add_argument("--resolved", action="store_true", help="Show only resolved incidents")

    args = parser.parse_args()

    try:
        config = get_config()
        client = StatusPageClient(config)

        # Determine filter
        ongoing_filter = None
        if args.ongoing:
            ongoing_filter = True
            print("Fetching ongoing incidents...")
        elif args.resolved:
            ongoing_filter = False
            print("Fetching resolved incidents...")
        else:
            print("Fetching all incidents...")

        result = list_incidents(client, ongoing_filter)

        # Print summary
        days = result.get("days", [])
        print_incidents_summary(days)

        # Print full JSON
        print("\n\nFull Incident Details:")
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
