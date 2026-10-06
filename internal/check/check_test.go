package check

import (
	"os"
	"testing"
)

func TestAuditGitDiffClean(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}

	res := AuditGitDiff(wd)
	if !res.Passed {
		t.Fatalf("expected diff audit to pass on clean repo, got errors: %v", res.Errors)
	}
}

func TestRunCommandEcho(t *testing.T) {
	res := RunCommand(".", "Echo", "echo hello")
	if !res.Passed {
		t.Fatalf("expected echo to pass, got: %+v", res)
	}
}
