"""Morpheus MCP server — exposes dreaming/consolidation as MCP tools.

Any MCP client (Claude Desktop, Claude Code, Cursor, ...) can dream/wake/list against a
project's memory store. Thin adapters over the public API in `morpheus`.

Run:
    pip install "morpheus-dreaming[mcp]"
    python -m morpheus.mcp_server

Register (Claude Code):
    claude mcp add morpheus -- python -m morpheus.mcp_server
"""
from __future__ import annotations

import morpheus

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "the MCP server needs the 'mcp' package — install with: "
        'pip install "morpheus-dreaming[mcp]"'
    ) from e

mcp = FastMCP("morpheus")


@mcp.tool()
def dream(cwd: str, transcript_path: str = "", session_id: str = "", mode: str = "") -> dict:
    """Consolidate a session transcript's new delta into the project's long-term memory NOW.

    Runs the reflection engine over everything past the session's high-water mark and writes
    durable memories + a dream-log entry. Returns {outcome, session_id, cwd, mode}.

    cwd:             project working dir (keys the per-project memory store).
    transcript_path: the session .jsonl to consolidate.
    session_id:      session id (for the high-water mark + dream-log naming).
    mode:            optional engine override — headless | hybrid | deterministic.
    """
    return morpheus.dream(cwd, session_id=session_id, transcript_path=transcript_path,
                          mode=mode or None)


@mcp.tool()
def wake(cwd: str, light: bool = False) -> str:
    """Return the recall digest for a project — its long-term memory index + recent dreams."""
    return morpheus.wake(cwd, light=light)


@mcp.tool()
def dreams(cwd: str, n: int = 5) -> list:
    """List the most recent dream-log entries for a project."""
    return morpheus.list_dreams(cwd, n=n)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
