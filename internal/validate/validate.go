package validate

import (
	"strings"
)

type ValidationRubric struct {
	IdeaTitle     string   `json:"idea_title"`
	Verdict       string   `json:"verdict"` // "GO", "KILL", "PIVOT"
	Score         int      `json:"score"`   // 0-100
	KeyStrengths  []string `json:"key_strengths"`
	CriticalRisks []string `json:"critical_risks"`
	KillCriteria  []string `json:"kill_criteria"`
}

// EvaluateIdea analyzes a product idea against the Capsule Corp validation rubric.
func EvaluateIdea(ideaDescription string) ValidationRubric {
	rubric := ValidationRubric{
		IdeaTitle: ideaDescription,
		Verdict:   "GO",
		Score:     70,
	}

	lower := strings.ToLower(ideaDescription)

	if len(ideaDescription) < 30 {
		rubric.CriticalRisks = append(rubric.CriticalRisks, "Idea description is underspecified; scope is undefined.")
		rubric.Score -= 20
	}

	if !strings.Contains(lower, "user") && !strings.Contains(lower, "customer") && !strings.Contains(lower, "developer") {
		rubric.CriticalRisks = append(rubric.CriticalRisks, "Target user/audience is not clearly identified.")
		rubric.Score -= 15
	}

	if !strings.Contains(lower, "pain") && !strings.Contains(lower, "problem") && !strings.Contains(lower, "solve") {
		rubric.CriticalRisks = append(rubric.CriticalRisks, "Core user pain point is vague; risk of building a solution looking for a problem.")
		rubric.Score -= 15
	}

	if strings.Contains(lower, "ai") || strings.Contains(lower, "agent") || strings.Contains(lower, "tool") {
		rubric.KeyStrengths = append(rubric.KeyStrengths, "High developer leverage domain.")
		rubric.Score += 10
	}

	rubric.KillCriteria = []string{
		"Kill if zero target users confirm painful manual friction during problem interview.",
		"Kill if core prototype cannot demonstrate measurable time savings within 1 week of dogfooding.",
	}

	if rubric.Score < 50 {
		rubric.Verdict = "KILL"
	} else if rubric.Score < 65 {
		rubric.Verdict = "PIVOT"
	}

	return rubric
}
