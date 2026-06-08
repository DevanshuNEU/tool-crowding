"""Gate 5: per-repo query count within tier cap.

Per QUERY_SET_HYGIENE.md §9 step 5 + §6:
    public:    <= 10 queries per source_repo
    held_back: <=  7 queries per source_repo
    sealed:    (no cap; sealed tier is intentionally single-repo from OCI)

A failed gate means the set is over-concentrated on one repo; diversify or drop.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import TIER_REPO_CAPS

if TYPE_CHECKING:
    from tcrun.tasks import Query


def check(queries: list["Query"]) -> CheckResult:
    errors: list[str] = []
    per_tier_counts: dict[str, Counter] = {}
    for q in queries:
        per_tier_counts.setdefault(q.tier, Counter())[q.source_repo] += 1

    for tier, counter in per_tier_counts.items():
        cap = TIER_REPO_CAPS.get(tier)
        if cap is None:
            continue
        for repo, n in counter.items():
            if n > cap:
                errors.append(
                    f"tier={tier}: repo {repo!r} contributes {n} queries (cap {cap})"
                )

    summary = []
    for tier, counter in sorted(per_tier_counts.items()):
        cap = TIER_REPO_CAPS.get(tier)
        max_count = max(counter.values()) if counter else 0
        summary.append(
            f"{tier}: {len(counter)} repos, max {max_count}/repo (cap={cap})"
        )
    detail = "; ".join(summary) if summary else "no queries to check"
    return CheckResult(
        gate="per_repo_cap_check", passed=not errors, detail=detail, errors=errors
    )


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
