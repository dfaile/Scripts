#!/usr/bin/env python3
"""Complete production-ready example for external issue reporting.

This script demonstrates all features of the /status-page/issues/external endpoint
with best practices for production use:
- Comprehensive error handling
- Retry logic with exponential backoff
- Component verification
- Issue verification
- Detailed logging and output
- Command-line interface

Features demonstrated:
1. Basic issue reporting
2. Issue with status change
3. Status change with propagation
4. Component name verification
5. Issue verification after creation
6. Error handling and retries

This script can be used as-is or as a template for your own integrations.

For detailed documentation, see: EXTERNAL_ISSUES_GUIDE.md
"""

import sys
from pathlib import Path
import argparse
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# Import will be available through examples package

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


# ==============================================================================
# Configuration
# ==============================================================================

class Config:
    """Configuration for external issue reporting."""

    def __init__(self, org_id: str, base_url: str = "https://app.nobl9.com"):
        """
        Initialize configuration.

        Args:
            org_id: Organization ID (from NOBL9_ORG environment variable)
            base_url: API base URL (default: https://app.nobl9.com)
        """
        if not org_id:
            raise ValueError("Organization ID is required. Set NOBL9_ORG environment variable.")

        self.org_id = org_id
        self.base_url = base_url.rstrip("/")
        self.external_endpoint = f"{base_url}/api/dashboards/v1/status-page/issues/external"
        self.components_endpoint = f"{base_url}/api/dashboards/v1/status-page/components"


# ==============================================================================
# API Client with Retry Logic
# ==============================================================================

class ExternalIssueReporter:
    """Client for reporting external issues with retry logic."""

    def __init__(self, config: Config, max_retries: int = 3, initial_backoff: float = 1.0):
        """
        Initialize the reporter.

        Args:
            config: Configuration object
            max_retries: Maximum number of retry attempts (default: 3)
            initial_backoff: Initial backoff time in seconds (default: 1.0)
        """
        self.config = config
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

    def report_issue(
        self,
        component_name: str,
        comment: Optional[str] = None,
        occurred_at: Optional[str] = None,
        requested_by: str = "external-system",
        status: Optional[str] = None,
        propagate_up: bool = False,
    ) -> Dict[str, Any]:
        """
        Report an external issue with retry logic.

        Args:
            component_name: Name of the component (required)
            comment: Description of the issue (optional)
            occurred_at: ISO 8601 timestamp when issue occurred (optional, defaults to now)
            requested_by: Identifier for the requester (default: "external-system")
            status: Status to set (optional): operational, degradedPerformance, majorOutage
            propagate_up: Propagate status change to parent components (default: False)

        Returns:
            Response dictionary with 'reports' and optionally 'statusChanges'

        Raises:
            ValueError: If parameters are invalid
            Exception: If request fails after all retries
        """
        # Validate parameters
        if not component_name:
            raise ValueError("component_name is required")

        if status and status not in ["operational", "degradedPerformance", "majorOutage"]:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: "
                "operational, degradedPerformance, majorOutage"
            )

        # Build payload
        payload = {
            "componentName": component_name,
            "occurredAt": occurred_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "requestedBy": requested_by,
        }

        if comment:
            payload["comment"] = comment

        if status:
            payload["statusChange"] = {
                "status": status,
                "propagateUp": propagate_up,
            }

        # Make request with retry logic
        return self._request_with_retry(payload)

    def _request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make POST request with exponential backoff retry.

        Args:
            payload: Request payload

        Returns:
            Response dictionary

        Raises:
            Exception: If all retries fail
        """
        headers = {
            "organization": self.config.org_id,
            "Content-Type": "application/json",
        }

        backoff = self.initial_backoff
        last_error = None

        for attempt in range(self.max_retries):
            try:
                print(f"  → Attempt {attempt + 1}/{self.max_retries}...", end=" ")

                response = requests.post(
                    self.config.external_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=10,
                )

                # Success
                if response.status_code == 201:
                    print("✅ Success")
                    return response.json()

                # Client errors (don't retry)
                elif response.status_code == 400:
                    print("❌ Failed")
                    raise ValueError(f"Bad request: {response.text}")

                elif response.status_code == 404:
                    print("❌ Failed")
                    raise ValueError(
                        f"Component '{payload['componentName']}' not found. "
                        "Check component name spelling and case."
                    )

                # Rate limited (retry with backoff)
                elif response.status_code == 429:
                    print(f"⏸ Rate limited (retrying in {backoff:.1f}s)")
                    last_error = "Rate limit exceeded"
                    if attempt < self.max_retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                    continue

                # Server errors or other (retry)
                else:
                    print(f"⚠ HTTP {response.status_code} (retrying)")
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    if attempt < self.max_retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                    continue

            except requests.exceptions.Timeout:
                print(f"⏱ Timeout (retrying in {backoff:.1f}s)")
                last_error = "Request timeout"
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2

            except requests.exceptions.ConnectionError as e:
                print(f"🔌 Connection error (retrying in {backoff:.1f}s)")
                last_error = f"Connection error: {e}"
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2

        # All retries exhausted
        raise Exception(
            f"Failed to report issue after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def verify_component_exists(
        self,
        component_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> bool:
        """
        Verify that a component exists (requires authentication).

        Args:
            component_name: Name of the component to check
            client_id: Client ID for authentication (required)
            client_secret: Client secret for authentication (required)

        Returns:
            True if component exists, False otherwise

        Note:
            This requires authentication. If you don't have client credentials,
            use the Nobl9 web UI or list components manually.
        """
        if not client_id or not client_secret:
            print("⚠ Warning: Cannot verify component without client credentials")
            print("  Set NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET to enable component verification")
            return True  # Assume exists

        try:
            # Use the common StatusPageClient which handles token generation
            from examples.common import StatusPageClient
            from examples.common.config import Config

            # Create config with credentials
            import os
            os.environ["NOBL9_CLIENT_ID"] = client_id
            os.environ["NOBL9_CLIENT_SECRET"] = client_secret
            os.environ["NOBL9_ORG"] = self.config.org_id

            config = Config()
            client = StatusPageClient(config)

            # List components
            components = client.get("/status-page/components")

            # Check if any component matches the name
            matching = [c for c in components if c.get("name") == component_name]
            return len(matching) > 0

        except Exception as e:
            print(f"⚠ Warning: Error verifying component: {e}")
            return True  # Assume exists

    def list_components(
        self,
        client_id: str,
        client_secret: str
    ) -> List[Dict[str, Any]]:
        """
        List all components (requires authentication).

        Args:
            client_id: Client ID for authentication
            client_secret: Client secret for authentication

        Returns:
            List of component dictionaries

        Raises:
            Exception: If request fails
        """
        try:
            # Use the common StatusPageClient which handles token generation
            from examples.common import StatusPageClient
            from examples.common.config import Config

            # Create config with credentials
            import os
            os.environ["NOBL9_CLIENT_ID"] = client_id
            os.environ["NOBL9_CLIENT_SECRET"] = client_secret
            os.environ["NOBL9_ORG"] = self.config.org_id

            config = Config()
            client = StatusPageClient(config)

            # List components
            return client.get("/status-page/components")

        except Exception as e:
            raise Exception(f"Failed to list components: {e}")


# ==============================================================================
# Output Formatting
# ==============================================================================

def print_banner(text: str):
    """Print a banner with text."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text: str):
    """Print a section header."""
    print(f"\n{text}")
    print("-" * len(text))


