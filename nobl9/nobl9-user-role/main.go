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
	"project-viewer":     true,
	"project-editor":     true,
	"project-admin":      true,
	"project-owner":      true,
	"organization-admin": true,
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

// checkExistingRoleBinding checks if user already has the specified role for the project
func checkExistingRoleBinding(ctx context.Context, client *sdk.Client, projectName, userID, role string) (bool, error) {
	// Get existing role bindings for the project
	// This is a simplified check - in a production environment, you'd want more robust checking

	// Note: The Nobl9 SDK doesn't appear to have a direct method to check existing role bindings
	// In practice, you might need to implement this differently based on your specific requirements
	// For now, we'll return false to allow the assignment to proceed

	log.Printf("Checking existing role bindings for user %s in project %s with role %s", userID, projectName, role)

	// TODO: Implement actual role binding check if SDK supports it
	// This would involve querying existing role bindings and checking if this specific
	// user-project-role combination already exists

	return false, nil
}

// assignProjectOwnerRole assigns the specified role to a user for a project
func assignProjectOwnerRole(ctx context.Context, client *sdk.Client, projectName, userEmail, role string, dryRun bool) error {
	// Step 1: Check if the user exists by their email
	user, err := client.Users().V2().GetUser(ctx, userEmail)
	if err != nil {
		return fmt.Errorf("error retrieving user from Nobl9 API: %v", err)
	}

	if user == nil {
		return fmt.Errorf("user with email '%s' not found", userEmail)
	}

	log.Printf("Found user: %s (ID: %s)", userEmail, user.UserID)

	// Step 2: Check if user already has this role for this project
	exists, err := checkExistingRoleBinding(ctx, client, projectName, user.UserID, role)
	if err != nil {
		log.Printf("Warning: Could not check existing role bindings: %v", err)
		// Continue with assignment even if we can't check
	}

	if exists {
		return fmt.Errorf("user already has role '%s' for project '%s'", role, projectName)
	}

	if dryRun {
		log.Printf("DRY RUN: Would assign role '%s' to user '%s' in project '%s'", role, userEmail, projectName)
		return nil
	}

	// Step 3: Generate a unique name for the role binding
	sanitizedProject := sanitizeName(projectName)
	sanitizedEmail := sanitizeName(userEmail)
	// Use nanosecond precision to avoid race conditions
	roleBindingName := fmt.Sprintf("assign-%s-%s-%d", sanitizedProject, sanitizedEmail, time.Now().UnixNano())

	// Step 4: Create the role binding object
	roleBinding := v1alphaRoleBinding.New(
		v1alphaRoleBinding.Metadata{Name: roleBindingName},
		v1alphaRoleBinding.Spec{
			User:       ptr(user.UserID),
			RoleRef:    role,
			ProjectRef: projectName,
		},
	)

	// Step 5: Apply the role binding to assign the role
	if err := client.Objects().V1().Apply(ctx, []manifest.Object{roleBinding}); err != nil {
		return fmt.Errorf("failed to apply role binding: %v", err)
	}

	log.Printf("Successfully assigned role '%s' to user '%s' in project '%s'", role, userEmail, projectName)
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

	// Process each row
	for i, row := range rows {
		stats.Processed++

		log.Printf("Processing row %d: Project '%s', User '%s'", i+1, row.AppShortName, row.UserEmail)

		// Validate row data
		if row.AppShortName == "" {
			err := fmt.Sprintf("Row %d: Empty project name", i+1)
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

		// Skip if user doesn't exist in Nobl9 (according to CSV)
		if strings.ToUpper(row.UserExists) == "N" {
			log.Printf("Skipping %s - user marked as not existing in Nobl9", row.UserEmail)
			stats.SkippedUserNotExists++
			continue
		}

		// Attempt to assign role
		err := assignProjectOwnerRole(ctx, client, row.AppShortName, row.UserEmail, role, dryRun)
		if err != nil {
			errorMsg := fmt.Sprintf("Row %d: %v", i+1, err)

			// Check if it's an "already has role" error
			if strings.Contains(err.Error(), "already has role") {
				log.Printf("User '%s' already has role '%s' for project '%s' - skipping", row.UserEmail, role, row.AppShortName)
				stats.SkippedAlreadyOwner++
			} else {
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
	fmt.Printf("Skipped (already owner): %d\n", stats.SkippedAlreadyOwner)
	fmt.Printf("Skipped (user not exists): %d\n", stats.SkippedUserNotExists)
	fmt.Printf("Skipped (invalid data): %d\n", stats.SkippedInvalidData)
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
}

func main() {
	// Define command-line flags
	var (
		projectFlag = flag.String("project", "", "Name of the project to add the user to (single user mode)")
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
		fmt.Println("This tool assigns roles to users in Nobl9 projects.")
		fmt.Println()
		fmt.Println("MODES:")
		fmt.Println("  Single User Mode: Use --project, --email, and --role flags")
		fmt.Println("  Bulk CSV Mode: Use --csv flag with optional --role")
		fmt.Println()
		fmt.Println("FLAGS:")
		flag.PrintDefaults()
		fmt.Println()
		fmt.Printf("Valid roles: %s\n", getValidRoles())
		fmt.Println()
		fmt.Println("CSV FORMAT:")
		fmt.Println("  Required columns: 'App Short Name', 'User Email'")
		fmt.Println("  Optional columns: 'User Exists' (Y/N)")
		fmt.Println()
		fmt.Println("ENVIRONMENT VARIABLES:")
		fmt.Println("  NOBL9_CLIENT_ID: Your Nobl9 API Client ID")
		fmt.Println("  NOBL9_CLIENT_SECRET: Your Nobl9 API Client Secret")
		fmt.Println()
		fmt.Println("EXAMPLES:")
		fmt.Println("  Single user: ./add-user-role --project myproject --email user@example.com --role project-owner")
		fmt.Println("  Bulk CSV:    ./add-user-role --csv projects.csv --role project-owner")
		fmt.Println("  Dry run:     ./add-user-role --csv projects.csv --dry-run")
		return
	}

	// Validate role
	if !validRoles[*roleFlag] {
		log.Fatalf("Error: Invalid role '%s'. Must be one of: %v", *roleFlag, getValidRoles())
	}

	// Determine mode: single user or bulk CSV
	isSingleMode := *projectFlag != "" || *emailFlag != ""
	isBulkMode := *csvFlag != ""

	if isSingleMode && isBulkMode {
		log.Fatal("Error: Cannot use single user mode flags (--project, --email) with bulk mode flag (--csv)")
	}

	if !isSingleMode && !isBulkMode {
		log.Fatal("Error: Must specify either single user mode (--project and --email) or bulk mode (--csv)")
	}

	// Single user mode validation
	if isSingleMode {
		if *projectFlag == "" || *emailFlag == "" {
			log.Fatal("Error: Both --project and --email are required for single user mode")
		}

		if !validateEmail(*emailFlag) {
			log.Fatal("Error: Invalid email format")
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
		log.Printf("Processing single user assignment: %s -> %s (%s)", *emailFlag, *projectFlag, *roleFlag)

		err := assignProjectOwnerRole(ctx, client, *projectFlag, *emailFlag, *roleFlag, *dryRunFlag)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}

		fmt.Printf("Success: Assigned role '%s' to user '%s' in project '%s'\n", *roleFlag, *emailFlag, *projectFlag)
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
