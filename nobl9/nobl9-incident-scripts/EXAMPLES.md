# Usage Examples

Detailed examples for creating and managing incidents.

## Table of Contents

1. [Creating External Issues (Monitoring)](#creating-external-issues)
2. [Creating User Issues](#creating-user-issues)
3. [Changing Component Status](#changing-component-status)
4. [Listing Incidents](#listing-incidents)
5. [Complete Workflows](#complete-workflows)

---

## Creating External Issues

For automated monitoring systems (Datadog, Prometheus, etc.).

### Basic External Issue

```bash
python3 -m examples.issues.create_external_issue "My Component" \
    --comment "Service experiencing issues"
```

### With Status Change

```bash
python3 -m examples.issues.create_external_issue "API Service" \
    --status majorOutage \
    --comment "500 errors exceeding threshold" \
    --requested-by "monitoring-system"
```

### With Status Propagation

```bash
python3 -m examples.issues.create_external_issue "Database" \
    --status degradedPerformance \
    --comment "High query latency" \
    --propagate
```

### Full Example with All Options

```bash
python3 -m examples.issues.create_external_issue "Payment Service" \
    --status majorOutage \
    --comment "Payment processing failures: 95% error rate" \
    --occurred-at "2026-02-05T10:30:00Z" \
    --requested-by "datadog" \
    --propagate \
    --verify
```

---

## Creating User Issues

For manual incident reporting.

### Basic User Issue

```bash
# Get component ID first
python3 -m examples.components.list_components

# Create issue
python3 -m examples.issues.create_issue <component-id> \
    --comment "Users reporting slow page loads"
```

---

## Changing Component Status

Changes component status and automatically creates incidents.

### Change to Major Outage

```bash
python3 -m examples.status_changes.change_status <component-id> majorOutage \
    --comment "Service completely down"
```

### Change to Degraded Performance

```bash
python3 -m examples.status_changes.change_status <component-id> degradedPerformance \
    --comment "High latency observed"
```

### With Propagation to Parents

```bash
python3 -m examples.status_changes.change_status <component-id> partialOutage \
    --comment "Some features unavailable" \
    --propagate
```

### Restore to Operational

```bash
python3 -m examples.status_changes.change_status <component-id> operational \
    --comment "Service restored"
```

---

## Listing Incidents

View incident history with various filters.

### List All Incidents

```bash
python3 -m examples.incidents.list_incidents
```

### List Only Ongoing Incidents

```bash
python3 -m examples.incidents.list_incidents --ongoing
```

### List Only Resolved Incidents

```bash
python3 -m examples.incidents.list_incidents --resolved
```

---

## Complete Workflows

End-to-end incident management patterns.

### Incident Workflow

Complete lifecycle: Create issue → Change status → Resolve

```bash
python3 -m examples.workflows.incident_workflow <component-id> majorOutage
```

### Monitoring Integration Workflow

Simulates monitoring system alerts:

```bash
# Warning alert
python3 -m examples.workflows.monitoring_integration "Component Name" warning

# Critical alert
python3 -m examples.workflows.monitoring_integration "Component Name" critical

# Resolution
python3 -m examples.workflows.monitoring_integration "Component Name" resolved
```

---

## Monitoring System Integration

### Datadog Example

```bash
# In Datadog webhook handler
python3 -m examples.issues.create_external_issue "${COMPONENT_NAME}" \
    --status majorOutage \
    --comment "Alert: ${ALERT_NAME} - ${ALERT_MESSAGE}" \
    --requested-by "datadog"
```

### Prometheus Example

```bash
# In Alertmanager webhook receiver
python3 -m examples.issues.create_external_issue "${SERVICE_NAME}" \
    --status degradedPerformance \
    --comment "Alert: ${ALERT_NAME}" \
    --requested-by "prometheus"
```

### PagerDuty Example

```bash
# When incident created in PagerDuty
python3 -m examples.issues.create_external_issue "${AFFECTED_SERVICE}" \
    --status "${SEVERITY}" \
    --comment "PagerDuty Incident #${INCIDENT_ID}: ${TITLE}" \
    --requested-by "pagerduty"
```

---

## Python Integration

### Using in Your Python Code

```python
from examples.common import get_config, StatusPageClient

# Initialize
config = get_config()
client = StatusPageClient(config)

# Create external issue
result = client.post_external("/status-page/issues/external", {
    "componentName": "API Service",
    "occurredAt": "2026-02-05T10:30:00Z",
    "comment": "High error rate detected",
    "requestedBy": "monitoring-system",
    "statusChange": {
        "status": "majorOutage",
        "propagateUp": False
    }
})

print(f"Created {len(result['reports'])} issue report(s)")
```

---

## Advanced Usage

### Custom Retry Configuration

```python
from examples.common import get_config, StatusPageClient

config = get_config()

# More aggressive retries
client = StatusPageClient(
    config,
    max_retries=5,
    initial_backoff=2.0,
    max_backoff=60.0
)

result = client.get("/status-page/status")
```

### Error Handling

```python
from examples.common import (
    StatusPageClient,
    TransientAPIError,
    AuthenticationError,
    NotFoundError
)

try:
    result = client.post_external("/status-page/issues/external", data)
except TransientAPIError as e:
    print(f"API temporarily unavailable: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except NotFoundError as e:
    print(f"Component not found: {e}")
```

---

## Tips and Best Practices

1. **Use External Issues for Monitoring** - Automation-friendly API
2. **Verify Component Names** - Use `--verify` flag to check before creating
3. **Add Context in Comments** - Include alert details, metrics, etc.
4. **Use Descriptive Requested-By** - Identify monitoring system
5. **Propagate Carefully** - Only propagate when parent should be affected
6. **Test in Non-Production** - Verify integration before production

---

For more information, see the README.md and inline script documentation.
