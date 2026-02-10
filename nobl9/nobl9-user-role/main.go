package main

import (
	"context"
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
	"time"

	"github.com/nobl9/nobl9-go/manifest"
	v1alphaRoleBinding "github.com/nobl9/nobl9-go/manifest/v1alpha/rolebinding"
	"github.com/nobl9/nobl9-go/sdk"
	objectsV1 "github.com/nobl9/nobl9-go/sdk/endpoints/objects/v1"
	usersV2 "github.com/nobl9/nobl9-go/sdk/endpoints/users/v2"
)

// ProcessingStats tracks the results of bulk processing
type ProcessingStats struct {
	TotalRows            int
	Processed            int
	Assigned             int
	SkippedAlreadyOwner  int
	SkippedUserNotExists int
	SkippedInvalidData   int
	Failed               int
	Errors               []string
	// Detailed collections for better reporting
	MissingUsers    []string
	MissingProjects []string
	AlreadyAssigned []string // formatted as user@domain -> project
}

// CSVRow represents a row from the CSV file. Only project-name and user email are required.
type CSVRow struct {
	ProjectName string
	UserEmail   string
}

// Valid roles that can be assigned
var validRoles = map[string]bool{
	// Project-level roles
	"project-viewer": true,
	"project-editor": true,
	"project-admin":  true,
	"project-owner":  true,
	// Organization-level roles (do not require a project)
	"organization-admin":            true,
	"organization-user":             true,
	"organization-integrations-user": true,
	"organization-responder":        true,
	"organization-viewer":           true,
	"viewer-status-page-manager":    true,
}

// Sentinel errors for stable error classification (used with errors.Is).
var (
	ErrUserNotFound    = errors.New("user not found")
	ErrAlreadyAssigned = errors.New("user already has this role")
	ErrProjectNotFound = errors.New("project not found")
	ErrRoleBindingExists = errors.New("role binding already exists")
	ErrValidation      = errors.New("validation error")
	ErrProjectRequired = errors.New("project required for project-level role")
)

// ptr creates a pointer to a string, used for fields in the role binding spec
func ptr(s string) *string { return &s }

// sanitizeName ensures the string is RFC-1123 compliant by converting to lowercase,
// replacing non-alphanumeric (except hyphen) characters with hyphens,
// and trimming leading/trailing hyphens.
func sanitizeName(name string) string {
	// Convert to lowercase
	name = strings.ToLower(name)
	// Replace non-alphanumeric characters (except hyphen) with a hyphen
	reg := regexp.MustCompile("[^a-z0-9-]+")
	name = reg.ReplaceAllString(name, "-")
	// Trim hyphens from the start and end
	name = strings.Trim(name, "-")
	return name
}

// validateEmail performs basic email validation
func validateEmail(email string) bool {
	emailRegex := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
	return emailRegex.MatchString(email)
}

// getValidRoles returns a formatted string of valid roles
func getValidRoles() string {
	roles := make([]string, 0, len(validRoles))
	for role := range validRoles {
		roles = append(roles, role)
	}
	return strings.Join(roles, ", ")
}

// organizationRoleNames lists roles that are org-wide but don't use the "organization-" prefix
var organizationRoleNames = map[string]bool{
	"viewer-status-page-manager": true,
}

// isOrganizationRole checks if a role is an organization-level role
func isOrganizationRole(role string) bool {
	return strings.HasPrefix(role, "organization-") || organizationRoleNames[role]
}

// isRetryable returns false for sentinel and context errors (do not retry).
func isRetryable(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, ErrUserNotFound) || errors.Is(err, ErrAlreadyAssigned) ||
		errors.Is(err, ErrProjectNotFound) || errors.Is(err, ErrRoleBindingExists) ||
		errors.Is(err, ErrValidation) || errors.Is(err, ErrProjectRequired) {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}
	return true
}

const retryAttempts = 3
const retryInitialDelay = 1 * time.Second

