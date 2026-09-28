#!/usr/bin/env bash
# ==============================================================================
# Capsule Corp Cohort Sync Script
# Centralizes skills and rules globally across all dev workspaces
# ==============================================================================

set -euo pipefail

CAPSULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_CONFIG_DIR="$HOME/.gemini/config"
GLOBAL_SKILLS_DIR="$GLOBAL_CONFIG_DIR/skills"

echo " Capsule Corp Centralizer: Syncing cohort skills to global Antigravity config..."

mkdir -p "$GLOBAL_SKILLS_DIR"

# Link each skill into ~/.gemini/config/skills
for skill_path in "$CAPSULE_DIR"/skills/*; do
  if [ -d "$skill_path" ]; then
    skill_name="$(basename "$skill_path")"
    target="$GLOBAL_SKILLS_DIR/$skill_name"
    
    if [ -L "$target" ] || [ -e "$target" ]; then
      rm -rf "$target"
    fi
    
    ln -s "$skill_path" "$target"
    echo "  Linked skill: $skill_name -> $target"
  fi
done

echo ""
echo " Capsule Corp cohort skills successfully linked to $GLOBAL_SKILLS_DIR!"
echo "All projects on this machine can now discover these skills globally."
