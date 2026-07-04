"""Grimoire — the book that holds both.

An umbrella over two independent Claude Code memory engines:

- **mnemosyne** — reflexion *lessons* memory (recall / capture / reflect / promote / prune / hygiene).
- **morpheus** — automatic session *dreaming* / consolidation (dream / wake / dreams).

Grimoire itself is thin: one MCP server (`grimoire.mcp_server`, exposing both engines' tools) and
one Claude Code plugin (a single lifecycle-hook dispatcher composing both). The engines remain
separately installable; Grimoire just unifies the surface.
"""
__version__ = "0.3.0"
