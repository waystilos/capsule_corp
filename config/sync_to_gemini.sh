#!/usr/bin/env bash
# ==============================================================================
# Capsule Corp Cohort Sync Script
# Centralizes skills and rules globally across all dev workspaces
# ==============================================================================

set -euo pipefail

CAPSULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_CONFIG_DIR="$HOME/.gemini/config"
GLOBAL_SKILLS_DIR="$GLOBAL_CONFIG_DIR/skills"
FORCE=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      echo "Usage: sync_to_gemini.sh [--force] [--dry-run]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

backup_target() {
  local target="$1"
  if [ -L "$target" ] || [ -e "$target" ]; then
    local backup="${target}.capsule-backup-$(date +%Y%m%d%H%M%S)"
    mv "$target" "$backup"
    echo "  Backed up existing target to $backup"
  fi
}

echo " Capsule Corp Centralizer: Syncing cohort skills to global Antigravity config..."

if [ "$DRY_RUN" -ne 1 ]; then
  mkdir -p "$GLOBAL_SKILLS_DIR"
fi

# Link each skill into ~/.gemini/config/skills
for skill_path in "$CAPSULE_DIR"/skills/*; do
  if [ -d "$skill_path" ]; then
    skill_name="$(basename "$skill_path")"
    target="$GLOBAL_SKILLS_DIR/$skill_name"
    
    if [ -L "$target" ] || [ -e "$target" ]; then
      if [ "$FORCE" -ne 1 ]; then
        echo "  Preserved existing skill: $target (use --force to replace)"
        continue
      fi
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "  Would replace skill: $target"
        continue
      fi
      backup_target "$target"
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  Would link skill: $skill_name -> $target"
      continue
    fi
    
    ln -s "$skill_path" "$target"
    echo "  Linked skill: $skill_name -> $target"
  fi
done

echo ""
echo " Capsule Corp cohort skills successfully linked to $GLOBAL_SKILLS_DIR!"
echo "All projects on this machine can now discover these skills globally."
