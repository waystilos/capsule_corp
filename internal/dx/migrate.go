package dx

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type MigrationReport struct {
	Actions []string `json:"actions"`
	Warnings []string `json:"warnings"`
}

// CheckLegacyPython inspects the system to see if a broken Python version is active.
func CheckLegacyPython() []string {
	var warnings []string

	if capsulePath, err := exec.LookPath("capsule"); err == nil {
		if content, err := os.ReadFile(capsulePath); err == nil {
			text := string(content)
			if strings.Contains(text, "from capsule") || strings.Contains(text, "capsule.cli") {
				warnings = append(warnings, fmt.Sprintf("Legacy Python shim detected at %s (causes ModuleNotFoundError). Run 'capsule sync' to upgrade to Go.", capsulePath))
			}
		}
	}

	for _, pipCmd := range []string{"pip", "pip3"} {
		if _, err := exec.LookPath(pipCmd); err == nil {
			checkCmd := exec.Command(pipCmd, "show", "capsule-corp")
			if err := checkCmd.Run(); err == nil {
				warnings = append(warnings, fmt.Sprintf("Legacy 'capsule-corp' Python package still installed in %s.", pipCmd))
				break
			}
		}
	}

	if pyenvPath, err := exec.LookPath("pyenv"); err == nil {
		checkCmd := exec.Command(pyenvPath, "exec", "pip", "show", "capsule-corp")
		if err := checkCmd.Run(); err == nil {
			warnings = append(warnings, "Legacy 'capsule-corp' Python package detected in active pyenv environment.")
		}
	}

	return warnings
}

// MigrateLegacyPython removes stale Python packages, shims, and debris.
func MigrateLegacyPython(repoDir string) MigrationReport {
	var rep MigrationReport

	// 1. Uninstall via pip / pip3 if present
	for _, pipCmd := range []string{"pip", "pip3"} {
		if _, err := exec.LookPath(pipCmd); err == nil {
			checkCmd := exec.Command(pipCmd, "show", "capsule-corp")
			if err := checkCmd.Run(); err == nil {
				uninst := exec.Command(pipCmd, "uninstall", "-y", "capsule-corp")
				if err := uninst.Run(); err == nil {
					rep.Actions = append(rep.Actions, fmt.Sprintf("Uninstalled legacy 'capsule-corp' package via %s", pipCmd))
				}
			}
		}
	}

	// 2. Check pyenv if present
	if pyenvPath, err := exec.LookPath("pyenv"); err == nil {
		checkCmd := exec.Command(pyenvPath, "exec", "pip", "show", "capsule-corp")
		if err := checkCmd.Run(); err == nil {
			uninst := exec.Command(pyenvPath, "exec", "pip", "uninstall", "-y", "capsule-corp")
			if err := uninst.Run(); err == nil {
				rep.Actions = append(rep.Actions, "Uninstalled legacy 'capsule-corp' via pyenv pip")
				_ = exec.Command(pyenvPath, "rehash").Run()
				rep.Actions = append(rep.Actions, "Ran pyenv rehash to remove stale shims")
			}
		}
	}

	// 3. Check pipx if present
	if pipxPath, err := exec.LookPath("pipx"); err == nil {
		uninst := exec.Command(pipxPath, "uninstall", "capsule-corp")
		if out, err := uninst.CombinedOutput(); err == nil && strings.Contains(string(out), "uninstalled") {
			rep.Actions = append(rep.Actions, "Uninstalled legacy 'capsule-corp' via pipx")
		}
	}

	// 4. Check for legacy python scripts/shims on PATH
	if capsulePath, err := exec.LookPath("capsule"); err == nil {
		if content, err := os.ReadFile(capsulePath); err == nil {
			text := string(content)
			if strings.Contains(text, "from capsule") || strings.Contains(text, "capsule.cli") {
				goBin := filepath.Join(repoDir, "bin", "capsule-go")
				if _, err := os.Stat(goBin); err == nil {
					_ = os.Rename(capsulePath, capsulePath+".legacy-python.bak")
					if copyErr := copyFile(goBin, capsulePath); copyErr == nil {
						_ = os.Chmod(capsulePath, 0755)
						rep.Actions = append(rep.Actions, fmt.Sprintf("Replaced legacy Python script at %s with Go binary", capsulePath))
					}
				}
			}
		}
	}

	// 5. Clean up repo debris
	for _, debris := range []string{".pytest_cache", ".venv"} {
		p := filepath.Join(repoDir, debris)
		if _, err := os.Stat(p); err == nil {
			if err := os.RemoveAll(p); err == nil {
				rep.Actions = append(rep.Actions, fmt.Sprintf("Removed legacy %s directory from repository", debris))
			}
		}
	}

	matches, _ := filepath.Glob(filepath.Join(repoDir, "*.egg-info"))
	for _, m := range matches {
		_ = os.RemoveAll(m)
		rep.Actions = append(rep.Actions, fmt.Sprintf("Removed %s", filepath.Base(m)))
	}

	return rep
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}
