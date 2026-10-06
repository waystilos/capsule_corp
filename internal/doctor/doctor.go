package doctor

import (
	"os/exec"
	"strings"
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

	return rep
}