// retryWithBackoff runs fn up to retryAttempts times with exponential backoff and jitter.
// Stops on success, non-retryable error, or context cancellation.
func retryWithBackoff(ctx context.Context, fn func() error) error {
	var lastErr error
	delay := retryInitialDelay
	for attempt := 0; attempt < retryAttempts; attempt++ {
		lastErr = fn()
		if lastErr == nil {
			return nil
		}
		if !isRetryable(lastErr) {
			return lastErr
		}
		if attempt == retryAttempts-1 {
			return lastErr
		}
		// Jitter: 0.5 * delay to 1.5 * delay
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(delay):
			// advance backoff for next iteration
			delay = time.Duration(float64(delay) * 1.5)
			if delay > 30*time.Second {
				delay = 30 * time.Second
			}
		}
	}
	return lastErr
}

// getExistingOrganizationRoleBinding returns the organization-level role binding for the user, if any.
// Nobl9 creates a default org role binding per user; we must update it rather than create a new one.
func getExistingOrganizationRoleBinding(ctx context.Context, client *sdk.Client, userID string) (*v1alphaRoleBinding.RoleBinding, error) {
	all, err := client.Objects().V1().GetV1alphaRoleBindings(ctx, objectsV1.GetRoleBindingsRequest{Project: sdk.ProjectsWildcard})
	if err != nil {
		return nil, err
	}
	for i := range all {
		rb := &all[i]
		// Organization bindings have no project
		if rb.Spec.ProjectRef != "" {
			continue
		}
		if rb.Spec.User != nil && *rb.Spec.User == userID {
			return rb, nil
		}
	}
	return nil, nil
}

// checkExistingRoleBinding checks if user already has the specified role.
// For organization roles, looks up the user's org-level binding and compares RoleRef.
func checkExistingRoleBinding(ctx context.Context, client *sdk.Client, projectName, userID, role string) (bool, error) {
	if isOrganizationRole(role) {
		log.Printf("Checking existing organization role bindings with role %s", role)
		existing, err := getExistingOrganizationRoleBinding(ctx, client, userID)
		if err != nil {
			return false, err
		}
		if existing != nil && existing.Spec.RoleRef == role {
			return true, nil
		}
		return false, nil
	}
	log.Printf("Checking existing role bindings in project %s with role %s", projectName, role)
	// Project-level: no robust check implemented; allow assignment to proceed
	return false, nil
}

