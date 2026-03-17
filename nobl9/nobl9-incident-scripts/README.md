# Nobl9 Status Page: Scripts for Issues and Disruptions

Python scripts for reporting issues and managing **disruptions** on the Nobl9 Status Page (Mar 16 API). Component status is driven by disruptions; use these scripts to register or clear disruptions and to report issues from monitoring systems.

## Features

- **Report issues from monitoring** – External issue API (e.g. Prometheus, Datadog); `requestedBy` required; no status change in the API
- **Change component status** – Via disruptions: register (degraded/majorOutage) or clear (operational)
- **List disruptions** – Impacting, cleared, or timeline view
- **Workflows** – End-to-end disruption lifecycle and monitoring integration
- **Retry logic** – Automatic retry with backoff for transient API errors

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.7+.

### 2. Configure Credentials

```bash
cp .env.example .env
# Edit .env with your Nobl9 credentials
```

Get credentials from: https://app.nobl9.com → Settings → API Access

### 3. Test Connection

```bash
python3 test_connection.py
```

Expected: `✅ Configuration loaded` and `✅ Authentication successful!`

### 4. Run Scripts

**List disruptions (impacting or cleared):**
```bash
python3 -m examples.incidents.list_incidents --impacting
python3 -m examples.incidents.list_incidents --timeline
```

**Change component status (via disruptions):**
```bash
python3 -m examples.status_changes.change_status <component-id> majorOutage --comment "Service down"
python3 -m examples.status_changes.change_status <component-id> operational --comment "Resolved"
```

**Create external issue from monitoring (report only; use change_status or workflow to change status):**
```bash
python3 -m examples.issues.create_external_issue "Component Name" \
    --comment "High error rate detected" \
    --requested-by prometheus
```

**Full disruption workflow:**
```bash
python3 -m examples.workflows.incident_workflow <component-id> majorOutage
```

## Available Scripts

### Disruption listing
- `examples/incidents/list_incidents.py` – List disruptions (`--impacting`, `--cleared`, `--timeline`, `--limit`)

### Issue creation
- `examples/issues/create_issue.py` – Create user-reported issue
- `examples/issues/create_external_issue.py` – Create issue from monitoring (`--requested-by` required; no `--status` in API)
- `examples/issues/list_issues.py` – List issues
- `examples/issues/get_issue_summary.py` – Issue statistics

### Status (via disruptions)
- `examples/status_changes/change_status.py` – Set status by registering or clearing a disruption
- `examples/status_changes/get_status_history.py` – Component disruption history

### Workflows
- `examples/workflows/incident_workflow.py` – Disruption lifecycle (issue → register → list → clear → history)
- `examples/workflows/monitoring_integration.py` – External issue + optional register/clear disruption

## Authentication

**Client credentials (recommended)** – in `.env`:
```bash
NOBL9_CLIENT_ID=your_client_id_here
NOBL9_CLIENT_SECRET=your_client_secret_here
NOBL9_ORG=your_organization_id
```

**API token (alternative):**
```bash
NOBL9_API_TOKEN=your_token_here
NOBL9_ORG=your_organization_id
```

## Mar 16 API Notes

- **Status is driven by disruptions.** There is no `statusChange` in the external-issue request or response. To change component status, register or clear a disruption (e.g. via `change_status.py` or the workflow scripts).
- **External issues:** `requestedBy` is required (1–50 chars). Use `--requested-by` on the command line.
- **Disruption endpoints:** `GET/POST /status-page/disruptions`, `POST .../disruptions/{id}/clear`, `POST .../disruptions/timeline`.

## Monitoring integration (no statusChange in API)

Report an issue, then change status separately if needed:

```python
from examples.common import get_config, StatusPageClient

config = get_config()
client = StatusPageClient(config)

# 1. Report issue (no statusChange in payload)
client.post_external("/status-page/issues/external", {
    "componentName": "API Service",
    "occurredAt": "2026-03-16T12:00:00Z",
    "comment": "High error rate",
    "requestedBy": "datadog",
})

# 2. To change status: register or clear a disruption (e.g. via client.register_disruption / clear_disruption)
# Or run: python3 -m examples.status_changes.change_status <component-id> majorOutage --comment "..."
```

## Troubleshooting

- **Authentication failed** – Check `.env`, `NOBL9_ORG`, and client ID/secret or token.
- **Component not found** – Use `--list-components` (e.g. on `create_external_issue`) to see names; match case.
- **Module not found** – Run from the package root; use `python3 -m examples.xxx` syntax.

## Security

- Never commit `.env`. Commit only `.env.example` with placeholders.
- Use client credentials or tokens with minimal scope; rotate if exposed.

## Requirements

- Python 3.7+
- requests >= 2.31.0
- python-dotenv >= 1.0.0

## Support

- [Nobl9 Documentation](https://docs.nobl9.com)
- [API Reference](https://docs.nobl9.com/api)

---

**Version:** 2.0 (Mar 16 API – disruptions)  
**Last updated:** 2026-03-16
