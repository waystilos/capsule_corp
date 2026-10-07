package watchdog

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"capsule-corp/internal/room"
)

var SensitiveFiles = []string{
	"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
	"Cargo.toml", "Cargo.lock",
	"go.mod", "go.sum",
	"pyproject.toml", "poetry.lock", "requirements.txt", "Pipfile", "Pipfile.lock",
	"Gemfile", "Gemfile.lock",
	"pom.xml", "build.gradle",
}

type SpyIssue struct {
	Type           string   `json:"type"`                     // ROGUE_ACTIVITY, SCOPE_DRIFT, STALE_SHIFT, DEPENDENCY_TAMPERING
	Severity       string   `json:"severity"`                 // FAIL, WARN
	Message        string   `json:"message"`                  // Human-readable issue description
	Files          []string `json:"files,omitempty"`          // Offending files
	UnclaimedFiles []string `json:"unclaimed_files,omitempty"`// Unclaimed files for scope drift
	ShiftID        string   `json:"shift_id,omitempty"`       // Associated shift ID
	Fix            string   `json:"fix"`                      // Actionable remediation guidance
}

type SpyReport struct {
	Status              string     `json:"status"`                 // ALIGNED, DRIFT_WARNING, SCOPE_DRIFT, ROGUE_ACTIVITY
	Verdict             string     `json:"verdict"`                // PASS, WARN, FAIL
	TargetDir           string     `json:"target_dir"`             // Audited directory
	ActiveShiftsChecked int        `json:"active_shifts_checked"`  // Number of active shifts
	ClaimedFiles        []string   `json:"claimed_files"`          // All claimed files/directories
	DirtyFiles          []string   `json:"dirty_files"`            // All uncommitted files
	UnclaimedFiles      []string   `json:"unclaimed_files,omitempty"`// Files modified outside claimed scope
	Warnings            []string   `json:"warnings"`               // Human-readable warning messages
	Issues              []SpyIssue `json:"issues"`                 // Structured deviation issues with fixes
	Clean               bool       `json:"clean"`                  // True if verdict == PASS
}

