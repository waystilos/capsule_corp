package check

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"capsule-corp/internal/secretpatterns"
)

type CheckResult struct {
	Name     string        `json:"name"`
	Passed   bool          `json:"passed"`
	Skipped  bool          `json:"skipped"`
	Command  string        `json:"command,omitempty"`
	Output   string        `json:"output,omitempty"`
	Duration time.Duration `json:"duration"`
	Errors   []string      `json:"errors,omitempty"`
}

type CheckReport struct {
	OverallPassed bool          `json:"overall_passed"`
	Checks        []CheckResult `json:"checks"`
	DiffAudit     *CheckResult  `json:"diff_audit,omitempty"`
}

// AuditGitDiff scans unstaged and staged git changes for merge markers, secrets, and debug leftovers.
func AuditGitDiff(targetDir string) CheckResult {
	start := time.Now()
	res := CheckResult{
		Name:   "Secrets & Diff Audit",
		Passed: true,
	}

	// 1. Check if git repo
	cmd := exec.Command("git", "rev-parse", "--is-inside-work-tree")
	cmd.Dir = targetDir
	if err := cmd.Run(); err != nil {
		res.Skipped = true
		res.Duration = time.Since(start)
		return res
	}

	// 2. Fetch unstaged and staged diff
	diffCmd := exec.Command("git", "diff", "HEAD")
	diffCmd.Dir = targetDir
	out, err := diffCmd.CombinedOutput()
	if err != nil {
		// Fallback to plain git diff if HEAD has no commits yet
		diffCmd = exec.Command("git", "diff")
		diffCmd.Dir = targetDir
		out, _ = diffCmd.CombinedOutput()
	}

	diffText := string(out)
	matches := secretpatterns.ScanDiff(diffText)
	if len(matches) > 0 {
		res.Passed = false
		for _, m := range matches {
			res.Errors = append(res.Errors, fmt.Sprintf("%s: %s (line %d)", m.Rule, m.Match, m.Line))
		}
	}

	res.Duration = time.Since(start)
	return res
}

// RunCommand executes a shell command and captures output safely.
func RunCommand(targetDir, name, commandStr string) CheckResult {
	start := time.Now()
	res := CheckResult{
		Name:    name,
		Command: commandStr,
	}

	parts := strings.Fields(commandStr)
	if len(parts) == 0 {
		res.Skipped = true
		res.Duration = time.Since(start)
		return res
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = targetDir
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf

	err := cmd.Run()
	res.Duration = time.Since(start)
	res.Output = buf.String()
	if err != nil {
		res.Passed = false
		res.Errors = append(res.Errors, fmt.Sprintf("Command failed: %v", err))
	} else {
		res.Passed = true
	}

	return res
}

// RunProjectChecks detects project ecosystem and executes standard gates.
func RunProjectChecks(targetDir string, trustMode bool) CheckReport {
	report := CheckReport{
		OverallPassed: true,
	}

	// 1. Audit Diff First
	diffRes := AuditGitDiff(targetDir)
	report.DiffAudit = &diffRes
	if !diffRes.Passed {
		report.OverallPassed = false
	}

	// 2. Detect Go ecosystem
	if _, err := os.Stat(filepath.Join(targetDir, "go.mod")); err == nil {
		testRes := RunCommand(targetDir, "Go Tests", "go test ./...")
		report.Checks = append(report.Checks, testRes)
		if !testRes.Passed {
			report.OverallPassed = false
		}

		vetRes := RunCommand(targetDir, "Go Vet", "go vet ./...")
		report.Checks = append(report.Checks, vetRes)
		if !vetRes.Passed {
			report.OverallPassed = false
		}
		return report
	}

	// 3. Detect Node ecosystem
	if _, err := os.Stat(filepath.Join(targetDir, "package.json")); err == nil {
		testRes := RunCommand(targetDir, "NPM Tests", "npm test")
		report.Checks = append(report.Checks, testRes)
		if !testRes.Passed {
			report.OverallPassed = false
		}
		return report
	}

	// 4. Detect Python ecosystem
	if _, err := os.Stat(filepath.Join(targetDir, "pyproject.toml")); err == nil {
		testRes := RunCommand(targetDir, "Python Tests", "pytest")
		report.Checks = append(report.Checks, testRes)
		if !testRes.Passed {
			report.OverallPassed = false
		}
		return report
	}

	// 5. Detect Rust ecosystem
	if _, err := os.Stat(filepath.Join(targetDir, "Cargo.toml")); err == nil {
		testRes := RunCommand(targetDir, "Cargo Test", "cargo test")
		report.Checks = append(report.Checks, testRes)
		if !testRes.Passed {
			report.OverallPassed = false
		}
		return report
	}

	return report
}
