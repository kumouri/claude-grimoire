"""Grimoire MCP server — the umbrella exposing both engines' tools on one server.

Composes mnemosyne (reflexion lessons memory) and morpheus (session dreaming) into a single
`FastMCP("grimoire")`. Thin adapters over each engine's public library API — no dependency on
the engines' own MCP servers.

Run:
    pip install "grimoire[mcp]"          # pulls mnemosyne-reflexion + morpheus-dreaming + mcp
    python -m grimoire.mcp_server

Register (Claude Code):
    claude mcp add grimoire -e MNEMOSYNE_REPO=/path/to/memory-repo -- python -m grimoire.mcp_server
"""
from __future__ import annotations

import mnemosyne as mn
import morpheus as mo

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "the Grimoire MCP server needs the 'mcp' package — install with: "
        'pip install "grimoire[mcp]"'
    ) from e

mcp = FastMCP("grimoire")


# ---------------------------------------------------------------------------
# Mnemosyne — reflexion lessons memory (deliberate, git-backed, PR-governed)
# ---------------------------------------------------------------------------

@mcp.tool()
def recall(query: str = "", stage: str = "", tags: str = "", top: int = 6) -> str:
    """[memory] Recall the durable lessons most relevant to the current work, as a ranked digest.

    Call BEFORE starting a task and apply the returned lessons; tell the user which you applied.
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
    """[memory] Save a reusable decision/convention/rule to LOCAL reflexion memory."""
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
    """[memory] Turn a real failure into a durable lesson (learned-from-failure) in LOCAL memory."""
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
    """[memory] Move a LOCAL lesson to the SHARED tier and mark it review=proposed (stage the PR)."""
    return mn.promote(lesson_id)


@mcp.tool()
def prune(apply: bool = False) -> dict:
    """[memory] Retire (never delete) aged / over-cap low-value lessons. Dry-run unless apply=true."""
    return mn.prune(apply=apply)


@mcp.tool()
def hygiene() -> dict:
    """[memory] Report store health: duplicate pairs, never-recalled lessons, cap headroom."""
    return mn.hygiene()


# ---------------------------------------------------------------------------
# Morpheus — session dreaming / consolidation (automatic, per-project memory)
# ---------------------------------------------------------------------------

@mcp.tool()
def dream(cwd: str, transcript_path: str = "", session_id: str = "", mode: str = "") -> dict:
    """[dreams] Consolidate a session transcript's new delta into the project's long-term memory NOW.

    cwd: project working dir. transcript_path: the session .jsonl. mode (optional):
    headless | hybrid | deterministic. Returns {outcome, session_id, cwd, mode}.
    """
    return mo.dream(cwd, session_id=session_id, transcript_path=transcript_path, mode=mode or None)


@mcp.tool()
def wake(cwd: str, light: bool = False) -> str:
    """[dreams] Return the recall digest for a project — its long-term memory index + recent dreams."""
    return mo.wake(cwd, light=light)


@mcp.tool()
def dreams(cwd: str, n: int = 5) -> list:
    """[dreams] List the most recent dream-log entries for a project."""
    return mo.list_dreams(cwd, n=n)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