// assignRole assigns the specified role to a user
// For project-level roles, requires a project name
// For organization-level roles, project name is optional and ignored
func assignRole(ctx context.Context, client *sdk.Client, projectName, userEmail, role string, dryRun bool) error {
	isOrgRole := isOrganizationRole(role)

	// Validate: project-level roles require a project
	if !isOrgRole && projectName == "" {
		return fmt.Errorf("project-level role '%s' requires a project to be specified: %w", role, ErrProjectRequired)
	}

	// Step 1: Check if the user exists by their email (with retry for transient failures)
	var user *usersV2.User
	err := retryWithBackoff(ctx, func() error {
		u, e := client.Users().V2().GetUser(ctx, userEmail)
		if e != nil {
			return e
		}
		if u == nil {
			return ErrUserNotFound
		}
		user = u
		return nil
	})
	if err != nil {
		if errors.Is(err, ErrUserNotFound) {
			return fmt.Errorf("user with email '%s' not found: %w", userEmail, ErrUserNotFound)
		}
		return fmt.Errorf("error retrieving user from Nobl9 API: %w", err)
	}

	// Avoid logging internal user IDs
	log.Printf("Found user: %s", userEmail)

	// Step 2: Check if user already has this role
	exists, err := checkExistingRoleBinding(ctx, client, projectName, user.UserID, role)
	if err != nil {
		log.Printf("Warning: Could not check existing role bindings: %v", err)
		// Continue with assignment even if we can't check
	}

	if exists {
		if isOrgRole {
			return fmt.Errorf("user already has organization role '%s': %w", role, ErrAlreadyAssigned)
		}
		return fmt.Errorf("user already has role '%s' for project '%s': %w", role, projectName, ErrAlreadyAssigned)
	}

	if dryRun {
		if isOrgRole {
			log.Printf("DRY RUN: Would assign organization role '%s' to user '%s'", role, userEmail)
		} else {
			log.Printf("DRY RUN: Would assign role '%s' to user '%s' in project '%s'", role, userEmail, projectName)
		}
		return nil
	}

	var roleBinding v1alphaRoleBinding.RoleBinding

	if isOrgRole {
		// Organization roles: Nobl9 allows only one org-level binding per user (e.g. default).
		// Fetch existing binding and update its RoleRef instead of creating a new one.
		existing, err := getExistingOrganizationRoleBinding(ctx, client, user.UserID)
		if err != nil {
			return fmt.Errorf("failed to get existing organization role binding: %w", err)
		}
		if existing != nil {
			// Update existing binding to the new role (change default org role)
			roleBinding = v1alphaRoleBinding.New(
				v1alphaRoleBinding.Metadata{Name: existing.Metadata.Name},
				v1alphaRoleBinding.Spec{
					User:    ptr(user.UserID),
					RoleRef: role,
				},
			)
			log.Printf("Updating existing organization role binding '%s' from '%s' to '%s'", existing.Metadata.Name, existing.Spec.RoleRef, role)
		} else {
			// No existing org binding: create new one
			sanitizedEmail := sanitizeName(userEmail)
			timestamp := fmt.Sprintf("%x", time.Now().UnixNano())[:8]
			roleBindingName := fmt.Sprintf("rb-org-%s-%s", sanitizedEmail, timestamp)
			if len(roleBindingName) > 63 {
				maxEmailLen := 63 - len(fmt.Sprintf("rb-org--%s", timestamp))
				if maxEmailLen > 0 && len(sanitizedEmail) > maxEmailLen {
					sanitizedEmail = sanitizedEmail[:maxEmailLen]
				}
				roleBindingName = fmt.Sprintf("rb-org-%s-%s", sanitizedEmail, timestamp)
			}
			roleBinding = v1alphaRoleBinding.New(
				v1alphaRoleBinding.Metadata{Name: roleBindingName},
				v1alphaRoleBinding.Spec{
					User:    ptr(user.UserID),
					RoleRef: role,
				},
			)
		}
	} else {
		// Project-level: generate unique name and create new binding
		sanitizedEmail := sanitizeName(userEmail)
		timestamp := fmt.Sprintf("%x", time.Now().UnixNano())[:8]
		sanitizedProject := sanitizeName(projectName)
		roleBindingName := fmt.Sprintf("rb-%s-%s-%s", sanitizedProject, sanitizedEmail, timestamp)
		if len(roleBindingName) > 63 {
			maxEmailLen := 63 - len(fmt.Sprintf("rb-%s--%s", sanitizedProject, timestamp))
			if maxEmailLen > 0 && len(sanitizedEmail) > maxEmailLen {
				sanitizedEmail = sanitizedEmail[:maxEmailLen]
			}
			roleBindingName = fmt.Sprintf("rb-%s-%s-%s", sanitizedProject, sanitizedEmail, timestamp)
		}
		sanitizedProjectRef := sanitizeName(projectName)
		if sanitizedProjectRef != projectName {
			log.Printf("Warning: Project name '%s' sanitized to '%s' for RFC-1123 compliance", projectName, sanitizedProjectRef)
		}
		roleBinding = v1alphaRoleBinding.New(
			v1alphaRoleBinding.Metadata{Name: roleBindingName},
			v1alphaRoleBinding.Spec{
				User:       ptr(user.UserID),
				RoleRef:    role,
				ProjectRef: sanitizedProjectRef,
			},
		)
	}

	applyErr := retryWithBackoff(ctx, func() error {
		err := client.Objects().V1().Apply(ctx, []manifest.Object{roleBinding})
		if err != nil {
			errStr := err.Error()
			if strings.Contains(errStr, "Another RoleBinding") && strings.Contains(errStr, "already exists") {
				return fmt.Errorf("failed to apply role binding: %w", ErrRoleBindingExists)
			}
			if strings.Contains(errStr, "Project") && strings.Contains(errStr, "not found") {
				return fmt.Errorf("failed to apply role binding: %w", ErrProjectNotFound)
			}
			if strings.Contains(errStr, "Validation") {
				return fmt.Errorf("failed to apply role binding: %w", ErrValidation)
			}
			return err
		}
		return nil
	})
	if applyErr != nil {
		return applyErr
	}

	if isOrgRole {
		log.Printf("Successfully assigned organization role '%s' to user '%s'", role, userEmail)
	} else {
		log.Printf("Successfully assigned role '%s' to user '%s' in project '%s'", role, userEmail, projectName)
	}
	return nil
}

