"""Query-set hygiene preflight gates per design/QUERY_SET_HYGIENE.md §9.

Seven gates that must pass before tasks/v1/queries.jsonl is committed for the
launch run. Each gate lives in its own module and exposes a `check()` function
that takes a list of `Query` objects (plus optional context) and returns a
`CheckResult`.

A runner (`run_all.py`) orchestrates all seven, writes
`tasks/v1/verification_report.md`, and exits non-zero on any failure.

This package is parallel to `tcrun.preflight`, which is the 7-artifact
*reproducibility* gate (REPRODUCIBILITY.md §8). The two preflights run at
different times: this package runs at queries.jsonl commit-time; `tcrun.preflight`
runs at trial-start-time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Verdict for one gate. Aggregated by `run_all.py`."""

    gate: str
    passed: bool
    detail: str = ""
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


__all__ = ["CheckResult"]
