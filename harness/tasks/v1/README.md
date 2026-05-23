# tasks/v1/queries.jsonl — provenance

50-query v1 set across three tiers, per `../../../design/QUERY_SET_HYGIENE.md`.

## Tiers

| Tier | Count | Date band | License | Source | Released? |
|---|---|---|---|---|---|
| Public | 30 | strict-after 2026-01-31 | GPL family | Low-traffic GPL Python repos | Yes (Mon 2026-05-25 launch) |
| Held-back | 10 | strict-after 2026-04-30 | GPL family | Low-traffic GPL Python repos | No (.gitignored; released at v2 or 12 months from launch, whichever is later) |
| Sealed (OCI) | 10 | N/A | Proprietary | OCI private codebase | No (methodology disclosed; data sealed) |

## Provenance

Mining procedure per `../../../design/QUERY_SET_HYGIENE.md §8`:

1. Enumerate candidate source repos satisfying Defense 2 (low-traffic, < 10k stars, < 1M PyPI dl/month) + Defense 4 (GPL family license)
2. Pull issues + PRs opened on or after the tier's date threshold
3. Extract `(natural-language description → ground-truth function)` pairs from merged PRs
4. Score each candidate: difficulty (snippet-length quartile), retrieval-friendliness, license verification, 5-gram check
5. Accept queries that pass all 6 defenses (date + repo eligibility + license + 5-gram + per-repo cap + tier-count)
6. Sort into tiers by date band

Per QUERY_SET_HYGIENE.md Defense 5, no source repo contributes more than 10 public-tier queries or 7 held-back-tier queries.

## Verification report

After mining, `verification_report.md` records:

- Source repos (with license sources, star counts, dl counts)
- Date-of-publication per query
- 5-gram hit log per query (cached GitHub Code Search + Google Custom Search)
- Per-repo query count
- Tier counts (30 / 10 / 10)
- Tokenizer used for 5-gram check

The verification report participates in `h_queries` content hash; mutating it changes `run_id` per REPRODUCIBILITY.md §1.

## Format

JSONL, one query per line. Schema (Pydantic, implemented in `../../tcrun/tasks.py`):

```python
class Query(BaseModel):
    query_id: str                    # "v1-pub-001", "v1-held-001", "v1-sealed-001"
    tier: Literal["public", "held_back", "sealed"]
    text: str                        # natural-language description of what to retrieve
    ground_truth_target: str         # function name / symbol the answer must contain
    ground_truth_code: str           # canonical code snippet (used by the oracle)
    source_repo: str                 # "<owner>/<name>"
    source_publication_date: str     # ISO-8601 date, strict-after the tier threshold
    source_license: Literal["GPL-2.0", "GPL-3.0", "LGPL", "AGPL", "proprietary"]
    difficulty_quartile: Literal["q1", "q2", "q3", "q4"]
    primary_server: str              # which code-retrieval MCP is the intended target
    fivegram_audit: list[dict]       # per high-entropy 5-gram: {"ngram": str, "github_hits": int, "web_hits": int}
```

## Status

Empty / placeholder as of 2026-05-22 Fri PM. Mining begins Sat 2026-05-23 AM.

For the Sat pilot, a 3-row pilot subset is mined first per `../../design/PILOT_V0.md`.
