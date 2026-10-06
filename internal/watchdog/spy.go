package watchdog

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"capsule-corp/internal/room"
)

type SpyReport struct {
	ActiveShiftsChecked int      `json:"active_shifts_checked"`
	Warnings            []string `json:"warnings"`
	UnclaimedFiles      []string `json:"unclaimed_files,omitempty"`
	Clean               bool     `json:"clean"`
}

// InspectWorkplace examines the check-in room and git status for rogue edits and stalled shifts.
func InspectWorkplace(targetDir string) (*SpyReport, error) {
	rd, err := room.LoadRoomData(targetDir)
	if err != nil {
		return nil, err
	}

	report := &SpyReport{
		ActiveShiftsChecked: len(rd.ActiveShifts),
		Clean:               true,
	}

	// 1. Check for stalled shifts (> 15 minutes without heartbeat)
	stalledThreshold := time.Now().UTC().Add(-15 * time.Minute)
	claimedSet := make(map[string]bool)

	for id, s := range rd.ActiveShifts {
		if s.LastSeenAt.Before(stalledThreshold) {
			report.Warnings = append(report.Warnings,
				fmt.Sprintf("Shift %s (%s) has no heartbeat for >15m (last seen: %s)",
					id, s.AgentName, s.LastSeenAt.Format(time.RFC3339)))
			report.Clean = false
		}
		for _, f := range s.Files {
			claimedSet[filepath.Clean(f)] = true
		}
	}

	// 2. Check git modified files to catch scope drift
	cmd := exec.Command("git", "status", "--porcelain")
	cmd.Dir = targetDir
	out, err := cmd.Output()
	if err == nil && len(out) > 0 {
		lines := strings.Split(string(out), "\n")
		for _, line := range lines {
			if len(line) < 4 {
				continue
			}
			filePath := filepath.Clean(strings.TrimSpace(line[3:]))
			if filePath == "" || strings.HasPrefix(filePath, ".capsule") {
				continue
			}

			// Check if file is claimed
			if len(claimedSet) > 0 && !isClaimed(filePath, claimedSet) {
				report.UnclaimedFiles = append(report.UnclaimedFiles, filePath)
				report.Warnings = append(report.Warnings,
					fmt.Sprintf("Rogue edit / Scope drift: modified file '%s' is not claimed by any active shift", filePath))
				report.Clean = false
			}
		}
	}

	return report, nil
}

func isClaimed(path string, claimed map[string]bool) bool {
	if claimed[path] {
		return true
	}
	for c := range claimed {
		if strings.HasPrefix(path, c+string(filepath.Separator)) {
			return true
		}
	}
	return false
}
