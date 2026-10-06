package initcmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// InitProject sets up tool configs or directory structure for Capsule Corp integration.
func InitProject(targetDir, tool string) ([]string, error) {
	var created []string

	capsuleDir := filepath.Join(targetDir, ".capsule")
	if err := os.MkdirAll(capsuleDir, 0755); err != nil {
		return nil, err
	}

	tool = strings.ToLower(strings.TrimSpace(tool))
	switch tool {
	case "gemini", "antigravity":
		path := filepath.Join(targetDir, "GEMINI.md")
		content := "# Capsule Corp Directives for Gemini / Antigravity\n\nFollow Capsule Corp Standards: Product (@Bulma), Builder (@Goku), Reviewer (@Trunks), Coordinator (@Piccolo).\nAlways verify changes with `capsule check`.\n"
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return nil, err
		}
		created = append(created, path)

	case "claude":
		path := filepath.Join(targetDir, "CLAUDE.md")
		content := "# Capsule Corp Directives for Claude Code\n\nAdhere to Capsule Corp Standards. Verify with `capsule check` before declaring tasks complete.\n"
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return nil, err
		}
		created = append(created, path)

	case "cursor":
		path := filepath.Join(targetDir, ".cursorrules")
		content := "# Capsule Corp Cursor Rules\nExecute verification via `capsule check`.\n"
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return nil, err
		}
		created = append(created, path)

	case "windsurf":
		path := filepath.Join(targetDir, ".windsurfrules")
		content := "# Capsule Corp Windsurf Rules\nExecute verification via `capsule check`.\n"
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return nil, err
		}
		created = append(created, path)

	case "codex", "all", "":
		path := filepath.Join(targetDir, "AGENTS.md")
		content := "# Capsule Corp Directives for this Project\n\nAll AI agents operating in this repository adhere to the Capsule Corp Standards.\n"
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			return nil, err
		}
		created = append(created, path)

	default:
		return nil, fmt.Errorf("unknown tool: %s (supported: gemini, claude, cursor, windsurf, codex)", tool)
	}

	return created, nil
}
