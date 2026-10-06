package dx

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCompletionsNonEmpty(t *testing.T) {
	bash := BashCompletion()
	if !strings.Contains(bash, "complete -F _capsule_completions capsule") {
		t.Errorf("expected bash completion footer, got: %s", bash)
	}

	zsh := ZshCompletion()
	if !strings.Contains(zsh, "#compdef capsule") {
		t.Errorf("expected zsh compdef header, got: %s", zsh)
	}

	fish := FishCompletion()
	if !strings.Contains(fish, "complete -c capsule") {
		t.Errorf("expected fish completion command, got: %s", fish)
	}
}

func TestGitHookInstallAndUninstall(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "dx_hook_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	hookPath, err := InstallGitHook(tmpDir)
	if err != nil {
		t.Fatalf("InstallGitHook failed: %v", err)
	}

	content, err := os.ReadFile(hookPath)
	if err != nil {
		t.Fatalf("failed to read hook: %v", err)
	}
	if !strings.Contains(string(content), "capsule check . --trust") {
		t.Errorf("unexpected hook content: %s", string(content))
	}

	err = UninstallGitHook(tmpDir)
	if err != nil {
		t.Fatalf("UninstallGitHook failed: %v", err)
	}

	if _, err := os.Stat(hookPath); !os.IsNotExist(err) {
		t.Errorf("hook file still exists after uninstall")
	}
}

func TestInstallBinary(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "dx_install_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	srcBinary := filepath.Join(tmpDir, "fake-capsule")
	err = os.WriteFile(srcBinary, []byte("#!/bin/sh\necho ok\n"), 0755)
	if err != nil {
		t.Fatal(err)
	}

	t.Setenv("GOPATH", tmpDir)

	installed, _, err := InstallBinary(srcBinary)
	if err != nil {
		t.Fatalf("InstallBinary failed: %v", err)
	}

	if _, err := os.Stat(installed); err != nil {
		t.Fatalf("installed binary not found at %s", installed)
	}
}
