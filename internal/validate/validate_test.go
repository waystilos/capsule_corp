package validate

import (
	"testing"
)

func TestEvaluateIdea(t *testing.T) {
	goodIdea := "An autonomous CLI tool for developers that solves merge conflict churn and verifies diff security."
	rubric := EvaluateIdea(goodIdea)
	if rubric.Verdict != "GO" {
		t.Fatalf("expected GO verdict, got %s", rubric.Verdict)
	}

	badIdea := "A blockchain app"
	badRubric := EvaluateIdea(badIdea)
	if badRubric.Verdict == "GO" {
		t.Fatalf("expected KILL or PIVOT for underspecified idea, got %s", badRubric.Verdict)
	}
}
