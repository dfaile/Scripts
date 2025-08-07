# Enhanced Nobl9 User Role Manager

A robust command-line tool for managing user roles in Nobl9 projects with support for both single-user assignments and bulk CSV processing. This enhanced version of the original tool adds comprehensive CSV processing capabilities, extensive error handling, and detailed logging.

## Features

- ✅ **Single User Mode**: Assign roles to individual users
- ✅ **Bulk CSV Mode**: Process multiple role assignments from CSV files  
- ✅ **Email-to-UserID Resolution**: Automatically resolves user emails to Nobl9 user IDs
- ✅ **Comprehensive Error Handling**: Detailed error reporting and validation
- ✅ **Dry Run Support**: Test your assignments without making actual changes
- ✅ **Duplicate Detection**: Prevents duplicate role assignments
- ✅ **Detailed Logging**: Extensive logging for troubleshooting and audit trails
- ✅ **Statistics Reporting**: Comprehensive summary of processing results

## Prerequisites

- **Go 1.22 or later**
- **Nobl9 account** - Visit [https://nobl9.com](https://nobl9.com) for information
- **Nobl9 API credentials** (Client ID and Client Secret)
  - See [Nobl9 sloctl configuration guide](https://docs.nobl9.com/slos-as-code/sloctl-user-guide/configure-sloctl#prerequisites)

## Installation

### Option 1: Build from Source

1. **Clone the repository:**
```bash
git clone <repository-url>
cd nobl9-user-role
```

2. **Install dependencies:**
```bash
go mod tidy
```

3. **Build the binary:**
```bash
go build -o add-user-role main.go
```

### Option 2: Cross-Platform Builds

Build for different platforms:

```bash
# For Linux
GOOS=linux GOARCH=amd64 go build -o add-user-role-linux main.go

# For macOS (Intel)
GOOS=darwin GOARCH=amd64 go build -o add-user-role-darwin-amd64 main.go

# For macOS (Apple Silicon)
GOOS=darwin GOARCH=arm64 go build -o add-user-role-darwin-arm64 main.go

# For Windows
GOOS=windows GOARCH=amd64 go build -o add-user-role.exe main.go
```

## Configuration

### Environment Variables

Set your Nobl9 API credentials as environment variables:

```bash
export NOBL9_CLIENT_ID="your_client_id"
export NOBL9_CLIENT_SECRET="your_client_secret"
```

### Getting API Credentials

1. Log into your Nobl9 account
2. Navigate to **Settings** → **Access Keys**
3. Create a new access key
4. Save the Client ID and Client Secret securely

## Usage

### Option 1: Direct Binary Usage

You can use the Go binary directly for maximum control:

### Command-Line Options

```bash
./add-user-role [options]
```

**Available Options:**

| Flag | Description | Required |
|------|-------------|----------|
| `--project` | Project name (single user mode) | Yes (single mode) |
| `--email` | User email (single user mode) | Yes (single mode) |
| `--csv` | Path to CSV file (bulk mode) | Yes (bulk mode) |
| `--role` | Role to assign | No (default: `project-owner`) |
| `--dry-run` | Perform dry run without changes | No |
| `--help` | Show help message | No |

### Available Roles

- `project-viewer`: Read-only access to project resources
- `project-editor`: Can edit project resources  
- `project-admin`: Full administrative access to project
- `project-owner`: Project ownership with user management rights
- `organization-admin`: Organization-wide administrative access

### Option 2: Wrapper Script Usage (Recommended)

For enhanced functionality with additional validation, logging, and user-friendly features, use the wrapper script:

```bash
./rolemanagerwrapper.sh [OPTIONS]
```

**Wrapper Script Features:**
- ✅ **Enhanced Validation**: Comprehensive CSV and environment validation
- ✅ **Automatic Logging**: Detailed logs with timestamps and log levels
- ✅ **Backup Creation**: Automatic backup of CSV files before processing
- ✅ **Confirmation Prompts**: Safety prompts for bulk operations
- ✅ **Colored Output**: Easy-to-read colored status messages
- ✅ **Dry Run Support**: Built-in dry run validation
- ✅ **Error Handling**: Graceful error handling and recovery

**Wrapper Script Options:**
```bash
-c, --csv FILE          Path to CSV file for bulk processing
-p, --project PROJECT   Project name (single user mode)
-e, --email EMAIL       User email (single user mode)
-r, --role ROLE         Role to assign (default: project-owner)
-d, --dry-run           Perform dry run without making changes
-v, --verbose           Enable verbose output
-f, --force             Skip confirmation prompts
--backup                Create backup before processing
--validate-only         Only validate the CSV file without processing
-h, --help              Show help message
```

**Wrapper Script Examples:**
```bash
# Bulk assignment with validation and backup
./rolemanagerwrapper.sh --csv projects.csv --role project-owner --backup

# Single user assignment with confirmation
./rolemanagerwrapper.sh --project myproject --email user@example.com --role project-editor

# Validate CSV format only
./rolemanagerwrapper.sh --csv projects.csv --validate-only

# Dry run with verbose output
./rolemanagerwrapper.sh --csv projects.csv --dry-run --verbose

# Force mode (skip confirmations)
./rolemanagerwrapper.sh --csv projects.csv --force
```

## Operating Modes

### 1. Single User Mode

Assign a role to a single user:

```bash
# Direct binary usage
./add-user-role --project "my-project" --email "user@example.com" --role "project-owner"

# Wrapper script usage (recommended)
./rolemanagerwrapper.sh --project "my-project" --email "user@example.com" --role "project-owner"
```

**Example Output:**
```
Success: Assigned role 'project-owner' to user 'user@example.com' in project 'my-project'
```

### 2. Bulk CSV Mode

Process multiple assignments from a CSV file:

```bash
# Direct binary usage
./add-user-role --csv "$CSV_FILE" --role "$ROLE" --dry-run

echo "Dry run completed successfully. Proceeding with actual assignment..."

# Actual assignment
./add-user-role --csv "$CSV_FILE" --role "$ROLE"

echo "Role assignment completed!"

# Wrapper script usage (recommended)
./rolemanagerwrapper.sh --csv "$CSV_FILE" --role "$ROLE" --backup --dry-run

echo "Dry run completed successfully. Proceeding with actual assignment..."

# Actual assignment with backup
./rolemanagerwrapper.sh --csv "$CSV_FILE" --role "$ROLE" --backup

echo "Role assignment completed!"
```

### Cron Job Example

```bash
#!/bin/bash
# Daily role sync from shared CSV file (direct binary)
0 2 * * * /path/to/add-user-role --csv /data/daily-roles.csv --role project-owner >> /var/log/nobl9-roles.log 2>&1

# Daily role sync with wrapper script (recommended)
0 2 * * * /path/to/rolemanagerwrapper.sh --csv /data/daily-roles.csv --role project-owner --force
```

## Advanced Usage

### Processing Multiple CSV Files

```bash
#!/bin/bash
# Process multiple CSV files (direct binary)
for csv_file in /data/roles/*.csv; do
    echo "Processing $csv_file..."
    ./add-user-role --csv "$csv_file" --role project-owner
    sleep 5  # Brief pause between files
done

# Process multiple CSV files with wrapper script (recommended)
for csv_file in /data/roles/*.csv; do
    echo "Processing $csv_file..."
    ./rolemanagerwrapper.sh --csv "$csv_file" --role project-owner --backup --force
    sleep 5  # Brief pause between files
done
```

### Conditional Role Assignment

```bash
#!/bin/bash
# Assign different roles based on file names (direct binary)
for csv_file in /data/roles/*.csv; do
    filename=$(basename "$csv_file" .csv)
    
    case "$filename" in
        *-viewers)
            role="project-viewer"
            ;;
        *-editors)
            role="project-editor"
            ;;
        *-owners)
            role="project-owner"
            ;;
        *)
            role="project-viewer"  # default
            ;;
    esac
    
    echo "Processing $csv_file with role $role..."
    ./add-user-role --csv "$csv_file" --role "$role"
done

# Assign different roles based on file names with wrapper script (recommended)
for csv_file in /data/roles/*.csv; do
    filename=$(basename "$csv_file" .csv)
    
    case "$filename" in
        *-viewers)
            role="project-viewer"
            ;;
        *-editors)
            role="project-editor"
            ;;
        *-owners)
            role="project-owner"
            ;;
        *)
            role="project-viewer"  # default
            ;;
    esac
    
    echo "Processing $csv_file with role $role..."
    ./rolemanagerwrapper.sh --csv "$csv_file" --role "$role" --backup --force
done
```

## Monitoring and Alerting

### Log Analysis

Monitor logs for patterns:

```bash
# Count successful assignments
grep "Successfully assigned" nobl9-roles.log | wc -l

# Find failed assignments
grep "Failed to assign" nobl9-roles.log

# Monitor for authentication issues
grep "authentication" nobl9-roles.log
```

### Alerting Integration

```bash
#!/bin/bash
# Example alerting wrapper
LOG_FILE="/var/log/nobl9-roles.log"
ERROR_COUNT=$(grep -c "Error\|Failed" "$LOG_FILE")

if [ "$ERROR_COUNT" -gt 0 ]; then
    # Send alert (example with curl to Slack)
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"Nobl9 role assignment errors detected: $ERROR_COUNT\"}" \
        "$SLACK_WEBHOOK_URL"
fi
```

## Testing

### Unit Testing

Create test CSV files:

```csv
App Short Name,User Exists,User Email
test-project-1,Y,test1@example.com
test-project-2,Y,test2@example.com
test-project-3,N,nonexistent@example.com
invalid-project,,invalid-email
```

### Integration Testing

```bash
#!/bin/bash
# Test script
set -e

echo "Running integration tests..."

# Test 1: Dry run with valid CSV
echo "Test 1: Dry run validation"
./nobl9-role-manager --csv test-data.csv --dry-run

# Test 2: Single user mode
echo "Test 2: Single user assignment"
./nobl9-role-manager --project test-project --email test@example.com --role project-viewer --dry-run

# Test 3: Invalid role handling
echo "Test 3: Invalid role rejection"
if ./nobl9-role-manager --project test-project --email test@example.com --role invalid-role 2>/dev/null; then
    echo "ERROR: Should have rejected invalid role"
    exit 1
else
    echo "PASS: Invalid role properly rejected"
fi

echo "All tests passed!"
```

## Migration from Original Script

If you're migrating from the original single-user script:

### Original Command Format
```bash
./add-user-role --project "my-project" --email "user@example.com" --role "project-viewer"
```

### Enhanced Command Format (Recommended)
```bash
./rolemanagerwrapper.sh --project "my-project" --email "user@example.com" --role "project-viewer"
```

The command-line interface is fully backward compatible.

### New Bulk Processing Capability
```bash
# Convert your individual assignments to CSV format (direct binary)
./add-user-role --csv projects.csv --role project-owner

# Enhanced bulk processing with wrapper script (recommended)
./rolemanagerwrapper.sh --csv projects.csv --role project-owner --backup
```

## API Rate Limits and Best Practices

### Rate Limiting
- Built-in 500ms delay between API calls
- Configurable timeout settings
- Graceful handling of API rate limit responses

### Best Practices
- Process during off-peak hours
- Use dry-run mode for validation
- Monitor API usage and quotas
- Implement exponential backoff for retries

## Wrapper Script Features

The `rolemanagerwrapper.sh` script provides enhanced functionality beyond the basic Go binary:

### Key Features

- **🔍 Enhanced Validation**: Comprehensive CSV format validation, environment variable checking, and binary verification
- **📝 Automatic Logging**: Detailed logs with timestamps, log levels, and automatic log file rotation
- **💾 Backup Creation**: Automatic backup of CSV files before processing with timestamped backups
- **⚠️ Safety Prompts**: Interactive confirmation prompts for bulk operations (can be bypassed with `--force`)
- **🎨 Colored Output**: Easy-to-read colored status messages (green for success, red for errors, yellow for warnings)
- **🧪 Dry Run Support**: Built-in dry run validation with detailed reporting
- **🛡️ Error Handling**: Graceful error handling with proper exit codes and cleanup
- **📊 Verbose Mode**: Detailed debugging output with `--verbose` flag

### Directory Structure

The wrapper script creates the following directory structure:

```
nobl9-user-role/
├── add-user-role              # Go binary
├── rolemanagerwrapper.sh      # Wrapper script
├── logs/                      # Log files (auto-created)
│   └── nobl9-roles-YYYYMMDD-HHMMSS.log
├── backups/                   # CSV backups (auto-created)
│   └── filename.YYYYMMDD-HHMMSS.backup
└── main.go                    # Source code
```

### Log File Format

Log files include:
- Timestamped entries with log levels (INFO, ERROR, WARN, DEBUG)
- Command execution details
- Processing statistics
- Error details and stack traces
- Performance metrics

### Backup Strategy

- Automatic backup creation with `--backup` flag
- Timestamped backup files to prevent overwrites
- Backup directory automatically created if needed
- Original file permissions preserved

## Troubleshooting Guide

### Debugging Steps

1. **Verify Environment Setup**
   ```bash
   echo $NOBL9_CLIENT_ID
   echo $NOBL9_CLIENT_SECRET
   ```

2. **Test Single User Assignment**
   ```bash
   ./nobl9-role-manager --project test --email test@example.com --dry-run
   ```

3. **Validate CSV Format**
   ```bash
   head -5 your-file.csv
   ```

4. **Check Network Connectivity**
   ```bash
   curl -I https://app.nobl9.com
   ```

### Common Error Messages

| Error Message | Cause | Solution |
|---------------|--------|----------|
| `user not found` | User doesn't exist in Nobl9 | Check email, ensure user is invited |
| `project not found` | Project doesn't exist | Verify project name and access |
| `invalid role` | Role name is incorrect | Use one of the valid roles listed |
| `authentication failed` | Invalid credentials | Check CLIENT_ID and CLIENT_SECRET |

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Code Standards

- Follow Go conventions and best practices
- Add comprehensive error handling
- Include detailed logging
- Write tests for new features
- Update documentation

## License

[Specify your license here]

## Support

For issues and questions:

1. Check this README for common solutions
2. Review the troubleshooting guide
3. Check Nobl9 documentation
4. Open an issue in the repository

## Changelog

### Version 2.0.0 (Current)
- ✅ Added bulk CSV processing support
- ✅ Enhanced error handling and validation
- ✅ Added dry-run functionality
- ✅ Improved logging and statistics
- ✅ Added comprehensive documentation
- ✅ Backward compatibility with original script

### Version 1.0.0 (Original)
- ✅ Basic single-user role assignment
- ✅ Email-to-UserID resolution
- ✅ Basic error handling "projects.csv" --role "project-owner"
```

**With dry run:**
```bash
./nobl9-role-manager --csv "projects.csv" --role "project-owner" --dry-run
```

## CSV File Format

### Required Columns

Your CSV file must contain these columns (case-sensitive):

- **`App Short Name`**: The name of the Nobl9 project
- **`User Email`**: The email address of the user to assign the role to

### Optional Columns

- **`User Exists`**: Y/N flag indicating if the user exists in Nobl9 (defaults to Y if not specified)

### Example CSV Format

```csv
App Short Name,Product Manager,User Exists,User Email,SLOs
tiisaa,Akaniro Samuel Edozie,Y,samuel.akaniro@msd.com,https://app.nobl9.com/...
msx,Anand Ruchika,Y,ruchika.anand@merck.com,
bardscpi,Arnold Elizabeth F,Y,elizabeth_arnold2@merck.com,
DARC,Arnold Elizabeth F,N,elizabeth_arnold2@merck.com,
```

**Notes:**
- Rows with `User Exists = N` will be skipped automatically
- Empty project names or email addresses will be skipped
- Invalid email formats will be rejected with detailed error messages

## Processing Results

### Statistics Summary

After processing, you'll see a comprehensive summary:

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

### Error Reporting

Detailed error messages for troubleshooting:

```
Errors encountered (2):
  1. Row 15: Invalid email format 'invalid-email'
  2. Row 32: Empty project name
```

## Validation and Error Handling

### Input Validation

- ✅ **Email Format**: Validates email addresses using regex
- ✅ **Role Validation**: Ensures only valid roles are used
- ✅ **CSV Structure**: Validates required columns exist
- ✅ **Empty Data**: Detects and skips empty rows/values

### Error Categories

| Category | Description | Action Taken |
|----------|-------------|--------------|
| **Invalid Data** | Empty fields, invalid emails | Skip row, log error |
| **User Not Found** | Email doesn't exist in Nobl9 | Skip row, log warning |
| **Already Assigned** | User already has the role | Skip row, log info |
| **API Errors** | Network/authentication issues | Fail with error |

### Duplicate Prevention

The tool automatically checks for existing role assignments to prevent duplicates, though this feature may have limited capability based on the current Nobl9 SDK.

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Error:** `Error: Failed to create Nobl9 client`

**Solution:**
- Verify your `NOBL9_CLIENT_ID` and `NOBL9_CLIENT_SECRET` are set correctly
- Ensure the credentials have appropriate permissions
- Check your network connectivity to Nobl9 APIs

#### 2. User Not Found

**Error:** `User with email 'user@example.com' not found`

**Solutions:**
- Verify the user exists in your Nobl9 organization
- Check the email address spelling
- Ensure the user has been invited to your Nobl9 organization

#### 3. Project Not Found

**Error:** `Project 'project-name' not found`

**Solutions:**
- Verify the project exists in your Nobl9 organization
- Check project name spelling and capitalization
- Ensure you have access to the project

#### 4. CSV Format Issues

**Error:** `CSV file must contain 'App Short Name' and 'User Email' columns`

**Solutions:**
- Ensure your CSV has the exact column headers (case-sensitive)
- Check for extra spaces in column headers
- Verify the CSV file is properly formatted

### Debug Mode

For detailed debugging, you can modify the logging level in the code or add additional logging as needed.

### Dry Run Testing

Always test with `--dry-run` first:

```bash
./nobl9-role-manager --csv "projects.csv" --dry-run
```

This allows you to:
- Validate your CSV format
- Check for authentication issues
- Verify user and project existence
- Preview what changes would be made

## Performance Considerations

### Rate Limiting

The tool includes built-in rate limiting:
- 500ms delay between API calls during bulk processing
- Prevents overwhelming the Nobl9 API
- Ensures reliable processing of large CSV files

### Batch Processing

For very large CSV files (1000+ rows):
- Consider processing in smaller batches
- Monitor API rate limits
- Use dry-run mode first to validate data

### Timeout Settings

- Default context timeout: 5 minutes
- Individual API call timeout: 30 seconds
- Adjust timeouts based on your network conditions

## Security Best Practices

### Credential Management

- **Never commit credentials to version control**
- Use environment variables for API credentials
- Consider using a secrets management system for production
- Rotate credentials regularly

### Access Control

- Use least-privilege access principles
- Only assign necessary roles
- Regularly audit role assignments
- Monitor for unauthorized changes

### Audit Logging

The tool provides comprehensive logging:
- All role assignments are logged
- Failed attempts are recorded
- Processing statistics are maintained
- Consider integrating with your logging infrastructure

## Integration Examples

### CI/CD Pipeline Integration

```yaml
# GitHub Actions example
name: Assign Nobl9 Roles
on:
  push:
    paths: ['roles/*.csv']

jobs:
  assign-roles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Go
        uses: actions/setup-go@v2
        with:
          go-version: 1.22
      - name: Build tool
        run: go build -o nobl9-role-manager main.go
      - name: Assign roles
        env:
          NOBL9_CLIENT_ID: ${{ secrets.NOBL9_CLIENT_ID }}
          NOBL9_CLIENT_SECRET: ${{ secrets.NOBL9_CLIENT_SECRET }}
        run: ./nobl9-role-manager --csv roles/projects.csv --role project-owner
```

### Shell Script Wrapper

```bash
#!/bin/bash
# assign-roles.sh

set -e

CSV_FILE="$1"
ROLE="${2:-project-owner}"

if [ -z "$CSV_FILE" ]; then
    echo "Usage: $0 <csv-file> [role]"
    exit 1
fi

echo "Starting role assignment process..."
echo "CSV File: $CSV_FILE"
echo "Role: $ROLE"

# Dry run first
echo "Performing dry run..."
./nobl9-role-manager --csv