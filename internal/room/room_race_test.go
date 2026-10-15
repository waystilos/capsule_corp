package room

import (
	"fmt"
	"strings"
	"sync"
	"testing"
	"unicode/utf8"
)

func TestConcurrentClockInsAllRecorded(t *testing.T) {
	tmpDir := t.TempDir()
	const n = 20
	var wg sync.WaitGroup
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			_, _, _, err := ClockIn(tmpDir, fmt.Sprintf("agent_%d", i), "Builder", "task", []string{fmt.Sprintf("file_%d.go", i)}, false)
			errs <- err
		}(i)
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatalf("concurrent ClockIn failed: %v", err)
		}
	}
	rd, err := LoadRoomData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(rd.ActiveShifts) != n {
		t.Fatalf("expected %d active shifts (no lost updates), got %d", n, len(rd.ActiveShifts))
	}
	sd, err := LoadSessionData(tmpDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(sd.Tokens) != n {
		t.Fatalf("expected %d tokens, got %d", n, len(sd.Tokens))
	}
}

func TestBareClockOutDoesNotCloseOtherAgentsShift(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("CLAUDECODE", "1")

	mine, _, _, err := ClockIn(tmpDir, "", "Builder", "mine", []string{"a.go"}, false)
	if err != nil {
		t.Fatal(err)
	}
	// A different agent clocks in afterwards, becoming session.json's last ShiftID.
	if _, _, _, err := ClockIn(tmpDir, "gemini", "Reviewer", "theirs", []string{"b.go"}, false); err != nil {
		t.Fatal(err)
	}

	hist, err := ClockOut(tmpDir, "", "", "done")
	if err != nil {
		t.Fatalf("ClockOut failed: %v", err)
	}
	if hist.ShiftID != mine.ShiftID {
		t.Fatalf("bare clock-out closed %s (%s), want own shift %s", hist.ShiftID, hist.AgentID, mine.ShiftID)
	}
}

func TestBareClockOutAmbiguousErrors(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("CLAUDECODE", "1")
	for _, a := range []string{"goku", "vegeta"} {
		if _, _, _, err := ClockIn(tmpDir, a, "", "t", []string{a + ".go"}, false); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := ClockOut(tmpDir, "", "", "done"); err == nil {
		t.Fatal("expected error when several shifts are active and none belongs to the caller")
	}
}

func TestClaimNormalizationAndLimits(t *testing.T) {
	tmpDir := t.TempDir()
	if _, _, _, err := ClockIn(tmpDir, "a1", "", "t", []string{"./src/"}, false); err != nil {
		t.Fatal(err)
	}
	_, _, conflicts, err := ClockIn(tmpDir, "a2", "", "t", []string{"src/x.go"}, false)
	if err == nil || len(conflicts) != 1 {
		t.Fatalf("expected conflict between ./src/ and src/x.go, got err=%v conflicts=%v", err, conflicts)
	}

	many := make([]string, MaxClaims+1)
	for i := range many {
		many[i] = fmt.Sprintf("f%d.go", i)
	}
	if _, _, _, err := ClockIn(tmpDir, "a3", "", "t", many, false); err == nil {
		t.Fatal("expected error for too many claims")
	}
}

func TestTruncateKeepsValidUTF8(t *testing.T) {
	tmpDir := t.TempDir()
	task := strings.Repeat("é", MaxTaskLen) // 2 bytes per rune
	shift, _, _, err := ClockIn(tmpDir, "a", "", task, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	if !utf8.ValidString(shift.Task) || len(shift.Task) > MaxTaskLen {
		t.Fatalf("task truncated badly: len=%d valid=%v", len(shift.Task), utf8.ValidString(shift.Task))
	}
}