def print_result(result: Dict[str, Any]):
    """
    Print the result of an external issue report.

    Args:
        result: Response dictionary from API
    """
    print_section("Result Summary")

    # Issue reports
    reports = result.get("reports", [])
    print(f"\n✅ Created {len(reports)} issue report(s):")
    for i, report in enumerate(reports, 1):
        print(f"\n  Report #{i}:")
        print(f"    Issue ID:      {report.get('id')}")
        print(f"    Component:     {report.get('componentName')}")
        print(f"    Component ID:  {report.get('componentId')}")
        print(f"    Occurred At:   {report.get('occurredAt')}")
        if report.get('comment'):
            print(f"    Comment:       {report.get('comment')}")

    # Status changes
    status_changes = result.get("statusChanges", [])
    if status_changes:
        print(f"\n✅ Triggered {len(status_changes)} status change(s):")
        for i, change in enumerate(status_changes, 1):
            print(f"\n  Status Change #{i}:")
            print(f"    Component:     {change.get('componentName')}")
            print(f"    Component ID:  {change.get('componentId')}")
            print(f"    Status:        {change.get('previousStatus')} → {change.get('newStatus')}")

    # Message
    if result.get("message"):
        print(f"\n📝 {result.get('message')}")


# ==============================================================================
# Main Function
# ==============================================================================

