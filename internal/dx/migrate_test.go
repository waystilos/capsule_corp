package dx

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCheckLegacyPythonMock(t *testing.T) {
	// Simple sanity test for CheckLegacyPython
	warnings := CheckLegacyPython()
	// Should not panic, returns slice
	_ = warnings
}

func TestMigrateLegacyPythonCleansDebris(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "migrate_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	// Create fake debris
	debris1 := filepath.Join(tmpDir, ".pytest_cache")
	_ = os.MkdirAll(debris1, 0755)
	debris2 := filepath.Join(tmpDir, "fake.egg-info")
	_ = os.MkdirAll(debris2, 0755)

	rep := MigrateLegacyPython(tmpDir)
	if len(rep.Actions) == 0 {
		t.Errorf("expected migration actions for debris cleanup")
	}

	if _, err := os.Stat(debris1); !os.IsNotExist(err) {
		t.Errorf("expected debris1 to be removed")
	}
	if _, err := os.Stat(debris2); !os.IsNotExist(err) {
		t.Errorf("expected debris2 to be removed")
	}
}
