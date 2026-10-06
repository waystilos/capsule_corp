package initcmd

import (
	"os"
	"path/filepath"
	"testing"
)

func TestInitGemini(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "init_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	created, err := InitProject(tmpDir, "gemini")
	if err != nil {
		t.Fatalf("InitProject failed: %v", err)
	}
	if len(created) == 0 {
		t.Fatal("expected created files")
	}

	geminiPath := filepath.Join(tmpDir, "GEMINI.md")
	if _, err := os.Stat(geminiPath); err != nil {
		t.Fatalf("expected GEMINI.md to exist: %v", err)
	}
}
