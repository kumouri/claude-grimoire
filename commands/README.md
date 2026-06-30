# commands/

Custom Claude Code **slash commands**.

Each command is a Markdown file whose name becomes the command (e.g. `my-command.md` →
`/my-command`). The file body is the prompt; optional YAML frontmatter can set `description`
and `argument-hint`.

```
commands/
└── my-command.md
```

To use one, copy it into `~/.claude/commands/` (user-level) or a project's
`.claude/commands/` directory.