// parseCSVFile parses the CSV file and returns the data rows
func parseCSVFile(filename string) ([]CSVRow, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, fmt.Errorf("cannot open CSV file: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("cannot read CSV file: %v", err)
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("CSV file must have at least a header row and one data row")
	}

	// Find column indices; only project-name and user email are required
	header := records[0]
	var projectIdx, userEmailIdx = -1, -1

	for i, col := range header {
		colLower := strings.ToLower(strings.TrimSpace(col))
		switch colLower {
		case "project-name", "project name":
			projectIdx = i
		case "user email":
			userEmailIdx = i
		}
	}

	if projectIdx == -1 || userEmailIdx == -1 {
		return nil, fmt.Errorf("CSV file must contain 'project-name' and 'user email' columns")
	}

	// Parse data rows
	var rows []CSVRow
	for i, record := range records[1:] {
		if len(record) <= projectIdx || len(record) <= userEmailIdx {
			log.Printf("Warning: Row %d has insufficient columns, skipping", i+2)
			continue
		}

		row := CSVRow{
			ProjectName: strings.TrimSpace(record[projectIdx]),
			UserEmail:   strings.TrimSpace(record[userEmailIdx]),
		}

		// Skip empty rows
		if row.ProjectName == "" && row.UserEmail == "" {
			continue
		}

		rows = append(rows, row)
	}

	return rows, nil
}

// validateCSVFile performs pre-flight checks: file exists, readable, non-empty.
// Call before opening the CSV for bulk processing to fail fast.
func validateCSVFile(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("CSV file does not exist: %s", path)
		}
		return fmt.Errorf("CSV file inaccessible: %w", err)
	}
	if info.IsDir() {
		return fmt.Errorf("CSV path is a directory, not a file: %s", path)
	}
	if info.Size() == 0 {
		return fmt.Errorf("CSV file is empty: %s", path)
	}
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("CSV file not readable: %w", err)
	}
	f.Close()
	return nil
}

// getExistingProjectNames returns the set of project names that exist in Nobl9 (for pre-flight validation).
func getExistingProjectNames(ctx context.Context, client *sdk.Client) (map[string]bool, error) {
	projects, err := client.Objects().V1().GetV1alphaProjects(ctx, objectsV1.GetProjectsRequest{})
	if err != nil {
		return nil, err
	}
	out := make(map[string]bool, len(projects))
	for i := range projects {
		p := &projects[i]
		name := p.Metadata.Name
		out[name] = true
		// Also allow sanitized form if it differs
		if s := sanitizeName(name); s != name {
			out[s] = true
		}
	}
	return out, nil
}

// validateProjectsInCSV ensures every unique project name in the CSV exists in Nobl9.
// Returns a list of missing project names, or nil if all exist.
func validateProjectsInCSV(ctx context.Context, client *sdk.Client, filename string) (missing []string, err error) {
	rows, err := parseCSVFile(filename)
	if err != nil {
		return nil, err
	}
	existing, err := getExistingProjectNames(ctx, client)
	if err != nil {
		return nil, fmt.Errorf("failed to list projects: %w", err)
	}
	seen := make(map[string]bool)
	for _, row := range rows {
		p := strings.TrimSpace(row.ProjectName)
		if p == "" {
			continue
		}
		if seen[p] {
			continue
		}
		seen[p] = true
		sanitized := sanitizeName(p)
		if !existing[p] && !existing[sanitized] {
			missing = append(missing, p)
		}
	}
	return missing, nil
}