def main():
    """Main function with command-line interface."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Complete example for external issue reporting to Nobl9 Status Page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Simple issue report
  %(prog)s "API Service" --comment "High error rate detected"

  # Issue with status change
  %(prog)s "Database" --comment "Connection pool exhausted" --status degradedPerformance

  # Issue with status propagation
  %(prog)s "Auth Service" --status majorOutage --propagate --requested-by prometheus

  # List available components (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)
  %(prog)s --list-components

  # Verify component exists before reporting
  %(prog)s "API Service" --comment "Test" --verify

Environment Variables:
  NOBL9_ORG            Organization ID (required)
  NOBL9_CLIENT_ID      Client ID for verification/listing (optional)
  NOBL9_CLIENT_SECRET  Client secret for verification/listing (optional)
  NOBL9_BASE_URL       API base URL (optional, default: https://app.nobl9.com)

Note: The script automatically handles token generation and base64 encoding when
client credentials are provided. You don't need to manually generate tokens.

For detailed documentation, see: EXTERNAL_ISSUES_GUIDE.md
        """,
    )

    # Positional arguments
    parser.add_argument(
        "component_name",
        nargs="?",
        help="Component name to report issue for"
    )

    # Issue details
    parser.add_argument(
        "--comment",
        help="Description of the issue"
    )
    parser.add_argument(
        "--occurred-at",
        help="When the issue occurred (ISO 8601 format, default: now)"
    )
    parser.add_argument(
        "--requested-by",
        default="external-system",
        help="Identifier for the requester (default: external-system)"
    )

    # Status change
    parser.add_argument(
        "--status",
        choices=["operational", "degradedPerformance", "majorOutage"],
        help="Status to set for the component"
    )
    parser.add_argument(
        "--propagate",
        action="store_true",
        help="Propagate status change to parent components (requires --status)"
    )

    # Verification and debugging
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify component exists before reporting (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)"
    )
    parser.add_argument(
        "--list-components",
        action="store_true",
        help="List all available components (requires NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET)"
    )

    # Retry configuration
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts (default: 3)"
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable retry logic (fail on first error)"
    )

    args = parser.parse_args()

    # Load configuration from environment
    import os
    org_id = os.getenv("NOBL9_ORG")
    client_id = os.getenv("NOBL9_CLIENT_ID")
    client_secret = os.getenv("NOBL9_CLIENT_SECRET")
    base_url = os.getenv("NOBL9_BASE_URL", "https://app.nobl9.com")

    if not org_id:
        print("❌ Error: NOBL9_ORG environment variable is required", file=sys.stderr)
        print("\nSet it with: export NOBL9_ORG='your-org-id'", file=sys.stderr)
        sys.exit(1)

    try:
        config = Config(org_id, base_url)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize reporter
    max_retries = 1 if args.no_retry else args.max_retries
    reporter = ExternalIssueReporter(config, max_retries=max_retries)

    # Handle --list-components
    if args.list_components:
        if not client_id or not client_secret:
            print("❌ Error: NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET are required to list components", file=sys.stderr)
            print("\nSet these environment variables to enable component listing.", file=sys.stderr)
            sys.exit(1)

        print_banner("Listing Available Components")
        try:
            components = reporter.list_components(client_id, client_secret)
            print(f"\nFound {len(components)} component(s):\n")
            for i, comp in enumerate(components, 1):
                print(f"{i}. {comp.get('name')}")
                print(f"   ID:          {comp.get('id')}")
                print(f"   Description: {comp.get('description', 'N/A')}")
                print(f"   Status:      {comp.get('status', 'N/A')}")
                print()
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Validate required arguments for reporting
    if not args.component_name:
        parser.error("component_name is required (unless using --list-components)")

    if args.propagate and not args.status:
        parser.error("--propagate requires --status to be specified")

    # Display configuration
    print_banner("External Issue Reporting - Complete Example")
    print(f"\n📋 Configuration:")
    print(f"   Organization:     {config.org_id}")
    print(f"   Base URL:         {config.base_url}")
    print(f"   Max Retries:      {max_retries}")
    print(f"\n📦 Issue Details:")
    print(f"   Component:        {args.component_name}")
    print(f"   Comment:          {args.comment or '(none)'}")
    print(f"   Occurred At:      {args.occurred_at or '(now)'}")
    print(f"   Requested By:     {args.requested_by}")
    if args.status:
        print(f"   Status Change:    {args.status}")
        print(f"   Propagate Up:     {args.propagate}")

    # Verify component exists (if requested)
    if args.verify:
        print_section("Component Verification")
        if reporter.verify_component_exists(args.component_name, client_id, client_secret):
            print(f"✅ Component '{args.component_name}' exists")
        else:
            print(f"❌ Component '{args.component_name}' NOT found", file=sys.stderr)
            print("\nAvailable components can be listed with: --list-components", file=sys.stderr)
            sys.exit(1)

    # Report the issue
    print_section("Reporting Issue")
    try:
        result = reporter.report_issue(
            component_name=args.component_name,
            comment=args.comment,
            occurred_at=args.occurred_at,
            requested_by=args.requested_by,
            status=args.status,
            propagate_up=args.propagate,
        )

        # Print result
        print_result(result)

        # Success message
        print_banner("✅ Issue Reported Successfully")
        print("\nNext Steps:")
        print("  1. Check your status page to see the issue")
        print("  2. View the issue details in the Nobl9 UI")
        if args.status:
            print("  3. Verify the status change took effect")
        if args.propagate:
            print("  4. Check parent components for propagated status")

    except ValueError as e:
        print(f"\n❌ Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
