#!/usr/bin/env python3
"""External monitoring system integration example.

This script simulates an external monitoring system (e.g., Prometheus, Datadog)
integrating with the Nobl9 Status Page API. It demonstrates:
1. Receiving an alert payload from a monitoring system
2. Creating an external issue report
3. Triggering status changes based on alert severity

This example shows how to integrate external monitoring tools with the status page.

Usage:
    python monitoring_integration.py <component_name> <alert_severity>

Arguments:
    component_name: Name of the component (will match all components with this name)
    alert_severity: Alert severity level (warning, critical, resolved)

Examples:
    # Warning alert - trigger degraded performance
    python monitoring_integration.py "API Service" warning

    # Critical alert - trigger major outage
    python monitoring_integration.py "Database" critical

    # Resolution - return to operational
    python monitoring_integration.py "API Service" resolved

Environment Variables:
    NOBL9_ORG: Your organization ID (required)
    NOBL9_BASE_URL: API base URL (optional)

Note: This endpoint does NOT require NOBL9_API_TOKEN.
"""
import sys
import json
from datetime import datetime

from examples.common import StatusPageClient, pretty_print, APIError
from examples.common.config import Config


# Simulated alert payloads from external systems
ALERT_EXAMPLES = {
    "prometheus": {
        "alertname": "HighErrorRate",
        "instance": "api-service-1",
        "severity": "critical",
        "summary": "Error rate above 5%",
        "description": "The API service is experiencing high error rates",
    },
    "datadog": {
        "alert_id": "12345",
        "alert_type": "metric alert",
        "title": "High CPU Usage",
        "message": "CPU usage exceeded 90% threshold",
        "priority": "P1",
    },
}


def map_severity_to_status(alert_severity: str) -> str:
    """Map alert severity to component status.

    Args:
        alert_severity: Alert severity (warning, critical, resolved).

    Returns:
        Component status.
    """
    mapping = {
        "warning": "degradedPerformance",
        "critical": "majorOutage",
        "resolved": "operational",
    }
    return mapping.get(alert_severity.lower(), "degradedPerformance")


def simulate_monitoring_alert(
    client: StatusPageClient,
    component_name: str,
    alert_severity: str,
    monitoring_system: str = "prometheus",
) -> None:
    """Simulate receiving and processing a monitoring alert.

    Args:
        client: StatusPageClient instance.
        component_name: Component name to report for.
        alert_severity: Alert severity.
        monitoring_system: Which monitoring system (prometheus/datadog).
    """
    print("=" * 80)
    print("EXTERNAL MONITORING INTEGRATION DEMONSTRATION")
    print("=" * 80)

    # Step 1: Receive alert from monitoring system
    print(f"\n[Step 1] Receiving alert from {monitoring_system}...")
    alert_payload = ALERT_EXAMPLES.get(monitoring_system, ALERT_EXAMPLES["prometheus"])
    print("Alert payload:")
    pretty_print(alert_payload)

    # Step 2: Map alert to component and status
    print(f"\n[Step 2] Processing alert...")
    component_status = map_severity_to_status(alert_severity)
    print(f"Alert severity: {alert_severity} → Component status: {component_status}")

    # Step 3: Create external issue report with status change
    print(f"\n[Step 3] Creating external issue report for '{component_name}'...")

    # Build comment from alert data
    if monitoring_system == "prometheus":
        comment = f"[{alert_payload['alertname']}] {alert_payload['summary']}: {alert_payload['description']}"
    else:
        comment = f"[{alert_payload['alert_type']}] {alert_payload['title']}: {alert_payload['message']}"

    # Create external issue with status change
    issue_payload = {
        "componentName": component_name,
        "occurredAt": datetime.utcnow().isoformat() + "Z",
        "comment": comment,
        "requestedBy": monitoring_system,
    }

    # Only include status change if not already operational
    if component_status != "operational" or alert_severity == "resolved":
        issue_payload["statusChange"] = {
            "status": component_status,
            "propagateUp": alert_severity == "critical",  # Propagate critical alerts
        }

    print("External issue payload:")
    pretty_print(issue_payload)

    result = client.post_external("/status-page/issues/external", issue_payload)

    print("\n[Step 4] External issue result:")
    pretty_print(result)

    # Step 5: Summary
    reports = result.get("reports", [])
    status_changes = result.get("statusChanges", [])

    print("\n" + "=" * 80)
    print("INTEGRATION SUMMARY")
    print("=" * 80)
    print(f"✅ Created {len(reports)} issue report(s)")
    for report in reports:
        print(f"   - Issue ID: {report.get('id')}")
        print(f"     Component ID: {report.get('componentId')}")

    if status_changes:
        print(f"✅ Triggered {len(status_changes)} status change(s)")
        for change in status_changes:
            print(f"   - Component: {change.get('componentName')}")
            print(f"     Status: {change.get('previousStatus')} → {change.get('newStatus')}")
    else:
        print("ℹ️  No status changes triggered")

    print("\n💡 Next steps:")
    if alert_severity in ["warning", "critical"]:
        print("   - Monitoring system continues to track the issue")
        print("   - When resolved, send another alert with severity 'resolved'")
        print(f"   - Example: python {sys.argv[0]} '{component_name}' resolved")
    else:
        print("   - Issue has been resolved")
        print("   - Component status restored to operational")

    print("=" * 80)


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python monitoring_integration.py <component_name> <alert_severity>", file=sys.stderr)
        print("\nAlert severity options: warning, critical, resolved")
        print("\nExamples:")
        print('  python monitoring_integration.py "API Service" warning')
        print('  python monitoring_integration.py "Database" critical')
        print('  python monitoring_integration.py "API Service" resolved')
        sys.exit(1)

    component_name = sys.argv[1]
    alert_severity = sys.argv[2]

    if alert_severity.lower() not in ["warning", "critical", "resolved"]:
        print("Error: Alert severity must be 'warning', 'critical', or 'resolved'", file=sys.stderr)
        sys.exit(1)

    # Allow optional monitoring system argument
    monitoring_system = sys.argv[3] if len(sys.argv) > 3 else "prometheus"
    if monitoring_system not in ALERT_EXAMPLES:
        print(f"Warning: Unknown monitoring system '{monitoring_system}', using 'prometheus'")
        monitoring_system = "prometheus"

    try:
        # Only organization is required for external endpoint
        config = Config()
        if not config.organization:
            raise ValueError("NOBL9_ORG environment variable is required")

        client = StatusPageClient(config)

        simulate_monitoring_alert(client, component_name, alert_severity, monitoring_system)

    except APIError as e:
        print(f"\n❌ API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
