"""Hard-coded deny list — paths scope must NEVER read.

Not configurable. Not a setting. Refusal happens here.
"""
from pathlib import Path
from fnmatch import fnmatch

EXCLUDED_PATTERNS: tuple[str, ...] = (
    # Claude Code session transcripts and credentials
    "*/.claude/projects/*",
    "*/.claude/.credentials.json",
    # SSH / cloud credentials
    "*/.ssh",
    "*/.ssh/*",
    "*/.aws",
    "*/.aws/*",
    "*/.gnupg",
    "*/.gnupg/*",
    "*/.config/gh",
    "*/.config/gh/*",
    # Secrets in any dir
    "*/.env",
    "*/.env.*",
    "*/id_rsa",
    "*/id_rsa.*",
    "*/*.pem",
    "*/*.key",
    "*/*.p12",
)


def is_excluded(path: Path) -> bool:
    """Return True if `path` matches any deny-list pattern.

    Compares against the absolute path string. Patterns use shell-glob syntax.
    """
    s = str(path.resolve() if path.is_absolute() else path)
    return any(fnmatch(s, pat) for pat in EXCLUDED_PATTERNS)
