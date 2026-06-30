# hooks/dreaming

Automatic session **memory consolidation** ("dreaming") for Claude Code — hooks that run before
compaction and at session end to distill the transcript into long-term memory, plus a wake step on
session start and a manual `/dream`.

- **User guide:** [`docs/dreaming/README.md`](../../docs/dreaming/README.md)
- **Architecture + diagrams:** [`docs/dreaming/architecture.md`](../../docs/dreaming/architecture.md)

## Quick install

```bash
python hooks/dreaming/install/install.py          # global; --project DIR / --uninstall / --dry-run
```

## Layout

```
dispatch.py         hook entrypoint (PreCompact / SessionEnd / SessionStart)
worker.py           background dreamer: drains the spool, runs an engine, retries
reconcile.py        scheduled sweep for crashed / archived sessions
engines/            headless (default) · hybrid · deterministic  (one DreamResult contract)
lib/                config, projectdir, redact, lock, highwater, spool, transcript, memory, digest
prompts/            dream.system.md (reflection) · wake.system.md
install/            install.py + Windows/macOS/Linux schedulers
config.example.json settings.snippet.json
```

Pure Python 3 standard library — no dependencies. Tests live in the repo-root `tests/`
(`python -m unittest discover -s tests -t .`).
