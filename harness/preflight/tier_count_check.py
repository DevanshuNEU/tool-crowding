"""Gate 6: exact tier counts.

Per QUERY_SET_HYGIENE.md §9 step 6 + §7:
    public:    exactly 30
    held_back: exactly 10
    sealed:    exactly 10

Hard counts, no fuzz. A short tier fails the gate; an overflowing tier also
fails (we want the launch artifact deterministic at the count level).

Caveat: by design, queries.jsonl ships only the public tier (the held-back
and sealed tiers live in `held_back.jsonl` / `sealed.jsonl` and are
.gitignored — `tasks/v1/README.md` table). When running the gate on the
PUBLIC artifact alone, sealed and held_back counts are expected to be 0 and
the gate accepts that. To validate the FULL launch set, the runner has to
load all three jsonl files and pass them as a combined list.

The check therefore takes a `mode` argument:
    "public-only" (default): expects only tier=public, count exactly 30
    "all-tiers":              expects all three tiers, exact counts
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Literal

from preflight import CheckResult
from preflight._common import TIER_COUNTS

if TYPE_CHECKING:
    from tcrun.tasks import Query

Mode = Literal["public-only", "all-tiers"]


def check(queries: list["Query"], *, mode: Mode = "public-only") -> CheckResult:
    errors: list[str] = []
    counts = Counter(q.tier for q in queries)

    if mode == "public-only":
        public_n = counts.get("public", 0)
        if public_n != TIER_COUNTS["public"]:
            errors.append(
                f"tier=public: expected {TIER_COUNTS['public']}, got {public_n}"
            )
        for tier in ("held_back", "sealed"):
            if counts.get(tier, 0) != 0:
                errors.append(
                    f"tier={tier}: expected 0 in public-only mode, got {counts[tier]}"
                )
    else:  # all-tiers
        for tier, expected in TIER_COUNTS.items():
            got = counts.get(tier, 0)
            if got != expected:
                errors.append(f"tier={tier}: expected {expected}, got {got}")

    detail = (
        f"counts: {dict(counts)} mode={mode}"
        if counts
        else f"no queries; expected {TIER_COUNTS} (mode={mode})"
    )
    return CheckResult(
        gate="tier_count_check", passed=not errors, detail=detail, errors=errors
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tcrun.tasks import load_tasks

    path = sys.argv[1] if len(sys.argv) > 1 else "tasks/v1/queries.jsonl"
    mode: Mode = "all-tiers" if "--all-tiers" in sys.argv else "public-only"
    result = check(load_tasks(path), mode=mode)
    print(result.gate, "PASS" if result.passed else "FAIL", "-", result.detail)
    for e in result.errors:
        print(" ", e)
    sys.exit(0 if result.passed else 1)
