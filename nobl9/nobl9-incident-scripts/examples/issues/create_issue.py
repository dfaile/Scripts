#!/usr/bin/env python3
"""Create an authenticated issue report for a component.

This script creates an issue report as an authenticated user. Issue reports:
- Track user-reported problems with components
- Trigger spike detection for automatic status changes
- Can include optional comments and custom timestamps

When many issue reports are created in a short time, spike detection may
automatically change the component's status.

Usage:
    python create_issue.py <component_id> [options]

Arguments:
    component_id: UUID of the component

Options:
    --comment TEXT: Description of the issue
    --occurred-at TIMESTAMP: When the issue occurred (ISO 8601 format, defaults to now)

Examples:
    # Report an issue now
    python create_issue.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 --comment "Slow response times"

    # Report an issue that occurred in the past
    python create_issue.py abc123 --comment "Timeout error" --occurred-at "2024-11-04T10:30:00Z"

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys
import argparse
from datetime import datetime

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def create_issue(
    client: StatusPageClient,
    component_id: str,
    comment: str = None,
    occurred_at: str = None,
) -> dict:
    """Create an issue report.

    Args:
        client: StatusPageClient instance.
        component_id: UUID of the component.
        comment: Optional issue description.
        occurred_at: Optional timestamp (ISO 8601).

    Returns:
        Created issue report.
    """
    payload = {
        "componentId": component_id,
        "occurredAt": occurred_at or datetime.utcnow().isoformat() + "Z",
    }
    if comment:
        payload["comment"] = comment

    return client.post("/status-page/issues", payload)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create an authenticated issue report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("component_id", help="Component UUID")
    parser.add_argument("--comment", help="Description of the issue")
    parser.add_argument(
        "--occurred-at",
        help="When the issue occurred (ISO 8601 format, e.g., 2024-11-04T10:30:00Z)",
    )

    args = parser.parse_args()

    try:
        config = get_config()
        client = StatusPageClient(config)

        print(f"Creating issue report for component {args.component_id}...")
        result = create_issue(
            client,
            args.component_id,
            args.comment,
            args.occurred_at,
        )

        print("\nIssue Report Created:")
        print("=" * 80)
        pretty_print(result)

        print("\n✅ Issue report created successfully!")
        print(f"Issue ID: {result.get('id')}")

    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
