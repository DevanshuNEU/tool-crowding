"""Gate 1: source_publication_date strictly after tier threshold.

Per QUERY_SET_HYGIENE.md §9 step 1:
    public:    > 2026-01-31
    held_back: > 2026-04-30
    sealed:    N/A (any date)

Failure mode: any query whose source_publication_date is on-or-before its tier's
threshold is reported. The check fails iff any such query exists.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import TIER_DATE_THRESHOLDS

if TYPE_CHECKING:
    from tcrun.tasks import Query


def _parse_iso_date(s: str) -> date:
    """Accept YYYY-MM-DD. Raises ValueError on malformed input (caller handles)."""
    return date.fromisoformat(s)


def check(queries: list["Query"]) -> CheckResult:
    errors: list[str] = []
    for q in queries:
        threshold = TIER_DATE_THRESHOLDS.get(q.tier)
        if threshold is None:
            # Sealed tier: no date constraint per §2 last bullet
            continue
        try:
            pub = _parse_iso_date(q.source_publication_date)
        except ValueError as e:
            errors.append(
                f"{q.query_id}: source_publication_date={q.source_publication_date!r} "
                f"is not ISO-8601 ({e})"
            )
            continue
        if pub <= threshold:
            errors.append(
                f"{q.query_id} (tier={q.tier}): source_publication_date "
                f"{q.source_publication_date} is not strictly after {threshold.isoformat()}"
            )
    detail = (
        f"{len(queries) - len(errors)}/{len(queries)} queries pass date threshold"
        if queries
        else "no queries to check"
    )
    return CheckResult(gate="date_check", passed=not errors, detail=detail, errors=errors)


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
