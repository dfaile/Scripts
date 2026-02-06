#!/usr/bin/env python3
"""Get status change history for a component.

This script retrieves the complete timeline of status changes for a component,
including:
- All status transitions
- Who made each change
- When changes occurred
- Comments associated with each change
- Information about propagated changes

Usage:
    python get_status_history.py <component_id>

Arguments:
    component_id: UUID of the component

Example:
    python get_status_history.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def get_status_history(client: StatusPageClient, component_id: str) -> dict:
    """Get status change history for a component.

    Args:
        client: StatusPageClient instance.
        component_id: UUID of the component.

    Returns:
        Status history result.
    """
    return client.get(f"/status-page/components/{component_id}/status-changes")


def print_history_timeline(history: list) -> None:
    """Print status history in a timeline format.

    Args:
        history: List of status change records.
    """
    if not history:
        print("No status changes found.")
        return

    print("\nStatus Change Timeline:")
    print("-" * 80)

    for change in history:
        status_emoji = {
            "operational": "✅",
            "degradedPerformance": "⚠️",
            "majorOutage": "❌",
        }

        prev_emoji = status_emoji.get(change.get("previousStatus", ""), "❓")
        new_emoji = status_emoji.get(change.get("newStatus", ""), "❓")

        print(f"\n{change.get('changedAt', 'Unknown time')}")
        print(f"  {prev_emoji} {change.get('previousStatus')} → {new_emoji} {change.get('newStatus')}")
        print(f"  Changed by: {change.get('changedBy', 'Unknown')}")

        if change.get("comment"):
            print(f"  Comment: {change.get('comment')}")

        if change.get("propagatedFrom"):
            print(f"  ↳ Propagated from: {change.get('propagatedFrom')}")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python get_status_history.py <component_id>", file=sys.stderr)
        print("\nExample:")
        print("  python get_status_history.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298")
        sys.exit(1)

    component_id = sys.argv[1]

    try:
        config = get_config()
        client = StatusPageClient(config)

        print(f"Fetching status history for component {component_id}...")
        result = get_status_history(client, component_id)

        # Print timeline view
        history = result.get("history", [])
        print_history_timeline(history)

        # Print full JSON
        print("\n\nFull Status History:")
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
