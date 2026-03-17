#!/usr/bin/env python3
"""External monitoring + disruption integration example (Mar 16 API).

Demonstrates:
1. Receiving an alert payload from a monitoring system
2. Creating an external issue report (requestedBy required; no statusChange in API)
3. Creating or clearing a disruption separately to change component status
   (resolve component name to id, then POST /status-page/disruptions or
    POST /status-page/disruptions/{id}/clear).

Usage:
    python monitoring_integration.py <component_name> <alert_severity> [--requested-by ID]

Arguments:
    component_name: Name of the component (may match multiple)
    alert_severity: warning, critical, or resolved

Options:
    --requested-by: Required by API (1-50 chars). Default: prometheus-alertmanager
    --url: Optional link to source alert (uri, max 2048)

Examples:
    python monitoring_integration.py "API Service" warning --requested-by prometheus
    python monitoring_integration.py "Database" critical

Environment Variables:
    NOBL9_ORG (required). NOBL9_CLIENT_ID + NOBL9_CLIENT_SECRET for auth.
"""
import sys
from datetime import datetime, timezone

from examples.common import get_config, StatusPageClient, pretty_print, APIError


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
    """Map alert severity to disruption-driven component status."""
    mapping = {
        "warning": "degradedPerformance",
        "critical": "majorOutage",
        "resolved": "operational",
    }
    return mapping.get(alert_severity.lower(), "degradedPerformance")


def _flatten_components(components: list) -> list:
    """Recursively flatten component tree to list of dicts."""
    out = []
    for c in components:
        out.append(c)
        if c.get("children"):
            out.extend(_flatten_components(c["children"]))
    return out


def _component_ids_by_name(client: StatusPageClient, component_name: str) -> list:
    """Resolve component name to list of component IDs (may match multiple)."""
    resp = client.get("/status-page/components")
    flat = _flatten_components(resp.get("components") or [])
    return [c["id"] for c in flat if c.get("name") == component_name]


def simulate_monitoring_alert(
    client: StatusPageClient,
    component_name: str,
    alert_severity: str,
    requested_by: str,
    url: str = None,
    monitoring_system: str = "prometheus",
) -> None:
    """Create external issue (requestedBy required; no statusChange). Optionally register/clear disruptions."""
    print("=" * 80)
    print("EXTERNAL MONITORING + DISRUPTIONS INTEGRATION (Mar 16 API)")
    print("=" * 80)

    print(f"\n[Step 1] Receiving alert from {monitoring_system}...")
    alert_payload = ALERT_EXAMPLES.get(monitoring_system, ALERT_EXAMPLES["prometheus"])
    pretty_print(alert_payload)

    print(f"\n[Step 2] Processing alert...")
    component_status = map_severity_to_status(alert_severity)
    print(f"Alert severity: {alert_severity} → derived status: {component_status}")

    print(f"\n[Step 3] Creating external issue report for '{component_name}' (requestedBy required)...")
    if monitoring_system == "prometheus":
        comment = f"[{alert_payload['alertname']}] {alert_payload['summary']}: {alert_payload['description']}"
    else:
        comment = f"[{alert_payload['alert_type']}] {alert_payload['title']}: {alert_payload['message']}"

    issue_payload = {
        "componentName": component_name,
        "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requestedBy": requested_by[:50],
        "comment": comment,
    }
    if url:
        issue_payload["url"] = url[:2048]
    pretty_print(issue_payload)

    result = client.post_external("/status-page/issues/external", issue_payload)

    print("\n[Step 4] External issue result:")
    pretty_print(result)

    reports = result.get("reports", [])
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Created {len(reports)} issue report(s)")
    for report in reports:
        print(f"   - Issue ID: {report.get('id')}  Component ID: {report.get('componentId')}")

    # Optional: create or clear disruptions to reflect severity (no statusChange in external issue)
    if alert_severity.lower() in ("warning", "critical", "resolved"):
        try:
            comp_ids = _component_ids_by_name(client, component_name)
            if not comp_ids:
                print("\nℹ️  No components matched by name; skipping incident create/resolve.")
            else:
                if component_status in ("degradedPerformance", "majorOutage"):
                    for cid in comp_ids:
                        client.register_disruption(
                            {
                                "originComponentId": cid,
                                "severity": component_status,
                                "startTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                "comment": comment[:500] if comment else None,
                                "source": "external",
                            }
                        )
                    print(f"✅ Registered disruption(s) for {len(comp_ids)} component(s)")
                elif component_status == "operational":
                    from examples.status_changes.change_status import _get_impacting_disruption_id_for_component

                    for cid in comp_ids:
                        try:
                            disruption_id = _get_impacting_disruption_id_for_component(client, cid)
                            client.clear_disruption(
                                disruption_id,
                                {
                                    "endTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                    "comment": "Resolved via monitoring integration",
                                },
                            )
                            print(f"✅ Cleared disruption for component {cid}")
                        except Exception:
                            # If there is no impacting disruption, skip silently
                            continue
        except Exception as e:
            print(f"\nℹ️  Incident create/resolve skipped: {e}")

    print("=" * 80)


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description="External monitoring integration (Mar 5 API)")
    parser.add_argument("component_name", help="Component name to match")
    parser.add_argument("alert_severity", choices=["warning", "critical", "resolved"],
                        help="Alert severity")
    parser.add_argument("--requested-by", default="prometheus-alertmanager",
                        help="Requester id (required by API, 1-50 chars)")
    parser.add_argument("--url", help="Optional link to source alert (uri, max 2048)")
    parser.add_argument("--monitoring-system", default="prometheus", choices=["prometheus", "datadog"])
    args = parser.parse_args()

    requested_by = (args.requested_by or "prometheus-alertmanager").strip()
    if not requested_by or len(requested_by) > 50:
        print("Error: --requested-by must be 1-50 characters", file=sys.stderr)
        sys.exit(1)

    try:
        config = get_config()
        client = StatusPageClient(config)
        simulate_monitoring_alert(
            client,
            args.component_name,
            args.alert_severity,
            requested_by,
            url=args.url,
            monitoring_system=args.monitoring_system,
        )
    except APIError as e:
        print(f"\n❌ API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
