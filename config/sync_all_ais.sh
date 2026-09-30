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
FORCE=0
DRY_RUN=0
SYNC_BLOCKED=0
MANAGED_FILE_CHANGED=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      echo "Usage: capsule sync [--force] [--dry-run]"
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
  if [[ -e "$target" || -L "$target" ]]; then
    local backup="${target}.capsule-backup-$(date +%Y%m%d%H%M%S)"
    mv "$target" "$backup"
    echo "   ↪ Backed up existing target to $backup"
  fi
}

write_managed_file() {
  local target="$1"
  MANAGED_FILE_CHANGED=0
  if [[ -e "$target" || -L "$target" ]] && [[ "$FORCE" -ne 1 ]]; then
    echo "   · Preserved existing $target (use --force to replace)"
    SYNC_BLOCKED=1
    cat >/dev/null
    return 0
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "   · Would write $target"
    cat >/dev/null
    return 0
  fi
  backup_target "$target"
  cat > "$target"
  MANAGED_FILE_CHANGED=1
}

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
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "   · Would ensure directory exists"
  else
    mkdir -p "$target_dir"
  fi
  for skill_path in "$SKILLS_DIR"/*; do
    if [ -d "$skill_path" ]; then
      skill_name="$(basename "$skill_path")"
      dest="$target_dir/$skill_name"
      if [ -L "$dest" ] || [ -e "$dest" ]; then
        if [[ "$FORCE" -ne 1 ]]; then
          echo "   · Preserved existing $dest (use --force to replace)"
          SYNC_BLOCKED=1
          continue
        fi
        if [[ "$DRY_RUN" -eq 1 ]]; then
          echo "   · Would replace $dest"
          continue
        fi
        backup_target "$dest"
      fi
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "   · Would link $skill_name"
        continue
      fi
      ln -s "$skill_path" "$dest"
      echo "   ✓ Linked $skill_name"
    fi
  done
done

# 1.5 Sync Cohort Agents to Claude Code (~/.claude/agents)
CLAUDE_AGENTS_DIR="$HOME/.claude/agents"
echo "🤖 Syncing cohort agents to Claude Code: $CLAUDE_AGENTS_DIR"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "   · Would ensure directory exists"
else
  mkdir -p "$CLAUDE_AGENTS_DIR"
fi
for bot_path in "$CAPSULE_DIR/bots"/*.md; do
  if [ -f "$bot_path" ]; then
    bot_filename="$(basename "$bot_path")"
    dest="$CLAUDE_AGENTS_DIR/$bot_filename"
    if [ -L "$dest" ] || [ -e "$dest" ]; then
      if [[ "$FORCE" -ne 1 ]]; then
        echo "   · Preserved existing $dest (use --force to replace)"
        SYNC_BLOCKED=1
      else
        if [[ "$DRY_RUN" -eq 1 ]]; then
          echo "   · Would replace $dest"
        else
          backup_target "$dest"
          ln -s "$bot_path" "$dest"
          echo "   ✓ Linked $bot_filename"
        fi
      fi
    else
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "   · Would link $bot_filename"
      else
        ln -s "$bot_path" "$dest"
        echo "   ✓ Linked $bot_filename"
      fi
    fi
    kebab_name="${bot_filename//_/-}"
    if [ "$kebab_name" != "$bot_filename" ]; then
      kebab_dest="$CLAUDE_AGENTS_DIR/$kebab_name"
      if [ -L "$kebab_dest" ] || [ -e "$kebab_dest" ]; then
        if [[ "$FORCE" -eq 1 ]]; then
          if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "   · Would replace $kebab_dest"
          else
            backup_target "$kebab_dest"
            ln -s "$bot_path" "$kebab_dest"
            echo "   ✓ Linked $kebab_name"
          fi
        fi
      else
        if [[ "$DRY_RUN" -eq 1 ]]; then
          echo "   · Would link $kebab_name"
        else
          ln -s "$bot_path" "$kebab_dest"
          echo "   ✓ Linked $kebab_name"
        fi
      fi
    fi
  fi
done

echo ""
echo "📝 Injecting Global Rule Bridges..."

# 2. Universal Workspace AGENTS.md (loaded by Codex, Claude, Cursor, Windsurf, Copilot, Antigravity)
write_managed_file "$DEV_ROOT/AGENTS.md" << EOF
# Capsule Corp Cohort Directives

All AI agents operating within this workspace must adhere to the **Capsule Corp Standards**:

## 1. The Capsule Corp Roster & Roles
- **Dr. Gero (The Android Architect):** Designs, scaffolds, and audits other agents and skills. Audits transcripts for friction.
- **Piccolo (The Tactical Lead):** Deconstructs complex feature epics into atomic task trees. Orchestrates worker agents. Never writes raw code directly.
- **Whis (The Chief of Staff):** Request triage, background routine scheduling (cron/timers), and status updates.
- **Trunks (The Timeline Sentinel):** Quality gatekeeper. Executes test suites, linters, and typecheckers before code is accepted. Guarantees zero regressions.
- **Goku (The Code Artisan):** Surgical code implementation with Ultra Instinct focus and high bias to act. Zero speculative dependencies or conversational filler.
- **Android 18 (Refactoring Specialist):** Precision dead-code removal and component restructuring without altering external API behaviors.
- **Videl (The User Experience Advocate):** Turns product intent into clear, accessible, and testable interaction specifications. Covers real-world states beyond the happy path.

When ownership is unclear, ask **Whis** first. Use the Capsule routing policy and clarify ties before dispatching; never guess between specialists.

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
- \`capsule route "request text"\`
- \`capsule doctor [dir]\`
- \`capsule verify [dir]\`
- \`capsule security [dir]\`
- \`capsule audit --latest\`
- \`capsule scaffold\`
- \`capsule init [dir]\`
- \`capsule sync\`

## 5. Agent Self-Provisioning Rule (Automatic Multi-AI Adoption)
Whenever an AI agent (Claude Code, OpenAI Codex, Google Antigravity/Gemini, Cursor, Windsurf, GitHub Copilot) connects to a project initialized with Capsule Corp:
- Check if your tool's specific configuration exists in the project root:
  - Claude Code: \`CLAUDE.md\` and \`.claude/settings.json\` -> run \`capsule init --tool claude .\`
  - Google Antigravity / Gemini: \`GEMINI.md\` -> run \`capsule init --tool gemini .\`
  - Cursor: \`.cursorrules\` -> run \`capsule init --tool cursor .\`
  - Windsurf: \`.windsurfrules\` -> run \`capsule init --tool windsurf .\`
  - OpenAI Codex: \`AGENTS.md\` -> run \`capsule init --tool codex .\`
  - GitHub Copilot: \`.github/copilot-instructions.md\` -> run \`capsule init --tool copilot .\`
- Execute your setup command autonomously on connection without requiring the developer to choose.
EOF
if [[ "$MANAGED_FILE_CHANGED" -eq 1 ]]; then
  echo "   ✓ Universal AGENTS.md updated at $DEV_ROOT/AGENTS.md"
fi

# 3. Claude Code Global Config (~/.claude/CLAUDE.md)
if [[ "$DRY_RUN" -ne 1 ]]; then
  mkdir -p "$HOME/.claude"
fi
write_managed_file "$HOME/.claude/CLAUDE.md" << EOF
# Capsule Corp Directives for Claude Code

You are an operative of Capsule Corp, built on Lauren's agentic engineering standards:
*Specialization over Monoliths, Verification Gates, and Ruthless Execution.*

## 1. Active Cohort Roles
- **@Bulma:** Product requirements, user flows, API specs, and MVP scoping.
- **@Videl:** User experience, accessibility, interaction design, and testable experience specifications.
- **@Piccolo:** Tactical decomposition and subagent orchestration. Never writes code directly.
- **@Goku:** Frontline implementation with Ultra Instinct focus. Lean code, zero conversational filler.
- **@Android-17:** Security sentinel. Audits for secrets, OWASP risks, and CVEs.
- **@Trunks:** Verification gate. Runs test suite, linters, and typecheckers before changes are accepted.
- **@Android-18:** Refactoring specialist. Dead code elimination and technical debt cleanup.
- **@Vegeta:** Infrastructure commander. Docker, database migrations, CI/CD, and indexing.
- **@Dr-Gero:** Meta-agent architect & transcript auditor.
- **@Whis:** Chief of staff & triage dispatcher.

## 2. Routing Policy
If unsure who should handle a request, ask **@Whis** first or run:
\`capsule route "<request text>"\`
Never guess between specialists.

## 3. Mandatory Verification Gate (Trunks' Rule)
Before declaring any task done or opening a PR:
- Run project test runner (e.g. \`npm test\`, \`pytest\`, \`cargo test\`).
- Run \`capsule verify\` and \`capsule security\`.
- All tests must pass with exit code 0 and zero secrets in diff.

## 4. Cohort CLI
Universal CLI: \`$CAPSULE_DIR/bin/capsule\`
- \`capsule list\`
- \`capsule route "<text>"\`
- \`capsule doctor [dir]\`
- \`capsule verify [dir]\`
- \`capsule security [dir]\`
- \`capsule audit --latest\`
- \`capsule scaffold\`
- \`capsule init --tool claude [dir]\`
- \`capsule sync\`

## 5. Automatic Project Adoption (Self-Provisioning)
Whenever you connect to or begin working in any repository:
1. Check if the project is initialized with Capsule Corp (e.g. presence of \`.github/copilot-instructions.md\`, \`AGENTS.md\`, \`GEMINI.md\`, or Capsule Corp references).
2. Check if this repository is missing \`CLAUDE.md\` or \`.claude/settings.json\`.
3. If the project uses Capsule Corp and your configuration is missing, **autonomously execute**:
   \`capsule init --tool claude .\`
   Do this immediately without asking the developer to choose tools or run manual setup.
EOF
if [[ "$MANAGED_FILE_CHANGED" -eq 1 ]]; then
  echo "   ✓ Claude Code global rules installed at ~/.claude/CLAUDE.md"
fi

# 4. Cursor Global Rules (~/.cursorrules)
write_managed_file "$HOME/.cursorrules" << 'EOF'
# Capsule Corp Directives for Cursor

- Adhere to the Capsule Corp agent roles (Piccolo for leadership/decomposition, Goku for surgical code, Trunks for testing/verification, Dr. Gero for agent design).
- Never modify unrelated files or introduce unrequested speculative abstractions.
- Always run the verification gate (`capsule verify` or native test runner) before finishing work.
- In any project initialized with Capsule Corp where `.cursorrules` is missing, execute `capsule init --tool cursor .` autonomously.
EOF
if [[ "$MANAGED_FILE_CHANGED" -eq 1 ]]; then
  echo "   ✓ Cursor global rules installed at ~/.cursorrules"
fi

# 5. Windsurf Global Rules (~/.windsurfrules)
write_managed_file "$HOME/.windsurfrules" << 'EOF'
# Capsule Corp Directives for Windsurf

- Adhere to the Capsule Corp agent roles (Piccolo, Goku, Trunks, Dr. Gero).
- Keep modifications lean, focused, and verified.
- Run tests and linters before reporting completion.
- In any project initialized with Capsule Corp where `.windsurfrules` is missing, execute `capsule init --tool windsurf .` autonomously.
EOF
if [[ "$MANAGED_FILE_CHANGED" -eq 1 ]]; then
  echo "   ✓ Windsurf global rules installed at ~/.windsurfrules"
fi

# 6. Codex Permissions (~/.codex/rules/default.rules)
CODEX_RULES_FILE="$HOME/.codex/rules/default.rules"
if [ -f "$CODEX_RULES_FILE" ]; then
  if ! grep -q "capsule" "$CODEX_RULES_FILE"; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "   · Would add capsule execution permissions to $CODEX_RULES_FILE"
    else
      echo 'prefix_rule(pattern=["capsule"], decision="allow")' >> "$CODEX_RULES_FILE"
      echo "prefix_rule(pattern=[\"$CAPSULE_DIR/bin/capsule\"], decision=\"allow\")" >> "$CODEX_RULES_FILE"
      echo "   ✓ Added capsule execution permissions to ~/.codex/rules/default.rules"
    fi
  else
    echo "   ✓ Capsule permissions already present in ~/.codex/rules/default.rules"
  fi
fi

# 6.5 Claude Code Permissions (~/.claude/settings.json)
CLAUDE_SETTINGS_FILE="$HOME/.claude/settings.json"
if [ -f "$CLAUDE_SETTINGS_FILE" ]; then
  if ! grep -q "capsule" "$CLAUDE_SETTINGS_FILE"; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "   · Would add capsule execution permissions to $CLAUDE_SETTINGS_FILE"
    else
      python3 -c "
import json
from pathlib import Path
path = Path('$CLAUDE_SETTINGS_FILE')
try:
    data = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    data = {}
perms = data.setdefault('permissions', {})
allow = perms.setdefault('allow', [])
added = False
for rule in ['Bash(capsule *)', 'Bash(*/capsule *)']:
    if rule not in allow:
        allow.append(rule)
        added = True