// validateCSVRows validates all rows for structure (project when required, email format).
// Used by --validate-only. Returns a list of validation errors and whether all rows are valid.
func validateCSVRows(rows []CSVRow, isOrgRole bool) (invalid []string, valid bool) {
	valid = true
	for i, row := range rows {
		if !isOrgRole && row.ProjectName == "" {
			invalid = append(invalid, fmt.Sprintf("Row %d: empty project name (required for project-level roles)", i+1))
			valid = false
		}
		if row.UserEmail == "" {
			invalid = append(invalid, fmt.Sprintf("Row %d: empty user email", i+1))
			valid = false
		} else if !validateEmail(row.UserEmail) {
			invalid = append(invalid, fmt.Sprintf("Row %d: invalid email format '%s'", i+1, row.UserEmail))
			valid = false
		}
	}
	return invalid, valid
}

// processBulkAssignment processes the CSV file for bulk role assignments.
// delay is the pause between successful assignments (ignored in dry-run).
func processBulkAssignment(ctx context.Context, client *sdk.Client, filename, role string, dryRun bool, delay time.Duration) (*ProcessingStats, error) {
	stats := &ProcessingStats{}

	// Parse CSV file
	rows, err := parseCSVFile(filename)
	if err != nil {
		return stats, err
	}

	stats.TotalRows = len(rows)
	log.Printf("Processing %d rows from CSV file...", stats.TotalRows)

	if dryRun {
		log.Printf("DRY RUN MODE: No actual changes will be made")
	}

	// Check if role is organization-level
	isOrgRole := isOrganizationRole(role)

	// Process each row
	for i, row := range rows {
		if ctx.Err() != nil {
			return stats, ctx.Err()
		}
		stats.Processed++

		if isOrgRole {
			log.Printf("Processing row %d: Organization role, User '%s'", i+1, row.UserEmail)
		} else {
			log.Printf("Processing row %d: Project '%s', User '%s'", i+1, row.ProjectName, row.UserEmail)
		}

		// Validate row data
		// Project is required for project-level roles, optional for organization roles
		if !isOrgRole && row.ProjectName == "" {
			err := fmt.Sprintf("Row %d: Empty project name (required for project-level roles)", i+1)
			log.Printf("Skipping - %s", err)
			stats.SkippedInvalidData++
			stats.Errors = append(stats.Errors, err)
			continue
		}

		if row.UserEmail == "" {
			err := fmt.Sprintf("Row %d: Empty user email", i+1)
			log.Printf("Skipping - %s", err)
			stats.SkippedInvalidData++
			stats.Errors = append(stats.Errors, err)
			continue
		}

		if !validateEmail(row.UserEmail) {
			err := fmt.Sprintf("Row %d: Invalid email format '%s'", i+1, row.UserEmail)
			log.Printf("Skipping - %s", err)
			stats.SkippedInvalidData++
			stats.Errors = append(stats.Errors, err)
			continue
		}

		// Attempt to assign role (for organization roles, project name is ignored)
		err := assignRole(ctx, client, row.ProjectName, row.UserEmail, role, dryRun)
		if err != nil {
			errorMsg := fmt.Sprintf("Row %d: %v", i+1, err)

			switch {
			case errors.Is(err, ErrAlreadyAssigned), errors.Is(err, ErrRoleBindingExists):
				if isOrgRole {
					log.Printf("User '%s' already has organization role '%s' - skipping", row.UserEmail, role)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> organization", row.UserEmail))
				} else {
					log.Printf("User '%s' already has role '%s' for project '%s' - skipping", row.UserEmail, role, row.ProjectName)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> %s", row.UserEmail, row.ProjectName))
				}
				stats.SkippedAlreadyOwner++
			case errors.Is(err, ErrUserNotFound):
				if isOrgRole {
					log.Printf("User '%s' not found in Nobl9 - skipping organization role assignment", row.UserEmail)
				} else {
					log.Printf("User '%s' not found in Nobl9 - skipping assignment for project '%s'", row.UserEmail, row.ProjectName)
				}
				stats.SkippedUserNotExists++
				stats.MissingUsers = append(stats.MissingUsers, row.UserEmail)
			case errors.Is(err, ErrProjectNotFound):
				log.Printf("Project '%s' not found in Nobl9 - skipping assignment for user '%s'", row.ProjectName, row.UserEmail)
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Project '%s' not found", i+1, row.ProjectName))
				stats.MissingProjects = append(stats.MissingProjects, row.ProjectName)
			case errors.Is(err, ErrProjectRequired):
				log.Printf("Row %d: Project-level role '%s' requires a project name", i+1, role)
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Project required for role '%s'", i+1, role))
			case errors.Is(err, ErrValidation):
				if isOrgRole {
					log.Printf("Validation error for user '%s': %v", row.UserEmail, err)
				} else {
					log.Printf("Validation error for project '%s', user '%s': %v", row.ProjectName, row.UserEmail, err)
				}
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Validation error - %s", i+1, err.Error()))
			default:
				log.Printf("Failed to assign role: %v", err)
				stats.Failed++
				stats.Errors = append(stats.Errors, errorMsg)
			}
		} else {
			stats.Assigned++

			if !dryRun && delay > 0 {
				time.Sleep(delay)
			}
		}
	}

	return stats, nil
}

