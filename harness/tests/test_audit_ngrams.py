"""Tests for mining.audit_ngrams covering the unsearchable-ngram filter.

GitHub Code Search rejects phrase queries containing `[`, `]`, or three
consecutive double-quotes with HTTP 422 (ERROR_TYPE_QUERY_PARSING_FATAL).
compute_audit filters those ngrams before the max_ngrams truncation so each
body still contributes max_ngrams worth of real audit signal.

Motivating failure: v1-pub-004's body produced a 5-gram spanning a
`Callable[[int, bool], None]` annotation into a docstring opener; the
resulting phrase contained both bracket characters and a triple-quote, and
crashed the live audit on 2026-05-25.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `mining` importable from harness/ root, matching production layout.
HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from mining.audit_ngrams import compute_audit  # noqa: E402


# Body shaped to produce risky 5-grams early in its high-entropy token stream:
# - `list[int]` and `dict[str, int]` produce ngrams containing `[` and `]`
# - The `"""..."""` docstring produces ngrams containing three double-quotes
# - The remainder is plain code so compute_audit can walk forward to find
#   max_ngrams worth of searchable ngrams.
_BODY_WITH_RISKY_NGRAMS = '''def process_records(records: list[int]) -> dict[str, int]:
    """Group integer records by parity and return label counts.

    Even values are tagged with the literal string "even" and odd
    with "odd"; the result dictionary maps each label to its count.
    """
    even_count = sum(1 for record in records if record % 2 == 0)
    odd_count = sum(1 for record in records if record % 2 == 1)
    negative_count = sum(1 for record in records if record < 0)
    positive_count = sum(1 for record in records if record > 0)
    zero_count = sum(1 for record in records if record == 0)
    return {"even": even_count, "odd": odd_count, "negative": negative_count}
'''


def test_compute_audit_drops_bracket_ngrams():
    """5-grams containing `[` or `]` are filtered before search."""
    audit = compute_audit(_BODY_WITH_RISKY_NGRAMS, online=False, max_ngrams=None)
    assert audit, "audit unexpectedly empty"
    for entry in audit:
        assert "[" not in entry["ngram"], f"bracket leaked: {entry['ngram']!r}"
        assert "]" not in entry["ngram"], f"bracket leaked: {entry['ngram']!r}"


def test_compute_audit_drops_triple_quote_ngrams():
    """5-grams containing three consecutive double-quotes are filtered before search."""
    triple_quote = '"' * 3
    audit = compute_audit(_BODY_WITH_RISKY_NGRAMS, online=False, max_ngrams=None)
    assert audit, "audit unexpectedly empty"
    for entry in audit:
        assert triple_quote not in entry["ngram"], (
            f"triple-quote leaked: {entry['ngram']!r}"
        )


def test_compute_audit_walks_past_filter_to_reach_max_ngrams():
    """Filter runs BEFORE max_ngrams truncation. A body whose first several
    5-grams are risky still yields max_ngrams of clean audit entries because
    compute_audit walks forward to find searchable ones."""
    audit = compute_audit(_BODY_WITH_RISKY_NGRAMS, online=False, max_ngrams=8)
    assert len(audit) == 8, f"expected 8 clean ngrams after walk-forward, got {len(audit)}"
    triple_quote = '"' * 3
    for entry in audit:
        ng = entry["ngram"]
        assert "[" not in ng and "]" not in ng and triple_quote not in ng, (
            f"risky char leaked past filter: {ng!r}"
        )
