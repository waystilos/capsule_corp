package scaffold

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// BotTemplate returns markdown content for a new agent bot spec.
func BotTemplate(botName, alias, role, modelTier, description string) string {
	return fmt.Sprintf(`# %s (%s)

**Model Tier:** %s  
**Primary Role:** %s  

## Description
%s

## Responsibilities
- Execute domain tasks with high focus and minimal token waste.
- Comply strictly with Capsule Corp verification gates.
- Maintain immutable root requests across task handoffs.

## Operating Guidelines
1. Zero conversational fluff.
2. Produce testable diffs.
3. Validate against 'capsule check' before clocking out.
`, alias, botName, modelTier, role, description)
}

// ScaffoldBot creates a new bot markdown file in the bots/ directory.
func ScaffoldBot(targetDir, botName, alias, role, modelTier, description string) (string, error) {
	botsDir := filepath.Join(targetDir, "bots")
	if err := os.MkdirAll(botsDir, 0755); err != nil {
		return "", err
	}
	cleanName := strings.ToLower(strings.TrimPrefix(botName, "@"))
	filePath := filepath.Join(botsDir, cleanName+".md")

	if alias == "" {
		alias = "@" + strings.Title(cleanName)
	}
	if modelTier == "" {
		modelTier = "pro"
	}
	if role == "" {
		role = "Specialist"
	}

	content := BotTemplate(cleanName, alias, role, modelTier, description)
	if err := os.WriteFile(filePath, []byte(content), 0644); err != nil {
		return "", err
	}
	return filePath, nil
}
