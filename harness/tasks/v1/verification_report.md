# tasks/v1 verification report

- Generated: 2026-05-25 17:37 UTC
- Queries loaded: 21
- Gates: 6/7 pass — **FAIL**

## Per-gate status

| Gate | Status | Detail |
|---|---|---|
| date_check | PASS | 21/21 queries pass date threshold |
| license_check | PASS | 21/21 queries pass license verification (online=True) |
| repo_eligibility_check | PASS | 21/21 queries pass repo eligibility (online=True) |
| fivegram_check | PASS | 21/21 queries pass 5-gram check (threshold=2) |
| per_repo_cap_check | PASS | public: 5 repos, max 5/repo (cap=10) |
| tier_count_check | FAIL | counts: {'public': 21} mode=public-only |
| tokenizer_cache_check | PASS | 21/21 queries have valid o200k_base token counts (cache=tasks/v1/tokenizer_cache.json, populated +0) |

## Failures

### tier_count_check

- tier=public: expected 30, got 21

## Spec

Each gate corresponds to a numbered step in `design/QUERY_SET_HYGIENE.md §9` (verification workflow). All 7 must pass before `tasks/v1/queries.jsonl` is committed for launch.
