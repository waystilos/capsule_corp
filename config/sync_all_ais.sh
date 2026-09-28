#!/usr/bin/env bash
# ==============================================================================
# Capsule Corp Universal Multi-AI Sync Engine
# Synchronizes skills, personas, and verification gates across:
#   - OpenAI Codex CLI (~/.codex/skills, ~/.codex/rules)
#   - Anthropic Claude Code (~/.claude/skills, ~/.claude/CLAUDE.md)
#   - Google Antigravity / Gemini (~/.gemini/config/skills, ~/.gemini/GEMINI.md)
#   - Cursor (~/.cursorrules)
#   - Windsurf (~/.windsurfrules)
#   - Open Agent Standard (~/.agents/skills)
#   - Workspace Root (AGENTS.md)
# ==============================================================================

set -euo pipefail

CAPSULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$CAPSULE_DIR/skills"
DEV_ROOT="${DEV_ROOT:-$(cd "$CAPSULE_DIR/../.." && pwd)}"

echo "=================================================================="
echo " 🌐 CAPSULE CORP UNIVERSAL MULTI-AI SYNCHRONIZER"
echo "=================================================================="

# 1. Target Skill Directories for All AIs
TARGET_SKILL_DIRS=(
  "$HOME/.gemini/config/skills"
  "$HOME/.codex/skills"
  "$HOME/.claude/skills"
  "$HOME/.agents/skills"
)

