package registry

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	capsulecorp "capsule-corp"
)

type Bot struct {
	Name        string   `yaml:"name" json:"name"`
	Alias       string   `yaml:"alias" json:"alias"`
	ModelTier   string   `yaml:"model_tier" json:"model_tier"`
	Role        string   `yaml:"role" json:"role"`
	Description string   `yaml:"description" json:"description"`
	Skills      []string `yaml:"skills,omitempty" json:"skills,omitempty"`
}

type Registry struct {
	Bots map[string]Bot `yaml:"bots" json:"bots"`
}

// LoadRegistry loads registry.yaml from resourceRoot if provided, or embedded filesystem.
func LoadRegistry(resourceRoot string) (*Registry, error) {
	var data []byte
	var err error

	if resourceRoot != "" {
		regPath := filepath.Join(resourceRoot, "registry.yaml")
		data, err = os.ReadFile(regPath)
	}

	if data == nil || err != nil {
		// Fallback to embedded filesystem
		f, embedErr := capsulecorp.AssetsFS.Open("registry.yaml")
		if embedErr != nil {
			return nil, fmt.Errorf("unable to load embedded registry.yaml: %w", embedErr)
		}
		defer f.Close()
		data, err = io.ReadAll(f)
		if err != nil {
			return nil, fmt.Errorf("unable to read embedded registry.yaml: %w", err)
		}
	}

	var reg Registry
	if err := yaml.Unmarshal(data, &reg); err != nil {
		return nil, fmt.Errorf("invalid registry.yaml: %w", err)
	}

	// Normalize bot names
	normalized := make(map[string]Bot)
	for k, bot := range reg.Bots {
		if bot.Name == "" {
			bot.Name = k
		}
		if bot.Alias == "" {
			bot.Alias = "@" + strings.Title(bot.Name)
		}
		if bot.ModelTier == "" {
			bot.ModelTier = "inherit"
		}
		normalized[strings.ToLower(k)] = bot
	}
	reg.Bots = normalized

	return &reg, nil
}

// FindBot locates a bot by id, name, or alias (e.g. "bulma", "@Bulma").
func (r *Registry) FindBot(identifier string) (*Bot, bool) {
	clean := strings.ToLower(strings.TrimPrefix(strings.TrimSpace(identifier), "@"))
	if bot, ok := r.Bots[clean]; ok {
		return &bot, true
	}
	for _, bot := range r.Bots {
		if strings.EqualFold(bot.Alias, identifier) || strings.EqualFold(bot.Name, identifier) {
			return &bot, true
		}
	}
	return nil, false
}

// ListBots returns all bots sorted by name.
func (r *Registry) ListBots() []Bot {
	var list []Bot
	for _, b := range r.Bots {
		list = append(list, b)
	}
	sort.Slice(list, func(i, j int) bool {
		return list[i].Name < list[j].Name
	})
	return list
}
