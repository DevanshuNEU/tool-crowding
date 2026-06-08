"""Gate 3: source repo is not banned AND star count is within ceiling.

Per QUERY_SET_HYGIENE.md §9 step 3 + §3:
    - source_repo not in banned-repos list (Defense 2)
    - GitHub stars < 10_000 (presumed-in-training threshold)
    - PyPI downloads < 1M/month (when applicable; best-effort)

Sealed tier is exempt (proprietary repo is not on GitHub).

The star count is fetched via `gh api repos/{repo}` (cached per repo). PyPI
download checks are best-effort: only run when the repo declares a `pypi_name`
metadata field in the query record (not part of the v1 Query schema; deferred).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import STAR_CEILING, is_banned_repo

if TYPE_CHECKING:
    from tcrun.tasks import Query


def _gh_repo_stars(source_repo: str) -> int | None:
    """Return repo's stargazer count, or None on any gh failure."""
    if shutil.which("gh") is None:
        return None
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{source_repo}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        return int(data.get("stargazers_count", 0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return None


def check(queries: list["Query"], *, online: bool = True) -> CheckResult:
    errors: list[str] = []
    star_cache: dict[str, int | None] = {}
    for q in queries:
        if q.tier == "sealed":
            continue  # proprietary repos exempt from public-eligibility gate
        if is_banned_repo(q.source_repo):
            errors.append(
                f"{q.query_id}: source_repo {q.source_repo!r} is in §3 banned-repos list"
            )
            continue
        if online:
            if q.source_repo not in star_cache:
                star_cache[q.source_repo] = _gh_repo_stars(q.source_repo)
            stars = star_cache[q.source_repo]
            if stars is None:
                errors.append(
                    f"{q.query_id}: gh failed to fetch stars for {q.source_repo}; "
                    f"cannot verify <{STAR_CEILING}-stars eligibility"
                )
            elif stars >= STAR_CEILING:
                errors.append(
                    f"{q.query_id}: {q.source_repo} has {stars} stars (>= {STAR_CEILING}); "
                    f"presumed in training corpora per §3"
                )
    detail = (
        f"{len(queries) - len(errors)}/{len(queries)} queries pass repo eligibility "
        f"(online={online})"
    )
    return CheckResult(
        gate="repo_eligibility_check", passed=not errors, detail=detail, errors=errors
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tcrun.tasks import load_tasks

    path = sys.argv[1] if len(sys.argv) > 1 else "tasks/v1/queries.jsonl"
    online = "--offline" not in sys.argv
    result = check(load_tasks(path), online=online)
    print(result.gate, "PASS" if result.passed else "FAIL", "-", result.detail)
    for e in result.errors:
        print(" ", e)
    sys.exit(0 if result.passed else 1)
