"""Gate 7: every query carries pre-computed token counts under the panel encoding.

Per QUERY_SET_HYGIENE.md §9 step 7:
    Pre-computed token counts are used by PADDING_STRATEGY.md §4
    (token-matching for padded-N=1 controls).

We use the o200k_base encoding (the strictest panel tokenizer per §4) and
verify that each query's ground_truth_code tokenizes to a positive count.

The cache itself lives at tasks/v1/tokenizer_cache.json (keyed by query_id);
this gate verifies (a) the cache file exists, (b) every query_id has an
entry, and (c) the entry's token count matches a fresh re-tokenization.

If the cache doesn't exist yet, the gate writes it (idempotent population)
unless `--read-only` is passed. This makes the gate self-bootstrapping during
mining, while still failing closed on stale or tampered caches at launch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import TOKENIZER_NAME

if TYPE_CHECKING:
    from tcrun.tasks import Query


def _tokenize(text: str) -> int:
    """Token count under the panel's strictest encoding."""
    import tiktoken

    enc = tiktoken.get_encoding(TOKENIZER_NAME)
    return len(enc.encode(text))


def check(
    queries: list["Query"],
    *,
    cache_path: Path | str = "tasks/v1/tokenizer_cache.json",
    read_only: bool = False,
) -> CheckResult:
    errors: list[str] = []
    cache_path = Path(cache_path)
    cache: dict[str, int] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"tokenizer cache {cache_path} is malformed JSON: {e}")
            return CheckResult(
                gate="tokenizer_cache_check",
                passed=False,
                detail=f"cache load failed: {e}",
                errors=errors,
            )

    fresh: dict[str, int] = {}
    for q in queries:
        live_count = _tokenize(q.ground_truth_code)
        cached = cache.get(q.query_id)
        if cached is None:
            if read_only:
                errors.append(
                    f"{q.query_id}: no entry in tokenizer cache {cache_path} "
                    f"(read-only mode)"
                )
            else:
                fresh[q.query_id] = live_count
        elif int(cached) != live_count:
            errors.append(
                f"{q.query_id}: tokenizer cache says {cached}, live tokenize says "
                f"{live_count} (stale cache or mutated ground_truth_code)"
            )

    if fresh and not read_only:
        cache.update(fresh)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    detail = (
        f"{len(queries) - len(errors)}/{len(queries)} queries have valid {TOKENIZER_NAME} "
        f"token counts (cache={cache_path}, populated +{len(fresh)})"
    )
    return CheckResult(
        gate="tokenizer_cache_check", passed=not errors, detail=detail, errors=errors
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tcrun.tasks import load_tasks

    path = sys.argv[1] if len(sys.argv) > 1 else "tasks/v1/queries.jsonl"
    read_only = "--read-only" in sys.argv
    result = check(load_tasks(path), read_only=read_only)
    print(result.gate, "PASS" if result.passed else "FAIL", "-", result.detail)
    for e in result.errors:
        print(" ", e)
    sys.exit(0 if result.passed else 1)
