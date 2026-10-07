package watchdog

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"capsule-corp/internal/room"
)

func initGitRepo(t *testing.T, dir string) {
	t.Helper()
	cmd := exec.Command("git", "init")
	cmd.Dir = dir
	if err := cmd.Run(); err != nil {
		t.Fatalf("git init failed: %v", err)
	}
	_ = exec.Command("git", "-C", dir, "config", "user.name", "Test").Run()
	_ = exec.Command("git", "-C", dir, "config", "user.email", "test@test.com").Run()
}

func TestInspectWorkplaceClean(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if !rep.Clean {
		t.Fatalf("expected clean workplace report, got warnings: %v", rep.Warnings)
	}
	if rep.Verdict != "PASS" || rep.Status != "ALIGNED" {
		t.Fatalf("expected PASS/ALIGNED, got verdict=%s status=%s", rep.Verdict, rep.Status)
	}
}

func TestInspectWorkplaceRogueActivity(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_rogue_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Create an uncommitted file with 0 active shifts
	if err := os.WriteFile(filepath.Join(tmpDir, "rogue.go"), []byte("package rogue"), 0644); err != nil {
		t.Fatal(err)
	}

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if rep.Clean {
		t.Fatalf("expected rogue activity to mark report not clean")
	}
	if rep.Verdict != "FAIL" || rep.Status != "ROGUE_ACTIVITY" {
		t.Fatalf("expected FAIL/ROGUE_ACTIVITY, got verdict=%s status=%s", rep.Verdict, rep.Status)
	}
	if len(rep.Issues) == 0 || rep.Issues[0].Type != "ROGUE_ACTIVITY" {
		t.Fatalf("expected ROGUE_ACTIVITY issue, got: %+v", rep.Issues)
	}
	if rep.Issues[0].Fix == "" {
		t.Fatalf("expected actionable fix on issue")
	}
}

func TestInspectWorkplaceScopeDrift(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_drift_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Clock in Goku claiming only allowed.go
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"allowed.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Create allowed.go and rogue.go
	if err := os.WriteFile(filepath.Join(tmpDir, "allowed.go"), []byte("package allowed"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tmpDir, "rogue.go"), []byte("package rogue"), 0644); err != nil {
		t.Fatal(err)
	}

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if rep.Clean {
		t.Fatalf("expected scope drift to mark report not clean")
	}
	if rep.Verdict != "FAIL" || rep.Status != "SCOPE_DRIFT" {
		t.Fatalf("expected FAIL/SCOPE_DRIFT, got verdict=%s status=%s", rep.Verdict, rep.Status)
	}
	if len(rep.UnclaimedFiles) != 1 || rep.UnclaimedFiles[0] != "rogue.go" {
		t.Fatalf("expected unclaimed files to contain rogue.go, got: %v", rep.UnclaimedFiles)
	}
}

func TestInspectWorkplaceAligned(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_aligned_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Clock in Goku claiming allowed.go
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"allowed.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Create only allowed.go
	if err := os.WriteFile(filepath.Join(tmpDir, "allowed.go"), []byte("package allowed"), 0644); err != nil {
		t.Fatal(err)
	}

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if !rep.Clean {
		t.Fatalf("expected aligned workplace report, got warnings: %v", rep.Warnings)
	}
	if rep.Verdict != "PASS" || rep.Status != "ALIGNED" {
		t.Fatalf("expected PASS/ALIGNED, got verdict=%s status=%s", rep.Verdict, rep.Status)
	}
}

func TestInspectWorkplaceStaleShift(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_stale_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Clock in Goku claiming allowed.go
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"allowed.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Mutate shift last seen to 30 minutes ago
	rd, err := room.LoadRoomData(tmpDir)
	if err != nil {
		t.Fatalf("LoadRoomData failed: %v", err)
	}
	for id, s := range rd.ActiveShifts {
		s.LastSeenAt = time.Now().UTC().Add(-30 * time.Minute)
		rd.ActiveShifts[id] = s
	}
	if err := room.SaveRoomData(tmpDir, rd); err != nil {
		t.Fatalf("SaveRoomData failed: %v", err)
	}

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if rep.Clean {
		t.Fatalf("expected stale shift to mark report not clean")
	}
	if rep.Verdict != "WARN" || rep.Status != "DRIFT_WARNING" {
		t.Fatalf("expected WARN/DRIFT_WARNING, got verdict=%s status=%s", rep.Verdict, rep.Status)
	}
	if len(rep.Issues) == 0 || rep.Issues[0].Type != "STALE_SHIFT" {
		t.Fatalf("expected STALE_SHIFT issue, got: %+v", rep.Issues)
	}
}

func TestInspectWorkplaceDependencyTampering(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_deps_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Clock in Goku claiming only src/app.go
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"src/app.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Create src/app.go and also package.json
	_ = os.MkdirAll(filepath.Join(tmpDir, "src"), 0755)
	_ = os.WriteFile(filepath.Join(tmpDir, "src", "app.go"), []byte("package main"), 0644)
	_ = os.WriteFile(filepath.Join(tmpDir, "package.json"), []byte("{}"), 0644)

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	foundDepIssue := false
	for _, iss := range rep.Issues {
		if iss.Type == "DEPENDENCY_TAMPERING" {
			foundDepIssue = true
		}
	}
	if !foundDepIssue {
		t.Fatalf("expected DEPENDENCY_TAMPERING issue, got: %+v", rep.Issues)
	}
}

func TestInspectWorkplaceDirectoryPrefixClaim(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_dir_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	// Clock in Goku claiming internal/
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{"internal"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	_ = os.MkdirAll(filepath.Join(tmpDir, "internal", "sub"), 0755)
	_ = os.WriteFile(filepath.Join(tmpDir, "internal", "sub", "file.go"), []byte("package sub"), 0644)

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if !rep.Clean {
		t.Fatalf("expected clean report for directory prefix claim, got: %v", rep.Warnings)
	}
	if rep.Verdict != "PASS" {
		t.Fatalf("expected PASS, got %s", rep.Verdict)
	}
}

func TestInspectWorkplaceAbsolutePathClaim(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_abs_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	initGitRepo(t, tmpDir)

	absFile := filepath.Join(tmpDir, "allowed.go")
	// Clock in Goku claiming the file using an ABSOLUTE path
	_, _, _, err = room.ClockIn(tmpDir, "goku", "Builder", "Implement feature", []string{absFile}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	if err := os.WriteFile(absFile, []byte("package allowed"), 0644); err != nil {
		t.Fatal(err)
	}

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if !rep.Clean {
		t.Fatalf("expected clean report when claiming absolute path, got warnings: %v", rep.Warnings)
	}
	if rep.Verdict != "PASS" {
		t.Fatalf("expected PASS, got %s", rep.Verdict)
	}
}
