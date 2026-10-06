package capsulecorp

import (
	"embed"
	"io/fs"
)

//go:embed registry.yaml config/* bots/* skills/*
var AssetsFS embed.FS

// FS returns the embedded assets file system.
func FS() fs.FS {
	return AssetsFS
}
