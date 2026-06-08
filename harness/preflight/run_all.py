"""Run all 7 query-hygiene gates and write tasks/v1/verification_report.md.

Per QUERY_SET_HYGIENE.md §9: this is the single command that the launch
playbook runs before queries.jsonl is committed.

Usage:
    python -m preflight.run_all                              # public-tier from queries.jsonl
    python -m preflight.run_all --all-tiers                  # combined public+held+sealed
    python -m preflight.run_all --offline                    # skip gh calls
    python -m preflight.run_all --queries tasks/v1/queries.jsonl ...

Exit status:
    0 = all 7 gates pass
    1 = at least one gate failed (details in verification_report.md + stdout)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python -m preflight.run_all` from harness/ root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preflight import CheckResult  # noqa: E402
from preflight import (  # noqa: E402
    date_check,
    fivegram_check,
    license_check,
    per_repo_cap_check,
    repo_eligibility_check,
    tier_count_check,
    tokenizer_cache_check,
)
from tcrun.tasks import Query, load_tasks  # noqa: E402


def _load_combined(paths: list[Path]) -> list[Query]:
    out: list[Query] = []
    for p in paths:
        if p.exists():
            out.extend(load_tasks(p))
    return out


def _format_report(results: list[CheckResult], queries: list[Query]) -> str:
    """Reviewer-readable markdown report per §9."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_pass = sum(1 for r in results if r.passed)
    n_total = len(results)
    status = "PASS" if n_pass == n_total else "FAIL"

    lines: list[str] = [
        "# tasks/v1 verification report",
        "",
        f"- Generated: {now}",
        f"- Queries loaded: {len(queries)}",
        f"- Gates: {n_pass}/{n_total} pass — **{status}**",
        "",
        "## Per-gate status",
        "",
        "| Gate | Status | Detail |",
        "|---|---|---|",
    ]
    for r in results:
        status_cell = "PASS" if r.passed else "FAIL"
        # Markdown table cells: escape pipes in detail to avoid breaking the row
        detail_cell = (r.detail or "").replace("|", "\\|")
        lines.append(f"| {r.gate} | {status_cell} | {detail_cell} |")
    lines.append("")

    failed = [r for r in results if not r.passed]
    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.gate}")
            lines.append("")
            for e in r.errors:
                lines.append(f"- {e}")
            lines.append("")

    lines.append("## Spec")
    lines.append("")
    lines.append(
        "Each gate corresponds to a numbered step in "
        "`design/QUERY_SET_HYGIENE.md §9` (verification workflow). "
        "All 7 must pass before `tasks/v1/queries.jsonl` is committed for launch."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight.run_all")
    parser.add_argument(
        "--queries", type=Path, default=Path("tasks/v1/queries.jsonl"),
        help="Path to the public-tier queries jsonl (default: tasks/v1/queries.jsonl)",
    )
    parser.add_argument(
        "--held-back", type=Path, default=Path("tasks/v1/held_back.jsonl"),
        help="Path to the held-back jsonl (loaded only with --all-tiers)",
    )
    parser.add_argument(
        "--sealed", type=Path, default=Path("tasks/v1/sealed.jsonl"),
        help="Path to the sealed jsonl (loaded only with --all-tiers)",
    )
    parser.add_argument("--all-tiers", action="store_true",
                        help="Validate combined public+held_back+sealed set")
    parser.add_argument("--offline", action="store_true",
                        help="Skip gh-dependent gates (license + repo eligibility)")
    parser.add_argument("--read-only", action="store_true",
                        help="Do not populate tokenizer cache; fail on missing entries")
    parser.add_argument(
        "--report", type=Path, default=Path("tasks/v1/verification_report.md"),
        help="Output path for the markdown report",
    )
    args = parser.parse_args(argv)

    paths = [args.queries]
    tier_mode = "public-only"
    if args.all_tiers:
        paths.extend([args.held_back, args.sealed])
        tier_mode = "all-tiers"

    queries = _load_combined(paths)

    results: list[CheckResult] = [
        date_check.check(queries),
        license_check.check(queries, online=not args.offline),
        repo_eligibility_check.check(queries, online=not args.offline),
        fivegram_check.check(queries),
        per_repo_cap_check.check(queries),
        tier_count_check.check(queries, mode=tier_mode),
        tokenizer_cache_check.check(queries, read_only=args.read_only),
    ]

    report = _format_report(results, queries)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    for r in results:
        print(f"{r.gate}: {'PASS' if r.passed else 'FAIL'} — {r.detail}")
        if not r.passed:
            for e in r.errors:
                print(f"    {e}")

    all_pass = all(r.passed for r in results)
    print(f"\nReport written to: {args.report}")
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
