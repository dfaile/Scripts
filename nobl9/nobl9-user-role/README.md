# Nobl9 User Role Manager

A command-line tool for managing user roles in Nobl9 projects. Supports single-user assignments and bulk CSV processing with email-to-UserID resolution, dry-run validation, duplicate detection, and detailed logging.

## Prerequisites

- **Go 1.22+**
- **Nobl9 account** with API credentials (Client ID and Client Secret)
  - See the [sloctl configuration guide](https://docs.nobl9.com/slos-as-code/sloctl-user-guide/configure-sloctl#prerequisites) to generate credentials

## Installation

### Build from Source

```bash
git clone <repository-url>
cd nobl9-user-role
go mod tidy
go build -o add-user-role main.go
```

### Cross-Platform Builds

```bash
GOOS=linux   GOARCH=amd64 go build -o add-user-role-linux main.go
GOOS=darwin  GOARCH=amd64 go build -o add-user-role-darwin-amd64 main.go
GOOS=darwin  GOARCH=arm64 go build -o add-user-role-darwin-arm64 main.go
GOOS=windows GOARCH=amd64 go build -o add-user-role.exe main.go
```

## Configuration

Set your Nobl9 API credentials as environment variables:

```bash
export NOBL9_CLIENT_ID="your_client_id"
export NOBL9_CLIENT_SECRET="your_client_secret"
```

To generate credentials, log into Nobl9 and navigate to **Settings → Access Keys**.

## Available Roles

### Project-Level Roles (require `--project`)

| Role | Description |
|------|-------------|
| `project-viewer` | Read-only access to project resources |
| `project-editor` | Can edit project resources |
| `project-admin` | Full administrative access to the project |
| `project-owner` | Project ownership with user management rights |

### Organization-Level Roles (no `--project` required)

| Role | Description |
|------|-------------|
| `organization-admin` | Organization-wide administrative access |
| `organization-user` | Standard user access at the organization level |
| `organization-integrations-user` | Access for integrations and automation |
| `organization-responder` | Access to respond to alerts and incidents |
| `organization-viewer` | Read-only access at the organization level |
| `viewer-status-page-manager` | Status page manager access |

For full details on role permissions, see the [Nobl9 Organization Roles documentation](https://docs.nobl9.com/access-management/rbac/organization-roles/).

## Usage

There are two ways to run the tool: the Go binary directly, or the wrapper script (recommended for its additional validation and logging).

### Command-Line Options

#### Go Binary (`add-user-role`)

```bash
./add-user-role [options]
```

| Flag | Description | Required |
|------|-------------|----------|
| `--project` | Project name | Yes (for project-level roles) |
| `--email` | User email (single-user mode) | Yes (if no `--csv`) |
| `--csv` | Path to CSV file (bulk mode) | Yes (if no `--email`) |
| `--role` | Role to assign (default: `project-owner`) | No |
| `--dry-run` | Validate without making changes | No |
| `--help` | Show help message | No |

#### Wrapper Script (`rolemanagerwrapper.sh`)

The wrapper script adds enhanced CSV validation, automatic logging, backup creation, colored output, and confirmation prompts. When run, it auto-creates `logs/` and `backups/` directories alongside the binary:

```
nobl9-user-role/
├── main.go                    # Go source
├── add-user-role              # Compiled binary
├── rolemanagerwrapper.sh      # Wrapper script
├── logs/                      # Auto-created by wrapper script
│   └── nobl9-roles-YYYYMMDD-HHMMSS.log
└── backups/                   # Auto-created when --backup is used
    └── filename.YYYYMMDD-HHMMSS.backup
```

```bash
./rolemanagerwrapper.sh [options]
```

| Flag | Description |
|------|-------------|
| `-c, --csv FILE` | Path to CSV file for bulk processing |
| `-p, --project PROJECT` | Project name |
| `-e, --email EMAIL` | User email (single-user mode) |
| `-r, --role ROLE` | Role to assign (default: `project-owner`) |
| `-d, --dry-run` | Validate without making changes |
| `-v, --verbose` | Enable verbose output |
| `-f, --force` | Skip confirmation prompts |
| `--backup` | Create a timestamped backup of the CSV before processing |
| `--validate-only` | Validate the CSV file without processing |
| `-h, --help` | Show help message |

### Examples

**Assign a project-level role to a single user:**

```bash
./add-user-role --project "my-project" --email "user@example.com" --role "project-editor"
```

**Assign an organization-level role (no project needed):**

```bash
./add-user-role --email "user@example.com" --role "organization-admin"
```

**Bulk assignment from CSV with dry run, then apply:**

```bash
./rolemanagerwrapper.sh --csv projects.csv --role project-owner --backup --dry-run
./rolemanagerwrapper.sh --csv projects.csv --role project-owner --backup
```

**Validate a CSV file without processing:**

```bash
./rolemanagerwrapper.sh --csv projects.csv --validate-only
```

## CSV File Format

### Required Columns

| Column | Description |
|--------|-------------|
| `User Email` | Email address of the user to assign the role to |
| `Project Name` | Nobl9 project name (required for project-level roles; leave empty for organization roles).|

### Example CSV — Project-Level Roles

```csv
Project Name,User Email
default,some.user@somedomain.com
project_name,another.user@example.com
```

### Example CSV — Organization-Level Roles

```csv
Project Name,User Email
,admin@example.com
,user@example.com
```

**Notes:**
- Headers are case-insensitive.
- Empty email addresses are skipped; invalid formats are rejected with detailed error messages.
- For project-level roles, `Project Name` must not be empty.

## Processing Results

After processing, you'll see a summary:

```
==================================================
PROCESSING SUMMARY
==================================================
Total rows processed: 117
Successfully assigned: 95
Skipped (already owner): 12
Skipped (user not exists): 8
Skipped (invalid data): 2
Failed: 0
```

Detailed errors are listed per row:

```
Errors encountered (2):
  1. Row 15: Invalid email format 'invalid-email'
  2. Row 32: Empty project name
```

## Advanced Usage

### Processing Multiple CSV Files

```bash
for csv_file in /data/roles/*.csv; do
    echo "Processing $csv_file..."
    ./rolemanagerwrapper.sh --csv "$csv_file" --role project-owner --backup --force
    sleep 5
done
```

### Conditional Role Assignment by Filename

```bash
for csv_file in /data/roles/*.csv; do
    filename=$(basename "$csv_file" .csv)
    case "$filename" in
        *-viewers) role="project-viewer" ;;
        *-editors) role="project-editor" ;;
        *-owners)  role="project-owner"  ;;
        *)         role="project-viewer"  ;;
    esac
    echo "Processing $csv_file with role $role..."
    ./rolemanagerwrapper.sh --csv "$csv_file" --role "$role" --backup --force
done
```

### Cron Job

```bash
# Daily role sync at 2:00 AM
0 2 * * * /path/to/rolemanagerwrapper.sh --csv /data/daily-roles.csv --role project-owner --force >> /var/log/nobl9-roles.log 2>&1
```

### CI/CD Integration (GitHub Actions)

```yaml
name: Assign Nobl9 Roles
on:
  push:
    paths: ['roles/*.csv']

jobs:
  assign-roles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - name: Build
        run: go build -o add-user-role main.go
      - name: Assign roles
        env:
          NOBL9_CLIENT_ID: ${{ secrets.NOBL9_CLIENT_ID }}
          NOBL9_CLIENT_SECRET: ${{ secrets.NOBL9_CLIENT_SECRET }}
        run: ./add-user-role --csv roles/projects.csv --role project-owner
```

## Testing

### Unit Tests

Unit tests require no credentials and cover CSV parsing, validation, sanitization, role checks, and output formatting:

```bash
go test -v ./...
```

### Integration Tests

Integration tests create a real Nobl9 project via `sloctl`, perform role assignments, and clean up afterward. They are gated behind the `integration` build tag and skip automatically if the required environment variables are not set.

```bash
go test -v -tags=integration ./...
```

**Required environment variables:**

| Variable | Purpose | Example |
|----------|---------|---------|
| `NOBL9_CLIENT_ID` | API Client ID | — |
| `NOBL9_CLIENT_SECRET` | API Client Secret | — |
| `NOBL9_TEST_CONTEXT` | sloctl context name | `daniel` |
| `NOBL9_TEST_USER_PROJECT` | User email for project-level test | `user@example.com` |
| `NOBL9_TEST_USER_ORG` | User email for org-level test (role is **not** restored) | `admin@example.com` |
| `SLOCTL_BIN` | Path to `sloctl` binary (optional; default: `sloctl`) | `/usr/local/bin/sloctl` |

**Behavior:** A temporary project (`test-role-manager-<timestamp>`) is created and deleted on completion, even if a test fails. The org-role user is left at the role set by the test.

## Performance and Rate Limiting

- Built-in 500ms delay between API calls during bulk processing.
- Default context timeout: 5 minutes; individual API call timeout: 30 seconds.
- For very large CSV files (1,000+ rows), consider splitting into smaller batches and validating with `--dry-run` first.

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `authentication failed` | Invalid credentials | Verify `NOBL9_CLIENT_ID` and `NOBL9_CLIENT_SECRET` |
| `user not found` | Email not in Nobl9 org | Check spelling; ensure user has been invited |
| `project not found` | Project doesn't exist | Verify project name and your access |
| `invalid role` | Unrecognized role name | Use a role from the tables above |
| `requires a project` | Project-level role without `--project` | Add `--project` or ensure CSV has `Project Name` |
| CSV column error | Missing required headers | Ensure headers include `Project Name` and `User Email` (case-insensitive) |

**Quick diagnostic steps:**

```bash
# 1. Verify credentials are set
echo $NOBL9_CLIENT_ID && echo $NOBL9_CLIENT_SECRET

# 2. Test connectivity
curl -I https://app.nobl9.com

# 3. Validate CSV headers
head -1 your-file.csv

# 4. Dry run
./add-user-role --csv your-file.csv --dry-run
```

## Security Best Practices

- Never commit credentials to version control — use environment variables or a secrets manager.
- Apply least-privilege principles when assigning roles.
- Rotate API credentials regularly.
- Use the built-in audit logging for compliance and review.

## License

This project is licensed under the [Mozilla Public License Version 2.0](https://www.mozilla.org/en-US/MPL/2.0/).

## Changelog

### v2.0.0

- Bulk CSV processing support
- Wrapper script with validation, logging, and backup
- Dry-run mode
- Duplicate detection
- Comprehensive error handling and statistics reporting
- Backward compatible with v1.0.0 CLI

### v1.0.0

- Single-user role assignment
- Email-to-UserID resolution
- Basic error handling