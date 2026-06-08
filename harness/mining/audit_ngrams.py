"""Compute the 5-gram contamination audit for a query.

Implements QUERY_SET_HYGIENE.md §4 verbatim:

    1. Tokenize ground_truth_code with the panel's strictest encoding (o200k_base).
    2. Strip low-entropy tokens (whitespace, comments, keywords, common builtins).
    3. Extract all contiguous 5-grams from the remaining stream.
    4. For each 5-gram, GitHub Code Search for that exact phrase; count hits.
    5. Return a list of FivegramAuditEntry rows for Query.fivegram_audit.

The web-hits half of §4 (Google Custom Search) is currently set to 0 for every
row because the session was scoped to "GitHub Code Search only" per the
user's session-start question. If Google CSE is wired in later, populate
`web_hits` here.

GitHub Code Search has stiff rate limits (~30 req/min). The caller is
responsible for throttling across queries.

Usage:
    from mining.audit_ngrams import compute_audit
    audit = compute_audit(ground_truth_code, language="python", max_ngrams=20)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

# Reuse the panel constants directly from the preflight package.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight._common import LOW_ENTROPY_TOKENS, TOKENIZER_NAME  # noqa: E402

if TYPE_CHECKING:
    pass


# Approximation of "low-entropy token" set in the tokenized-string space.
# tiktoken token strings often have a leading space (b' word' style); after
# decoding back to str we lowercase + strip whitespace before comparing.
_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)


class RateLimitError(RuntimeError):
    """Raised when GitHub Code Search returns a rate-limit error.

    The audit MUST fail-closed on rate-limit: a silent 0 would be a contamination
    defense vulnerability — it would let a contaminated query pass the §4 check
    just because the search couldn't be performed. The caller decides whether to
    sleep and retry or abort.
    """


def _tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
    """Return [(decoded_token, char_start, char_end)] over the o200k tokenization.

    The (start, end) span is into the ORIGINAL text — i.e., text[start:end] is
    a verbatim substring of the input. This lets 5-grams be reconstructed as
    real source-code slices rather than tokenizer-artifact concatenations.
    """
    import tiktoken

    enc = tiktoken.get_encoding(TOKENIZER_NAME)
    ids = enc.encode(text)
    out: list[tuple[str, int, int]] = []
    cursor = 0
    for tid in ids:
        decoded = enc.decode([tid])
        # tiktoken's decode is lossless for the o200k_base BPE on UTF-8 text we
        # control, so `''.join(decoded) == text` holds. The cursor walks the
        # original text in lockstep with the decoded stream.
        start = cursor
        end = cursor + len(decoded)
        out.append((decoded, start, end))
        cursor = end
    return out


def _is_low_entropy(token: str) -> bool:
    """Drop whitespace-only, punctuation-only, or stoplist tokens (§4 step 3)."""
    stripped = token.strip().lower()
    if not stripped:
        return True
    if _PUNCT_RE.match(stripped):
        return True
    if stripped in LOW_ENTROPY_TOKENS:
        return True
    return False


def _extract_5grams(text: str) -> list[str]:
    """Return source-code substrings each spanning 5 consecutive high-entropy tokens.

    Each 5-gram is a verbatim slice of the input — the slice from the start of
    the i-th high-entropy token to the end of the (i+4)-th, in source order. The
    slice may include low-entropy tokens in between (which makes it a real
    code substring, the right shape for `gh search code "..."`).
    """
    toks = _tokens_with_offsets(text)
    he_idxs = [i for i, (tok, _s, _e) in enumerate(toks) if not _is_low_entropy(tok)]
    if len(he_idxs) < 5:
        return []
    grams: list[str] = []
    for i in range(len(he_idxs) - 4):
        start = toks[he_idxs[i]][1]
        end = toks[he_idxs[i + 4]][2]
        gram = text[start:end].strip()
        # Collapse whitespace; GitHub Code Search treats `a\n b` and `a  b` as
        # the same phrase, so normalize to single spaces before searching.
        gram = " ".join(gram.split())
        if gram:
            grams.append(gram)
    return grams


def _gh_code_search_hits(query: str, *, timeout: int = 30) -> int:
    """Return number of hits from `gh search code <query>` (capped at 1).

    Raises RateLimitError on a 403 rate-limit response from GitHub. Raises
    RuntimeError on other hard failures. Returns 0 only when the API
    successfully returned an empty result set.
    """
    if shutil.which("gh") is None:
        raise RuntimeError("gh CLI not on PATH; cannot perform 5-gram audit")
    try:
        proc = subprocess.run(
            ["gh", "search", "code", query, "--json", "path", "--limit", "1"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"gh search code timed out after {timeout}s on {query!r}") from e

    if proc.returncode != 0:
        stderr = proc.stderr or ""
        if "rate limit" in stderr.lower() or "403" in stderr:
            raise RateLimitError(stderr.strip().splitlines()[0] if stderr else "rate limited")
        raise RuntimeError(
            f"gh search code failed (rc={proc.returncode}) on {query!r}: {stderr[:200]}"
        )
    try:
        results = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh search code returned non-JSON: {proc.stdout[:200]!r}") from e
    return len(results)


def compute_audit(
    ground_truth_code: str,
    *,
    max_ngrams: int | None = 20,
    sleep_between: float = 2.0,
    rate_limit_backoff: float = 60.0,
    max_retries: int = 3,
    online: bool = True,
) -> list[dict]:
    """Return the fivegram_audit row list for a query's ground_truth_code.

    Each entry: {"ngram": str, "github_hits": int, "web_hits": int}.
    web_hits is always 0 in this implementation (see module docstring).

    Args:
        ground_truth_code: the code body to audit.
        max_ngrams: cap the number of 5-grams audited per query to bound API cost.
                    Picks the first N high-entropy 5-grams (deterministic order).
        sleep_between: seconds between successful gh calls (rate-limit hygiene).
        rate_limit_backoff: seconds to sleep after a RateLimitError before retry.
        max_retries: number of rate-limit retries before giving up on a 5-gram.
        online: if False, return entries with github_hits=0 (useful for tests).
    """
    ngrams = _extract_5grams(ground_truth_code)
    # GitHub Code Search rejects phrase queries containing certain characters:
    # `[`/`]` are treated as character-class regex, and `"""` inside the quoted
    # phrase breaks the parser. These ngrams return HTTP 422 instead of a hit
    # count. Filter them at audit time and walk forward to the next searchable
    # ngram so each body still contributes max_ngrams worth of real audit signal.
    ngrams = [ng for ng in ngrams if "[" not in ng and "]" not in ng and '"""' not in ng]
    if max_ngrams is not None:
        ngrams = ngrams[:max_ngrams]
    audit: list[dict] = []
    for ng in ngrams:
        if not online:
            audit.append({"ngram": ng, "github_hits": 0, "web_hits": 0})
            continue
        hits: int | None = None
        for attempt in range(max_retries):
            try:
                hits = _gh_code_search_hits(f'"{ng}"')
                break
            except RateLimitError as e:
                wait = rate_limit_backoff * (attempt + 1)
                print(
                    f"  rate-limited on attempt {attempt + 1}/{max_retries} "
                    f"({e}); sleeping {wait:.0f}s",
                    flush=True,
                )
                time.sleep(wait)
        if hits is None:
            # Exhausted retries — fail-closed. The caller (preflight) will see
            # this audit entry and fail the run.
            raise RateLimitError(
                f"5-gram {ng!r} could not be audited after {max_retries} retries"
            )
        audit.append({"ngram": ng, "github_hits": hits, "web_hits": 0})
        time.sleep(sleep_between)
    return audit


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="mining.audit_ngrams")
    parser.add_argument("--code", required=True, help="Path to a file holding ground_truth_code")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-ngrams", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()
    code = Path(args.code).read_text(encoding="utf-8")
    audit = compute_audit(
        code,
        max_ngrams=args.max_ngrams,
        sleep_between=args.sleep,
        online=not args.offline,
    )
    print(json.dumps(audit, indent=2))
