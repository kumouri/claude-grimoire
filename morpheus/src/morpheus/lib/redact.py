"""Best-effort secret redaction so a dream never persists credentials.

This is defense-in-depth on top of the instruction (in the dreaming system
prompt) to never store secrets. It errs toward over-redaction.
"""
from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),                       # OpenAI-style
    re.compile(r"\b(?:gh[posu]|github_pat)_[A-Za-z0-9_]{20,}\b"),    # GitHub tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS access key id
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),                # Slack tokens
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),                     # Google API key
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|authorization|bearer)\b"
        r"\s*[:=]\s*\S+"
    ),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        out = pat.sub(REDACTED, out)
    return out
