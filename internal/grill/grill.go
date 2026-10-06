package grill

import (
	"fmt"
	"strings"
)

type GrillQuestion struct {
	Category string `json:"category"`
	Question string `json:"question"`
	Severity string `json:"severity"`
}

type GrillAudit struct {
	Questions  []GrillQuestion `json:"questions"`
	DiffIssues []string        `json:"diff_issues"`
	HakaiScore int             `json:"hakai_score"` // 0 to 100 (100 = flawless)
}

// GrillArchitecture generates ruthless architectural questions for a given proposal or design.
func GrillArchitecture(systemDescription string) GrillAudit {
	audit := GrillAudit{
		HakaiScore: 85,
	}

	lower := strings.ToLower(systemDescription)

	if !strings.Contains(lower, "timeout") && !strings.Contains(lower, "deadline") {
		audit.Questions = append(audit.Questions, GrillQuestion{
			Category: "Resilience",
			Severity: "HIGH",
			Question: "How do you guarantee upstream hangs or slow dependencies will not exhaust your thread/goroutine pools without explicit deadlines?",
		})
		audit.HakaiScore -= 10
	}

	if !strings.Contains(lower, "idempotent") && !strings.Contains(lower, "dedup") {
		audit.Questions = append(audit.Questions, GrillQuestion{
			Category: "Data Integrity",
			Severity: "HIGH",
			Question: "If a network glitch causes duplicate request delivery, does your state machine corrupt data or safely deduplicate?",
		})
		audit.HakaiScore -= 10
	}

	if !strings.Contains(lower, "concurrency") && !strings.Contains(lower, "lock") && !strings.Contains(lower, "mutex") {
		audit.Questions = append(audit.Questions, GrillQuestion{
			Category: "Concurrency",
			Severity: "MEDIUM",
			Question: "What is the race condition defense when multiple workers update the same entity simultaneously?",
		})
		audit.HakaiScore -= 5
	}

	return audit
}

// GrillDiff inspects a diff for missing error handling, unhandled edge cases, or debug statements.
func GrillDiff(diff string) []string {
	var issues []string
	lines := strings.Split(diff, "\n")
	for idx, line := range lines {
		if !strings.HasPrefix(line, "+") || strings.HasPrefix(line, "+++") {
			continue
		}
		if strings.Contains(line, "TODO") || strings.Contains(line, "FIXME") {
			issues = append(issues, fmt.Sprintf("Line %d: Unresolved TODO/FIXME in diff: %s", idx+1, strings.TrimSpace(line)))
		}
		if strings.Contains(line, "panic(") {
			issues = append(issues, fmt.Sprintf("Line %d: Bare panic() call introduced in diff: %s", idx+1, strings.TrimSpace(line)))
		}
		if strings.Contains(line, "fmt.Println") || strings.Contains(line, "console.log") {
			issues = append(issues, fmt.Sprintf("Line %d: Temporary debug print in diff: %s", idx+1, strings.TrimSpace(line)))
		}
	}
	return issues
}
