package doctor

import (
	"fmt"
	"os/exec"
	"strings"

	"capsule-corp/internal/dx"
)

type DiagnosticItem struct {
	Name    string `json:"name"`
	Status  string `json:"status"` // "OK", "WARN", "FAIL"
	Details string `json:"details"`
}

type DoctorReport struct {
	Items   []DiagnosticItem `json:"items"`
	Healthy bool             `json:"healthy"`
}

// DiagnoseEnvironment inspects toolchain and repository health.
func DiagnoseEnvironment(targetDir string) DoctorReport {
	rep := DoctorReport{
		Healthy: true,
	}

	// 1. Check Git
	gitOut, err := exec.Command("git", "--version").Output()
	if err != nil {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Git",
			Status:  "FAIL",
			Details: "git command not found in PATH",
		})
		rep.Healthy = false
	} else {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Git",
			Status:  "OK",
			Details: strings.TrimSpace(string(gitOut)),
		})
	}

	// 2. Check Go
	goOut, err := exec.Command("go", "version").Output()
	if err == nil {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Go",
			Status:  "OK",
			Details: strings.TrimSpace(string(goOut)),
		})
	} else {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Go",
			Status:  "WARN",
			Details: "go compiler not found in PATH",
		})
	}

	// 3. Check inside git work tree
	insideCmd := exec.Command("git", "rev-parse", "--is-inside-work-tree")
	insideCmd.Dir = targetDir
	if err := insideCmd.Run(); err == nil {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Repository",
			Status:  "OK",
			Details: "Valid git repository work tree",
		})
	} else {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Repository",
			Status:  "WARN",
			Details: "Target directory is not inside a git work tree",
		})
	}

	// 4. Check if capsule is directly on PATH
	if capsulePath, err := exec.LookPath("capsule"); err == nil {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "CLI (PATH)",
			Status:  "OK",
			Details: fmt.Sprintf("capsule command is directly available in PATH (%s)", capsulePath),
		})
	} else {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "CLI (PATH)",
			Status:  "WARN",
			Details: "capsule is not in PATH (run 'capsule install' or use ./bin/capsule)",
		})
	}

	// 5. Check for legacy Python installations and broken shims
	legacyWarnings := dx.CheckLegacyPython()
	if len(legacyWarnings) > 0 {
		for _, w := range legacyWarnings {
			rep.Items = append(rep.Items, DiagnosticItem{
				Name:    "Legacy Python",
				Status:  "WARN",
				Details: w,
			})
		}
	} else {
		rep.Items = append(rep.Items, DiagnosticItem{
			Name:    "Legacy Python",
			Status:  "OK",
			Details: "No conflicting legacy Python shims or packages detected",
		})
	}

	return rep
}
