---
title: Candidate source repos for tasks/v1/queries.jsonl mining
status: v1 candidate shortlist (locked 2026-05-24 Sun PM)
binds: QUERY_SET_HYGIENE.md §3 (Defense 2 — low-traffic repo restriction) + §5 (Defense 4 — GPL license filter)
related_docs: design/QUERY_SET_HYGIENE.md, harness/tasks/v1/README.md, design/MODEL_VERSIONS.md
---

# Candidate source repos for v1 mining

7-repo shortlist verified against QUERY_SET_HYGIENE.md §3 + §5 defenses, plus a live `gh pr list` activity check on 2026-05-24. None of the 7 appears in the §3 banned-repos list; all are <10k stars, GPL-family licensed, actively maintained, with confirmed post-2026-02-01 merged-PR activity.

## Shortlist

| Repo | License | Stars | PRs merged ≥2026-02-01 (public-tier eligible) | PRs merged ≥2026-05-01 (held-back eligible) | Notes |
|---|---|---|---|---|---|
| `pylint-dev/pylint` | GPL-2.0 | 5,684 | 120 | 35 | Python linter; function-level changes are the norm. Strong for both tiers. |
| `buildbot/buildbot` | GPL-2.0 | 5,449 | 108 | 0 | Build automation; **public-tier only** (no held-back activity in post-2026-04-30 window). |
| `saulpw/visidata` | GPL-3.0 | 9,102 | 80 | 19 | TUI data tool; clean Python; many function-level fixes. |
| `archlinux/archinstall` | GPL-3.0 | 8,234 | 200 | 32 | Installer; very active. Highest absolute volume. |
| `pymupdf/PyMuPDF` | AGPL-3.0 | 9,790 | 45 | 4 | PDF library. Some changes are C-binding plumbing (skip during mining); the Python-level work is mineable. |
| `OctoPrint/OctoPrint` | AGPL-3.0 | 8,991 | 138 | 16 | 3D printer host; clean Python; active. |
| `psycopg/psycopg` | LGPL-3.0 | 2,396 | 15 | 5 | Postgres driver; lower volume but high-quality code. |

## Tier-mining plan

**Public tier (30 queries, post-2026-01-31, ≤10/repo):**
- pylint-dev/pylint: ≤10
- buildbot/buildbot: ≤10
- saulpw/visidata: ≤10
- archlinux/archinstall: ≤10
- pymupdf/PyMuPDF: ≤10 (skip C-binding plumbing PRs)
- OctoPrint/OctoPrint: ≤10
- psycopg/psycopg: ≤10
- 7 repos × ≤10 cap = 70 query ceiling; aim for ~4-5 per repo to keep diversity high.

**Held-back tier (10 queries, post-2026-04-30, ≤7/repo):**
- pylint-dev/pylint: ≤7
- saulpw/visidata: ≤7
- archlinux/archinstall: ≤7
- OctoPrint/OctoPrint: ≤7
- psycopg/psycopg: ≤7 (marginal; only 5 candidate PRs to choose from)
- 5 repos × ≤7 cap = 35 query ceiling. **buildbot/buildbot is NOT eligible** for held-back (0 activity in window).

**Sealed tier (10 queries):** OCI proprietary repo (see task #6, separate procedure).

## Defenses passed

- **§3 Banned-repos list:** none of the 7 names appear in {numpy, scipy, pytorch, pandas, celery, aiohttp, jupyter, jupyterlab, requests, flask, django, tensorflow, scikit-learn, matplotlib, seaborn}.
- **§3 Star ceiling:** all 7 are <10,000 stars (highest is pymupdf/PyMuPDF at 9,790).
- **§3 Active maintenance:** all 7 had merged PRs in the post-2026-02-01 window (lowest is psycopg/psycopg at 15; highest archlinux/archinstall at 200).
- **§5 License family:** all 7 are GPL-2.0 / GPL-3.0 / LGPL-3.0 / AGPL-3.0 per GitHub's detected license metadata.
- **PyPI dl/month (§3 secondary):** not verified per-repo; treated as best-effort, deferred to mining-time spot-check if any candidate is unexpectedly high-traffic.

## Enumeration commands (reproducibility)

```bash
# Top-starred GPL-3.0 Python repos under 10k stars
gh search repos --language python --license gpl-3.0 --stars "500..10000" \
  --sort stars --limit 25 --json fullName,stargazersCount,license,pushedAt,isArchived

# Same for GPL-2.0, AGPL-3.0, LGPL-3.0 (separate calls).

# Per-repo activity check
gh pr list --repo <owner>/<name> --state merged \
  --search "merged:>=2026-02-01" --limit 200 --json number
```

Re-run before mining if more than 7 days have passed since this lock.
