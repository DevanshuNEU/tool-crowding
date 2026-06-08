"""Gate 2: source repo carries a verified GPL-family license.

Per QUERY_SET_HYGIENE.md §9 step 2 + §5:
    - Public + held-back tier source_repo licenses must be in {GPL-2.0, GPL-3.0, LGPL, AGPL}.
    - Sealed tier is exempt (source_license="proprietary").
    - Three-source verification per §5: LICENSE file + manifest + header.
      Disagreement among the three = reject (license ambiguity = red flag).

For v1 the *primary* signal is GitHub's detected license via `gh api repos/{r}/license`.
A secondary signal is the `source_license` field in the query record (set during
mining). If GitHub's detection disagrees with the field's value, the check fails.

The third signal (per-file LICENSE header inside the function body) is a manual
spot-check at mining time, not automated here, to keep the check side-effect-free
and offline-capable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

from preflight import CheckResult
from preflight._common import GPL_FAMILY

if TYPE_CHECKING:
    from tcrun.tasks import Query


# Normalize GitHub's spdx_id values to our canonical set.
_GITHUB_SPDX_NORMALIZE: dict[str, str] = {
    "GPL-2.0": "GPL-2.0",
    "GPL-2.0-only": "GPL-2.0",
    "GPL-2.0-or-later": "GPL-2.0",
    "GPL-3.0": "GPL-3.0",
    "GPL-3.0-only": "GPL-3.0",
    "GPL-3.0-or-later": "GPL-3.0",
    "LGPL-2.1": "LGPL",
    "LGPL-2.1-only": "LGPL",
    "LGPL-2.1-or-later": "LGPL",
    "LGPL-3.0": "LGPL",
    "LGPL-3.0-only": "LGPL",
    "LGPL-3.0-or-later": "LGPL",
    "AGPL-3.0": "AGPL",
    "AGPL-3.0-only": "AGPL",
    "AGPL-3.0-or-later": "AGPL",
}


def _gh_repo_license(source_repo: str) -> str | None:
    """Return canonical GPL-family name from GitHub's detection, or None.

    Returns None on any failure (rate limit, missing gh, repo not found). The
    caller decides whether that's a hard error.
    """
    if shutil.which("gh") is None:
        return None
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{source_repo}/license"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        spdx = (data.get("license") or {}).get("spdx_id")
        if not spdx:
            return None
        return _GITHUB_SPDX_NORMALIZE.get(spdx)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def check(queries: list["Query"], *, online: bool = True) -> CheckResult:
    """Validate license per query.

    Args:
        queries: list of Query records
        online: if True, cross-check against GitHub's detected license via gh.
                Set False in tests / offline CI to skip the network call.
    """
    errors: list[str] = []
    checked_online: dict[str, str | None] = {}
    for q in queries:
        if q.tier == "sealed":
            if q.source_license != "proprietary":
                errors.append(
                    f"{q.query_id}: sealed tier must have source_license='proprietary', "
                    f"got {q.source_license!r}"
                )
            continue
        if q.source_license not in GPL_FAMILY:
            errors.append(
                f"{q.query_id}: source_license={q.source_license!r} not in GPL family "
                f"{sorted(GPL_FAMILY)}"
            )
            continue
        if online:
            if q.source_repo not in checked_online:
                checked_online[q.source_repo] = _gh_repo_license(q.source_repo)
            gh_license = checked_online[q.source_repo]
            if gh_license is None:
                errors.append(
                    f"{q.query_id}: GitHub license detection failed for "
                    f"{q.source_repo} (rate limit or non-GPL upstream); "
                    f"three-source verification incomplete"
                )
            elif gh_license != q.source_license:
                errors.append(
                    f"{q.query_id}: license mismatch on {q.source_repo}: "
                    f"manifest says {q.source_license}, GitHub detects {gh_license}"
                )
    detail = (
        f"{len(queries) - len(errors)}/{len(queries)} queries pass license verification "
        f"(online={online})"
    )
    return CheckResult(gate="license_check", passed=not errors, detail=detail, errors=errors)


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
