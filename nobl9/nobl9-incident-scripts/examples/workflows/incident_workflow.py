#!/usr/bin/env python3
"""Complete incident workflow demonstration.

This script demonstrates a complete incident lifecycle:
1. Create an issue report for a component
2. Change component status to degraded/outage
3. Monitor issue count
4. Resolve the incident by returning to operational status

This workflow shows how to manage an incident from detection to resolution.

Usage:
    python incident_workflow.py <component_id> <severity>

Arguments:
    component_id: UUID of the component
    severity: Incident severity (degradedPerformance or majorOutage)

Example:
    python incident_workflow.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 degradedPerformance

Environment Variables:
    NOBL9_API_TOKEN: Your Nobl9 API token (required)
    NOBL9_ORG: Your organization ID (required)
"""
import sys
import time
from datetime import datetime

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def run_incident_workflow(
    client: StatusPageClient,
    component_id: str,
    severity: str,
) -> None:
    """Run complete incident workflow.

    Args:
        client: StatusPageClient instance.
        component_id: Component UUID.
        severity: Incident severity.
    """
    print("=" * 80)
    print("INCIDENT WORKFLOW DEMONSTRATION")
    print("=" * 80)

    # Step 1: Create issue report
    print("\n[Step 1] Creating issue report...")
    issue_payload = {
        "componentId": component_id,
        "occurredAt": datetime.utcnow().isoformat() + "Z",
        "comment": f"Detected issue - triggering {severity} incident",
    }
    issue = client.post("/status-page/issues", issue_payload)
    print(f"✅ Issue created: {issue.get('id')}")
    pretty_print(issue)

    time.sleep(1)

    # Step 2: Change status to trigger incident
    print(f"\n[Step 2] Changing component status to {severity}...")
    status_change_payload = {
        "status": severity,
        "comment": "Incident detected - investigating",
        "propagateUp": False,
    }
    status_change = client.post(
        f"/status-page/components/{component_id}/change-status",
        status_change_payload,
    )
    print(f"✅ Status changed from {status_change.get('previousStatus')} to {status_change.get('newStatus')}")
    pretty_print(status_change)

    time.sleep(1)

    # Step 3: Check ongoing incidents
    print("\n[Step 3] Checking ongoing incidents...")
    incidents = client.get("/status-page/incidents", {"ongoing": "true"})
    ongoing_count = sum(day.get("count", 0) for day in incidents.get("days", []))
    print(f"✅ Found {ongoing_count} ongoing incident(s)")
    pretty_print(incidents)

    time.sleep(1)

    # Step 4: Get issue summary
    print("\n[Step 4] Checking issue report summary...")
    summary = client.get("/status-page/issues/summary")
    total = summary.get("totalCounts", {}).get("total", 0)
    print(f"✅ Total active issues: {total}")

    time.sleep(1)

    # Step 5: Simulate investigation and create update
    print("\n[Step 5] Adding investigation update (simulated)...")
    print("   (In production, you might create additional issue reports here)")
    time.sleep(2)

    # Step 6: Resolve incident
    print("\n[Step 6] Resolving incident - returning to operational status...")
    resolve_payload = {
        "status": "operational",
        "comment": "Issue resolved - service restored",
        "propagateUp": False,
    }
    resolved = client.post(
        f"/status-page/components/{component_id}/change-status",
        resolve_payload,
    )
    print(f"✅ Status changed from {resolved.get('previousStatus')} to {resolved.get('newStatus')}")
    pretty_print(resolved)

    time.sleep(1)

    # Step 7: Verify incident is resolved
    print("\n[Step 7] Verifying incident resolution...")
    final_incidents = client.get("/status-page/incidents", {"ongoing": "true"})
    final_count = sum(day.get("count", 0) for day in final_incidents.get("days", []))
    print(f"✅ Remaining ongoing incidents: {final_count}")

    # Step 8: Get status history
    print("\n[Step 8] Retrieving status history...")
    history = client.get(f"/status-page/components/{component_id}/status-changes")
    history_count = len(history.get("history", []))
    print(f"✅ Status history contains {history_count} record(s)")
    print("\nRecent status changes:")
    for change in history.get("history", [])[:5]:  # Show last 5
        print(f"  - {change.get('changedAt')}: {change.get('previousStatus')} → {change.get('newStatus')}")
        if change.get("comment"):
            print(f"    Comment: {change.get('comment')}")

    print("\n" + "=" * 80)
    print("INCIDENT WORKFLOW COMPLETED SUCCESSFULLY")
    print("=" * 80)


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python incident_workflow.py <component_id> <severity>", file=sys.stderr)
        print("\nSeverity options: degradedPerformance, majorOutage")
        print("\nExample:")
        print("  python incident_workflow.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 degradedPerformance")
        sys.exit(1)

    component_id = sys.argv[1]
    severity = sys.argv[2]

    if severity not in ["degradedPerformance", "majorOutage"]:
        print("Error: Severity must be 'degradedPerformance' or 'majorOutage'", file=sys.stderr)
        sys.exit(1)

    try:
        config = get_config()
        client = StatusPageClient(config)

        run_incident_workflow(client, component_id, severity)

    except APIError as e:
        print(f"\n❌ API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
