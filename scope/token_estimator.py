"""Estimate token count for arbitrary text.

Uses tiktoken's cl100k_base encoding as a reasonable proxy for
Anthropic tokenization. Exact counts differ; this is for UI display only,
never for billing or hard limits.
"""
import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    """Return estimated token count for `text`."""
    if not text:
        return 0
    return len(_ENC.encode(text))


def estimate_tokens_from_bytes(num_bytes: int) -> int:
    """Fast estimate without reading the file. ~4 bytes per token heuristic."""
    return max(0, num_bytes // 4)
