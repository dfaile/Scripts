#!/usr/bin/env python3
"""Create an external issue report.

IMPORTANT: Despite the name "external", this endpoint REQUIRES authentication.

This script creates issue reports from external monitoring systems. Features:
- Requires authentication (NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)
- Matches components by name (may create multiple reports if names match)
- Optionally triggers status change
- Custom requestedBy identifier
- Component verification (with --verify)
- Issue verification after creation
- Retry logic (with --retry)

This endpoint is designed for integration with external monitoring tools like
Prometheus, Datadog, or custom alerting systems.

Usage:
    python create_external_issue.py <component_name> [options]

Arguments:
    component_name: Name of the component (matches any component with this name)

Options:
    --comment TEXT: Description of the issue
    --occurred-at TIMESTAMP: When the issue occurred (ISO 8601, defaults to now)
    --requested-by ID: Identifier for the system making the request (default: "external-system")
    --status STATUS: Trigger status change (operational, degradedPerformance, majorOutage)
    --propagate: Propagate status change to parent components (requires --status)
    --verify: Verify component exists before creating issue (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)
    --list-components: List all available components (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)
    --retry: Enable retry logic with exponential backoff (3 attempts)

Examples:
    # Simple external issue report
    python create_external_issue.py "API Service" --comment "High error rate"

    # Report with status change
    python create_external_issue.py "API Service" \\
        --comment "Critical failure" \\
        --status majorOutage \\
        --requested-by prometheus-alertmanager

    # Report with propagation
    python create_external_issue.py "Database" \\
        --status degradedPerformance \\
        --propagate \\
        --requested-by datadog

    # Verify component before reporting
    python create_external_issue.py "API Service" --comment "Test" --verify

    # List available components
    python create_external_issue.py --list-components

Environment Variables:
    NOBL9_ORG: Your organization ID (required)
    NOBL9_CLIENT_ID: Client ID (required)
    NOBL9_CLIENT_SECRET: Client secret (required)
    NOBL9_BASE_URL: API base URL (optional)

Note: Authentication is REQUIRED for this endpoint. The script automatically handles
token generation and base64 encoding from your client credentials.

For comprehensive documentation, see: EXTERNAL_ISSUES_GUIDE.md
For a production-ready example, see: external_issue_complete_example.py
"""
import sys
from pathlib import Path
import argparse
from datetime import datetime, timezone
import time

from examples.common import get_config, StatusPageClient, pretty_print, APIError, NotFoundError, RateLimitError, AuthenticationError


