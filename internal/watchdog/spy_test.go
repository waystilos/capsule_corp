package watchdog

import (
	"os"
	"testing"
)

func TestInspectWorkplaceClean(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spy_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	rep, err := InspectWorkplace(tmpDir)
	if err != nil {
		t.Fatalf("InspectWorkplace failed: %v", err)
	}
	if !rep.Clean {
		t.Fatalf("expected clean workplace report, got warnings: %v", rep.Warnings)
	}
}
