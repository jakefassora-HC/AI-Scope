"""Regex-based secret redaction.

Defense in depth. Even though scope's deny list blocks high-risk files,
project-level CLAUDE.md or git metadata could contain pasted tokens.
Run every string heading to the browser through `redact()` first.
"""
import re

_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}"),       # Anthropic
    re.compile(r"sk-proj-[a-zA-Z0-9_\-]{20,}"),       # OpenAI project
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),            # generic OpenAI-style
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),              # GitHub PAT (classic)
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),      # GitHub PAT (fine-grained)
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access key
    re.compile(r"xox[baprs]-[a-zA-Z0-9\-]{10,}"),     # Slack tokens
    re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),  # JWT
)


def redact(text: str) -> str:
    """Replace any matched secret pattern with `[REDACTED]`."""
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out
