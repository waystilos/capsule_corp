# Situation: I need to sync rules to my AI tools

Use this recipe when you want Capsule Corp skills and global guidance available in Codex, Claude, Gemini, Cursor, or Windsurf.

## Preview first

```bash
capsule sync --dry-run
```

The preview does not create directories, replace skill links, or write global instruction files.

## Sync intentionally

```bash
capsule sync --force
```

Forced replacement moves existing targets to timestamped `.capsule-backup-*` files before installing the new links or directives.

The sync affects global locations such as:

- `~/.codex/skills/`
- `~/.claude/agents/`, `~/.claude/skills/`, `~/.claude/CLAUDE.md`, and `~/.claude/settings.json`
- `~/.gemini/config/skills/`
- `~/.agents/skills/`
- `~/.cursorrules` and `~/.windsurfrules`
- the configured workspace-root `AGENTS.md`

Review those paths before using `--force` on a shared or heavily customized machine.

## You are ready when

- The dry run matches your intent.
- You know which existing files will be backed up.
- The sync exits successfully and the target AI can see the skills.

