#!/bin/bash

#
# Nobl9 Role Manager Wrapper Script
#
# This script provides a convenient wrapper around the Go-based Nobl9 role manager
# with additional validation, logging, and user-friendly features.
#
# Usage:
#   ./assign-nobl9-roles.sh [OPTIONS]
#
# Author: Generated for Nobl9 RBAC Management
# Version: 1.0.0
# Date: 2025-08-07
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Script configuration
SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/nobl9-roles-$(date +%Y%m%d-%H%M%S).log"
GO_BINARY="${SCRIPT_DIR}/add-user-role"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_ROLE="project-owner"
DRY_RUN=false
VERBOSE=false
FORCE=false
BACKUP_DIR="${SCRIPT_DIR}/backups"

# Usage information
usage() {
    cat << EOF
${SCRIPT_NAME} - Nobl9 Role Assignment Wrapper Script

USAGE:
    ${SCRIPT_NAME} [OPTIONS] --csv <csv-file>
    ${SCRIPT_NAME} [OPTIONS] --project <project> --email <email>

DESCRIPTION:
    A wrapper script for the Nobl9 role manager that provides additional
    validation, logging, and user-friendly features.

OPTIONS:
    -c, --csv FILE          Path to CSV file for bulk processing
    -p, --project PROJECT   Project name (required for project-level roles, optional for organization roles)
    -e, --email EMAIL       User email (single user mode)
    -r, --role ROLE         Role to assign (default: ${DEFAULT_ROLE})
    -d, --dry-run           Perform dry run without making changes
    -v, --verbose           Enable verbose output
    -f, --force             Skip confirmation prompts
    --backup                Create backup before processing
    --validate-only         Only validate the CSV file without processing
    -h, --help              Show this help message

VALID ROLES:
    Project-level: project-viewer, project-editor, project-admin, project-owner
    Organization-level: organization-admin, organization-user, organization-integrations-user, organization-responder, organization-viewer, viewer-status-page-manager

ENVIRONMENT VARIABLES:
    NOBL9_CLIENT_ID         Nobl9 API Client ID (required)
    NOBL9_CLIENT_SECRET     Nobl9 API Client Secret (required)
    NOBL9_ORGANIZATION      Nobl9 Organization name (optional)

EXAMPLES:
    # Bulk assignment from CSV
    ${SCRIPT_NAME} --csv projects.csv --role project-owner

    # Single user assignment (project role)
    ${SCRIPT_NAME} --project myproject --email user@example.com --role project-editor
    
    # Single user assignment (organization role - no project needed)
    ${SCRIPT_NAME} --email user@example.com --role organization-admin

    # Dry run with verbose output
    ${SCRIPT_NAME} --csv projects.csv --dry-run --verbose

    # Validate CSV format only
    ${SCRIPT_NAME} --csv projects.csv --validate-only

CSV FORMAT:
    Required columns: 'User Email'
    Optional columns: 'App Short Name' (required for project-level roles, can be empty for organization roles)
    Note: For organization-level roles, 'App Short Name' column can be empty

EOF
}

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $*" | tee -a "$LOG_FILE" >&2
}

log_warn() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] $*" | tee -a "$LOG_FILE"
}

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [DEBUG] $*" | tee -a "$LOG_FILE"
    fi
}

# Colored output functions
print_success() {
    echo -e "${GREEN}✓ $*${NC}"
}

print_error() {
    echo -e "${RED}✗ $*${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $*${NC}"
}

# Setup function
setup() {
    # Create necessary directories
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    
    # Initialize log file
    log "Starting ${SCRIPT_NAME} with PID $$"
    log "Script directory: $SCRIPT_DIR"
    log "Log file: $LOG_FILE"
}

# Cleanup function
cleanup() {
    local exit_code=$?
    log "Script completed with exit code: $exit_code"
    
    if [[ $exit_code -eq 0 ]]; then
        print_success "Script completed successfully"
    else
        print_error "Script failed with exit code: $exit_code"
    fi
    
    exit $exit_code
}

