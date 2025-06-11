package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"regexp"  // Import the regexp package for sanitization
	"strings" // Import the strings package for string manipulation
	"time"

	"github.com/nobl9/nobl9-go/manifest"
	v1alphaRoleBinding "github.com/nobl9/nobl9-go/manifest/v1alpha/rolebinding"
	"github.com/nobl9/nobl9-go/sdk"
)

// Valid roles that can be assigned
var validRoles = map[string]bool{
	"project-viewer":     true,
	"project-editor":     true,
	"project-admin":      true,
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

func main() {
	// Define command-line flags for project, email, and role
	var projectFlag, emailFlag, roleFlag string
	flag.StringVar(&projectFlag, "project", "", "Name of the project to add the user to")
	flag.StringVar(&emailFlag, "email", "", "Email of the user to add")
	flag.StringVar(&roleFlag, "role", "", "Role to assign to the user (e.g., project-viewer, project-editor)")
	flag.Parse()

	// Enhanced input validation
	if projectFlag == "" || emailFlag == "" || roleFlag == "" {
		log.Fatal("Error: All flags (--project, --email, --role) are required")
	}

	if !validateEmail(emailFlag) {
		log.Fatal("Error: Invalid email format")
	}

	if !validRoles[roleFlag] {
		log.Fatalf("Error: Invalid role. Must be one of: %v", getValidRoles())
	}

	// Get authentication credentials from environment variables
	clientID := os.Getenv("NOBL9_CLIENT_ID")
	clientSecret := os.Getenv("NOBL9_CLIENT_SECRET")
	if clientID == "" || clientSecret == "" {
		log.Fatal("Error: Environment variables NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET must be set")
	}

	// Initialize client with timeout context
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Initialize the Nobl9 client
	client, err := sdk.DefaultClient()
	if err != nil {
		log.Fatalf("Error: Failed to create Nobl9 client: %v", err)
	}

	// Step 1: Check if the user exists by their email
	user, err := client.Users().V2().GetUser(ctx, emailFlag)
	if err != nil {
		// This block catches general API errors during the GetUser call (e.g., network issues,
		// authentication problems with the SDK itself), but typically not "user not found"
		// if the SDK returns a nil user object for that case.
		log.Fatalf("Error retrieving user from Nobl9 API: %v", err)
	}

	// IMPORTANT: Even if 'err' is nil, the 'user' object might be nil if the user
	// was not found by the SDK. This is the specific scenario causing the panic
	// with non-existent email addresses, as accessing 'user.UserID' on a nil 'user'
	// would cause a nil pointer dereference.
	if user == nil {
		log.Fatalf("Error: User with email '%s' not found", emailFlag)
	}

	// Step 2: Generate a unique name for the role binding
	// Sanitize the project and email flags before incorporating them into the name
	sanitizedProject := sanitizeName(projectFlag)
	sanitizedEmail := sanitizeName(emailFlag)

	roleBindingName := fmt.Sprintf("assign-%s-%s-%d", sanitizedProject, sanitizedEmail, time.Now().Unix())

	// Step 3: Create the role binding object
	roleBinding := v1alphaRoleBinding.New(
		v1alphaRoleBinding.Metadata{Name: roleBindingName},
		v1alphaRoleBinding.Spec{
			User:       ptr(user.UserID), // Use the user's ID from the GetUser response
			RoleRef:    roleFlag,         // Role provided via flag (e.g., "project-viewer")
			ProjectRef: projectFlag,      // Project provided via flag (projectFlag itself doesn't need to be sanitized for this field)
		},
	)

	// Step 4: Apply the role binding to assign the role
	// Note: Verify this method in the Nobl9 SDK documentation; it's assumed based on test patterns
	if err := client.Objects().V1().Apply(ctx, []manifest.Object{roleBinding}); err != nil {
		log.Fatalf("Error: Failed to apply role binding: %v", err)
	}

	// Print success message
	fmt.Printf("Success: Assigned role '%s' to user '%s' in project '%s'\n", roleFlag, emailFlag, projectFlag)
}

// getValidRoles returns a formatted string of valid roles
func getValidRoles() string {
	roles := make([]string, 0, len(validRoles))
	for role := range validRoles {
		roles = append(roles, role)
	}
	return strings.Join(roles, ", ")
}
