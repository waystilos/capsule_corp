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

	created, _, err := InitProject(tmpDir, "gemini", false)
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

func TestInitCopilot(t *testing.T) {
	tmpDir := t.TempDir()

	created, _, err := InitProject(tmpDir, "copilot", false)
	if err != nil {
		t.Fatalf("InitProject failed: %v", err)
	}
	if len(created) != 1 {
		t.Fatalf("expected 1 created file, got %d", len(created))
	}

	path := filepath.Join(tmpDir, ".github", "copilot-instructions.md")
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected copilot-instructions.md to exist: %v", err)
	}
}

func TestInitPreservesExistingUnlessForce(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, ".github", "copilot-instructions.md")
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("custom"), 0644); err != nil {
		t.Fatal(err)
	}

	created, skipped, err := InitProject(tmpDir, "copilot", false)
	if err != nil {
		t.Fatal(err)
	}
	if len(created) != 0 || len(skipped) != 1 {
		t.Fatalf("expected skip, got created=%v skipped=%v", created, skipped)
	}
	if b, _ := os.ReadFile(path); string(b) != "custom" {
		t.Fatalf("existing file was overwritten: %q", b)
	}

	created, _, err = InitProject(tmpDir, "copilot", true)
	if err != nil || len(created) != 1 {
		t.Fatalf("force failed: created=%v err=%v", created, err)
	}
	if b, _ := os.ReadFile(path); string(b) == "custom" {
		t.Fatal("force did not overwrite")
	}
}
