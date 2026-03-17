#!/usr/bin/env python3
"""Get disruption history for a component (Mar 16 API).

Replaces the old status-changes endpoint. Uses GET /status-page/components/{id}
which returns GetComponentDetailsResult with:
- impactingDisruption: currently impacting disruption for this component
- disruptionHistory: 90-day summary (days with disruption counts)

Optionally uses POST /status-page/components/{id}/disruptions to fetch a paginated
list of disruptions for more detail.

Usage:
    python get_status_history.py <component_id> [--list-disruptions]

Arguments:
    component_id: UUID of the component

Options:
    --list-disruptions: Also call POST .../disruptions with state=cleared to show recent cleared disruptions

Example:
    python get_status_history.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298

Environment Variables:
    NOBL9_API_TOKEN or NOBL9_CLIENT_ID+NOBL9_CLIENT_SECRET, NOBL9_ORG (required)
"""
import sys

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def get_component_disruption_history(client: StatusPageClient, component_id: str) -> dict:
    """Get disruption history for a component via GET component details.

    Returns:
        GetComponentDetailsResult slice with impactingDisruption and disruptionHistory.
    """
    return client.get(f"/status-page/components/{component_id}")


def get_component_disruptions_list(
    client: StatusPageClient,
    component_id: str,
    state: str = "cleared",
    limit: int = 20,
) -> dict:
    """Get paginated list of disruptions for a component (POST .../disruptions)."""
    body = {"state": state, "limit": limit, "offset": 0}
    return client.list_component_disruptions(component_id, body)


def print_disruption_history(details: dict) -> None:
    """Print impacting disruption and 90-day disruption history from component details."""
    comp_id = details.get("id", "?")
    name = details.get("name", "?")
    print(f"\nComponent: {name} ({comp_id})")
    print("-" * 80)

    impacting = details.get("impactingDisruption")
    if impacting and impacting.get("id"):
        origin = (impacting.get("originComponent") or {}).get("name", "?")
        print("\n🔴 Impacting disruption:")
        print(f"  - Id: {impacting.get('id')}  Severity: {impacting.get('severity')}  Origin: {origin}")
        print(f"    Start: {impacting.get('startedAt')}")
        if impacting.get("comment"):
            print(f"    Comment: {impacting.get('comment')}")
    else:
        print("\n✅ No impacting disruption.")

    history = details.get("disruptionHistory")
    if not history:
        print("\nNo 90-day disruption history.")
        return

    days_list = history.get("days") or []
    summary = history.get("summary") or {}
    if summary:
        print(
            f"\n📊 90-day summary: total={summary.get('total', 0)}  "
            f"daysWithDisruptions={summary.get('daysWithDisruptions', 0)}  "
            f"avgPerDay={summary.get('avgPerDay', 0):.2f}"
        )
    if days_list:
        print("\nDays with disruptions (recent first):")
        for day in days_list[:30]:
            print(
                f"  {day.get('date')}: {day.get('disruptions')} disruptions "
                f"(degraded: {day.get('degradedPerformanceCount', 0)}, major: {day.get('majorOutageCount', 0)})"
            )


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python get_status_history.py <component_id> [--list-disruptions]", file=sys.stderr)
        print("\nExample:")
        print("  python get_status_history.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298")
        sys.exit(1)

    component_id = sys.argv[1]
    list_disruptions = "--list-disruptions" in sys.argv

    try:
        config = get_config()
        client = StatusPageClient(config)

        print(f"Fetching disruption history for component {component_id}...")
        details = get_component_disruption_history(client, component_id)
        print_disruption_history(details)

        if list_disruptions:
            print("\n\nRecent cleared disruptions (POST .../disruptions):")
            print("-" * 80)
            result = get_component_disruptions_list(client, component_id, state="cleared", limit=10)
            disruptions = result.get("disruptions") or []
            for disruption in disruptions:
                origin = (disruption.get("originComponent") or {}).get("name", "?")
                print(
                    f"  {disruption.get('id')}: {disruption.get('severity')}  origin={origin}  "
                    f"start={disruption.get('startTime')}  end={disruption.get('endTime')}  "
                    f"cleared={disruption.get('isCleared')}"
                )
            if not disruptions:
                print("  (none)")

        print("\n\nFull component details (disruption-related):")
        print("=" * 80)
        out = {
            "id": details.get("id"),
            "name": details.get("name"),
            "status": details.get("status"),
            "impactingDisruption": details.get("impactingDisruption"),
            "disruptionHistory": details.get("disruptionHistory"),
        }
        pretty_print(out)

    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
