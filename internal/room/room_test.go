package room

import (
	"os"
	"path/filepath"
	"testing"
)

func TestClockInAndOut(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "capsule_room_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	// Clock in
	shift, token, conflicts, err := ClockIn(tmpDir, "test_agent", "Builder", "Building feature X", []string{"main.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}
	if shift == nil || token == "" {
		t.Fatalf("expected valid shift and token, got shift=%v, token=%s", shift, token)
	}
	if len(conflicts) > 0 {
		t.Fatalf("unexpected conflicts: %v", conflicts)
	}

	// Conflict detection: second agent claiming main.go
	_, _, conflicts, err = ClockIn(tmpDir, "another_agent", "Reviewer", "Reviewing", []string{"main.go"}, false)
	if err == nil {
		t.Fatal("expected conflict error, got nil")
	}
	if len(conflicts) == 0 {
		t.Fatal("expected conflict detection on main.go")
	}

	// Heartbeat
	hbShift, err := Heartbeat(tmpDir, shift.ShiftID, "")
	if err != nil {
		t.Fatalf("Heartbeat failed: %v", err)
	}
	if hbShift.ShiftID != shift.ShiftID {
		t.Fatalf("expected shift ID %s, got %s", shift.ShiftID, hbShift.ShiftID)
	}

	// Check CONFERENCE.md exists
	confBytes, err := os.ReadFile(filepath.Join(tmpDir, ".capsule", "CONFERENCE.md"))
	if err != nil {
		t.Fatalf("expected CONFERENCE.md: %v", err)
	}
	if len(confBytes) == 0 {
		t.Fatal("CONFERENCE.md was empty")
	}

	// Clock out
	hist, err := ClockOut(tmpDir, shift.ShiftID, "", "Feature X completed successfully")
	if err != nil {
		t.Fatalf("ClockOut failed: %v", err)
	}
	if hist.ShiftID != shift.ShiftID {
		t.Fatalf("expected history entry shift ID %s, got %s", shift.ShiftID, hist.ShiftID)
	}

	// Room should now have 0 active shifts
	rd, err := LoadRoomData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(rd.ActiveShifts) != 0 {
		t.Fatalf("expected 0 active shifts, got %d", len(rd.ActiveShifts))
	}
	if len(rd.History) != 1 {
		t.Fatalf("expected 1 history entry, got %d", len(rd.History))
	}
}