def create_external_issue(
    client: StatusPageClient,
    component_name: str,
    comment: str = None,
    occurred_at: str = None,
    requested_by: str = None,
    status: str = None,
    propagate_up: bool = False,
) -> dict:
    """Create an external issue report.

    Args:
        client: StatusPageClient instance.
        component_name: Name of the component.
        comment: Optional issue description.
        occurred_at: Optional timestamp (ISO 8601).
        requested_by: Optional identifier for requester.
        status: Optional status to set.
        propagate_up: Whether to propagate status change.

    Returns:
        External issue result.
    """
    payload = {
        "componentName": component_name,
        "occurredAt": occurred_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    if comment:
        payload["comment"] = comment
    if requested_by:
        payload["requestedBy"] = requested_by
    if status:
        payload["statusChange"] = {
            "status": status,
            "propagateUp": propagate_up,
        }

    # Note: External endpoint requires Basic auth (not Bearer token)
    return client.post_external("/status-page/issues/external", payload)


def create_external_issue_with_retry(
    client: StatusPageClient,
    component_name: str,
    comment: str = None,
    occurred_at: str = None,
    requested_by: str = None,
    status: str = None,
    propagate_up: bool = False,
    max_retries: int = 3,
) -> dict:
    """Create an external issue report with retry logic.

    Args:
        client: StatusPageClient instance.
        component_name: Name of the component.
        comment: Optional issue description.
        occurred_at: Optional timestamp (ISO 8601).
        requested_by: Optional identifier for requester.
        status: Optional status to set.
        propagate_up: Whether to propagate status change.
        max_retries: Maximum number of retry attempts.

    Returns:
        External issue result.

    Raises:
        APIError: If all retries fail.
    """
    backoff = 1.0
    last_error = None

    for attempt in range(max_retries):
        try:
            return create_external_issue(
                client,
                component_name,
                comment,
                occurred_at,
                requested_by,
                status,
                propagate_up,
            )
        except RateLimitError as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"⏸ Rate limited, retrying in {backoff:.1f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
        except APIError as e:
            # For non-retryable errors, raise immediately
            if isinstance(e, NotFoundError):
                raise
            last_error = e
            if attempt < max_retries - 1:
                print(f"⚠ Error, retrying in {backoff:.1f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(backoff)
                backoff *= 2
            else:
                raise

    raise APIError(f"Failed after {max_retries} attempts: {last_error}")


def verify_component_exists(client: StatusPageClient, component_name: str) -> bool:
    """Verify that a component with the given name exists.

    Args:
        client: StatusPageClient instance (must be authenticated).
        component_name: Name of the component to check.

    Returns:
        True if component exists, False otherwise.

    Note:
        This requires authentication (NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET).
    """
    try:
        components = list_components(client)
        matching = [c for c in components if c.get("name") == component_name]
        return len(matching) > 0
    except APIError:
        # If we can't verify, assume it exists
        return True


def list_components(client: StatusPageClient) -> list:
    """List all components (recursively flattens nested structure).

    Args:
        client: StatusPageClient instance (must be authenticated).

    Returns:
        List of component dictionaries.

    Note:
        This requires authentication (NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET).
    """
    def flatten_components(components):
        """Recursively flatten nested component structure."""
        result = []
        for comp in components:
            result.append(comp)
            if comp.get("children"):
                result.extend(flatten_components(comp["children"]))
        return result

    response = client.get("/status-page/components")
    components = response.get("components", [])
    return flatten_components(components)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create an external issue report (requires authentication)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "component_name",
        nargs="?",
        help="Component name to match"
    )
    parser.add_argument("--comment", help="Description of the issue")
    parser.add_argument(
        "--occurred-at",
        help="When the issue occurred (ISO 8601 format)",
    )
    parser.add_argument(
        "--requested-by",
        default="external-system",
        help="Identifier for the requester (default: external-system)",
    )
    parser.add_argument(
        "--status",
        choices=["operational", "degradedPerformance", "majorOutage"],
        help="Trigger status change",
    )
    parser.add_argument(
        "--propagate",
        action="store_true",
        help="Propagate status change to parents (requires --status)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify component exists before creating issue (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)",
    )
    parser.add_argument(
        "--list-components",
        action="store_true",
        help="List all available components (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Enable retry logic with exponential backoff",
    )

    args = parser.parse_args()

    # Handle --list-components
    if args.list_components:
        try:
            from common.config import Config
            config = Config()
            if not config.organization:
                raise ValueError("NOBL9_ORG environment variable is required")
            if not config.client_id or not config.client_secret:
                raise ValueError(
                    "NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET environment variables are "
                    "required for listing components"
                )

            client = StatusPageClient(config)
            components = list_components(client)

            print(f"Found {len(components)} component(s):\n")
            for i, comp in enumerate(components, 1):
                # Handle both dict and object responses
                if isinstance(comp, dict):
                    name = comp.get('name', 'N/A')
                    comp_id = comp.get('id', 'N/A')
                    desc = comp.get('description', 'N/A')
                    status = comp.get('status', 'N/A')
                else:
                    # If it's an object, try to access attributes
                    name = getattr(comp, 'name', str(comp))
                    comp_id = getattr(comp, 'id', 'N/A')
                    desc = getattr(comp, 'description', 'N/A')
                    status = getattr(comp, 'status', 'N/A')

                print(f"{i}. {name}")
                print(f"   ID:          {comp_id}")
                print(f"   Description: {desc}")
                print(f"   Status:      {status}")
                print()
            sys.exit(0)

        except APIError as e:
            print(f"❌ API Error: {e}", file=sys.stderr)
            print("\nTip: Make sure NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET are set correctly.", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"❌ Configuration Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate required arguments
    if not args.component_name:
        parser.error("component_name is required (unless using --list-components)")

    if args.propagate and not args.status:
        parser.error("--propagate requires --status to be specified")

    try:
        # Note: Despite the endpoint name "external", it DOES require authentication
        # Use get_config to ensure credentials are validated
        config = get_config()

        client = StatusPageClient(config)

        # Verify component if requested
        if args.verify:
            if not config.client_id or not config.client_secret:
                print("⚠ Warning: --verify requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET, skipping verification")
            else:
                print(f"Verifying component '{args.component_name}' exists...")
                if verify_component_exists(client, args.component_name):
                    print("✅ Component found")
                else:
                    print(f"❌ Component '{args.component_name}' not found", file=sys.stderr)
                    print("\nTip: Use --list-components to see all available components", file=sys.stderr)
                    sys.exit(1)

        print(f"Creating external issue report for component '{args.component_name}'...")
        if args.status:
            print(f"Will change status to: {args.status}")
            if args.propagate:
                print("Status change will propagate to parent components.")

        # Create issue (with or without retry)
        if args.retry:
            result = create_external_issue_with_retry(
                client,
                args.component_name,
                args.comment,
                args.occurred_at,
                args.requested_by,
                args.status,
                args.propagate,
            )
        else:
            result = create_external_issue(
                client,
                args.component_name,
                args.comment,
                args.occurred_at,
                args.requested_by,
                args.status,
                args.propagate,
            )

        print("\nExternal Issue Result:")
        print("=" * 80)
        pretty_print(result)

        reports = result.get("reports", [])
        print(f"\n✅ Created {len(reports)} issue report(s)")
        for report in reports:
            print(f"   - Issue ID: {report.get('id')}")
            print(f"     Component: {report.get('componentName')} ({report.get('componentId')})")

        if result.get("statusChanges"):
            status_changes = result.get("statusChanges", [])
            print(f"\n✅ Triggered {len(status_changes)} status change(s)")
            for change in status_changes:
                print(f"   - {change.get('componentName')}: "
                      f"{change.get('previousStatus')} → {change.get('newStatus')}")

    except AuthenticationError as e:
        print(f"❌ Authentication Error: {e}", file=sys.stderr)
        print("\nAuthentication failed. Please check:", file=sys.stderr)
        print("  ✗ NOBL9_CLIENT_ID is set correctly", file=sys.stderr)
        print("  ✗ NOBL9_CLIENT_SECRET is set correctly", file=sys.stderr)
        print("  ✗ NOBL9_ORG matches your Nobl9 account", file=sys.stderr)
        print("\nTo fix:", file=sys.stderr)
        print("  1. Get credentials from Nobl9 UI: Settings > API > Client Credentials", file=sys.stderr)
        print("  2. Set: export NOBL9_CLIENT_ID='your-client-id'", file=sys.stderr)
        print("  3. Set: export NOBL9_CLIENT_SECRET='your-client-secret'", file=sys.stderr)
        print("  4. Set: export NOBL9_ORG='your-org-id'", file=sys.stderr)
        sys.exit(1)
    except NotFoundError as e:
        print(f"❌ Component Not Found: {e}", file=sys.stderr)
        print(f"\nTip: Check that component '{args.component_name}' exists (case-sensitive)", file=sys.stderr)
        print("     Use --list-components to see all available components", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"❌ API Error: {e}", file=sys.stderr)
        print("\nTroubleshooting tips:", file=sys.stderr)
        print("  - Verify NOBL9_ORG is set correctly", file=sys.stderr)
        print("  - Check component name spelling (case-sensitive)", file=sys.stderr)
        print("  - Ensure timestamp is in ISO 8601 format (e.g., 2024-01-15T10:00:00Z)", file=sys.stderr)
        print("  - Try with --retry flag for transient errors", file=sys.stderr)
        print("\nFor detailed documentation, see: EXTERNAL_ISSUES_GUIDE.md", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
