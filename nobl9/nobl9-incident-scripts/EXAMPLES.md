# Usage Examples

Examples for reporting issues and managing disruptions (Mar 16 API).

## Table of Contents

1. [External issues (monitoring)](#creating-external-issues)
2. [User-reported issues](#creating-user-issues)
3. [Changing component status (disruptions)](#changing-component-status)
4. [Listing disruptions](#listing-disruptions)
5. [Workflows](#workflows)
6. [Python integration](#python-integration)

---

## Creating External Issues

External issue API: report only. `requestedBy` is required (1–50 chars). There is no `statusChange` in the API; to change status, use the disruption scripts below.

### Basic external issue

```bash
python3 -m examples.issues.create_external_issue "My Component" \
    --comment "Service experiencing issues" \
    --requested-by "monitoring-system"
```

### With optional URL and timestamp

```bash
python3 -m examples.issues.create_external_issue "API Service" \
    --comment "500 errors exceeding threshold" \
    --requested-by "datadog" \
    --url "https://grafana.example.com/alert/123" \
    --occurred-at "2026-03-16T10:30:00Z"
```

### Verify component and list components

```bash
python3 -m examples.issues.create_external_issue "API Service" --comment "Test" --verify
python3 -m examples.issues.create_external_issue --list-components
```

---

## Creating User Issues

```bash
# List components first if needed
python3 -m examples.issues.create_external_issue --list-components

python3 -m examples.issues.create_issue <component-id> \
    --comment "Users reporting slow page loads"
```

---

## Changing Component Status

Status is driven by **disruptions**. Use `change_status` to register or clear a disruption.

### Set to degraded or major outage

```bash
python3 -m examples.status_changes.change_status <component-id> majorOutage \
    --comment "Service completely down"

python3 -m examples.status_changes.change_status <component-id> degradedPerformance \
    --comment "High latency observed"
```

### Restore to operational (clear disruption)

```bash
python3 -m examples.status_changes.change_status <component-id> operational \
    --comment "Service restored"
```

---

## Listing Disruptions

### List impacting disruptions

```bash
python3 -m examples.incidents.list_incidents --impacting
```

### List cleared disruptions

```bash
python3 -m examples.incidents.list_incidents --cleared --limit 20
```

### Day-grouped timeline

```bash
python3 -m examples.incidents.list_incidents --timeline
```

---

## Workflows

### Disruption workflow (full lifecycle)

```bash
python3 -m examples.workflows.incident_workflow <component-id> majorOutage
```

Runs: create issue → register disruption → list impacting → clear disruption → show history.

### Monitoring integration (external issue + optional disruption)

```bash
# Report issue and register disruption for "warning"
python3 -m examples.workflows.monitoring_integration "API Service" warning --requested-by prometheus

# Critical
python3 -m examples.workflows.monitoring_integration "Database" critical --requested-by datadog

# Resolved (clears disruption)
python3 -m examples.workflows.monitoring_integration "API Service" resolved
```

---

## Python Integration

### Report external issue (no statusChange)

```python
from examples.common import get_config, StatusPageClient

config = get_config()
client = StatusPageClient(config)

result = client.post_external("/status-page/issues/external", {
    "componentName": "API Service",
    "occurredAt": "2026-03-16T10:30:00Z",
    "comment": "High error rate detected",
    "requestedBy": "prometheus",
})
print(len(result.get("reports", [])), "report(s) created")
```

### Change status via disruptions

```python
from examples.common import get_config, StatusPageClient
from datetime import datetime, timezone

config = get_config()
client = StatusPageClient(config)
component_id = "<uuid>"

# Register disruption (degraded or majorOutage)
client.register_disruption({
    "originComponentId": component_id,
    "severity": "majorOutage",
    "startTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "comment": "Outage detected",
})

# Later: clear disruption (get id from component details or list_component_disruptions)
# client.clear_disruption(disruption_id, {"endTime": "...", "comment": "Resolved"})
```

### Error handling

```python
from examples.common import (
    StatusPageClient,
    TransientAPIError,
    AuthenticationError,
    NotFoundError,
)

try:
    result = client.post_external("/status-page/issues/external", data)
except TransientAPIError as e:
    print("API temporarily unavailable:", e)
except AuthenticationError as e:
    print("Authentication failed:", e)
except NotFoundError as e:
    print("Component not found:", e)
```

---

For more, see README.md and script docstrings.
