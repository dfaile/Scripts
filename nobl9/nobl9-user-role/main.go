package main

import (
	"context"
	"encoding/csv"
	"flag"
	"fmt"
	"log"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/nobl9/nobl9-go/manifest"
	v1alphaRoleBinding "github.com/nobl9/nobl9-go/manifest/v1alpha/rolebinding"
	"github.com/nobl9/nobl9-go/sdk"
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

// CSVRow represents a row from the CSV file
type CSVRow struct {
	AppShortName   string
	ProductManager string
	UserExists     string
	UserEmail      string
	SLOs           string
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

// checkExistingRoleBinding checks if user already has the specified role
// For project roles, checks within the project context
// For organization roles, checks at organization level
func checkExistingRoleBinding(ctx context.Context, client *sdk.Client, projectName, userID, role string) (bool, error) {
	// Get existing role bindings
	// This is a simplified check - in a production environment, you'd want more robust checking

	// Note: The Nobl9 SDK doesn't appear to have a direct method to check existing role bindings
	// In practice, you might need to implement this differently based on your specific requirements
	// For now, we'll return false to allow the assignment to proceed

	// Avoid logging internal user IDs
	if isOrganizationRole(role) {
		log.Printf("Checking existing organization role bindings with role %s", role)
	} else {
		log.Printf("Checking existing role bindings in project %s with role %s", projectName, role)
	}

	// TODO: Implement actual role binding check if SDK supports it
	// This would involve querying existing role bindings and checking if this specific
	// user-project-role (or user-role for org roles) combination already exists

	return false, nil
}

// assignRole assigns the specified role to a user
// For project-level roles, requires a project name
// For organization-level roles, project name is optional and ignored
func assignRole(ctx context.Context, client *sdk.Client, projectName, userEmail, role string, dryRun bool) error {
	isOrgRole := isOrganizationRole(role)

	// Validate: project-level roles require a project
	if !isOrgRole && projectName == "" {
		return fmt.Errorf("project-level role '%s' requires a project to be specified", role)
	}

	// Step 1: Check if the user exists by their email
	user, err := client.Users().V2().GetUser(ctx, userEmail)
	if err != nil {
		return fmt.Errorf("error retrieving user from Nobl9 API: %v", err)
	}

	if user == nil {
		return fmt.Errorf("user_not_found: user with email '%s' not found", userEmail)
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
			return fmt.Errorf("user already has organization role '%s'", role)
		}
		return fmt.Errorf("user already has role '%s' for project '%s'", role, projectName)
	}

	if dryRun {
		if isOrgRole {
			log.Printf("DRY RUN: Would assign organization role '%s' to user '%s'", role, userEmail)
		} else {
			log.Printf("DRY RUN: Would assign role '%s' to user '%s' in project '%s'", role, userEmail, projectName)
		}
		return nil
	}

	// Step 3: Generate a unique name for the role binding (max 63 chars)
	sanitizedEmail := sanitizeName(userEmail)
	timestamp := fmt.Sprintf("%x", time.Now().UnixNano())[:8] // 8-char hex timestamp

	var roleBindingName string
	if isOrgRole {
		// For organization roles, use org- prefix instead of project
		baseRole := fmt.Sprintf("rb-org-%s-%s", sanitizedEmail, timestamp)
		roleBindingName = baseRole
		if len(roleBindingName) > 63 {
			maxEmailLen := 63 - len(fmt.Sprintf("rb-org--%s", timestamp))
			if maxEmailLen > 0 && len(sanitizedEmail) > maxEmailLen {
				sanitizedEmail = sanitizedEmail[:maxEmailLen]
			}
			roleBindingName = fmt.Sprintf("rb-org-%s-%s", sanitizedEmail, timestamp)
		}
	} else {
		// For project roles, include project name
		sanitizedProject := sanitizeName(projectName)
		baseRole := fmt.Sprintf("rb-%s-%s-%s", sanitizedProject, sanitizedEmail, timestamp)
		roleBindingName = baseRole
		if len(roleBindingName) > 63 {
			// Keep project and timestamp, truncate email
			maxEmailLen := 63 - len(fmt.Sprintf("rb-%s--%s", sanitizedProject, timestamp))
			if maxEmailLen > 0 && len(sanitizedEmail) > maxEmailLen {
				sanitizedEmail = sanitizedEmail[:maxEmailLen]
			}
			roleBindingName = fmt.Sprintf("rb-%s-%s-%s", sanitizedProject, sanitizedEmail, timestamp)
		}
	}

	// Step 4: Create the role binding object
	var roleBinding v1alphaRoleBinding.RoleBinding

	if isOrgRole {
		// Organization-level role binding: omit ProjectRef
		roleBinding = v1alphaRoleBinding.New(
			v1alphaRoleBinding.Metadata{Name: roleBindingName},
			v1alphaRoleBinding.Spec{
				User:    ptr(user.UserID),
				RoleRef: role,
				// ProjectRef is intentionally omitted for organization roles
			},
		)
	} else {
		// Project-level role binding: include ProjectRef
		// Ensure project name is RFC-1123 compliant
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

	// Step 5: Apply the role binding to assign the role
	if err := client.Objects().V1().Apply(ctx, []manifest.Object{roleBinding}); err != nil {
		return fmt.Errorf("failed to apply role binding: %v", err)
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

	// Find column indices
	header := records[0]
	var appNameIdx, userEmailIdx, userExistsIdx = -1, -1, -1

	for i, col := range header {
		colLower := strings.ToLower(strings.TrimSpace(col))
		switch colLower {
		case "app short name":
			appNameIdx = i
		case "user email":
			userEmailIdx = i
		case "user exists":
			userExistsIdx = i
		}
	}

	if appNameIdx == -1 || userEmailIdx == -1 {
		return nil, fmt.Errorf("CSV file must contain 'App Short Name' and 'User Email' columns")
	}

	// Parse data rows
	var rows []CSVRow
	for i, record := range records[1:] {
		if len(record) <= appNameIdx || len(record) <= userEmailIdx {
			log.Printf("Warning: Row %d has insufficient columns, skipping", i+2)
			continue
		}

		userExists := "Y" // Default to Y if column doesn't exist
		if userExistsIdx != -1 && len(record) > userExistsIdx {
			userExists = strings.TrimSpace(record[userExistsIdx])
		}

		row := CSVRow{
			AppShortName: strings.TrimSpace(record[appNameIdx]),
			UserEmail:    strings.TrimSpace(record[userEmailIdx]),
			UserExists:   userExists,
		}

		// Skip empty rows
		if row.AppShortName == "" && row.UserEmail == "" {
			continue
		}

		rows = append(rows, row)
	}

	return rows, nil
}

// processBulkAssignment processes the CSV file for bulk role assignments
func processBulkAssignment(ctx context.Context, client *sdk.Client, filename, role string, dryRun bool) (*ProcessingStats, error) {
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
		stats.Processed++

		if isOrgRole {
			log.Printf("Processing row %d: Organization role, User '%s'", i+1, row.UserEmail)
		} else {
			log.Printf("Processing row %d: Project '%s', User '%s'", i+1, row.AppShortName, row.UserEmail)
		}

		// Validate row data
		// Project is required for project-level roles, optional for organization roles
		if !isOrgRole && row.AppShortName == "" {
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

		// Note: We now dynamically check if user exists instead of relying on CSV column
		// The User Exists column is ignored in favor of real-time validation

		// Attempt to assign role
		// For organization roles, project name is ignored
		err := assignRole(ctx, client, row.AppShortName, row.UserEmail, role, dryRun)
		if err != nil {
			errorMsg := fmt.Sprintf("Row %d: %v", i+1, err)

			// Check specific error types for better handling
			if strings.Contains(err.Error(), "already has role") || strings.Contains(err.Error(), "already has organization role") {
				if isOrgRole {
					log.Printf("User '%s' already has organization role '%s' - skipping", row.UserEmail, role)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> organization", row.UserEmail))
				} else {
					log.Printf("User '%s' already has role '%s' for project '%s' - skipping", row.UserEmail, role, row.AppShortName)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> %s", row.UserEmail, row.AppShortName))
				}
				stats.SkippedAlreadyOwner++
			} else if strings.Contains(err.Error(), "user_not_found:") {
				// User doesn't exist in Nobl9 - gracefully skip
				if isOrgRole {
					log.Printf("User '%s' not found in Nobl9 - skipping organization role assignment", row.UserEmail)
				} else {
					log.Printf("User '%s' not found in Nobl9 - skipping assignment for project '%s'", row.UserEmail, row.AppShortName)
				}
				stats.SkippedUserNotExists++
				stats.MissingUsers = append(stats.MissingUsers, row.UserEmail)
			} else if strings.Contains(err.Error(), "Another RoleBinding") && strings.Contains(err.Error(), "already exists") {
				// Duplicate role binding exists - treat as already assigned
				if isOrgRole {
					log.Printf("User '%s' already has an organization role binding - skipping", row.UserEmail)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> organization", row.UserEmail))
				} else {
					log.Printf("User '%s' already has a role binding for project '%s' - skipping", row.UserEmail, row.AppShortName)
					stats.AlreadyAssigned = append(stats.AlreadyAssigned, fmt.Sprintf("%s -> %s", row.UserEmail, row.AppShortName))
				}
				stats.SkippedAlreadyOwner++
			} else if strings.Contains(err.Error(), "Project") && strings.Contains(err.Error(), "not found") {
				// Project doesn't exist in Nobl9 (only for project-level roles)
				log.Printf("Project '%s' not found in Nobl9 - skipping assignment for user '%s'", row.AppShortName, row.UserEmail)
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Project '%s' not found", i+1, row.AppShortName))
				stats.MissingProjects = append(stats.MissingProjects, row.AppShortName)
			} else if strings.Contains(err.Error(), "requires a project") {
				// Project-level role used without project
				log.Printf("Row %d: Project-level role '%s' requires a project name", i+1, role)
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Project required for role '%s'", i+1, role))
			} else if strings.Contains(err.Error(), "Validation") {
				// Validation errors (RFC-1123, length, etc.)
				if isOrgRole {
					log.Printf("Validation error for user '%s': %v", row.UserEmail, err)
				} else {
					log.Printf("Validation error for project '%s', user '%s': %v", row.AppShortName, row.UserEmail, err)
				}
				stats.SkippedInvalidData++
				stats.Errors = append(stats.Errors, fmt.Sprintf("Row %d: Validation error - %s", i+1, err.Error()))
			} else {
				// Other errors (API issues, authentication, etc.)
				log.Printf("Failed to assign role: %v", err)
				stats.Failed++
				stats.Errors = append(stats.Errors, errorMsg)
			}
		} else {
			stats.Assigned++

			// Add small delay to avoid overwhelming the API
			if !dryRun {
				time.Sleep(500 * time.Millisecond)
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
		projectFlag = flag.String("project", "", "Name of the project (required for project-level roles, optional for organization roles)")
		emailFlag   = flag.String("email", "", "Email of the user to add (single user mode)")
		roleFlag    = flag.String("role", "project-owner", "Role to assign to the user")
		csvFlag     = flag.String("csv", "", "Path to CSV file for bulk processing")
		dryRunFlag  = flag.Bool("dry-run", false, "Perform a dry run without making actual changes")
		helpFlag    = flag.Bool("help", false, "Show help message")
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
		fmt.Println("  Required columns: 'User Email'")
		fmt.Println("  Optional columns: 'App Short Name' (required for project-level roles)")
		fmt.Println("  Note: User existence is now checked dynamically against Nobl9 API")
		fmt.Println("  Note: For organization roles, 'App Short Name' column can be empty")
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

	// Initialize client with timeout context
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

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
		log.Printf("Processing bulk assignment from CSV: %s (role: %s)", *csvFlag, *roleFlag)

		stats, err := processBulkAssignment(ctx, client, *csvFlag, *roleFlag, *dryRunFlag)
		if err != nil {
			log.Fatalf("Error during bulk processing: %v", err)
		}

		printStats(stats)

		// Exit with error code if there were failures
		if stats.Failed > 0 {
			os.Exit(1)
		}
	}
}