// printStats prints the processing statistics
func printStats(stats *ProcessingStats) {
	fmt.Println("\n" + strings.Repeat("=", 50))
	fmt.Println("PROCESSING SUMMARY")
	fmt.Println(strings.Repeat("=", 50))
	fmt.Printf("Total rows processed: %d\n", stats.TotalRows)
	fmt.Printf("Successfully assigned: %d\n", stats.Assigned)
	fmt.Printf("Skipped (already assigned): %d\n", stats.SkippedAlreadyOwner)
	fmt.Printf("Skipped (user not exists): %d\n", stats.SkippedUserNotExists)
	fmt.Printf("Skipped (invalid/missing projects): %d\n", stats.SkippedInvalidData)
	fmt.Printf("Failed: %d\n", stats.Failed)

	if len(stats.Errors) > 0 {
		fmt.Printf("\nErrors encountered (%d):\n", len(stats.Errors))
		for i, err := range stats.Errors {
			fmt.Printf("  %d. %s\n", i+1, err)
			if i >= 9 { // Show max 10 errors
				fmt.Printf("  ... and %d more errors\n", len(stats.Errors)-10)
				break
			}
		}
	}

	// Helper to unique and sort small lists
	uniqueSorted := func(items []string) []string {
		if len(items) == 0 {
			return items
		}
		m := make(map[string]struct{}, len(items))
		out := make([]string, 0, len(items))
		for _, it := range items {
			if _, ok := m[it]; !ok {
				m[it] = struct{}{}
				out = append(out, it)
			}
		}
		// simple insertion sort; lists are small
		for i := 1; i < len(out); i++ {
			j := i
			for j > 0 && out[j-1] > out[j] {
				out[j-1], out[j] = out[j], out[j-1]
				j--
			}
		}
		return out
	}

	if len(stats.MissingUsers) > 0 {
		fmt.Printf("\nUsers not found in Nobl9 (%d):\n", len(stats.MissingUsers))
		for _, u := range uniqueSorted(stats.MissingUsers) {
			fmt.Printf("  - %s\n", u)
		}
	}

	if len(stats.MissingProjects) > 0 {
		fmt.Printf("\nProjects not found or invalid (%d):\n", len(stats.MissingProjects))
		for _, p := range uniqueSorted(stats.MissingProjects) {
			fmt.Printf("  - %s\n", p)
		}
	}

	if len(stats.AlreadyAssigned) > 0 {
		fmt.Printf("\nAlready assigned (unique user -> project pairs, %d):\n", len(stats.AlreadyAssigned))
		for _, ap := range uniqueSorted(stats.AlreadyAssigned) {
			fmt.Printf("  - %s\n", ap)
		}
	}
}

