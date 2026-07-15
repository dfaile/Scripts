# AGENTS.md

## Cursor Cloud specific instructions

This repo is a monorepo of **client CLI tools** for the **Nobl9 SaaS API**
(`https://app.nobl9.com`). There is **no local server, database, or container** to
run — every tool authenticates against and calls the external Nobl9 cloud. Full
end-to-end runs therefore require valid Nobl9 credentials; without them the tools
still execute their full request path and fail only at the auth boundary (a real
`401` from Nobl9, which confirms network + code path are healthy).

### Products & where they live

| Product | Path | Language | Run command (from that dir) |
|---|---|---|---|
| A — SLO tools for CI/CD | `nobl9/` (`Nobl9_*.py`) | Python 3 | `python3 Nobl9_SLO_Info.py --help` |
| B — Status Page / incident scripts | `nobl9/nobl9-incident-scripts/` | Python 3 | `python3 -m examples.incidents.list_incidents --help` (must run from package root using `-m examples.xxx`) |
| C — User Role Manager | `nobl9/nobl9-user-role/` | Go | `go build -o add-user-role main.go` then `./add-user-role --help` |

### Toolchains (already installed in the VM snapshot)

- **Go 1.24.4** at `/usr/local/go` (symlinked into `/usr/local/bin`). The system
  `apt` Go is 1.22 at `/usr/lib/go-1.22`; do **not** use it — `go.mod` requires
  `go 1.24`. `which go` should resolve to `/usr/local/bin/go`.
- **Python 3.12** with `requests`, `python-dotenv`, `pytest` installed via
  `pip --break-system-packages` (PEP 668 externally-managed). `python3` picks
  these up directly — no virtualenv is used. `pytest`/`dotenv` console scripts
  live in `~/.local/bin` (not on `PATH` by default; invoke via `python3 -m ...`).

### Credentials for full end-to-end

Set these env vars (or the per-product config files) before running against the
real API:
- Products A & C: `NOBL9_CLIENT_ID`, `NOBL9_CLIENT_SECRET` (Product A also accepts
  them as `--client-id` / `--client-secret` flags).
- Product B: `NOBL9_CLIENT_ID`, `NOBL9_CLIENT_SECRET`, `NOBL9_ORG` (or
  `NOBL9_API_TOKEN` + `NOBL9_ORG`). Copy `nobl9-incident-scripts/.env.example`
  to `.env` for local use.

### Lint / test / build / run

- **Product C (Go)** — from `nobl9/nobl9-user-role/`:
  - Lint: `go vet ./...` (clean). Note: `gofmt -l .` reports `main.go`,
    `main_test.go`, `integration_test.go` as pre-existing formatting deviations;
    leave them unless the task is to reformat.
  - Unit tests (no creds): `go test ./...`
  - Integration tests (need creds + `sloctl` + `NOBL9_TEST_*` env vars, gated by
    the `integration` build tag; auto-skip when unset): `go test -tags=integration ./...`
  - Offline smoke test (real core logic, no creds): `./add-user-role --csv testdata/sample.csv --validate-only`
- **Products A & B (Python)** — no configured linter/test framework; the only
  Python "test" is `nobl9-incident-scripts/test_connection.py`, an auth smoke
  script that needs real creds. Use `python3 -m py_compile <file>` for a syntax
  check.

### Gotchas

- Run Product B scripts as modules from the package root
  (`nobl9/nobl9-incident-scripts/`), e.g. `python3 -m examples.incidents.list_incidents`.
  Running the `.py` file directly breaks the `examples.common` imports.
- The `rolemanagerwrapper.sh` wrapper (Product C) requires `NOBL9_CLIENT_ID`/
  `NOBL9_CLIENT_SECRET` even for `--validate-only` (its validate path runs a
  `--dry-run` that builds the API client). For a fully offline CSV check, call the
  Go binary's `--validate-only` directly instead.
