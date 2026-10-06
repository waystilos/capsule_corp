package scaffold

import (
	"os"
	"strings"
	"testing"
)

func TestScaffoldBot(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "scaffold_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	path, err := ScaffoldBot(tmpDir, "yamcha", "@Yamcha", "Cheerleader", "flash", "Moral support and comic relief.")
	if err != nil {
		t.Fatalf("ScaffoldBot failed: %v", err)
	}

	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}

	text := string(content)
	if !strings.Contains(text, "@Yamcha") || !strings.Contains(text, "Cheerleader") {
		t.Fatalf("unexpected bot content: %s", text)
	}
}
