"""Tests for scope.token_estimator."""
from scope.token_estimator import estimate_tokens, estimate_tokens_from_bytes


def test_empty_string_zero_tokens():
    assert estimate_tokens("") == 0


def test_short_string_returns_positive():
    assert estimate_tokens("hello world") > 0


def test_longer_string_more_tokens():
    short = estimate_tokens("hi")
    long = estimate_tokens("hi " * 1000)
    assert long > short


def test_from_bytes_roughly_chars_over_4():
    # 4000 bytes ≈ 1000 tokens (rough heuristic)
    assert 800 <= estimate_tokens_from_bytes(4000) <= 1200
