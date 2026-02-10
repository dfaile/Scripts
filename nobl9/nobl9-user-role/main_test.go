package main

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSanitizeName(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{"normal", "my-project", "my-project"},
		{"lowercase", "MyProject", "myproject"},
		{"spaces to hyphens", "my project name", "my-project-name"},
		{"special chars", "my_project!@#name", "my-project-name"},
		{"leading trailing hyphens", "-foo-bar-", "foo-bar"},
		{"empty", "", ""},
		{"already valid", "abc123", "abc123"},
		{"mixed", "  Foo Bar_ Baz  ", "foo-bar-baz"},
		{"long truncation not applied", strings.Repeat("a", 70), strings.Repeat("a", 70)},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := sanitizeName(tt.in)
			if got != tt.want {
				t.Errorf("sanitizeName(%q) = %q, want %q", tt.in, got, tt.want)
			}
		})
	}
}

func TestValidateEmail(t *testing.T) {
	valid := []string{"user@domain.com", "a+b@x.co", "a@b.co", "user.name@example.org"}
	for _, e := range valid {
		if !validateEmail(e) {
			t.Errorf("validateEmail(%q) = false, want true", e)
		}
	}
	invalid := []string{"", "no-at", "@nodomain", "nodomain@", "a b@x.com", "a@.com", "a@b"}
	for _, e := range invalid {
		if validateEmail(e) {
			t.Errorf("validateEmail(%q) = true, want false", e)
		}
	}
}

func TestParseCSVFile(t *testing.T) {
	dir := t.TempDir()

	t.Run("valid file with project-name and user email", func(t *testing.T) {
		f := filepath.Join(dir, "valid.csv")
		if err := os.WriteFile(f, []byte("project-name,user email\np1,u1@x.com\np2,u2@x.com"), 0644); err != nil {
			t.Fatal(err)
		}
		rows, err := parseCSVFile(f)
		if err != nil {
			t.Fatal(err)
		}
		if len(rows) != 2 {
			t.Fatalf("len(rows) = %d, want 2", len(rows))
		}
		if rows[0].ProjectName != "p1" || rows[0].UserEmail != "u1@x.com" {
			t.Errorf("row0 = %+v", rows[0])
		}
		if rows[1].ProjectName != "p2" || rows[1].UserEmail != "u2@x.com" {
			t.Errorf("row1 = %+v", rows[1])
		}
	})

	t.Run("header variant project name", func(t *testing.T) {
		f := filepath.Join(dir, "alt.csv")
		if err := os.WriteFile(f, []byte("project name,user email\np1,u@x.com"), 0644); err != nil {
			t.Fatal(err)
		}
		rows, err := parseCSVFile(f)
		if err != nil {
			t.Fatal(err)
		}
		if len(rows) != 1 || rows[0].ProjectName != "p1" || rows[0].UserEmail != "u@x.com" {
			t.Errorf("rows = %+v", rows)
		}
	})

	t.Run("empty rows skipped", func(t *testing.T) {
		f := filepath.Join(dir, "empty.csv")
		if err := os.WriteFile(f, []byte("project-name,user email\np1,u@x.com\n,\n"), 0644); err != nil {
			t.Fatal(err)
		}
		rows, err := parseCSVFile(f)
		if err != nil {
			t.Fatal(err)
		}
		if len(rows) != 1 {
			t.Errorf("len(rows) = %d, want 1 (empty row skipped)", len(rows))
		}
	})

	t.Run("file not found", func(t *testing.T) {
		_, err := parseCSVFile(filepath.Join(dir, "nonexistent.csv"))
		if err == nil {
			t.Fatal("expected error for missing file")
		}
		if !strings.Contains(err.Error(), "cannot open") {
			t.Errorf("err = %v", err)
		}
	})

	t.Run("header only", func(t *testing.T) {
		f := filepath.Join(dir, "headeronly.csv")
		if err := os.WriteFile(f, []byte("project-name,user email"), 0644); err != nil {
			t.Fatal(err)
		}
		_, err := parseCSVFile(f)
		if err == nil {
			t.Fatal("expected error for header-only file")
		}
		if !strings.Contains(err.Error(), "at least a header row and one data row") {
			t.Errorf("err = %v", err)
		}
	})

	t.Run("missing required columns", func(t *testing.T) {
		f := filepath.Join(dir, "badheader.csv")
		if err := os.WriteFile(f, []byte("col1,col2\na,b"), 0644); err != nil {
			t.Fatal(err)
		}
		_, err := parseCSVFile(f)
		if err == nil {
			t.Fatal("expected error for missing columns")
		}
		if !strings.Contains(err.Error(), "project-name") || !strings.Contains(err.Error(), "user email") {
			t.Errorf("err = %v", err)
		}
	})
}

