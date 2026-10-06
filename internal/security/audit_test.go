package security

import (
	"os"
	"path/filepath"
	"testing"
)

func TestScanRepositoryDetectsSecrets(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "sec_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	badFile := filepath.Join(tmpDir, "config.py")
	err = os.WriteFile(badFile, []byte("API_KEY = \""+"AKIA"+"IOSFODNN7TEST123\"\n"), 0644)
	if err != nil {
		t.Fatal(err)
	}

	findings, err := ScanRepository(tmpDir)
	if err != nil {
		t.Fatalf("ScanRepository failed: %v", err)
	}
	if len(findings) == 0 {
		t.Fatal("expected finding for AWS key")
	}
}
