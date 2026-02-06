# Nobl9 Status Page: Incident Creation Scripts

Python scripts for creating and managing incidents on the Nobl9 Status Page.

## Features

✅ **Create Incidents from Monitoring Systems** - External issue API for automation
✅ **Create User-Reported Incidents** - Manual issue reporting
✅ **Change Component Status** - Automatically creates incidents
✅ **List and Filter Incidents** - View incident history
✅ **Complete Workflow Examples** - End-to-end patterns
✅ **Automatic Retry Logic** - Resilient to transient API errors

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required: Python 3.7 or higher

### 2. Configure Credentials

```bash
cp .env.example .env
# Edit .env with your Nobl9 credentials
```

Get your credentials from: https://app.nobl9.com → Settings → API Access

### 3. Test Connection

```bash
python3 test_connection.py
```

Expected output:
```
✅ Configuration loaded
✅ Authentication successful!
```

### 4. Create Your First Incident

#### List existing incidents:
```bash
python3 -m examples.incidents.list_incidents
```

#### Change component status (creates incident):
```bash
python3 -m examples.status_changes.change_status <component-id> majorOutage --comment "Service down"
```

#### Create external issue from monitoring:
```bash
python3 -m examples.issues.create_external_issue "Component Name" \
    --status majorOutage \
    --comment "High error rate detected"
```

## Available Scripts

### Incident Management
- `examples/incidents/list_incidents.py` - List and filter incidents (--ongoing, --resolved)

### Issue Creation
- `examples/issues/create_issue.py` - Create user-reported issue
- `examples/issues/create_external_issue.py` - Create issue from monitoring system
- `examples/issues/list_issues.py` - List all issues
- `examples/issues/get_issue_summary.py` - Get issue statistics

### Status Changes
- `examples/status_changes/change_status.py` - Change component status (triggers incident)
- `examples/status_changes/get_status_history.py` - View status change history

### Workflows
- `examples/workflows/incident_workflow.py` - Complete incident lifecycle
- `examples/workflows/monitoring_integration.py` - Monitoring integration pattern

## Authentication

### Client Credentials (Recommended)

In your `.env` file:
```bash
NOBL9_CLIENT_ID=your_client_id_here
NOBL9_CLIENT_SECRET=your_client_secret_here
NOBL9_ORG=your_organization_id
```

### API Token (Alternative)

```bash
NOBL9_API_TOKEN=your_token_here
NOBL9_ORG=your_organization_id
```

## Usage Examples

### Create Incident from Monitoring Alert

```bash
# Datadog, Prometheus, etc. → Nobl9
python3 -m examples.issues.create_external_issue "API Service" \
    --status majorOutage \
    --comment "500 errors >50%" \
    --requested-by "datadog"
```

### Change Status with Propagation

```bash
# Change status and propagate to parent components
python3 -m examples.status_changes.change_status <component-id> degradedPerformance \
    --comment "High latency detected" \
    --propagate
```

### Complete Incident Workflow

```bash
# Create issue → Change status → Update → Resolve
python3 -m examples.workflows.incident_workflow <component-id> majorOutage
```

### List Ongoing Incidents

```bash
python3 -m examples.incidents.list_incidents --ongoing
```

## Features

### Automatic Retry with Exponential Backoff

All scripts include automatic retry for transient API errors (502, 503):
- Default: 3 retries with exponential backoff
- Configurable via StatusPageClient parameters
- Transparent to users

### Error Handling

- **401 Unauthorized** - Check credentials
- **404 Not Found** - Verify component ID
- **502/503** - Automatic retry with backoff
- **429 Rate Limit** - Wait and retry

## Monitoring Integration Examples

### Datadog Webhook

```python
# In your Datadog webhook handler
from examples.common import get_config, StatusPageClient

config = get_config()
client = StatusPageClient(config)

# On alert trigger
client.post_external("/status-page/issues/external", {
    "componentName": "API Service",
    "occurredAt": alert_time,
    "comment": f"Alert: {alert_message}",
    "requestedBy": "datadog",
    "statusChange": {
        "status": "majorOutage",
        "propagateUp": False
    }
})
```

### Prometheus Alertmanager

```python
# In Alertmanager webhook receiver
from examples.issues.create_external_issue import create_external_issue

# On firing alert
create_external_issue(
    component_name="Database",
    status="degradedPerformance",
    comment=f"Alert: {alert_name}",
    requested_by="prometheus"
)
```

## Troubleshooting

### "Authentication failed"
- Verify credentials in `.env` file
- Check organization ID is correct
- Ensure Client ID and Secret match

### "Component not found"
- List components to get valid IDs
- Verify component name spelling (for external issues)

### "Module not found"
- Run from package root directory
- Use `python3 -m examples.` syntax
- Verify all `__init__.py` files are present

### Retry messages appearing
- Normal during API instability
- Scripts automatically retry transient errors
- No action needed unless all retries fail

## Requirements

- Python 3.7 or higher
- requests >= 2.31.0
- python-dotenv >= 1.0.0

See `requirements.txt` for full dependency list.

## Security Best Practices

✅ Never commit `.env` file to version control
✅ Use client credentials (not API tokens) for production
✅ Rotate credentials periodically
✅ Use separate credentials per environment
✅ Store credentials securely (vault, secrets manager)

## Support

For assistance:
- **Nobl9 Documentation**: https://docs.nobl9.com
- **API Reference**: https://docs.nobl9.com/api
- **Support Email**: support@nobl9.com

## License

Contact your Nobl9 representative for licensing information.

---

**Version:** 1.0
**Last Updated:** 2026-02-05
