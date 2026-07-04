"""Mnemosyne MCP server — exposes the reflexion memory as MCP tools.

Any MCP client (Claude Desktop, Claude Code, Cursor, ...) can recall/capture/reflect/promote
against a git-backed memory. Thin adapters over the public API in `mnemosyne`; the repo and
config resolve from $MNEMOSYNE_REPO / $MNEMOSYNE_CONFIG exactly like the CLI.

Run:
    pip install "mnemosyne-reflexion[mcp]"
    MNEMOSYNE_REPO=/path/to/memory-repo python -m mnemosyne.mcp_server

Register (Claude Code):
    claude mcp add mnemosyne -e MNEMOSYNE_REPO=/path/to/memory-repo -- python -m mnemosyne.mcp_server
"""
from __future__ import annotations

import mnemosyne as mn

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "the MCP server needs the 'mcp' package — install with: pip install \"mnemosyne-reflexion[mcp]\""
    ) from e

mcp = FastMCP("mnemosyne")


@mcp.tool()
def recall(query: str = "", stage: str = "", tags: str = "", top: int = 6) -> str:
    """Recall the durable lessons most relevant to the current work, as a ranked digest.

    Call this BEFORE starting a task and apply the returned lessons. Announce to the user which
    lessons were applied.

    query: free-text description of what you're about to do (a brief, a ticket, a plan).
    stage: optional lifecycle stage to boost stage-scoped lessons (see the repo's config).
    tags:  optional comma-separated tags to match directly (the strongest signal).
    top:   max lessons to return.
    """
    kwargs = {"top": top, "as_text": True}
    if stage:
        kwargs["stage"] = stage
    if tags:
        kwargs["tags"] = tags
    return mn.recall(query or None, **kwargs)


@mcp.tool()
def capture(title: str, lesson: str, category: str = "", tags: str = "",
            confidence: str = "medium", stage: str = "", spec: str = "") -> dict:
    """Save a reusable decision/convention/rule to LOCAL reflexion memory.

    Use for a durable choice worth reusing (a naming rule, a default, a settled decision) — NOT
    for a mistake (use `reflect`). Lands local (per-developer); promote it separately for team review.
    Announce to the user that a lesson was saved.
    """
    kwargs = {"confidence": confidence}
    if category:
        kwargs["category"] = category
    if tags:
        kwargs["tags"] = tags
    if stage:
        kwargs["stage"] = stage
    if spec:
        kwargs["spec"] = spec
    return mn.capture(title, lesson, **kwargs)


@mcp.tool()
def reflect(title: str, lesson: str, reflection_of: str, tags: str = "",
            confidence: str = "high", stage: str = "", spec: str = "") -> dict:
    """Turn a real failure into a durable lesson (learned-from-failure) in LOCAL reflexion memory.

    reflection_of: what actually went wrong (the feedback that triggered this). The engine refuses
    missing-deliverable / transient failures (a re-run, not a lesson) and reinforces near-duplicates
    instead of adding noise. Announce to the user that a lesson was saved.
    """
    kwargs = {"confidence": confidence}
    if tags:
        kwargs["tags"] = tags
    if stage:
        kwargs["stage"] = stage
    if spec:
        kwargs["spec"] = spec
    return mn.reflect(title, lesson, reflection_of, **kwargs)


@mcp.tool()
def promote(lesson_id: str) -> dict:
    """Move a LOCAL lesson to the SHARED tier and mark it review=proposed (stage the governance PR).

    A human reviewer approves the PR before the lesson becomes team-wide truth. Announce this to the user.
    To send lesson(s) UP to a broader team/enterprise store instead of this repo's shared tier, use `export`.
    """
    return mn.promote(lesson_id)


@mcp.tool()
def export(lesson_ids: str, to: str) -> dict:
    """Export chosen LOCAL lesson(s) UP to a broader shared store (a tier from config.stores).

    lesson_ids: one id or a comma-separated list (e.g. "L-0007,L-0009").
    to:         the destination tier label (e.g. "team" or "enterprise").
    Each lesson is copied into the store under a new store-prefixed id (review=proposed) and the local
    original is kept + marked for retire-on-merge; `sync` retires it once the upstream PR is approved.
    Announce which lessons were exported and to which tier.
    """
    ids = [x.strip() for x in lesson_ids.split(",") if x.strip()]
    return mn.export(ids, to)


@mcp.tool()
def prune(apply: bool = False) -> dict:
    """Retire (never delete) aged / over-cap low-value lessons. Dry-run unless apply=true."""
    return mn.prune(apply=apply)


@mcp.tool()
def hygiene() -> dict:
    """Report store health: duplicate pairs, never-recalled lessons, cap headroom, prune candidates."""
    return mn.hygiene()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
