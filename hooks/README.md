# hooks/

Custom Claude Code **hooks** — scripts that run on lifecycle events (e.g. `PreToolUse`,
`PostToolUse`, `Stop`, `SessionStart`).

Each hook lives in its own subdirectory with the script(s) it runs and a snippet showing the
`settings.json` configuration that wires it up:

```
hooks/
└── my-hook/
    ├── hook.sh          # or .ps1 / .js / etc.
    └── settings.snippet.json
```

To install, merge the `settings.snippet.json` into your `~/.claude/settings.json` (or a
project's `.claude/settings.json`) and point it at the script path.
