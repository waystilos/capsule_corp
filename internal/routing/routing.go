package routing

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"

	capsulecorp "capsule-corp"
	"capsule-corp/internal/models"
	"capsule-corp/internal/registry"
)

type RouteRule struct {
	Intent         string   `yaml:"intent" json:"intent"`
	Owner          string   `yaml:"owner" json:"owner"`
	StrongKeywords []string `yaml:"strong_keywords" json:"strong_keywords,omitempty"`
	Keywords       []string `yaml:"keywords" json:"keywords"`
	Handoff        []string `yaml:"handoff" json:"handoff"`
	Avoid          []string `yaml:"avoid" json:"avoid,omitempty"`
	Entry          []string `yaml:"entry" json:"entry,omitempty"`
}

type RoutingConfig struct {
	Version  string      `yaml:"version" json:"version"`
	Fallback string      `yaml:"fallback" json:"fallback"`
	Routes   []RouteRule `yaml:"routes" json:"routes"`
}

type RouteDecision struct {
	Intent      string            `json:"intent"`
	Bot         string            `json:"bot"`
	Alias       string            `json:"alias"`
	ModelRes    models.Resolution `json:"model"`
	Handoff     []string          `json:"handoff"`
	MatchedWord string            `json:"matched_keyword,omitempty"`
}

type TaskEnvelope struct {
	RootRequest        string   `json:"root_request"`
	Goal               string   `json:"goal"`
	Scope              []string `json:"scope,omitempty"`
	Constraints        []string `json:"constraints,omitempty"`
	AcceptanceCriteria []string `json:"acceptance_criteria"`
	Verification       []string `json:"verification"`
	Ledger             []string `json:"ledger"`
	ModelTier          string   `json:"model_tier,omitempty"`
	Model              string   `json:"model,omitempty"`
}

// LoadRoutingConfig loads config/routing.yaml or falls back to embedded.
func LoadRoutingConfig(resourceRoot string) (*RoutingConfig, error) {
	var data []byte
	var err error

	if resourceRoot != "" {
		p := filepath.Join(resourceRoot, "config", "routing.yaml")
		data, err = os.ReadFile(p)
	}

	if data == nil || err != nil {
		f, embedErr := capsulecorp.AssetsFS.Open("config/routing.yaml")
		if embedErr == nil {
			defer f.Close()
			data, _ = io.ReadAll(f)
		}
	}

	cfg := &RoutingConfig{
		Fallback: "whis",
	}
	if len(data) > 0 {
		_ = yaml.Unmarshal(data, cfg)
	}
	return cfg, nil
}

// RouteTask determines the best bot and model tier for a given task prompt.
func RouteTask(taskPrompt, resourceRoot string, reg *registry.Registry) RouteDecision {
	cfg, _ := LoadRoutingConfig(resourceRoot)
	lowerPrompt := strings.ToLower(taskPrompt)

	// 1. Check strong keywords first
	for _, rule := range cfg.Routes {
		for _, sk := range rule.StrongKeywords {
			if strings.Contains(lowerPrompt, strings.ToLower(sk)) {
				return makeDecision(rule, rule.Owner, sk, taskPrompt, resourceRoot, reg)
			}
		}
	}

	// 2. Check regular keywords, respecting avoid keywords
	type scoredRoute struct {
		rule  RouteRule
		match string
		score int
	}
	var matches []scoredRoute

	for _, rule := range cfg.Routes {
		avoided := false
		for _, avoid := range rule.Avoid {
			if strings.Contains(lowerPrompt, strings.ToLower(avoid)) {
				avoided = true
				break
			}
		}
		if avoided {
			continue
		}

		for _, kw := range rule.Keywords {
			if strings.Contains(lowerPrompt, strings.ToLower(kw)) {
				matches = append(matches, scoredRoute{
					rule:  rule,
					match: kw,
					score: len(kw),
				})
			}
		}
	}

	if len(matches) > 0 {
		best := matches[0]
		for _, m := range matches[1:] {
			if m.score > best.score {
				best = m
			}
		}
		return makeDecision(best.rule, best.rule.Owner, best.match, taskPrompt, resourceRoot, reg)
	}

	// Fallback bot
	fallbackOwner := cfg.Fallback
	if fallbackOwner == "" {
		fallbackOwner = "whis"
	}
	defaultRule := RouteRule{
		Intent:  "general_coordination",
		Owner:   fallbackOwner,
		Handoff: []string{fallbackOwner, "goku", "trunks"},
	}
	return makeDecision(defaultRule, fallbackOwner, "fallback", taskPrompt, resourceRoot, reg)
}

func makeDecision(rule RouteRule, botID, matchedKeyword, prompt, root string, reg *registry.Registry) RouteDecision {
	alias := "@" + strings.Title(botID)
	tier := "pro"
	if reg != nil {
		if bot, ok := reg.FindBot(botID); ok {
			alias = bot.Alias
			tier = bot.ModelTier
		}
	}

	modelRes := models.ResolveModel(botID, tier, "", prompt, root)

	return RouteDecision{
		Intent:      rule.Intent,
		Bot:         botID,
		Alias:       alias,
		ModelRes:    modelRes,
		Handoff:     rule.Handoff,
		MatchedWord: matchedKeyword,
	}
}

// HashEnvelope computes SHA-256 hex string of the canonical JSON envelope.
func HashEnvelope(env *TaskEnvelope) (string, error) {
	data, err := json.Marshal(env)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:]), nil
}

// RenderMarkdown renders the task envelope in Capsule Corp markdown format.
func RenderMarkdown(env *TaskEnvelope) string {
	var sb strings.Builder
	sb.WriteString("### Task Brief Envelope\n")
	sb.WriteString(fmt.Sprintf("- **Root Request:** %s\n", env.RootRequest))
	sb.WriteString(fmt.Sprintf("- **Goal:** %s\n", env.Goal))
	if len(env.Scope) > 0 {
		sb.WriteString(fmt.Sprintf("- **Scope:** %s\n", strings.Join(env.Scope, ", ")))
	}
	if len(env.Constraints) > 0 {
		sb.WriteString(fmt.Sprintf("- **Constraints:** %s\n", strings.Join(env.Constraints, "; ")))
	}
	sb.WriteString("- **Acceptance Criteria:**\n")
	for _, ac := range env.AcceptanceCriteria {
		sb.WriteString(fmt.Sprintf("  - %s\n", ac))
	}
	sb.WriteString("- **Verification:**\n")
	for _, v := range env.Verification {
		sb.WriteString(fmt.Sprintf("  - `%s`\n", v))
	}
	if len(env.Ledger) > 0 {
		sb.WriteString("- **Ledger:**\n")
		for _, l := range env.Ledger {
			sb.WriteString(fmt.Sprintf("  - %s\n", l))
		}
	}
	return sb.String()
}
