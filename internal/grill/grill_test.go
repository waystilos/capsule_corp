package grill

import (
	"testing"
)

func TestGrillArchitecture(t *testing.T) {
	proposal := "We will store user sessions in memory and sync them occasionally."
	audit := GrillArchitecture(proposal)
	if len(audit.Questions) == 0 {
		t.Fatal("expected architectural grill questions")
	}
	if audit.HakaiScore >= 85 {
		t.Fatalf("expected HakaiScore to decrease for sloppy design, got %d", audit.HakaiScore)
	}
}

func TestGrillDiff(t *testing.T) {
	diff := `
+func doWork() {
+    // TODO: implement error check
+    panic("not implemented")
+}
`
	issues := GrillDiff(diff)
	if len(issues) < 2 {
		t.Fatalf("expected at least 2 issues (TODO and panic), got %d", len(issues))
	}
}
