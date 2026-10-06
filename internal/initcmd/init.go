package initcmd

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// InitProject sets up tool configs or directory structure for Capsule Corp integration.
// Existing files are never overwritten unless force is true; they are returned in skipped.
func InitProject(targetDir, tool string, force bool) (created, skipped []string, err error) {
	capsuleDir := filepath.Join(targetDir, ".capsule")
	if err := os.MkdirAll(capsuleDir, 0755); err != nil {
		return nil, nil, err
	}

	write := func(path, content string) error {
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			return err
		}
		flags := os.O_WRONLY | os.O_CREATE | os.O_EXCL
		if force {
			flags = os.O_WRONLY | os.O_CREATE | os.O_TRUNC
		}
		f, err := os.OpenFile(path, flags, 0644)
		if errors.Is(err, os.ErrExist) {
			skipped = append(skipped, path)
			return nil
		}
		if err != nil {
			return err
		}
		if _, err := f.WriteString(content); err != nil {
			f.Close()
			return err
		}
		if err := f.Close(); err != nil {
			return err
		}
		created = append(created, path)
		return nil
	}

	tool = strings.ToLower(strings.TrimSpace(tool))
	switch tool {
	case "gemini", "antigravity":
		err = write(filepath.Join(targetDir, "GEMINI.md"), "# Capsule Corp Directives for Gemini / Antigravity\n\nFollow Capsule Corp Standards: Product (@Bulma), Builder (@Goku), Reviewer (@Trunks), Coordinator (@Piccolo).\nAlways verify changes with `capsule check`.\n")
	case "claude":
		err = write(filepath.Join(targetDir, "CLAUDE.md"), "# Capsule Corp Directives for Claude Code\n\nAdhere to Capsule Corp Standards. Verify with `capsule check` before declaring tasks complete.\n")
	case "copilot", "github":
		err = write(filepath.Join(targetDir, ".github", "copilot-instructions.md"), "# Capsule Corp Directives for GitHub Copilot\n\nFollow Capsule Corp Standards: Product (@Bulma), Builder (@Goku), Reviewer (@Trunks), Coordinator (@Piccolo).\nAlways verify changes with `capsule check`.\n")
	case "cursor":
		err = write(filepath.Join(targetDir, ".cursorrules"), "# Capsule Corp Cursor Rules\nExecute verification via `capsule check`.\n")
	case "windsurf":
		err = write(filepath.Join(targetDir, ".windsurfrules"), "# Capsule Corp Windsurf Rules\nExecute verification via `capsule check`.\n")
	case "codex", "all", "":
		err = write(filepath.Join(targetDir, "AGENTS.md"), "# Capsule Corp Directives for this Project\n\nAll AI agents operating in this repository adhere to the Capsule Corp Standards.\n")
	default:
		return nil, nil, fmt.Errorf("unknown tool: %s (supported: gemini, claude, copilot, cursor, windsurf, codex)", tool)
	}
	if err != nil {
		return nil, nil, err
	}
	return created, skipped, nil
}
