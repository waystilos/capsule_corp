package secretpatterns

import (
	"math"
	"regexp"
	"strings"
)

type SecretMatch struct {
	Rule        string `json:"rule"`
	Description string `json:"description"`
	Line        int    `json:"line"`
	Match       string `json:"match"`
}

type PatternSpec struct {
	Regex       *regexp.Regexp
	Description string
}

var (
	MergeStartRe = regexp.MustCompile(`(?m)^\+<{7}(?:\s.*)?$`)
	MergeMidRe   = regexp.MustCompile(`(?m)^\+={7}\r?$`)
	MergeEndRe   = regexp.MustCompile(`(?m)^\+>{7}(?:\s.*)?$`)
)

var SecretSpecs = []struct {
	Pattern     string
	Description string
}{
	{`sk-ant-api\d{2}-[a-zA-Z0-9_\-]{80,}`, "Anthropic API Key"},
	{`github_pat_[a-zA-Z0-9_]{82}`, "GitHub Fine-Grained Personal Access Token"},
	{`ghp_[a-zA-Z0-9]{36}`, "GitHub Personal Access Token"},
	{`gh[ousr]_[a-zA-Z0-9]{36}`, "GitHub OAuth/App Token"},
	{`glpat-[A-Za-z0-9_-]{20,}`, "GitLab Personal Access Token"},
	{`npm_[A-Za-z0-9]{36}`, "npm Access Token"},
	{`SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}`, "SendGrid API Key"},
	{`ya29\.[A-Za-z0-9_-]{20,}`, "Google OAuth Access Token"},
	{`AIza[0-9A-Za-z_-]{35}`, "Google API Key"},
	{`(?:AKIA|ASIA)[0-9A-Z]{16}`, "AWS Access Key ID"},
	{`whsec_[0-9a-zA-Z]{24,}`, "Stripe Webhook Secret"},
	{`sk_test_[0-9a-zA-Z]{24,}`, "Stripe Secret Test Key"},
	{`rk_live_[0-9a-zA-Z]{24,}`, "Stripe Restricted Live Key"},
	{`sk_live_[0-9a-zA-Z]{24,}`, "Stripe Secret Live Key"},
	{`xox[baprs]-[0-9a-zA-Z]{10,48}`, "Slack Token"},
	{`hf_[a-zA-Z0-9]{34,}`, "HuggingFace Access Token"},
	{`sk-[A-Za-z0-9_-]{20,}`, "OpenAI / Service Secret Key"},
	{`-----BEGIN (?:(?:RSA|EC|OPENSSH|DSA|PGP|ENCRYPTED) )?PRIVATE KEY`, "Private Key Block"},
}

var compiledPatterns []PatternSpec

func init() {
	for _, spec := range SecretSpecs {
		re := regexp.MustCompile(`(?i)(?:^|[^A-Za-z0-9])(` + spec.Pattern + `)`)
		compiledPatterns = append(compiledPatterns, PatternSpec{
			Regex:       re,
			Description: spec.Description,
		})
	}
}

// ShannonEntropy calculates the Shannon entropy of a string.
func ShannonEntropy(s string) float64 {
	if len(s) == 0 {
		return 0.0
	}
	counts := make(map[rune]float64)
	for _, r := range s {
		counts[r]++
	}
	length := float64(len(s))
	entropy := 0.0
	for _, count := range counts {
		freq := count / length
		entropy -= freq * math.Log2(freq)
	}
	return entropy
}

// ScanText checks text line-by-line for known secrets.
func ScanText(text string) []SecretMatch {
	var matches []SecretMatch
	lines := strings.Split(text, "\n")
	for lineIdx, line := range lines {
		// Skip placeholder/dummy lines
		lower := strings.ToLower(line)
		if strings.Contains(lower, "example") || strings.Contains(lower, "changeme") ||
			strings.Contains(lower, "placeholder") || strings.Contains(lower, "xxx") {
			continue
		}

		for _, p := range compiledPatterns {
			if sub := p.Regex.FindStringSubmatch(line); len(sub) > 1 {
				matches = append(matches, SecretMatch{
					Rule:        p.Description,
					Description: p.Description,
					Line:        lineIdx + 1,
					Match:       sub[1],
				})
				break
			}
		}
	}
	return matches
}

// ScanDiff scans a unified diff for secrets and git merge conflict markers.
func ScanDiff(diff string) []SecretMatch {
	var matches []SecretMatch
	if MergeStartRe.MatchString(diff) {
		matches = append(matches, SecretMatch{
			Rule:        "MergeConflict",
			Description: "Git merge conflict marker (start)",
			Match:       "<<<<<<<",
		})
	}
	if MergeMidRe.MatchString(diff) {
		matches = append(matches, SecretMatch{
			Rule:        "MergeConflict",
			Description: "Git merge conflict marker (mid)",
			Match:       "=======",
		})
	}
	if MergeEndRe.MatchString(diff) {
		matches = append(matches, SecretMatch{
			Rule:        "MergeConflict",
			Description: "Git merge conflict marker (end)",
			Match:       ">>>>>>>",
		})
	}

	lines := strings.Split(diff, "\n")
	for lineIdx, line := range lines {
		if !strings.HasPrefix(line, "+") || strings.HasPrefix(line, "+++") {
			continue
		}
		cleanLine := strings.TrimPrefix(line, "+")
		lower := strings.ToLower(cleanLine)
		if strings.Contains(lower, "example") || strings.Contains(lower, "placeholder") || strings.Contains(lower, "changeme") {
			continue
		}
		for _, p := range compiledPatterns {
			if sub := p.Regex.FindStringSubmatch(cleanLine); len(sub) > 1 {
				matches = append(matches, SecretMatch{
					Rule:        p.Description,
					Description: "Exposed " + p.Description,
					Line:        lineIdx + 1,
					Match:       sub[1],
				})
			}
		}
	}
	return matches
}
