#!/usr/bin/env python3
"""Complete disruption workflow demonstration (Mar 16 API).

Demonstrates disruption-driven status lifecycle:
1. Create an issue report for the component
2. Register a disruption (POST /status-page/disruptions) for the component
3. List impacting disruptions (GET /disruptions?state=impacting)
4. Clear the disruption (POST /disruptions/{id}/clear) using id from component impactingDisruption
5. Show disruption history via GET component details

Usage:
    python incident_workflow.py <component_id> <severity>

Arguments:
    component_id: UUID of the component
    severity: degradedPerformance or majorOutage

Example:
    python incident_workflow.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 degradedPerformance

Environment Variables:
    NOBL9_API_TOKEN or NOBL9_CLIENT_ID+NOBL9_CLIENT_SECRET, NOBL9_ORG (required)
"""
import sys
import time
from datetime import datetime, timezone

from examples.common import get_config, StatusPageClient, pretty_print, APIError
from examples.status_changes.change_status import _get_impacting_disruption_id_for_component


def run_disruption_workflow(
    client: StatusPageClient,
    component_id: str,
    severity: str,
) -> None:
    """Run complete disruption workflow (Mar 16 disruption-driven API)."""
    print("=" * 80)
    print("DISRUPTION WORKFLOW DEMONSTRATION (Mar 16 API)")
    print("=" * 80)

    # Step 1: Create issue report
    print("\n[Step 1] Creating issue report...")
    issue_payload = {
        "componentId": component_id,
        "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "comment": f"Detected issue - triggering {severity} incident",
    }
    issue = client.post("/status-page/issues", issue_payload)
    print(f"✅ Issue created: {issue.get('id')}")
    pretty_print(issue)

    time.sleep(1)

    # Step 2: Create incident (replaces old change-status)
    print(f"\n[Step 2] Registering disruption (severity={severity})...")
    disruption_payload = {
        "originComponentId": component_id,
        "severity": severity,
        "startTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "comment": "Disruption detected - investigating",
        "source": "manual",
    }
    client.register_disruption(disruption_payload)
    print("✅ Disruption registered (204)")

    time.sleep(1)

    # Step 3: List impacting disruptions
    print("\n[Step 3] Checking impacting disruptions...")
    result = client.get_disruptions({"state": "impacting", "limit": "50", "offset": "0"})
    disruptions = result.get("disruptions") or []
    total = result.get("total", len(disruptions))
    print(f"✅ Found {total} impacting disruption(s)")
    pretty_print(result)

    time.sleep(1)

    # Step 4: Issue summary
    print("\n[Step 4] Checking issue report summary...")
    summary = client.get("/status-page/issues/summary")
    total_issues = summary.get("totalCounts", {}).get("total", 0)
    print(f"✅ Total active issues: {total_issues}")

    time.sleep(1)

    # Step 5: Clear disruption (get id from component impactingDisruption, then clear)
    print("\n[Step 5] Clearing disruption...")
    disruption_id = _get_impacting_disruption_id_for_component(client, component_id)
    clear_payload = {
        "endTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "comment": "Issue resolved - service restored",
    }
    client.clear_disruption(disruption_id, clear_payload)
    print(f"✅ Disruption {disruption_id} cleared")

    time.sleep(1)

    # Step 6: Verify
    print("\n[Step 6] Verifying disruption clearance...")
    final_result = client.get_disruptions({"state": "impacting", "limit": "50", "offset": "0"})
    final_count = final_result.get("total", 0)
    print(f"✅ Remaining impacting disruptions: {final_count}")

    # Step 7: Disruption history (GET component details)
    print("\n[Step 7] Retrieving disruption history for component...")
    details = client.get(f"/status-page/components/{component_id}")
    impacting = details.get("impactingDisruption")
    history = details.get("disruptionHistory") or {}
    days_list = history.get("days") or []
    print(f"✅ Impacting disruption for component: {'present' if impacting else 'none'}")
    print(f"✅ 90-day disruption history: {len(days_list)} days with disruptions")
    if days_list:
        print("Recent days with disruptions:")
        for day in days_list[:5]:
            print(f"  - {day.get('date')}: {day.get('disruptions')} disruptions")

    print("\n" + "=" * 80)
    print("DISRUPTION WORKFLOW COMPLETED SUCCESSFULLY")
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

        run_disruption_workflow(client, component_id, severity)

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
