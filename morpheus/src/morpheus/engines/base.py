"""Engine interface + shared result type + registry.

Every engine exposes ``run(**ctx) -> DreamResult`` and accepts a superset of
keyword args (``messages``, ``rendered``, ``memory_store``, ``memory_dir``,
``cfg``, ``session_id``, ``cwd``), ignoring the ones it doesn't need via
``**_``. This lets the worker call any engine uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DreamResult:
    summary: str = ""
    memories: list = field(default_factory=list)      # list[memory.Memory]
    associations: list = field(default_factory=list)  # speculative cross-links (str)
    hypotheses: list = field(default_factory=list)    # next-session hypotheses (str)
    processed_count: int = 0
    wrote_directly: bool = False                      # engine already wrote memory files
    engine: str = ""


def get_engine(mode: str):
    if mode == "deterministic":
        from morpheus.engines.deterministic import DeterministicEngine
        return DeterministicEngine()
    if mode == "hybrid":
        from morpheus.engines.hybrid import HybridEngine
        return HybridEngine()
    from morpheus.engines.headless import HeadlessEngine
    return HeadlessEngine()
