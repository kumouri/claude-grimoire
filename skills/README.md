# skills/

Custom Claude Code **Skills**.

Each skill lives in its own subdirectory containing a `SKILL.md` (with YAML frontmatter:
`name`, `description`, and optional `allowed-tools`) plus any supporting scripts, templates,
or reference files it needs.

```
skills/
└── my-skill/
    ├── SKILL.md
    └── ...supporting files
```

To use one, copy the skill folder into `~/.claude/skills/` (user-level) or a project's
`.claude/skills/` directory.
