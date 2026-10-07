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

func TestClockOutAndHeartbeatByToken(t *testing.T) {
	tmpDir := t.TempDir()

	shift, token, _, err := ClockIn(tmpDir, "agent_t", "Builder", "Token task", []string{"lib.go"}, false)
	if err != nil {
		t.Fatalf("ClockIn failed: %v", err)
	}

	// Heartbeat with wrong token
	if _, err := HeartbeatByToken(tmpDir, "wrong-token"); err == nil {
		t.Fatal("expected error with wrong token, got nil")
	}

	// Heartbeat with correct token
	hb, err := HeartbeatByToken(tmpDir, token)
	if err != nil {
		t.Fatalf("HeartbeatByToken failed: %v", err)
	}
	if hb.ShiftID != shift.ShiftID {
		t.Fatalf("expected shift ID %s, got %s", shift.ShiftID, hb.ShiftID)
	}

	// Clock out with wrong token
	if _, err := ClockOutByToken(tmpDir, "wrong-token", "done"); err == nil {
		t.Fatal("expected error clocking out with wrong token, got nil")
	}

	// Clock out with valid token
	hist, err := ClockOutByToken(tmpDir, token, "done with token")
	if err != nil {
		t.Fatalf("ClockOutByToken failed: %v", err)
	}
	if hist.ShiftID != shift.ShiftID {
		t.Fatalf("expected hist shift ID %s, got %s", shift.ShiftID, hist.ShiftID)
	}

	// Clock out again with same token (already used/expired)
	if _, err := ClockOutByToken(tmpDir, token, "done again"); err == nil {
		t.Fatal("expected error re-using token, got nil")
	}
}

func TestReClockInExpandsFilesWithoutSelfConflict(t *testing.T) {
	tmpDir := t.TempDir()

	shift1, tok1, conflicts1, err := ClockIn(tmpDir, "agent_goku", "Builder", "Initial task", []string{"main.go"}, false)
	if err != nil {
		t.Fatalf("first ClockIn failed: %v", err)
	}
	if len(conflicts1) > 0 {
		t.Fatalf("unexpected conflicts on first clock-in: %v", conflicts1)
	}

	// Re-clock in with same agent expanding files - should NOT trigger self-conflict
	shift2, tok2, conflicts2, err := ClockIn(tmpDir, "agent_goku", "Builder", "Expanded task", []string{"main.go", "utils.go"}, false)
	if err != nil {
		t.Fatalf("re-clock-in failed: %v", err)
	}
	if len(conflicts2) > 0 {
		t.Fatalf("re-clock-in reported self-conflict: %v", conflicts2)
	}
	if shift2.ShiftID == shift1.ShiftID {
		t.Fatalf("expected new shift ID on re-clock-in, got same: %s", shift2.ShiftID)
	}

	// Verify room only has 1 active shift (old shift retired)
	rd, err := LoadRoomData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(rd.ActiveShifts) != 1 {
		t.Fatalf("expected 1 active shift, got %d", len(rd.ActiveShifts))
	}
	if _, active := rd.ActiveShifts[shift2.ShiftID]; !active {
		t.Fatalf("expected active shift %s in room", shift2.ShiftID)
	}
	if _, active := rd.ActiveShifts[shift1.ShiftID]; active {
		t.Fatalf("old shift %s was not retired", shift1.ShiftID)
	}

	// Verify session data
	sd, err := LoadSessionData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if sd.ByAgent["agent_goku"] != shift2.ShiftID {
		t.Fatalf("expected sd.ByAgent to point to %s, got %s", shift2.ShiftID, sd.ByAgent["agent_goku"])
	}
	if _, hasOld := sd.Tokens[shift1.ShiftID]; hasOld {
		t.Fatalf("sd.Tokens still contains retired shift %s", shift1.ShiftID)
	}
	if tok, hasNew := sd.Tokens[shift2.ShiftID]; !hasNew || tok != tok2 {
		t.Fatalf("sd.Tokens missing or mismatched token for %s", shift2.ShiftID)
	}
	_ = tok1

	// Clock out shift2
	_, err = ClockOut(tmpDir, shift2.ShiftID, "agent_goku", "Work finished")
	if err != nil {
		t.Fatalf("ClockOut failed: %v", err)
	}

	sdAfter, _ := LoadSessionData(tmpDir)
	if _, exists := sdAfter.ByAgent["agent_goku"]; exists {
		t.Fatalf("sd.ByAgent still has agent_goku after clock-out")
	}
}

