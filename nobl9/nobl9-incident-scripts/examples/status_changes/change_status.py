#!/usr/bin/env python3
"""Change the status of a component.

This script creates a status change for a component, which can:
- Update component status (operational/degradedPerformance/majorOutage)
- Add optional comments to describe the change
- Propagate status changes up to parent components
- Set custom timestamps for when the change occurred

Status changes to non-operational states create incidents automatically.

Usage:
    python change_status.py <component_id> <status> [options]

Arguments:
    component_id: UUID of the component
    status: New status (operational, degradedPerformance, majorOutage)

Options:
    --comment TEXT: Comment describing the status change
    --propagate: Propagate status change to parent components

Examples:
    # Mark component as degraded with comment
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 degradedPerformance --comment "High latency detected"

    # Mark component as operational and propagate to parents
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 operational --propagate

    # Report major outage
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 majorOutage --comment "Service unavailable"

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys
import argparse

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def change_status(
    client: StatusPageClient,
    component_id: str,
    status: str,
    comment: str = None,
    propagate_up: bool = False,
) -> dict:
    """Change component status.

    Args:
        client: StatusPageClient instance.
        component_id: UUID of the component.
        status: New status value.
        comment: Optional comment.
        propagate_up: Whether to propagate to parent components.

    Returns:
        Status change result.
    """
    payload = {
        "status": status,
        "propagateUp": propagate_up,
    }
    if comment:
        payload["comment"] = comment

    return client.post(f"/status-page/components/{component_id}/change-status", payload)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Change component status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python change_status.py abc123 degradedPerformance --comment "High latency"
  python change_status.py abc123 operational --propagate
        """,
    )
    parser.add_argument("component_id", help="Component UUID")
    parser.add_argument(
        "status",
        choices=["operational", "degradedPerformance", "majorOutage"],
        help="New status",
    )
    parser.add_argument("--comment", help="Comment describing the change")
    parser.add_argument(
        "--propagate",
        action="store_true",
        help="Propagate status change to parent components",
    )

    args = parser.parse_args()

    try:
        config = get_config()
        client = StatusPageClient(config)

        print(f"Changing status of component {args.component_id} to {args.status}...")
        if args.propagate:
            print("Status change will propagate to parent components.")

        result = change_status(
            client,
            args.component_id,
            args.status,
            args.comment,
            args.propagate,
        )

        print("\nStatus Change Result:")
        print("=" * 80)
        pretty_print(result)

        print("\n✅ Status changed successfully!")

    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