for target_dir in "${TARGET_SKILL_DIRS[@]}"; do
  echo "📦 Syncing skills to: $target_dir"
  mkdir -p "$target_dir"
  for skill_path in "$SKILLS_DIR"/*; do
    if [ -d "$skill_path" ]; then
      skill_name="$(basename "$skill_path")"
      dest="$target_dir/$skill_name"
      if [ -L "$dest" ] || [ -e "$dest" ]; then
        rm -rf "$dest"
      fi
      ln -s "$skill_path" "$dest"
      echo "   ✓ Linked $skill_name"
    fi
  done
done

echo ""
echo "📝 Injecting Global Rule Bridges..."

# 2. Universal Workspace AGENTS.md (loaded by Codex, Claude, Cursor, Windsurf, Copilot, Antigravity)
cat << EOF > "$DEV_ROOT/AGENTS.md"
# Capsule Corp Cohort Directives

All AI agents operating within this workspace must adhere to the **Capsule Corp Standards**:

## 1. The Capsule Corp Roster & Roles
- **Dr. Gero (The Android Architect):** Designs, scaffolds, and audits other agents and skills. Audits transcripts for friction.
- **Piccolo (The Tactical Lead):** Deconstructs complex feature epics into atomic task trees. Orchestrates worker agents. Never writes raw code directly.
- **Whis (The Chief of Staff):** Request triage, background routine scheduling (cron/timers), and status updates.
- **Trunks (The Timeline Sentinel):** Quality gatekeeper. Executes test suites, linters, and typecheckers before code is accepted. Guarantees zero regressions.
- **Goku (The Code Artisan):** Surgical code implementation with Ultra Instinct focus and high bias to act. Zero speculative dependencies or conversational filler.
- **Android 18 (Refactoring Specialist):** Precision dead-code removal and component restructuring without altering external API behaviors.

## 2. The 3-Stage Trust Engine
1. **Watch:** Pair interactively with the developer; correct mistakes in flight.
2. **Skill:** Codify successful workflows into reusable runbooks under \`skills/<name>/SKILL.md\`.
3. **Routine:** Graduate verified skills into autonomous background cron or subagent routines.

## 3. Mandatory Verification Gate (Trunks' Rule)
Before declaring any task complete or submitting code changes:
- Run the project's native test suite and linters.
- Or run the automated verification sentinel:
  \`capsule verify [project_dir]\`
- Verify exit code is 0 and no exposed secrets or merge conflicts are in the diff.

## 4. Cohort CLI
Universal CLI available at: \`$CAPSULE_DIR/bin/capsule\`
- \`capsule list\`
- \`capsule verify [dir]\`
- \`capsule audit --latest\`
- \`capsule scaffold\`
EOF
echo "   ✓ Universal AGENTS.md updated at $DEV_ROOT/AGENTS.md"

# 3. Claude Code Global Config (~/.claude/CLAUDE.md)
mkdir -p "$HOME/.claude"
cat << EOF > "$HOME/.claude/CLAUDE.md"
# Capsule Corp Directives for Claude Code

You are an operative of Capsule Corp.

- **Role Specialization:** Follow single-responsibility principles. If asked to act as Piccolo (Lead), focus on task decomposition and verification. If asked to act as Goku, focus on surgical coding with zero fluff. If asked to act as Trunks, strictly run tests and diff audits.
- **Verification Gate:** Always run tests and verify zero regressions before reporting task completion.
- **Capsule CLI:** You can execute \`capsule list\`, \`capsule verify\`, and \`capsule audit\`.
- **Cohort Manifest:** Read \`$CAPSULE_DIR/registry.yaml\` for active agent definitions and tool allowlists.
EOF
echo "   ✓ Claude Code global rules installed at ~/.claude/CLAUDE.md"

# 4. Cursor Global Rules (~/.cursorrules)
cat << 'EOF' > "$HOME/.cursorrules"
# Capsule Corp Directives for Cursor

- Adhere to the Capsule Corp agent roles (Piccolo for leadership/decomposition, Goku for surgical code, Trunks for testing/verification, Dr. Gero for agent design).
- Never modify unrelated files or introduce unrequested speculative abstractions.
- Always run the verification gate (`capsule verify` or native test runner) before finishing work.
EOF
echo "   ✓ Cursor global rules installed at ~/.cursorrules"

# 5. Windsurf Global Rules (~/.windsurfrules)
cat << 'EOF' > "$HOME/.windsurfrules"
# Capsule Corp Directives for Windsurf

- Adhere to the Capsule Corp agent roles (Piccolo, Goku, Trunks, Dr. Gero).
- Keep modifications lean, focused, and verified.
- Run tests and linters before reporting completion.
EOF
echo "   ✓ Windsurf global rules installed at ~/.windsurfrules"

# 6. Codex Permissions (~/.codex/rules/default.rules)
CODEX_RULES_FILE="$HOME/.codex/rules/default.rules"
if [ -f "$CODEX_RULES_FILE" ]; then
  if ! grep -q "capsule" "$CODEX_RULES_FILE"; then
    echo 'prefix_rule(pattern=["capsule"], decision="allow")' >> "$CODEX_RULES_FILE"
    echo "prefix_rule(pattern=[\"$CAPSULE_DIR/bin/capsule\"], decision=\"allow\")" >> "$CODEX_RULES_FILE"
    echo "   ✓ Added capsule execution permissions to ~/.codex/rules/default.rules"
  else
    echo "   ✓ Capsule permissions already present in ~/.codex/rules/default.rules"
  fi
fi

# 7. Shell PATH Integration (~/.zshrc)
ZSHRC="$HOME/.zshrc"
if [ -f "$ZSHRC" ]; then
  if ! grep -q "capsule-corp" "$ZSHRC"; then
    echo '' >> "$ZSHRC"
    echo '# Capsule Corp Agent CLI' >> "$ZSHRC"
    echo "export PATH=\"\$PATH:$CAPSULE_DIR/bin\"" >> "$ZSHRC"
    echo "   ✓ Added capsule to PATH in ~/.zshrc"
  else
    echo "   ✓ Capsule already in PATH in ~/.zshrc"
  fi
fi

echo ""
echo "=================================================================="
echo " 🎉 ALL AIs ARE NOW SYNCHRONIZED WITH CAPSULE CORP!"
echo "    - Antigravity / Gemini: Connected (Skills & Rules)"
echo "    - OpenAI Codex: Connected (Skills, Rules & Execution Allow)"
echo "    - Anthropic Claude Code: Connected (Skills & Global Rules)"
echo "    - Cursor: Connected (Global ~/.cursorrules)"
echo "    - Windsurf: Connected (Global ~/.windsurfrules)"
echo "    - Open Agents Standard: Connected (~/.agents/skills)"
echo "=================================================================="
