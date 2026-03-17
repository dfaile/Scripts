# Changelog

## 2.0 (Mar 16 API – disruptions)

- **Status driven by disruptions.** Component status is no longer changed via the external-issue API. Use `POST /status-page/disruptions` to register and `POST /status-page/disruptions/{id}/clear` to clear. Scripts `change_status.py`, `incident_workflow.py`, and `monitoring_integration.py` use these endpoints.
- **External issues:** `requestedBy` is required (1–50 chars). Removed `statusChange` and `statusChanges` from request and response; the API does not support them. To change status after reporting an issue, call the disruption APIs or run `change_status.py`.
- **List script:** `list_incidents.py` now lists **disruptions** via `GET /status-page/disruptions` with options `--impacting`, `--cleared`, `--timeline`, `--limit`.
- **Client:** Added `get_disruptions`, `get_disruptions_timeline`, `register_disruption`, `clear_disruption`, `change_disruption_severity`, `list_component_disruptions` to `StatusPageClient`.

## 1.0

- Initial release (incident-based API; external issues with optional statusChange).
