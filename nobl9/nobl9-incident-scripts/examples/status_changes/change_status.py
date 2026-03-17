#!/usr/bin/env python3
"""Change the status of a component via the disruption-driven API (Mar 16+).

Component status is driven by disruptions. This script:
- degradedPerformance / majorOutage: registers a disruption (POST /status-page/disruptions).
- operational: clears the current impacting disruption for this component
  (GET component details for impactingDisruption, or POST /components/{id}/disruptions,
   then POST /disruptions/{id}/clear).

Propagation to parent components is handled by the API when creating incidents.
No propagateUp option (removed in Mar 5 API).

Usage:
    python change_status.py <component_id> <status> [options]

Arguments:
    component_id: UUID of the component
    status: New status (operational, degradedPerformance, majorOutage)

Options:
    --comment TEXT: Comment (creation comment for new incident, or resolution comment when resolving)

Examples:
    # Mark component as degraded
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 degradedPerformance --comment "High latency"

    # Resolve (find open incident for component and resolve it)
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 operational --comment "Service restored"

    # Report major outage
    python change_status.py 4c91326b-81f3-47aa-b2b7-da2d1da3e298 majorOutage --comment "Service unavailable"

Environment Variables:
    NOBL9_API_TOKEN / NOBL9_CLIENT_ID+NOBL9_CLIENT_SECRET, NOBL9_ORG (required)
"""
import sys
import argparse
from datetime import datetime, timezone

from examples.common import get_config, StatusPageClient, pretty_print, APIError, NotFoundError


def _get_impacting_disruption_id_for_component(client: StatusPageClient, component_id: str) -> str:
    """Get the encoded disruption id of the current impacting disruption for this component.

    Uses GET /status-page/components/{id} and reads impactingDisruption; falls back to
    POST /status-page/components/{id}/disruptions with state=impacting if needed.

    Returns:
        Encoded disruption id.

    Raises:
        NotFoundError: If no impacting disruption found for this component.
    """
    details = client.get(f"/status-page/components/{component_id}")
    impacting = details.get("impactingDisruption")
    if impacting and impacting.get("id"):
        return impacting["id"]

    # Fallback: list disruptions for this component filtered by impacting state
    body = {"state": "impacting", "limit": 1}
    result = client.list_component_disruptions(component_id, body)
    disruptions = result.get("disruptions") or []
    if disruptions:
        disruption_id = disruptions[0].get("id")
        if disruption_id:
            return disruption_id
    raise NotFoundError(
        f"No impacting disruption found for component {component_id}. "
        "Register a disruption first (e.g. set status to degradedPerformance or majorOutage)."
    )


def change_status(
    client: StatusPageClient,
    component_id: str,
    status: str,
    comment: str = None,
) -> dict:
    """Change component status via disruptions (Mar 16 API).

    - operational: clears an impacting disruption for this component.
    - degradedPerformance / majorOutage: registers a new disruption.

    Args:
        client: StatusPageClient instance.
        component_id: UUID of the component.
        status: New status (operational, degradedPerformance, majorOutage).
        comment: Optional comment (for register or clear).

    Returns:
        Summary dict for display (no body for 204 create/resolve).
    """
    if status == "operational":
        disruption_id = _get_impacting_disruption_id_for_component(client, component_id)
        payload = {"endTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        if comment:
            payload["comment"] = comment
        client.clear_disruption(disruption_id, payload)
        return {
            "componentId": component_id,
            "clearedDisruptionId": disruption_id,
            "newStatus": "operational",
            "comment": comment,
        }

    if status in ("degradedPerformance", "majorOutage"):
        payload = {
            "originComponentId": component_id,
            "severity": status,
            "startTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if comment:
            payload["comment"] = comment
        client.register_disruption(payload)
        return {"componentId": component_id, "newStatus": status, "comment": comment}
    raise ValueError(f"Invalid status: {status}. Use operational, degradedPerformance, or majorOutage.")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Change component status via disruptions (Mar 16 API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python change_status.py abc123 degradedPerformance --comment "High latency"
  python change_status.py abc123 operational --comment "Resolved"
        """,
    )
    parser.add_argument("component_id", help="Component UUID")
    parser.add_argument(
        "status",
        choices=["operational", "degradedPerformance", "majorOutage"],
        help="New status",
    )
    parser.add_argument("--comment", help="Comment for the change")

    args = parser.parse_args()

    try:
        config = get_config()
        client = StatusPageClient(config)

        print(f"Changing status of component {args.component_id} to {args.status}...")
        result = change_status(client, args.component_id, args.status, args.comment)

        print("\nResult:")
        print("=" * 80)
        pretty_print(result)
        print("\n✅ Status changed successfully!")

    except NotFoundError as e:
        print(f"Not found: {e}", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
