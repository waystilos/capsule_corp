package models

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"gopkg.in/yaml.v3"

	capsulecorp "capsule-corp"
)

var DefaultTiers = map[string]string{
	"flash":   "haiku",
	"pro":     "sonnet",
	"premium": "opus",
}

var ProtectedBots = map[string]bool{
	"android-17": true,
	"cell":       true,
	"beerus":     true,
}

var securityKeywordRe = regexp.MustCompile(`(?i)\b(secur|vuln|secret|leak|inject|auth|password|token|crypto|exploit|bypass|jwt|cve|pentest)\b`)

type ModelsConfig struct {
	Tiers map[string]string `yaml:"tiers" json:"tiers"`
	Bots  map[string]string `yaml:"bots" json:"bots"`
}

type Resolution struct {
	Model     string `json:"model"`
	Tier      string `json:"tier"`
	Source    string `json:"source"`
	Bot       string `json:"bot,omitempty"`
	Escalated bool   `json:"escalated,omitempty"`
}

// LoadConfig loads config/models.yaml or falls back to embedded.
func LoadConfig(resourceRoot string) (*ModelsConfig, error) {
	var data []byte
	var err error

	if resourceRoot != "" {
		cfgPath := filepath.Join(resourceRoot, "config", "models.yaml")
		data, err = os.ReadFile(cfgPath)
	}

	if data == nil || err != nil {
		f, embedErr := capsulecorp.AssetsFS.Open("config/models.yaml")
		if embedErr == nil {
			defer f.Close()
			data, _ = io.ReadAll(f)
		}
	}

	cfg := &ModelsConfig{
		Tiers: map[string]string{"flash": "haiku", "pro": "sonnet", "premium": "opus"},
		Bots:  make(map[string]string),
	}

	if len(data) > 0 {
		_ = yaml.Unmarshal(data, cfg)
	}

	return cfg, nil
}

// ResolveModel resolves the model name using the precedence hierarchy.
func ResolveModel(botName, requestedTier, explicitModel, taskPrompt, resourceRoot string) Resolution {
	botName = strings.ToLower(strings.TrimPrefix(botName, "@"))

	// 1. Explicit model flag
	if explicitModel != "" {
		return Resolution{
			Model:  explicitModel,
			Tier:   "custom",
			Source: "flag",
			Bot:    botName,
		}
	}

	// 2. Environment variable override
	if envModel := os.Getenv("CAPSULE_MODEL"); envModel != "" {
		return Resolution{
			Model:  envModel,
			Tier:   "custom",
			Source: "env:CAPSULE_MODEL",
			Bot:    botName,
		}
	}

	cfg, _ := LoadConfig(resourceRoot)

	// Determine Tier
	tier := requestedTier
	if tier == "" || tier == "inherit" {
		tier = "pro"
	}

	// Downshift / Escalation logic:
	// If task prompt contains security keywords, escalate to at least pro
	escalated := false
	if taskPrompt != "" && securityKeywordRe.MatchString(taskPrompt) {
		if tier == "flash" {
			tier = "pro"
			escalated = true
		}
	}

	// Protected bots must never run below pro
	if ProtectedBots[botName] && tier == "flash" {
		tier = "pro"
		escalated = true
	}

	// 2b. Tier env variable (e.g. CAPSULE_MODEL_FLASH, CAPSULE_MODEL_PRO)
	envTierKey := fmt.Sprintf("CAPSULE_MODEL_%s", strings.ToUpper(tier))
	if envTierModel := os.Getenv(envTierKey); envTierModel != "" {
		return Resolution{
			Model:     envTierModel,
			Tier:      tier,
			Source:    "env:" + envTierKey,
			Bot:       botName,
			Escalated: escalated,
		}
	}

	// 3. Per-bot override in config/models.yaml
	if botOverride, ok := cfg.Bots[botName]; ok && botOverride != "" {
		return Resolution{
			Model:     botOverride,
			Tier:      tier,
			Source:    "config:bot_override",
			Bot:       botName,
			Escalated: escalated,
		}
	}

	// 4. Tier default in config/models.yaml or built-in default
	modelName := cfg.Tiers[tier]
	if modelName == "" {
		modelName = DefaultTiers[tier]
	}
	if modelName == "" {
		modelName = DefaultTiers["pro"]
		tier = "pro"
	}

	return Resolution{
		Model:     modelName,
		Tier:      tier,
		Source:    "config:tier_default",
		Bot:       botName,
		Escalated: escalated,
	}
}