# Validation functions
validate_environment() {
    log_debug "Validating environment variables"
    
    if [[ -z "${NOBL9_CLIENT_ID:-}" ]]; then
        print_error "NOBL9_CLIENT_ID environment variable is not set"
        return 1
    fi
    
    if [[ -z "${NOBL9_CLIENT_SECRET:-}" ]]; then
        print_error "NOBL9_CLIENT_SECRET environment variable is not set"
        return 1
    fi
    
    print_success "Environment variables validated"
    return 0
}

validate_binary() {
    log_debug "Validating Go binary"
    
    if [[ ! -f "$GO_BINARY" ]]; then
        print_error "Go binary not found at: $GO_BINARY"
        print_info "Please build the binary using: go build -o add-user-role main.go"
        return 1
    fi
    
    if [[ ! -x "$GO_BINARY" ]]; then
        print_error "Go binary is not executable: $GO_BINARY"
        print_info "Please make it executable: chmod +x $GO_BINARY"
        return 1
    fi
    
    print_success "Go binary validated"
    return 0
}

validate_csv() {
    local csv_file="$1"
    
    log_debug "Validating CSV file: $csv_file"
    
    if [[ ! -f "$csv_file" ]]; then
        print_error "CSV file not found: $csv_file"
        return 1
    fi
    
    if [[ ! -r "$csv_file" ]]; then
        print_error "CSV file is not readable: $csv_file"
        return 1
    fi
    
    # Check file size
    local file_size
    file_size=$(stat -f%z "$csv_file" 2>/dev/null || stat -c%s "$csv_file" 2>/dev/null || echo 0)
    if [[ $file_size -eq 0 ]]; then
        print_error "CSV file is empty: $csv_file"
        return 1
    fi
    
    # Validate CSV headers
    local header
    header=$(head -1 "$csv_file")
    
    if [[ ! "$header" == *"App Short Name"* ]]; then
        print_error "CSV file missing required column: 'App Short Name'"
        return 1
    fi
    
    if [[ ! "$header" == *"User Email"* ]]; then
        print_error "CSV file missing required column: 'User Email'"
        return 1
    fi
    
    # Count rows (excluding header)
    local row_count
    row_count=$(($(wc -l < "$csv_file") - 1))
    log "CSV file contains $row_count data rows"
    
    if [[ $row_count -eq 0 ]]; then
        print_warning "CSV file contains no data rows"
        return 1
    fi
    
    print_success "CSV file validated successfully"
    return 0
}

# Backup function
create_backup() {
    local csv_file="$1"
    local backup_file="${BACKUP_DIR}/$(basename "$csv_file").$(date +%Y%m%d-%H%M%S).backup"
    
    log "Creating backup: $backup_file"
    cp "$csv_file" "$backup_file"
    print_success "Backup created: $backup_file"
}

# Confirmation prompt
confirm_action() {
    local message="$1"
    
    if [[ "$FORCE" == "true" ]]; then
        log_debug "Skipping confirmation (force mode enabled)"
        return 0
    fi
    
    echo -e "${YELLOW}$message${NC}"
    read -p "Do you want to continue? [y/N]: " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Operation cancelled by user"
        exit 0
    fi
}

# CSV validation only
validate_csv_only() {
    local csv_file="$1"
    
    print_info "Validating CSV file format..."
    
    if ! validate_csv "$csv_file"; then
        return 1
    fi
    
    # Additional validation using dry-run
    log "Performing dry-run validation with Go binary..."
    
    if "$GO_BINARY" --csv "$csv_file" --dry-run >> "$LOG_FILE" 2>&1; then
        print_success "CSV file validation completed successfully"
        return 0
    else
        print_error "CSV file validation failed (see log for details)"
        return 1
    fi
}