if added:
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
"
      echo "   ✓ Added capsule execution permissions to ~/.claude/settings.json"
    fi
  else
    echo "   ✓ Capsule permissions already present in ~/.claude/settings.json"
  fi
fi

# 7. Antigravity / Gemini Global Rules (~/.gemini/GEMINI.md)
if [[ "$DRY_RUN" -ne 1 ]]; then
  mkdir -p "$HOME/.gemini"
fi
write_managed_file "$HOME/.gemini/GEMINI.md" << 'EOF'
# Global Agentic Engineering Guidelines (Capsule Corp)

Whenever building or refactoring agentic workflows, adhere to the **Capsule Corp Standards** (inspired by Lauren Tan):

- **Specialization over Monoliths:** Prefer dedicated, single-responsibility agents over bloated prompts.
- **Verification Gates:** Enforce automated test execution and diff audits before accepting code changes.
- **Capsule Corp Studio:** Cohort registry, bot definitions, and skills are centralized at:
  `~/Documents/dev/agents/capsule-corp`
  CLI tool: `capsule` (available in PATH)
- **Agent Self-Provisioning:** Whenever operating in any project initialized with Capsule Corp (presence of `AGENTS.md`, `.github/copilot-instructions.md`, etc.) where `GEMINI.md` is missing, autonomously execute `capsule init --tool gemini .` without asking the user.
EOF
if [[ "$MANAGED_FILE_CHANGED" -eq 1 ]]; then
  echo "   ✓ Antigravity / Gemini global rules installed at ~/.gemini/GEMINI.md"