func main() {
	// Define command-line flags
	var (
		projectFlag       = flag.String("project", "", "Name of the project (required for project-level roles, optional for organization roles)")
		emailFlag         = flag.String("email", "", "Email of the user to add (single user mode)")
		roleFlag          = flag.String("role", "project-owner", "Role to assign to the user")
		csvFlag           = flag.String("csv", "", "Path to CSV file for bulk processing")
		dryRunFlag        = flag.Bool("dry-run", false, "Perform a dry run without making actual changes")
		validateOnlyFlag  = flag.Bool("validate-only", false, "Only validate CSV structure and exit (use with --csv)")
		timeoutFlag       = flag.Duration("timeout", 5*time.Minute, "Timeout for API operations")
		delayFlag         = flag.Duration("delay", 500*time.Millisecond, "Delay between API calls in bulk mode")
		logFileFlag       = flag.String("log-file", "", "Optional log file path (logs are also written to stderr)")
		strictFlag        = flag.Bool("strict", false, "Exit with code 1 if any rows were skipped (e.g. missing user, invalid data)")
		validateProjFlag  = flag.Bool("validate-projects", false, "In bulk project-level mode, validate all project names exist before applying")
		helpFlag          = flag.Bool("help", false, "Show help message")
	)
	flag.Parse()

	// Show help if requested
	if *helpFlag {
		fmt.Println("Nobl9 User Role Manager")
		fmt.Println("=======================")
		fmt.Println()
		fmt.Println("This tool assigns roles to users in Nobl9 projects or at the organization level.")
		fmt.Println()
		fmt.Println("MODES:")
		fmt.Println("  Single User Mode: Use --email and --role flags (--project optional for org roles)")
		fmt.Println("  Bulk CSV Mode: Use --csv flag with optional --role")
		fmt.Println()
		fmt.Println("FLAGS:")
		flag.PrintDefaults()
		fmt.Println()
		fmt.Printf("Valid roles: %s\n", getValidRoles())
		fmt.Println()
		fmt.Println("ROLE TYPES:")
		fmt.Println("  Project-level roles: Require --project flag (project-viewer, project-editor, etc.)")
		fmt.Println("  Organization-level roles: Do not require --project flag (organization-admin, etc.)")
		fmt.Println()
		fmt.Println("CSV FORMAT:")
		fmt.Println("  Required columns: 'project-name', 'user email'")
		fmt.Println("  For organization roles, project-name can be empty")
		fmt.Println()
		fmt.Println("ENVIRONMENT VARIABLES:")
		fmt.Println("  NOBL9_CLIENT_ID: Your Nobl9 API Client ID")
		fmt.Println("  NOBL9_CLIENT_SECRET: Your Nobl9 API Client Secret")
		fmt.Println()
		fmt.Println("EXAMPLES:")
		fmt.Println("  Project role:  ./add-user-role --project myproject --email user@example.com --role project-owner")
		fmt.Println("  Org role:      ./add-user-role --email user@example.com --role organization-admin")
		fmt.Println("  Bulk CSV:      ./add-user-role --csv projects.csv --role project-owner")
		fmt.Println("  Dry run:       ./add-user-role --csv projects.csv --dry-run")
		fmt.Println("  Validate only: ./add-user-role --csv projects.csv --validate-only")
		fmt.Println("  With options:  ./add-user-role --csv projects.csv --timeout 30m --delay 1s --log-file run.log")
		return
	}

	// Validate role
	if !validRoles[*roleFlag] {
		log.Fatalf("Error: Invalid role '%s'. Must be one of: %v", *roleFlag, getValidRoles())
	}

	// Determine mode: single user or bulk CSV
	isSingleMode := *emailFlag != ""
	isBulkMode := *csvFlag != ""

	if isSingleMode && isBulkMode {
		log.Fatal("Error: Cannot use single user mode flags (--email) with bulk mode flag (--csv)")
	}

	if !isSingleMode && !isBulkMode {
		log.Fatal("Error: Must specify either single user mode (--email) or bulk mode (--csv)")
	}

	if *validateOnlyFlag && !isBulkMode {
		log.Fatal("Error: --validate-only requires --csv")
	}

	// Validate-only mode: check CSV file and row structure, then exit (no API/client needed)
	if *validateOnlyFlag {
		if err := validateCSVFile(*csvFlag); err != nil {
			log.Fatalf("Error: %v", err)
		}
		rows, err := parseCSVFile(*csvFlag)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		isOrgRole := isOrganizationRole(*roleFlag)
		invalid, ok := validateCSVRows(rows, isOrgRole)
		if ok {
			fmt.Printf("Validation passed: %d rows valid\n", len(rows))
			return
		}
		fmt.Fprintf(os.Stderr, "Validation failed: %d error(s)\n", len(invalid))
		for _, msg := range invalid {
			fmt.Fprintf(os.Stderr, "  - %s\n", msg)
		}
		os.Exit(1)
	}

	// Check if role is organization-level
	isOrgRole := isOrganizationRole(*roleFlag)

	// Single user mode validation
	if isSingleMode {
		if *emailFlag == "" {
			log.Fatal("Error: --email is required for single user mode")
		}

		if !validateEmail(*emailFlag) {
			log.Fatal("Error: Invalid email format")
		}

		// Project is required for project-level roles, optional for organization roles
		if !isOrgRole && *projectFlag == "" {
			log.Fatalf("Error: --project is required for project-level role '%s'", *roleFlag)
		}
	}

	// Check environment variables
	clientID := os.Getenv("NOBL9_CLIENT_ID")
	clientSecret := os.Getenv("NOBL9_CLIENT_SECRET")
	if clientID == "" || clientSecret == "" {
		log.Fatal("Error: Environment variables NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET must be set")
	}

	// Set environment variables for the SDK
	os.Setenv("NOBL9_CLIENT_ID", clientID)
	os.Setenv("NOBL9_CLIENT_SECRET", clientSecret)

	// Pre-flight: bulk mode CSV file must exist and be readable
	if isBulkMode {
		if err := validateCSVFile(*csvFlag); err != nil {
			log.Fatalf("Error: %v", err)
		}
	}

	// Optional log file: tee log output to file and stderr
	if *logFileFlag != "" {
		f, err := os.OpenFile(*logFileFlag, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
		if err != nil {
			log.Fatalf("Error: cannot open log file %s: %v", *logFileFlag, err)
		}
		defer f.Close()
		log.SetOutput(io.MultiWriter(os.Stderr, f))
	}

	// Context: timeout and signal cancellation
	ctx, cancel := context.WithTimeout(context.Background(), *timeoutFlag)
	defer cancel()
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	// Initialize the Nobl9 client
	client, err := sdk.DefaultClient()
	if err != nil {
		log.Fatalf("Error: Failed to create Nobl9 client: %v", err)
	}

	if *dryRunFlag {
		log.Println("DRY RUN MODE: No actual changes will be made")
	}

	// Execute based on mode
	if isSingleMode {
		// Single user mode
		if isOrgRole {
			log.Printf("Processing single user assignment: %s (%s)", *emailFlag, *roleFlag)
		} else {
			log.Printf("Processing single user assignment: %s -> %s (%s)", *emailFlag, *projectFlag, *roleFlag)
		}

		err := assignRole(ctx, client, *projectFlag, *emailFlag, *roleFlag, *dryRunFlag)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}

		if isOrgRole {
			fmt.Printf("Success: Assigned organization role '%s' to user '%s'\n", *roleFlag, *emailFlag)
		} else {
			fmt.Printf("Success: Assigned role '%s' to user '%s' in project '%s'\n", *roleFlag, *emailFlag, *projectFlag)
		}
	} else {
		// Bulk CSV mode
		if *validateProjFlag && !isOrgRole {
			missing, err := validateProjectsInCSV(ctx, client, *csvFlag)
			if err != nil {
				log.Fatalf("Error during project validation: %v", err)
			}
			if len(missing) > 0 {
				log.Printf("The following projects from the CSV do not exist in Nobl9:")
				for _, p := range missing {
					log.Printf("  - %s", p)
				}
				os.Exit(1)
			}
			log.Printf("Pre-flight project validation passed")
		}

		log.Printf("Processing bulk assignment from CSV: %s (role: %s)", *csvFlag, *roleFlag)

		stats, err := processBulkAssignment(ctx, client, *csvFlag, *roleFlag, *dryRunFlag, *delayFlag)
		if err != nil {
			log.Fatalf("Error during bulk processing: %v", err)
		}

		printStats(stats)

		// Exit with error code if there were failures
		if stats.Failed > 0 {
			os.Exit(1)
		}
		// Strict: exit 1 if any rows were skipped
		if *strictFlag && (stats.SkippedAlreadyOwner > 0 || stats.SkippedUserNotExists > 0 || stats.SkippedInvalidData > 0) {
			os.Exit(1)
		}
	}
}
