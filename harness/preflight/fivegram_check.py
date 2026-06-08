"""Gate 4: high-entropy 5-gram public-hit count below rejection threshold.

Per QUERY_SET_HYGIENE.md §9 step 4 + §4:
    - Reject if 2 or more high-entropy 5-grams hit ≥1 public source.
    - Cached audit rows live on the Query.fivegram_audit field
      (schema in tcrun/tasks.py:49). This module validates the cache; it does
      NOT re-fetch from GitHub Code Search (re-fetching is the miner's job, in
      `harness/mining/audit_ngrams.py` — separate concern).

The validator is therefore offline by default. If a query's fivegram_audit is
empty (no rows), the check fails for that query: we require the audit to be
populated at mining time so the launch artifact is reproducible from cached
data, not live-search data that may shift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import FIVEGRAM_REJECT_THRESHOLD

if TYPE_CHECKING:
    from tcrun.tasks import Query


def _count_public_hits(audit: list) -> int:
    """Per §4: a 5-gram counts as 'hit' if EITHER github_hits OR web_hits >= 1."""
    return sum(1 for row in audit if row.github_hits >= 1 or row.web_hits >= 1)


def check(queries: list["Query"]) -> CheckResult:
    errors: list[str] = []
    for q in queries:
        if not q.fivegram_audit:
            errors.append(
                f"{q.query_id}: fivegram_audit is empty; "
                f"populate via harness/mining/audit_ngrams.py before commit"
            )
            continue
        hits = _count_public_hits(q.fivegram_audit)
        if hits >= FIVEGRAM_REJECT_THRESHOLD:
            errors.append(
                f"{q.query_id}: {hits} high-entropy 5-grams hit public sources "
                f"(>= reject threshold {FIVEGRAM_REJECT_THRESHOLD}); "
                f"likely lifted from training-set-adjacent content"
            )
    detail = (
        f"{len(queries) - len(errors)}/{len(queries)} queries pass 5-gram check "
        f"(threshold={FIVEGRAM_REJECT_THRESHOLD})"
    )
    return CheckResult(gate="fivegram_check", passed=not errors, detail=detail, errors=errors)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tcrun.tasks import load_tasks

    path = sys.argv[1] if len(sys.argv) > 1 else "tasks/v1/queries.jsonl"
    result = check(load_tasks(path))
    print(result.gate, "PASS" if result.passed else "FAIL", "-", result.detail)
    for e in result.errors:
        print(" ", e)
    sys.exit(0 if result.passed else 1)
