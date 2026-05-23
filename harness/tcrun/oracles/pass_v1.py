"""Pass criterion v1: symbol match + 50% token overlap.

Implements RESEARCH_DESIGN.md §4 Pass@1 (primary, pre-registered).

For each query, the trial PASSES if BOTH conditions hold:
    1. Symbol match: returned snippet contains ground_truth_symbol as a literal
       substring.
    2. Token overlap: >= 50% of ground-truth's tokenized words appear in the
       returned snippet (after lower-casing + removing punctuation, no stemming).

Robustness checks (secondary, reported separately, NOT this oracle):
    - Strict pass@1: exact-string match of function body to ground truth
    - Lenient pass@1: any-token-overlap >= 1 word

Oracle version: v1. Smoke-tested against 5 hand-curated cases on 2026-05-23.
"""

from __future__ import annotations
import string

ORACLE_VERSION = "pass_v1"
OVERLAP_THRESHOLD = 0.5


def pass_criterion_v1(
    returned_snippet: str,
    ground_truth_symbol: str,
    ground_truth_code: str,
) -> bool:
    """Default v1 pass@1 criterion per RESEARCH_DESIGN.md §4.

    Args:
        returned_snippet: The code snippet the agent returned (via tool call).
        ground_truth_symbol: The function/class/symbol name the answer must contain.
        ground_truth_code: The canonical ground-truth code (used for token overlap).

    Returns:
        True if both symbol match AND >= 50% token overlap; False otherwise.

    Edge cases:
        - Empty returned_snippet → False (no symbol can match in empty string)
        - Empty ground_truth_symbol → False (a meaningless oracle call; refuse)
        - Empty ground_truth_code → True only if symbol match holds
          (degenerate case; overlap fraction is vacuously 1.0)
    """
    if not ground_truth_symbol:
        return False
    if ground_truth_symbol not in returned_snippet:
        return False
    gt_tokens = _tokenize(ground_truth_code)
    if not gt_tokens:
        return True
    snippet_tokens = _tokenize(returned_snippet)
    overlap = gt_tokens & snippet_tokens
    return (len(overlap) / len(gt_tokens)) >= OVERLAP_THRESHOLD


def _tokenize(text: str) -> set[str]:
    """Lowercase + strip punctuation + split on whitespace. No stemming."""
    lowered = text.lower()
    translator = str.maketrans("", "", string.punctuation)
    stripped = lowered.translate(translator)
    return set(stripped.split())
