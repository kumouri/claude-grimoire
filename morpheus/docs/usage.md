# Morpheus 🌙

Automatic **memory consolidation** for Claude Code. Every session quietly leaves the agent a
little smarter: before context is compacted and when a session ends, a background "dreamer"
reflects over the transcript and writes the durable signal into your long-term memory store — no
manual note-taking.

> Full design + diagrams: [architecture.md](architecture.md).

## What it does

- **Dreams** at `PreCompact` and `SessionEnd`: distills the session's durable facts (your
  preferences, decisions, project state, references) into `memory/<type>-<slug>.md` + `MEMORY.md`,
  merging and deduping against what's already there, and logs speculative cross-memory
  *associations* into `memory/dreams/`.
- **Wakes** at `SessionStart`: injects a short recall digest so a new session starts already
  remembering.
- **`/dream`**: consolidate the current session on demand.

## Install

From your clone of this repo:

```bash
# Global — dreams for every project (recommended)
morpheus install

# Or scoped to one project
morpheus install --project /path/to/repo

# Preview without writing
morpheus install --dry-run
```

This merges the three hooks into `~/.claude/settings.json` (idempotent; backs up first), creates
`~/.claude/morpheus/`, and seeds `~/.claude/morpheus/config.json`. Remove anytime with
`--uninstall`. Restart or start a new session for the hooks to take effect.

For the `/dream` command and skill, copy `commands/dream.md` to `~/.claude/commands/` and
`skills/dreaming/` to `~/.claude/skills/` (or symlink them).

## Configure

Edit `~/.claude/morpheus/config.json`:

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"headless"` | `headless` \| `hybrid` \| `deterministic` (token budget vs. depth) |
| `model` | `null` | Override model for headless/hybrid (else the CLI default; hybrid uses `hybrid_model`) |
| `min_delta_records` | `6` | Skip dreaming below this many new transcript records |
| `max_new_memories` | `8` | Cap on new memories per dream |
| `dream_timeout_sec` | `240` | Timeout for a headless/hybrid reflection |
| `redact_secrets` | `true` | Redact obvious credentials before anything is written |
| `auto_commit_memory` | `false` | If `memory/` is a git repo, commit each dream |
| `digest_dreams` | `3` | Recent dreams surfaced in the wake digest |
| `enabled` | `true` | Master switch |

### Engine modes

- **headless** — most capable; a background `claude -p` does the reflection. Costs tokens.
- **hybrid** — cheaper; a deterministic prefilter + a small model (haiku).
- **deterministic** — zero added tokens; heuristic capture only, no creative association.

## Optional: reconciliation sweep

The hooks already cover compaction and clean exits. To also catch sessions that **crashed** or were
**archived/deleted** without a clean `SessionEnd` (Claude Code has no archive/delete hook), schedule
`reconcile.py`:

- Windows: `pwsh -File morpheus/src/morpheus/install/schtask.windows.ps1`
- macOS: edit + load `morpheus/src/morpheus/install/launchd.macos.plist`
- Linux: add `morpheus/src/morpheus/install/cron.linux.txt` to your crontab

## Troubleshooting

- **Nothing happens** — sessions below `min_delta_records` are skipped by design. Check
  `~/.claude/morpheus/worker.log`.
- **Stuck/failed jobs** — inspect `~/.claude/morpheus/spool/` (pending) and `spool/failed/`
  (quarantined after `retry_max`).
- **No tokens to spend** — set `"mode": "deterministic"`.
- **Verify safely** — run a dream by hand:

  ```bash
  echo '{"hook_event_name":"SessionEnd","reason":"clear","session_id":"<id>","transcript_path":"<path>.jsonl","cwd":"<cwd>"}' | python morpheus/src/morpheus/dispatch.py
  python morpheus/src/morpheus/worker.py --once
  ```

## How it works

See [architecture.md](architecture.md) for the component, sequence, lifecycle, durability, and
engine diagrams.
