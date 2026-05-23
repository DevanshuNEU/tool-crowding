# tool-crowding harness

Single-author research harness for measuring multi-MCP discrimination interference as a function of N (number of concurrently-installed MCP servers). Public launch: Mon 2026-05-25.

> **Engineering spec (binding):** `SPEC.md`
> **Research design:** `../RESEARCH_DESIGN.md`
> **Methodology foundation:** `../design/FOUNDATION.md`
> **Reproducibility contract:** `../design/REPRODUCIBILITY.md`
> **Padded-N=1 padding strategy:** `../design/PADDING_STRATEGY.md`
> **Query set hygiene:** `../design/QUERY_SET_HYGIENE.md`

## Status

Skeleton scaffolded 2026-05-22 Fri PM. Implementation begins Sat 2026-05-23 AM. Pilot runs Sat 9am-3pm per `../design/PILOT_V0.md`. Public launch Mon 2026-05-25.

## Layout

```
harness/
├── SPEC.md                    Engineering spec (locked v1.2)
├── README.md                  this file
├── pyproject.toml             Python package + deps
├── .gitignore
├── tcrun/                     the Python package
│   ├── __init__.py
│   ├── cli.py                 CLI entry point (stub)
│   ├── config.py              Pydantic Config + run_id derivation (v1.2 Section 8 Identity rule — IMPLEMENTED)
│   ├── seed.py                cell_seed mechanism (REPRODUCIBILITY.md §2 — IMPLEMENTED)
│   ├── preflight.py           run_id verification gate (stub)
│   ├── padding.py             padded-N=1 filler selection (stub)
│   ├── orchestrator.py        cell loop + resume (stub)
│   ├── agent.py               Anthropic + MCP loop (stub)
│   ├── results.py             Trial schema + JSONL writer (stub)
│   ├── servers.py             ServerPoolManager (stub)
│   ├── tasks.py               TaskLoader (stub)
│   ├── retry.py               backoff helpers (stub)
│   ├── env.py                 environment fingerprint (stub)
│   ├── servers_pinned.yaml    15-server pool pinning (TBD SHAs at install)
│   └── oracles/
│       ├── __init__.py
│       └── pass_v1.py         pass criterion (stub)
├── configs/
│   └── mve.yaml               the 2-week MVE config
├── tasks/
│   └── v1/
│       ├── README.md          query set provenance
│       └── queries.jsonl      50 queries (empty until Sat mining; 3-row pilot subset first)
├── pool/
│   └── descriptions.json      captured tool descriptions + schemas (filled at server install)
├── models/
│   └── endpoints.json         model API endpoint pinning
├── results/                   gitignored; per-run output
└── analysis/
    ├── README.md
    └── readers/
        └── v1.py              schema v1.* reader (stub)
```

## Quick start

```bash
# Install (uv recommended; pip works too)
cd harness
uv venv
source .venv/bin/activate
uv pip install -e .

# Validate config without API calls
tcrun validate --config configs/mve.yaml

# Compute run_id for a config without API calls
tcrun runid --config configs/mve.yaml

# Run the MVE
tcrun --config configs/mve.yaml

# Resume a crashed run
tcrun resume <run_id>
```

## Reproducibility commands

```bash
# Verify all 7 artifact hashes match the committed run_id
tcrun verify <run_id>

# Single-trial replay (REPRODUCIBILITY.md §4.1; target ≥ 99% replication rate)
tcrun reproduce <trial_id>

# Headline N-curve replay (full sweep; target: 24 hr compute, < $200 API)
tcrun reproduce-headline <run_id>
```

See `../design/REPRODUCIBILITY.md §4` for the three verification targets and §8 for the implementation gates.

## What's NOT in this skeleton (Sat AM work)