func TestValidateCSVFile(t *testing.T) {
	dir := t.TempDir()
	valid := filepath.Join(dir, "v.csv")
	if err := os.WriteFile(valid, []byte("project-name,user email\np,u@x.com"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := validateCSVFile(valid); err != nil {
		t.Errorf("validateCSVFile(valid) = %v", err)
	}
	if err := validateCSVFile(filepath.Join(dir, "nonexistent")); err == nil || !strings.Contains(err.Error(), "does not exist") {
		t.Errorf("validateCSVFile(nonexistent) = %v", err)
	}
	if err := validateCSVFile(dir); err == nil || !strings.Contains(err.Error(), "directory") {
		t.Errorf("validateCSVFile(dir) = %v", err)
	}
	empty := filepath.Join(dir, "empty.csv")
	if err := os.WriteFile(empty, nil, 0644); err != nil {
		t.Fatal(err)
	}
	if err := validateCSVFile(empty); err == nil || !strings.Contains(err.Error(), "empty") {
		t.Errorf("validateCSVFile(empty) = %v", err)
	}
}

func TestValidateCSVRows(t *testing.T) {
	t.Run("project-level role requires project", func(t *testing.T) {
		rows := []CSVRow{{ProjectName: "", UserEmail: "u@x.com"}}
		invalid, ok := validateCSVRows(rows, false)
		if ok {
			t.Fatal("expected invalid")
		}
		if len(invalid) == 0 || !strings.Contains(invalid[0], "empty project name") {
			t.Errorf("invalid = %v", invalid)
		}
	})
	t.Run("empty email", func(t *testing.T) {
		rows := []CSVRow{{ProjectName: "p", UserEmail: ""}}
		invalid, ok := validateCSVRows(rows, false)
		if ok {
			t.Fatal("expected invalid")
		}
		if len(invalid) == 0 || !strings.Contains(invalid[0], "empty user email") {
			t.Errorf("invalid = %v", invalid)
		}
	})
	t.Run("invalid email", func(t *testing.T) {
		rows := []CSVRow{{ProjectName: "p", UserEmail: "not-an-email"}}
		invalid, ok := validateCSVRows(rows, false)
		if ok {
			t.Fatal("expected invalid")
		}
		if len(invalid) == 0 || !strings.Contains(invalid[0], "invalid email") {
			t.Errorf("invalid = %v", invalid)
		}
	})
	t.Run("org role allows empty project", func(t *testing.T) {
		rows := []CSVRow{{ProjectName: "", UserEmail: "u@x.com"}}
		invalid, ok := validateCSVRows(rows, true)
		if !ok || len(invalid) != 0 {
			t.Errorf("valid expected for org role; invalid = %v", invalid)
		}
	})
	t.Run("all valid", func(t *testing.T) {
		rows := []CSVRow{{ProjectName: "p", UserEmail: "u@x.com"}}
		invalid, ok := validateCSVRows(rows, false)
		if !ok || len(invalid) != 0 {
			t.Errorf("invalid = %v, ok = %v", invalid, ok)
		}
	})
}

func TestIsOrganizationRole(t *testing.T) {
	orgRoles := []string{"organization-admin", "organization-viewer", "viewer-status-page-manager"}
	for _, r := range orgRoles {
		if !isOrganizationRole(r) {
			t.Errorf("isOrganizationRole(%q) = false, want true", r)
		}
	}
	projRoles := []string{"project-owner", "project-viewer", "project-editor", "project-admin"}
	for _, r := range projRoles {
		if isOrganizationRole(r) {
			t.Errorf("isOrganizationRole(%q) = true, want false", r)
		}
	}
}

func TestGetValidRoles(t *testing.T) {
	s := getValidRoles()
	for _, r := range []string{"project-owner", "organization-admin"} {
		if !strings.Contains(s, r) {
			t.Errorf("getValidRoles() does not contain %q: %s", r, s)
		}
	}
}

func TestValidRoles(t *testing.T) {
	for r := range validRoles {
		if r != "project-viewer" && r != "project-editor" && r != "project-admin" && r != "project-owner" &&
			r != "organization-admin" && r != "organization-user" && r != "organization-integrations-user" &&
			r != "organization-responder" && r != "organization-viewer" && r != "viewer-status-page-manager" {
			continue
		}
		if !validRoles[r] {
			t.Errorf("validRoles[%q] = false", r)
		}
	}
	if validRoles["invalid-role"] {
		t.Error("validRoles[invalid-role] should be false")
	}
}

func TestIsRetryable(t *testing.T) {
	nonRetryable := []error{ErrUserNotFound, ErrAlreadyAssigned, ErrProjectNotFound, ErrRoleBindingExists, ErrValidation, ErrProjectRequired, context.Canceled, context.DeadlineExceeded}
	for _, err := range nonRetryable {
		if isRetryable(err) {
			t.Errorf("isRetryable(%v) = true, want false", err)
		}
	}
	if !isRetryable(errors.New("transient")) {
		t.Error("isRetryable(transient) = false, want true")
	}
	if isRetryable(nil) {
		t.Error("isRetryable(nil) = true, want false")
	}
}

func TestPrintStats(t *testing.T) {
	stats := &ProcessingStats{
		TotalRows:           10,
		Processed:           10,
		Assigned:            6,
		SkippedAlreadyOwner: 2,
		SkippedUserNotExists: 1,
		SkippedInvalidData:  1,
		Failed:              0,
		Errors:              []string{"Row 2: something"},
		MissingUsers:        []string{"a@x.com"},
		MissingProjects:     []string{"proj-x"},
		AlreadyAssigned:     []string{"b@x.com -> p1"},
	}
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	old := os.Stdout
	os.Stdout = w
	defer func() { os.Stdout = old; w.Close() }()
	printStats(stats)
	w.Close()
	out, _ := io.ReadAll(r)
	outStr := string(out)
	if !strings.Contains(outStr, "PROCESSING SUMMARY") {
		t.Errorf("output missing SUMMARY: %s", outStr)
	}
	if !strings.Contains(outStr, "Total rows processed: 10") {
		t.Errorf("output missing total: %s", outStr)
	}
	if !strings.Contains(outStr, "Successfully assigned: 6") {
		t.Errorf("output missing assigned: %s", outStr)
	}
	if !strings.Contains(outStr, "a@x.com") {
		t.Errorf("output missing missing user: %s", outStr)
	}
	if !strings.Contains(outStr, "proj-x") {
		t.Errorf("output missing missing project: %s", outStr)
	}
	if !strings.Contains(outStr, "b@x.com -> p1") {
		t.Errorf("output missing already assigned: %s", outStr)
	}
}

func TestPrintStatsErrorTruncation(t *testing.T) {
	var errs []string
	for i := 0; i < 15; i++ {
		errs = append(errs, "error number")
	}
	stats := &ProcessingStats{TotalRows: 15, Processed: 15, Errors: errs}
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	old := os.Stdout
	os.Stdout = w
	defer func() { os.Stdout = old; w.Close() }()
	printStats(stats)
	w.Close()
	out, _ := io.ReadAll(r)
	outStr := string(out)
	if !strings.Contains(outStr, "... and 5 more errors") {
		t.Errorf("expected truncation message: %s", outStr)
	}
}
