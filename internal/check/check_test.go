package check

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"capsule-corp/internal/room"
)

func TestAuditGitDiffClean(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}

	res := AuditGitDiff(wd)
	if !res.Passed {
		t.Fatalf("expected diff audit to pass on clean repo, got errors: %v", res.Errors)
	}
}

func TestRunCommandEcho(t *testing.T) {
	res := RunCommand(".", "Echo", "echo hello")
	if !res.Passed {
		t.Fatalf("expected echo to pass, got: %+v", res)
	}
}

func TestAgentAlignmentAutoActivation(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "check_align_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	_ = exec.Command("git", "init", tmpDir).Run()
	_ = exec.Command("git", "-C", tmpDir, "config", "user.name", "Test").Run()
	_ = exec.Command("git", "-C", tmpDir, "config", "user.email", "test@test.com").Run()

	// 1. Without active shift or checkDrift flag, Agent Alignment check does not run
	repNoShift := RunProjectChecks(tmpDir, true)
	for _, c := range repNoShift.Checks {
		if c.Name == "Agent Alignment (King Kai Watchdog)" {
			t.Fatalf("expected no Agent Alignment check when no shift active, found one")
		}
	}

	// 2. Clock in Goku claiming only allowed.go
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"allowed.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Create allowed.go (aligned)
	_ = os.WriteFile(filepath.Join(tmpDir, "allowed.go"), []byte("package allowed"), 0644)

	repAligned := RunProjectChecks(tmpDir, true)
	var alignCheck *CheckResult
	for i, c := range repAligned.Checks {
		if c.Name == "Agent Alignment (King Kai Watchdog)" {
			alignCheck = &repAligned.Checks[i]
			break
		}
	}
	if alignCheck == nil {
		t.Fatalf("expected Agent Alignment check to activate when shift is active")
	}
	if !alignCheck.Passed {
		t.Fatalf("expected Agent Alignment check to pass when aligned, got errors: %v", alignCheck.Errors)
	}

	// 3. Create rogue.go outside claimed files
	_ = os.WriteFile(filepath.Join(tmpDir, "rogue.go"), []byte("package rogue"), 0644)

	repDrift := RunProjectChecks(tmpDir, true)
	alignDrift := (*CheckResult)(nil)
	for i, c := range repDrift.Checks {
		if c.Name == "Agent Alignment (King Kai Watchdog)" {
			alignDrift = &repDrift.Checks[i]
			break
		}
	}
	if alignDrift == nil || alignDrift.Passed {
		t.Fatalf("expected Agent Alignment check to fail when rogue.go created")
	}
	if repDrift.OverallPassed {
		t.Fatalf("expected OverallPassed=false when Agent Alignment fails")
	}
}
