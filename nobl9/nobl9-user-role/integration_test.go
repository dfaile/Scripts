//go:build integration

package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const (
	envSloctlBin         = "SLOCTL_BIN"
	envTestContext       = "NOBL9_TEST_CONTEXT"
	envTestUserProject   = "NOBL9_TEST_USER_PROJECT"
	envTestUserOrg       = "NOBL9_TEST_USER_ORG"
	placeholderProject   = "PLACEHOLDER_PROJECT_NAME"
	projectNamePrefix    = "test-role-manager-"
)

// getIntegrationConfig reads env vars and skips the test if any required value is missing.
func getIntegrationConfig(t *testing.T) (sloctlBin, contextName, userProject, userOrg string) {
	t.Helper()
	sloctlBin = os.Getenv(envSloctlBin)
	if sloctlBin == "" {
		sloctlBin = "sloctl"
	}
	contextName = os.Getenv(envTestContext)
	userProject = os.Getenv(envTestUserProject)
	userOrg = os.Getenv(envTestUserOrg)
	var missing []string
	if contextName == "" {
		missing = append(missing, envTestContext)
	}
	if userProject == "" {
		missing = append(missing, envTestUserProject)
	}
	if userOrg == "" {
		missing = append(missing, envTestUserOrg)
	}
	if len(missing) > 0 {
		t.Skipf("integration test skipped: set %s (and optionally %s for sloctl path). Example: NOBL9_TEST_CONTEXT=daniel NOBL9_TEST_USER_PROJECT=user@example.com NOBL9_TEST_USER_ORG=admin@example.com",
			strings.Join(missing, ", "), envSloctlBin)
	}
	if os.Getenv("NOBL9_CLIENT_ID") == "" || os.Getenv("NOBL9_CLIENT_SECRET") == "" {
		t.Skip("integration test skipped: NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET must be set")
	}
	return sloctlBin, contextName, userProject, userOrg
}

// runSloctl runs sloctl with the given args and context. Returns combined output and error.
func runSloctl(sloctlBin, contextName string, args ...string) ([]byte, error) {
	all := []string{}
	if contextName != "" {
		all = append(all, "--context", contextName)
	}
	all = append(all, args...)
	cmd := exec.Command(sloctlBin, all...)
	cmd.Env = os.Environ()
	return cmd.CombinedOutput()
}

// runBinary runs the add-user-role binary (must exist at binaryPath) with args. Returns output and exit code.
func runBinary(binaryPath string, args ...string) (stdout, stderr []byte, code int, err error) {
	cmd := exec.Command(binaryPath, args...)
	cmd.Env = os.Environ()
	var outb, errb bytes.Buffer
	cmd.Stdout = &outb
	cmd.Stderr = &errb
	runErr := cmd.Run()
	code = -1
	if cmd.ProcessState != nil {
		code = cmd.ProcessState.ExitCode()
	}
	if runErr != nil {
		err = runErr
	}
	return outb.Bytes(), errb.Bytes(), code, err
}

func TestIntegration_ProjectRoleAndBulkAndOrgRole(t *testing.T) {
	sloctlBin, contextName, userProject, userOrg := getIntegrationConfig(t)

	repoRoot, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	binaryPath := filepath.Join(repoRoot, "add-user-role")
	build := exec.Command("go", "build", "-o", binaryPath, ".")
	build.Dir = repoRoot
	build.Env = os.Environ()
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build failed: %v\n%s", err, out)
	}
	defer os.Remove(binaryPath)

	projectName := projectNamePrefix + fmt.Sprintf("%d", time.Now().UnixNano()/int64(time.Millisecond))
	projectName = sanitizeName(projectName)
	if len(projectName) > 63 {
		projectName = projectName[:63]
	}

	// Load project YAML template and substitute name
	projectYAML, err := os.ReadFile(filepath.Join(repoRoot, "testdata", "project.yaml"))
	if err != nil {
		t.Fatalf("read project template: %v", err)
	}
	yamlContent := strings.ReplaceAll(string(projectYAML), placeholderProject, projectName)
	projectFile := filepath.Join(t.TempDir(), "project.yaml")
	if err := os.WriteFile(projectFile, []byte(yamlContent), 0644); err != nil {
		t.Fatalf("write project yaml: %v", err)
	}

	// Create project via sloctl; defer delete (cleanup on success or failure)
	out, err := runSloctl(sloctlBin, contextName, "apply", "-f", projectFile)
	if err != nil {
		t.Fatalf("sloctl apply project: %v\n%s", err, out)
	}
	defer func() {
		out, delErr := runSloctl(sloctlBin, contextName, "delete", "-f", projectFile)
		if delErr != nil {
			t.Logf("sloctl delete project (cleanup): %v\n%s", delErr, out)
		}
	}()

	// 1) Project-level role: add user to project
	t.Run("project_role", func(t *testing.T) {
		stdout, stderr, code, runErr := runBinary(binaryPath, "--project", projectName, "--email", userProject, "--role", "project-viewer")
		if code != 0 {
			t.Fatalf("add-user-role exit code %d: %s %s %v", code, stdout, stderr, runErr)
		}
		if !strings.Contains(string(stdout)+string(stderr), "Success") {
			t.Logf("stdout: %s\nstderr: %s", stdout, stderr)
		}
	})

	// 2) Bulk CSV: same project + user
	t.Run("bulk_csv", func(t *testing.T) {
		csvContent := fmt.Sprintf("project-name,user email\n%s,%s\n", projectName, userProject)
		csvPath := filepath.Join(t.TempDir(), "bulk.csv")
		if err := os.WriteFile(csvPath, []byte(csvContent), 0644); err != nil {
			t.Fatal(err)
		}
		stdout, stderr, code, _ := runBinary(binaryPath, "--csv", csvPath, "--role", "project-owner", "--validate-projects")
		if code != 0 {
			t.Fatalf("bulk CSV exit code %d: %s %s", code, stdout, stderr)
		}
		combined := string(stdout) + string(stderr)
		if !strings.Contains(combined, "PROCESSING SUMMARY") {
			t.Errorf("expected summary in output: %s", combined)
		}
	})

	// 3) Organization role: change org role for user (leave as set, no restore)
	t.Run("org_role", func(t *testing.T) {
		stdout, stderr, code, runErr := runBinary(binaryPath, "--email", userOrg, "--role", "organization-viewer")
		if code != 0 {
			t.Fatalf("add-user-role org exit code %d: %s %s %v", code, stdout, stderr, runErr)
		}
		if !strings.Contains(string(stdout)+string(stderr), "Success") {
			t.Logf("stdout: %s\nstderr: %s", stdout, stderr)
		}
	})
}
