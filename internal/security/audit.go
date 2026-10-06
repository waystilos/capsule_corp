package security

import (
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"capsule-corp/internal/secretpatterns"
)

type FileFinding struct {
	Path        string `json:"path"`
	Line        int    `json:"line"`
	Rule        string `json:"rule"`
	Description string `json:"description"`
	Snippet     string `json:"snippet"`
}

var skippedDirs = map[string]bool{
	".git":         true,
	"node_modules": true,
	"vendor":       true,
	".venv":        true,
	"venv":         true,
	"__pycache__":  true,
	"dist":         true,
	"build":        true,
	"target":       true,
	".pytest_cache": true,
}

var binaryExts = map[string]bool{
	".exe":   true,
	".bin":   true,
	".dylib": true,
	".so":    true,
	".dll":   true,
	".png":   true,
	".jpg":   true,
	".jpeg":  true,
	".gif":   true,
	".ico":   true,
	".zip":   true,
	".tar":   true,
	".gz":    true,
	".pdf":   true,
	".pyc":   true,
}

// ScanRepository recursively inspects files for hardcoded secrets.
func ScanRepository(rootDir string) ([]FileFinding, error) {
	var findings []FileFinding

	err := filepath.WalkDir(rootDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			if skippedDirs[d.Name()] {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(path))
		if binaryExts[ext] {
			return nil
		}

		// Don't scan large files (> 2MB)
		info, err := d.Info()
		if err != nil || info.Size() > 2*1024*1024 {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		// Check for null bytes (binary file heuristic)
		if strings.IndexByte(string(content[:min(len(content), 1024)]), 0) != -1 {
			return nil
		}

		matches := secretpatterns.ScanText(string(content))
		relPath, _ := filepath.Rel(rootDir, path)
		if relPath == "" {
			relPath = path
		}

		for _, m := range matches {
			findings = append(findings, FileFinding{
				Path:        relPath,
				Line:        m.Line,
				Rule:        m.Rule,
				Description: m.Description,
				Snippet:     m.Match,
			})
		}

		return nil
	})

	return findings, err
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
