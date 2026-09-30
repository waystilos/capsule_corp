# Situation: Multi-AI Check-In Room & Conference Meeting

## When to use this recipe
Use this recipe when two or more AI agents (such as **Claude Code**, **OpenAI Codex**, **Google Antigravity / Gemini**, **Cursor**, or **Windsurf**) are working on the same codebase simultaneously, or when handing off work across shifts between different models.

---

## The Problem
When different AI models work on the same repository without coordination:
1. They can overwrite each other's in-flight edits.
2. They don't know what task another model is currently implementing.
3. Chatty multi-agent communication loops can cause token exhaustion or bloated logs.

---

## The Solution: Capsule Corp Check-In Room & Timeclock
Capsule Corp provides a zero-overhead, file-backed blackboard architecture located in `.capsule/room.json` and rendered into human-readable `.capsule/CONFERENCE.md`.

No background daemons or inter-agent network ports are required. Agents simply "clock in" when starting work and "clock out" when their changes pass verification.

---

## Step-by-Step Multi-AI Workflow

### 1. Check Who is in the Room
Before claiming work or editing files, check active shifts:

```bash
capsule room
```

Output preview:
```text
========================================================================
 🏛️  CAPSULE CORP CHECK-IN ROOM & TIMECLOCK
========================================================================
 ON SHIFT (1 active agent):
   🟢 Claude Code
      • Company / Model: Anthropic (Claude 3.7 Sonnet)
      • Role:            Builder (@Goku)
      • Task:            Implement Stripe webhook handlers
      • Active Files:    src/api/webhooks.ts, src/services/billing.ts
      • Clocked In At:   2026-09-30T15:10:00+00:00
------------------------------------------------------------------------
 ⚠️  ACTIVE FILE CAUTION:
   Currently modified by active shift: src/api/webhooks.ts, src/services/billing.ts
========================================================================
```

### 2. Clock In to Your Shift
Claim your task and the files you plan to touch:

```bash
capsule clock-in --task "Add unit tests for webhook signature verification" --files "tests/test_webhooks.py"
```

> **Note:** Capsule automatically detects your agent identity (`CLAUDE_CODE`, `CODEX`, `GEMINI_CLI`/`ANTIGRAVITY`, `CURSOR_AGENT`, `WINDSURF_AGENT`), provider company, and model. You do not need to pass `--agent` manually unless overriding.

### 3. Work & Run Project Checks
Implement your changes surgical and lean. Run project checks before clocking out:

```bash
capsule check .
```

### 4. Clock Out and Record Handoff Summary
When verification succeeds with exit code 0, clock out:

```bash
capsule clock-out --summary "Added 8 unit tests for webhook signature validation. All passed."
```

---

## Log Hygiene & Auto-Pruning Built In

You never have to worry about cleaning up shift logs or abandoned locks:

1. **Auto-Expiration (Anti-Deadlock):** If an agent crashes or the developer disconnects without clocking out, any shift older than **2 hours** is automatically moved to history with an `[Auto-Expired]` notice on the next command invocation. Active files are freed automatically.
2. **Rolling Ring Buffer:** Completed shifts in history are capped at a maximum of **15 entries**. The `.capsule/room.json` and `.capsule/CONFERENCE.md` files never bloat repository size.
3. **Manual Reset:** To clear all active shifts immediately:
   ```bash
   capsule room --clean
   ```

---

## What “Done” Looks Like
- `capsule room` shows your shift clocked out.
- `.capsule/CONFERENCE.md` contains the completed summary under Recent Handoffs.
- `capsule check .` exited with code 0.