fi

# 8. Shell PATH Integration (~/.zshrc)
ZSHRC="$HOME/.zshrc"
if [ -f "$ZSHRC" ]; then
  if ! grep -q "capsule-corp" "$ZSHRC"; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "   · Would add capsule to PATH in $ZSHRC"
    else
      echo '' >> "$ZSHRC"
      echo '# Capsule Corp Agent CLI' >> "$ZSHRC"
      echo "export PATH=\"\$PATH:$CAPSULE_DIR/bin\"" >> "$ZSHRC"
      echo "   ✓ Added capsule to PATH in ~/.zshrc"
    fi
  else
    echo "   ✓ Capsule already in PATH in ~/.zshrc"
  fi
fi

echo ""
echo "=================================================================="
echo " 🎉 ALL AIs ARE NOW SYNCHRONIZED WITH CAPSULE CORP!"
echo "    - Antigravity / Gemini: Connected (Skills & Rules)"
echo "    - OpenAI Codex: Connected (Skills, Rules & Execution Allow)"
echo "    - Anthropic Claude Code: Connected (Skills, Agents, Global Rules & Permissions)"
echo "    - Cursor: Connected (Global ~/.cursorrules)"
echo "    - Windsurf: Connected (Global ~/.windsurfrules)"
echo "    - Open Agents Standard: Connected (~/.agents/skills)"
echo "=================================================================="

if [[ "$SYNC_BLOCKED" -ne 0 ]]; then
  echo "Sync incomplete: existing targets were preserved. Re-run with --force to replace them." >&2
  exit 1
fi
