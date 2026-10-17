package room

import "testing"

func TestConcurrentSessionsOfSameToolDoNotRetireEachOther(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("CLAUDECODE", "1")

	t.Setenv("CLAUDE_CODE_SESSION_ID", "session-A")
	a, _, _, err := ClockIn(tmpDir, "", "Builder", "A's task", []string{"main.go"}, false)
	if err != nil {
		t.Fatalf("session A ClockIn failed: %v", err)
	}

	// Session B is the same tool (same agent ID) in a different session.
	t.Setenv("CLAUDE_CODE_SESSION_ID", "session-B")
	_, _, conflicts, err := ClockIn(tmpDir, "", "Builder", "B's task", []string{"main.go"}, false)
	if err == nil || len(conflicts) != 1 || conflicts[0].ShiftID != a.ShiftID {
		t.Fatalf("expected B to conflict with A's claim on main.go, got err=%v conflicts=%v", err, conflicts)
	}
	b, _, _, err := ClockIn(tmpDir, "", "Builder", "B's task", []string{"lib.go"}, false)
	if err != nil {
		t.Fatalf("session B ClockIn on a free file failed: %v", err)
	}

	rd, err := LoadRoomData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := rd.ActiveShifts[a.ShiftID]; !ok {
		t.Fatal("session B retired session A's shift")
	}
	if len(rd.ActiveShifts) != 2 {
		t.Fatalf("expected 2 active shifts, got %d", len(rd.ActiveShifts))
	}

	// A bare clock-out from B closes B's shift, not A's.
	hist, err := ClockOut(tmpDir, "", "", "B done")
	if err != nil {
		t.Fatalf("ClockOut from B failed: %v", err)
	}
	if hist.ShiftID != b.ShiftID {
		t.Fatalf("B's bare clock-out closed %s, want %s", hist.ShiftID, b.ShiftID)
	}

	// Re-clock-in from A still replaces A's own shift.
	t.Setenv("CLAUDE_CODE_SESSION_ID", "session-A")
	a2, _, _, err := ClockIn(tmpDir, "", "Builder", "A expanded", []string{"main.go", "util.go"}, false)
	if err != nil {
		t.Fatalf("A re-clock-in failed: %v", err)
	}
	rd, _ = LoadRoomData(tmpDir)
	if _, ok := rd.ActiveShifts[a.ShiftID]; ok || len(rd.ActiveShifts) != 1 {
		t.Fatalf("A's re-clock-in should replace its old shift; active=%d", len(rd.ActiveShifts))
	}
	if _, ok := rd.ActiveShifts[a2.ShiftID]; !ok {
		t.Fatal("A's new shift missing")
	}
}

func TestSessionKeyIsHashed(t *testing.T) {
	t.Setenv("CAPSULE_SESSION_ID", "raw-secret-id")
	k := DetectSessionKey()
	if k == "" || k == "raw-secret-id" || len(k) != 16 {
		t.Fatalf("expected 16-hex-char hashed key, got %q", k)
	}
	t.Setenv("CAPSULE_SESSION_ID", "")
	t.Setenv("CLAUDE_CODE_SESSION_ID", "")
	t.Setenv("ANTIGRAVITY_CONVERSATION_ID", "")
	t.Setenv("CODEX_SESSION_ID", "")
	t.Setenv("CURSOR_SESSION_ID", "")
	if DetectSessionKey() != "" {
		t.Fatal("expected empty key with no session env vars")
	}
}