// InspectWorkplace examines the check-in room and git status for rogue edits, scope drift, and stalled shifts.
func InspectWorkplace(targetDir string) (*SpyReport, error) {
	absDir, err := filepath.Abs(targetDir)
	if err != nil {
		absDir = targetDir
	}

	rd, err := room.LoadRoomData(absDir)
	if err != nil {
		return nil, err
	}

	report := &SpyReport{
		TargetDir:           absDir,
		ActiveShiftsChecked: len(rd.ActiveShifts),
		ClaimedFiles:        make([]string, 0),
		DirtyFiles:          make([]string, 0),
		Warnings:            make([]string, 0),
		Issues:              make([]SpyIssue, 0),
		Clean:               true,
		Verdict:             "PASS",
		Status:              "ALIGNED",
	}

	// 1. Process active shifts and claimed files
	claimedSet := make(map[string]bool)
	now := time.Now().UTC()
	stalledThreshold := now.Add(-15 * time.Minute)

	for id, s := range rd.ActiveShifts {
		// Check for stalled shifts (> 15 minutes without heartbeat)
		if s.LastSeenAt.Before(stalledThreshold) {
			inactiveMins := int(now.Sub(s.LastSeenAt).Minutes())
			warnMsg := fmt.Sprintf("Shift %s (%s) has no heartbeat for >15m (idle for %dm, last seen: %s)",
				id, s.AgentName, inactiveMins, s.LastSeenAt.Format(time.RFC3339))
			report.Warnings = append(report.Warnings, warnMsg)
			report.Issues = append(report.Issues, SpyIssue{
				Type:     "STALE_SHIFT",
				Severity: "WARN",
				Message:  warnMsg,
				ShiftID:  id,
				Fix:      "Run 'capsule heartbeat' to renew activity, or 'capsule clock-out'.",
			})
		}

		for _, f := range s.Files {
			cleanF := filepath.Clean(strings.TrimSpace(f))
			if cleanF != "" {
				if filepath.IsAbs(cleanF) {
					if rel, err := filepath.Rel(absDir, cleanF); err == nil && !strings.HasPrefix(rel, "..") {
						cleanF = rel
					}
				}
				if !claimedSet[cleanF] {
					claimedSet[cleanF] = true
					report.ClaimedFiles = append(report.ClaimedFiles, cleanF)
				}
			}
		}
	}

	// 2. Inspect git status for modified, untracked, and deleted files (expand untracked dirs with -uall)
	cmd := exec.Command("git", "status", "--porcelain", "-uall")
	cmd.Dir = absDir
	out, err := cmd.Output()
	if err == nil && len(out) > 0 {
		lines := strings.Split(string(out), "\n")
		for _, line := range lines {
			if len(line) < 4 {
				continue
			}
			rawPath := strings.TrimSpace(line[3:])
			if rawPath == "" {
				continue
			}
			// Handle renames: R  old -> new
			if strings.Contains(rawPath, " -> ") {
				parts := strings.Split(rawPath, " -> ")
				rawPath = strings.TrimSpace(parts[len(parts)-1])
			}
			rawPath = strings.Trim(rawPath, "\"")
			normPath := filepath.Clean(rawPath)

			// Ignore .capsule internal room data and .git directory
			if normPath == "." || normPath == "" ||
				normPath == ".capsule" || strings.HasPrefix(normPath, ".capsule/") || strings.HasPrefix(normPath, ".capsule"+string(filepath.Separator)) ||
				normPath == ".git" || strings.HasPrefix(normPath, ".git/") || strings.HasPrefix(normPath, ".git"+string(filepath.Separator)) {
				continue
			}

			report.DirtyFiles = append(report.DirtyFiles, normPath)
		}
	}

	// 3. Evaluate Rogue Activity (dirty tree with 0 active shifts)
	if len(report.DirtyFiles) > 0 && len(rd.ActiveShifts) == 0 {
		warnMsg := fmt.Sprintf("Rogue activity: %d uncommitted file(s) detected, but NO agent is clocked in to the Check-In Room.", len(report.DirtyFiles))
		report.Warnings = append(report.Warnings, warnMsg)
		report.UnclaimedFiles = append(report.UnclaimedFiles, report.DirtyFiles...)
		report.Issues = append(report.Issues, SpyIssue{
			Type:           "ROGUE_ACTIVITY",
			Severity:       "FAIL",
			Message:        warnMsg,
			Files:          report.DirtyFiles,
			UnclaimedFiles: report.DirtyFiles,
			Fix:            "Run 'capsule clock-in --task \"<description>\" --files \"<files>\"' before modifying code.",
		})
	} else if len(rd.ActiveShifts) > 0 {
		// 4. Evaluate Scope Drift (active agents touching unbudgeted files)
		var unclaimedDirty []string
		for _, df := range report.DirtyFiles {
			if !isClaimed(df, claimedSet) {
				unclaimedDirty = append(unclaimedDirty, df)
				report.Warnings = append(report.Warnings,
					fmt.Sprintf("Rogue edit / Scope drift: modified file '%s' is not claimed by any active shift", df))
			}
		}

		if len(unclaimedDirty) > 0 {
			report.UnclaimedFiles = unclaimedDirty
			report.Issues = append(report.Issues, SpyIssue{
				Type:           "SCOPE_DRIFT",
				Severity:       "FAIL",
				Message:        fmt.Sprintf("Active agent(s) touched %d file(s) outside their claimed shift scope.", len(unclaimedDirty)),
				Files:          unclaimedDirty,
				UnclaimedFiles: unclaimedDirty,
				Fix:            "Revert unbudgeted changes or clock in with expanded --files grant.",
			})
		}
	}

	// 5. Evaluate Sensitive Dependency Tampering
	var tamperedDeps []string
	for _, df := range report.DirtyFiles {
		base := filepath.Base(df)
		for _, sf := range SensitiveFiles {
			if base == sf || df == sf {
				if !isClaimed(df, claimedSet) {
					tamperedDeps = append(tamperedDeps, df)
				}
				break
			}
		}
	}
	if len(tamperedDeps) > 0 {
		warnMsg := fmt.Sprintf("Build/dependency manifests modified without explicit claim: %s", strings.Join(tamperedDeps, ", "))
		report.Warnings = append(report.Warnings, warnMsg)
		report.Issues = append(report.Issues, SpyIssue{
			Type:     "DEPENDENCY_TAMPERING",
			Severity: "WARN",
			Message:  warnMsg,
			Files:    tamperedDeps,
			Fix:      "Ensure package additions were explicitly requested in the Task Brief Envelope.",
		})
	}

	// 6. Compute Final Verdict & Status
	hasFail := false
	hasWarn := false
	for _, iss := range report.Issues {
		if iss.Severity == "FAIL" {
			hasFail = true
		} else if iss.Severity == "WARN" {
			hasWarn = true
		}
	}

	if hasFail {
		report.Clean = false
		report.Verdict = "FAIL"
		if len(rd.ActiveShifts) == 0 {
			report.Status = "ROGUE_ACTIVITY"
		} else {
			report.Status = "SCOPE_DRIFT"
		}
	} else if hasWarn {
		report.Clean = false
		report.Verdict = "WARN"
		report.Status = "DRIFT_WARNING"
	} else {
		report.Clean = true
		report.Verdict = "PASS"
		report.Status = "ALIGNED"
	}

	return report, nil
}

func isClaimed(path string, claimed map[string]bool) bool {
	if claimed["."] || claimed["*"] {
		return true
	}
	normPath := filepath.ToSlash(filepath.Clean(path))
	if claimed[normPath] || claimed[filepath.Clean(path)] {
		return true
	}
	for c := range claimed {
		normClaim := filepath.ToSlash(filepath.Clean(c))
		if normClaim == normPath {
			return true
		}
		if strings.HasPrefix(normPath, normClaim+"/") {
			return true
		}
	}
	return false
}
