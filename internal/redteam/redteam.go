package redteam

import (
	"regexp"
	"strings"
	"time"
)

type AttackFinding struct {
	Category    string `json:"category"`
	Severity    string `json:"severity"`
	Description string `json:"description"`
	Payload     string `json:"payload"`
}

var promptInjectionPatterns = []struct {
	Pattern     *regexp.Regexp
	Description string
}{
	{regexp.MustCompile(`(?i)ignore\s+all\s+(prior|previous)\s+instructions`), "Direct instruction override"},
	{regexp.MustCompile(`(?i)disregard\s+the\s+above`), "Direct context disregard"},
	{regexp.MustCompile(`(?i)system\s*prompt\s*leak`), "System prompt exfiltration probe"},
	{regexp.MustCompile(`(?i)you\s+are\s+now\s+in\s+developer\s+mode`), "Jailbreak mode switch"},
	{regexp.MustCompile(`(?i)you\s+are\s+DAN\b`), "Do-Anything-Now persona hijack"},
}

// CheckPromptInjection checks if input text contains adversarial prompt injection attacks.
func CheckPromptInjection(input string) []AttackFinding {
	var findings []AttackFinding
	for _, p := range promptInjectionPatterns {
		if p.Pattern.MatchString(input) {
			findings = append(findings, AttackFinding{
				Category:    "Prompt Injection",
				Severity:    "HIGH",
				Description: p.Description,
				Payload:     p.Pattern.FindString(input),
			})
		}
	}
	return findings
}

// CheckPathTraversal tests if a file path attempts directory traversal attacks.
func CheckPathTraversal(path string) []AttackFinding {
	var findings []AttackFinding
	clean := strings.ReplaceAll(path, "\\", "/")
	if strings.Contains(clean, "../") || strings.Contains(clean, "..\\") || strings.HasPrefix(clean, "/") {
		findings = append(findings, AttackFinding{
			Category:    "Path Traversal",
			Severity:    "CRITICAL",
			Description: "Path attempts to escape workspace boundaries or access absolute root",
			Payload:     path,
		})
	}
	return findings
}

// BenchmarkRegexSafe verifies that a regex pattern executes within safe latency limits (no catastrophic ReDoS).
func BenchmarkRegexSafe(re *regexp.Regexp, evilInput string, timeout time.Duration) bool {
	done := make(chan bool, 1)
	go func() {
		re.MatchString(evilInput)
		done <- true
	}()

	select {
	case <-done:
		return true
	case <-time.After(timeout):
		return false
	}
}