# Main processing function
process_assignments() {
    local args=()
    
    # Build arguments array
    if [[ -n "${CSV_FILE:-}" ]]; then
        args+=(--csv "$CSV_FILE")
    fi
    
    if [[ -n "${PROJECT:-}" ]]; then
        args+=(--project "$PROJECT")
    fi
    
    if [[ -n "${EMAIL:-}" ]]; then
        args+=(--email "$EMAIL")
    fi
    
    if [[ -n "${ROLE:-}" ]]; then
        args+=(--role "$ROLE")
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        args+=(--dry-run)
    fi
    
    log "Executing: $GO_BINARY ${args[*]}"
    
    # Execute the Go binary and capture output
    if "$GO_BINARY" "${args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log "Processing completed successfully"
        return 0
    else
        log_error "Processing failed"
        return 1
    fi
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--csv)
                CSV_FILE="$2"
                shift 2
                ;;
            -p|--project)
                PROJECT="$2"
                shift 2
                ;;
            -e|--email)
                EMAIL="$2"
                shift 2
                ;;
            -r|--role)
                ROLE="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            --backup)
                BACKUP=true
                shift
                ;;
            --validate-only)
                VALIDATE_ONLY=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Set default role if not specified
    ROLE="${ROLE:-$DEFAULT_ROLE}"
    
    # Check if role is organization-level (organization-* prefix or viewer-status-page-manager)
    IS_ORG_ROLE=false
    if [[ "${ROLE:-}" == organization-* || "${ROLE:-}" == "viewer-status-page-manager" ]]; then
        IS_ORG_ROLE=true
    fi
    
    # Validate argument combinations
    if [[ -n "${CSV_FILE:-}" && (-n "${PROJECT:-}" || -n "${EMAIL:-}") ]]; then
        print_error "Cannot use --csv with --project or --email"
        exit 1
    fi
    
    # For single user mode: email is required, project is required only for project-level roles
    if [[ -z "${CSV_FILE:-}" ]]; then
        if [[ -z "${EMAIL:-}" ]]; then
            print_error "Must specify --email for single user mode"
            usage
            exit 1
        fi
        
        # Project is required for project-level roles
        if [[ "$IS_ORG_ROLE" == "false" && -z "${PROJECT:-}" ]]; then
            print_error "Must specify --project for project-level role '${ROLE:-}'"
            usage
            exit 1
        fi
    fi
}

# Main function
main() {
    # Set up signal handlers
    trap cleanup EXIT
    trap 'log_error "Script interrupted by signal"; exit 130' INT TERM
    
    # Initialize
    setup
    
    # Parse arguments
    parse_arguments "$@"
    
    # Validate environment
    if ! validate_environment; then
        exit 1
    fi
    
    # Validate binary
    if ! validate_binary; then
        exit 1
    fi
    
    # Mode-specific processing
    if [[ -n "${CSV_FILE:-}" ]]; then
        # CSV mode
        log "Processing in CSV mode: $CSV_FILE"
        
        if ! validate_csv "$CSV_FILE"; then
            exit 1
        fi
        
        if [[ "${VALIDATE_ONLY:-}" == "true" ]]; then
            validate_csv_only "$CSV_FILE"
            exit $?
        fi
        
        # Create backup if requested
        if [[ "${BACKUP:-}" == "true" ]]; then
            create_backup "$CSV_FILE"
        fi
        
        # Confirmation for bulk processing
        local row_count
        row_count=$(($(wc -l < "$CSV_FILE") - 1))
        
        if [[ "$DRY_RUN" != "true" ]]; then
            confirm_action "You are about to process $row_count role assignments with role '$ROLE'."
        fi
        
    else
        # Single user mode
        if [[ "${ROLE:-}" == organization-* ]]; then
            log "Processing in single user mode (organization role): $EMAIL ($ROLE)"
            if [[ "$DRY_RUN" != "true" ]]; then
                confirm_action "You are about to assign organization role '$ROLE' to '$EMAIL'."
            fi
        else
            log "Processing in single user mode: $PROJECT -> $EMAIL ($ROLE)"
            if [[ "$DRY_RUN" != "true" ]]; then
                confirm_action "You are about to assign role '$ROLE' to '$EMAIL' in project '$PROJECT'."
            fi
        fi
    fi
    
    # Execute processing
    if process_assignments; then
        print_success "All operations completed successfully!"
        log "Log file available at: $LOG_FILE"
    else
        print_error "Some operations failed. Check the log file for details: $LOG_FILE"
        exit 1
    fi
}

# Execute main function with all arguments
main "$@"