1. **Python implementations** of `cli.py`, `orchestrator.py`, `agent.py`, `results.py`, `servers.py`, `tasks.py`, `retry.py`, `env.py`, `preflight.py`, `padding.py`, `oracles/pass_v1.py`. They are stub modules with docstrings pointing at the binding spec sections. Implement per `SPEC.md §3` per-component contracts.
2. **Server installs**: each entry in `tcrun/servers_pinned.yaml` has `git_sha: TBD` or `npm_version: TBD`. Run `npx <package>` or `git clone <repo>` for each, capture SHAs, fill in.
3. **Fake-tool corpus**: `../design/fake_tool_corpus.jsonl` is TBD (method A hand-curated or method B LLM-generated per `PADDING_STRATEGY.md §3`).
4. **Query set**: `tasks/v1/queries.jsonl` is empty. Mine per `../design/QUERY_SET_HYGIENE.md §8` for the 3-row pilot subset first; full 50-query set after pilot is green.
5. **Tool descriptions + schemas**: `pool/descriptions.json` is captured at server install (per server, per tool: name + description + input_schema verbatim).
6. **Endpoints pin**: `models/endpoints.json` records each model's API URL, snapshot id, temperature, max_tokens, system-prefix template, nonce-policy.
7. **Environment lock**: `environment.lock` is generated from `uv pip freeze` + Docker image SHA + OS info.

These 7 artifacts feed `run_id` per `../design/REPRODUCIBILITY.md §1`.

## Implementation order (Sat AM, suggested)

1. **`tcrun/config.py` validation pass.** Already implemented; verify it loads `configs/mve.yaml` cleanly. Implements v1.2 Section 8 Identity rule.
2. **`tcrun/seed.py` validation pass.** Already implemented; verify `cell_seed()` is deterministic.
3. **`pool/descriptions.json`**: write a one-off script that connects to each MCP server, dumps tool list + schemas, persists. Captures the artifact that participates in `run_id`.
4. **`tcrun/tasks.py`**: TaskLoader for `tasks/v1/queries.jsonl`.
5. **`tcrun/servers.py`**: ServerPoolManager. Install + health-check + teardown per cell.
6. **`tcrun/results.py`**: Pydantic Trial schema (incl. v1.1 padded-N=1 fields) + JSONL writer.
7. **`tcrun/agent.py`**: Anthropic API + MCP loop. Per-trial nonce (SPEC.md §5 rule 4 mandatory).
8. **`tcrun/orchestrator.py`**: cell loop + resume logic.
9. **`tcrun/oracles/pass_v1.py`**: symbol match + 50% token overlap per `RESEARCH_DESIGN.md §4`.
10. **`tcrun/preflight.py`**: verify all 7 hashes, abort on mismatch.
11. **`tcrun/padding.py`**: padded-N=1 filler selection per `PADDING_STRATEGY.md §4`.
12. **`tcrun/cli.py`**: Click CLI tying it all together.

SPEC.md §11 estimates ~1,500 LOC total. Cutting 100 LOC by merging `retry.py` + `env.py` into a `utils.py` gets to spec.

## Status of binding docs (as of 2026-05-22 Fri PM)

| Doc | Status |
|---|---|
| `../RESEARCH_DESIGN.md` | Locked Day 1 + revised Fri AM (§1 novelty) + revised Fri PM (§3 baselines + retriever axis + RAG-MCP cell + CoIR override) |
| `SPEC.md` | v1.2 (Fri AM `run_id` artifact-chain + Trial schema padded-N=1 fields) |
| `../design/FOUNDATION.md` | Binding methodology; SAT-D for 16/30 ABC items + 8/10 TC items |
| `../design/REPRODUCIBILITY.md` | v1 (Fri AM) |
| `../design/PADDING_STRATEGY.md` | v1 (Fri AM) |
| `../design/QUERY_SET_HYGIENE.md` | v1 (Fri AM) |
| `../design/PILOT_V0.md` | Locked Thu PM + padded pointer updated Fri AM |
| `../design/SERVER_POOL.md` | Locked Day 1; SHA pinning TBD at install |
