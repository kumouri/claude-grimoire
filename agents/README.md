# agents/

Custom Claude Code **subagents**.

Each agent is a Markdown file with YAML frontmatter (`name`, `description`, optional `tools`
and `model`) followed by the agent's system prompt.

```
agents/
└── my-agent.md
```

To use one, copy it into `~/.claude/agents/` (user-level) or a project's `.claude/agents/`
directory. It then becomes available to the `Agent` tool as a `subagent_type`.
