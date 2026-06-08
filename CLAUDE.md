# tool-crowding — Project Operating Manual

> Auto-loads when Claude works in this repo. The locked research design is `RESEARCH_DESIGN.md`. Read it before suggesting any change to scope, metric, or methodology.

## The locked thesis (one paragraph)

Real users install 10 to 20 MCP servers simultaneously. Existing benchmarks use a fixed pool. `tool-crowding` varies N (number of concurrently-installed servers) as a continuous independent variable and measures pass@1 degradation, marginal token cost, and per-server Marginal Performance Delta (MPD) on a held-constant code-retrieval task, with discrimination interference isolated from prompt-length capacity via a padded-N=1 control. Output: public reproducible harness + arXiv preprint + workshop submission.

## Status (as of v0.1.0-pre-pilot)

- **Methodology**: locked across 10 binding design docs in `design/`
- **Harness**: 12-module `tcrun` Python package + 326 passing pytest cases
- **Fake-tool corpus**: 199 entries shipped at `design/fake_tool_corpus.jsonl`
- **Server pool**: 18-server pool (5 chart-primaries + 13 distractors); 16 pinned in `harness/tcrun/servers_pinned.yaml` (Context7 + Sentry, both API-key-gated, pending)
- **Pilot**: 144 main trials + 30 retriever robustness + 50 RAG-MCP replication = 224 total, pre-registered
- **arXiv preprint**: Weeks 4-6 of the v1 sweep
- **Workshop submission**: Aug-Sep 2026 deadlines

See `CHANGELOG.md` for the version-by-version state.

## Hard rules

- NEVER start harness code without first reading the 11 paper-reading deep notes in `notes/`.
- NEVER run trials without a committed `design/PRE_REGISTRATION.md`.
- NEVER publish results without 7-day pre-disclosure to maintainers (Section 11 of `RESEARCH_DESIGN.md`).
- NEVER call this project `mcp-bench` (Accenture owns the name).
- NEVER skip the padded-N=1 control (it rules out long-prompt degradation as the explanation).
- COI disclosure: OCI is authored by the corresponding author. A leave-OCI-out sensitivity analysis is mandatory in the paper.
- Use `Marginal Performance Delta (MPD)`, never `Interference Score`. Causal-sounding terminology is banned.

## Kill criteria (re-check before any phase transition)

1. Flat curve: pass@1 differs by less than ±3pp across N ∈ {1, 5, 10}.
2. Pure context-overflow explanation (drop only at tokens > 180k on Sonnet 4.6's 200k window).
3. Pure long-prompt degradation (padded-N=1 within 5pp of unpadded-N=20).
4. Non-stable per-server MPD (Spearman ρ < 0.3 across re-runs).
5. Scoop (concurrent publication with the same scope).
6. Unfixable contamination.

If any kill criterion fires: stop, document, pivot or shelve. Do not push through.

## Where things live

- `RESEARCH_DESIGN.md` — locked 11-section canonical design
- `design/FOUNDATION.md` — binding construct + ABC checklist
- `design/PRE_REGISTRATION.md` — four scenario abstracts pre-locked before data
- `design/PADDING_STRATEGY.md` — padded-N=1 filler-selection algorithm
- `design/QUERY_SET_HYGIENE.md` — six layered contamination defenses
- `design/REPRODUCIBILITY.md` — 7-artifact content-addressed identity chain
- `design/SERVER_POOL.md` — 18-server pool + reachability + version pinning
- `design/MODEL_VERSIONS.md` — frontier-panel pinning
- `design/ADVERSARIAL_AUDIT.md` — six attack vectors on the benchmark itself
- `design/CHART_LAYOUT.md` — the headline figure specification
- `design/PILOT_V0.md` — the 224-trial pilot scope
- `design/fake_tool_corpus.jsonl` — 199 neutral-tool entries for padded-N=1
- `harness/` — `tcrun` Python package + tests + engineering spec
- `notes/` — 11 paper-reading deep notes
- `research/` — 5 landscape audits

## Related

- `[[RESEARCH_DESIGN]]` — canonical 11-section design
- `[[design/FOUNDATION]]` — binding construct + kill criteria
- `[[design/PRE_REGISTRATION]]` — four scenario abstracts pre-locked
- `[[design/SERVER_POOL]]` — server pool spec + version pinning
- `[[harness/SPEC]]` — engineering spec
