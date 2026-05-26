# Changelog

All notable changes to tool-crowding are documented here. Format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — embedder layer + retriever-ON code path (2026-05-25)

- `tcrun/embedder.py`: provider-agnostic `Embedder` Protocol + 3 provider classes (`OpenAIEmbedder`, `VoyageEmbedder`, `BGEM3Embedder`) with lazy SDK imports so the OpenAI-only install does not pull PyTorch. Factory `make_embedder(spec)` accepts pin dict or path; pin's `model`/`dimension`/`snapshot` drive runtime behavior (pin is the single source of truth, not just run_id metadata).
- `models/embedder.json` (OpenAI primary), `models/embedder.voyage.json`, `models/embedder.bge-m3.json`: per-provider pin files; content-hashed into run_id as the 8th artifact per `design/REPRODUCIBILITY.md §1`.
- `models/endpoints.json`: previously missing despite being a Config path-typed field; populated with the Sonnet 4.6 endpoint pin (Anthropic).
- `Config.embedder: Path` (8th `PATH_FIELDS` entry; mandatory, no Python-side default). `Config.retriever_top_k: int = 5` (value-hashed; varying it produces a new run_id).
- `EMBEDDER_ALIASES` dict + `_resolve_embedder_env`: `TC_EMBEDDER=voyage|bge|openai|<literal-path>` overrides the YAML's `embedder:` field at `load_config` time. Resolved Config hashes into run_id so env overrides remain reproducibility-honest. Typo'd alias values that don't look like paths emit a stderr warning listing the known aliases. Override fires emit a stderr notification so a stale shell export doesn't silently change run_id.
- `TrialInputs.embedder_spec` (pin dict for trial-row attribution + lazy embedder construction), `TrialInputs.retriever_top_k` (per-trial override), `AgentHarness(embedder=...)` (reusable client across trials).
- Retriever-ON branch in `AgentHarness._build_tools_manifest`: embeds query + tool descriptions in one batched call, ranks by cosine, keeps top-k per `inputs.retriever_top_k`. Mutually exclusive with `is_padded_n1` (hard `ValueError`); empty manifest raises `RuntimeError` (no silent skip).
- Orchestrator agent_factory contract: `agent_factory(pool, embedder_spec)` is a hard 2-arg signature. Concrete factories MUST propagate `embedder_spec` into `TrialInputs.embedder_spec` so trial rows match the run_id's h_embedder pin.
- `_gate_embedder` (gate 7 on `PreflightGate`): verifies pin parses, provider is canonical (`openai`/`voyageai`/`bge`), dimension is positive int, snapshot is not a `TBD-` placeholder. Optional `embedder_require_api_key=True` checks the provider's env var (`OPENAI_API_KEY` / `VOYAGE_API_KEY`; BGE is local).
- `python-dotenv>=1.0` base dependency + `_load_env()` in `cli.py::main()`: auto-loads `harness/.env` (path anchored to harness package root, not CWD) for `tcrun` invocations from any directory.
- Optional dependency extras: `embedders-openai`, `embedders-voyage`, `embedders-bge`, `embedders-all`.

### Changed

- **Schema bump v1.1 → v1.2.** Four embedder fields added to `Trial` with v1-primary defaults (`embedder_provider`, `embedder_model`, `embedder_snapshot`, `embedder_dimension`). `Trial.tool_listing_strategy` literal narrowed from `Literal["full", "rag-mcp", "mcp-zero", "oracle-filter"]` to `Literal["full", "retriever-on", "oracle-filter"]` to match `Config.tool_listing_strategy`. Reader chains migrations `v1.0 → v1.1 → v1.2`; legacy `rag-mcp`/`mcp-zero` values are normalized forward to `retriever-on` in the v1.1→v1.2 step. SPEC.md §4 updated.
- `Config.embedder` is mandatory (no Python-side default); forgetting it fails loud at construction, matching the other 7 path-typed fields.

### Fixed

- `tool_listing_strategy` literal mismatch between `Config` (`"retriever-on"`) and `Trial` (`"rag-mcp"`/`"mcp-zero"`) — latent bug that would have failed Pydantic validation the first time a non-`"full"` value was written. Now aligned.
- `models/endpoints.json` previously absent, blocking `compute_run_id` from succeeding for any config that referenced it (which mve.yaml did). Populated.

### Pending for v0.2.0-pilot (planned 2026-05-27)

- `harness/tasks/v1/queries.jsonl` populated with the three-tier query set per `design/QUERY_SET_HYGIENE.md` (30 public + 10 held-back; sealed tier dropped 2026-05-25)
- 144-trial pre-registered pilot results in `results/<run_id>/`
- Headline chart with paired-bootstrap confidence intervals (matplotlib code per `design/CHART_LAYOUT.md`)
- arXiv preprint draft in a separate paper repo
- GitHub MCP Docker image digest pinned in `servers_pinned.yaml` (digest captured 2026-05-25; pinning pending)
- BGE-M3 safetensors SHA-256 implementation (pin currently has `TBD-` placeholder; preflight gate blocks BGE trials until real hash lands)
- Orchestrator default agent_factory connecting AgentHarness end-to-end (currently factories are test-only; CLI `tcrun run` bails without dispatch)
- External-party reproducibility receipt for one fixture trial

## [0.1.0-pre-pilot] - 2026-05-23

Initial drop. Methodology locked, harness shipped, pilot pending.

### Added

- 10 binding design docs in `design/`: FOUNDATION, PRE_REGISTRATION, PADDING_STRATEGY, QUERY_SET_HYGIENE, REPRODUCIBILITY, SERVER_POOL, MODEL_VERSIONS, ADVERSARIAL_AUDIT, CHART_LAYOUT, PILOT_V0
- Canonical 11-section design at `RESEARCH_DESIGN.md` including a reviewer-2 dialectic and three pre-committed changes baked back into the design
- 12-module `tcrun` Python package (~1,800 LOC): `config`, `seed`, `results`, `env`, `retry`, `tasks`, `padding`, `servers`, `agent`, `orchestrator`, `preflight`, `cli`
- 116 passing pytest cases across 9 test files
- Content-addressed `run_id` via the 7-artifact identity chain (per `design/REPRODUCIBILITY.md`)
- Pre-registered scenario abstracts (4 outcomes, locked priors: clean win 15%, methodology contribution 35%, frontier robust 25%, mixed by model class 25%)
- Padded-N=1 falsification arm with deterministic filler selection and ±10% length-match tolerance
- Retriever ON/OFF as a second experimental axis (motivated by LiveMCPBench's 50% retrieval-side-error finding)
- RAG-MCP external-validity replication cell at N ∈ {10, 100, 1000} on Sonnet 4.6 + GPT-5-class
- 199-entry fake-tool corpus across 22 neutral domains in `design/fake_tool_corpus.jsonl` with deterministic generator at `harness/pool/gen_fake_corpus.py`
- 5 hand-curated oracle smoke tests (5/5 pass) covering symbol-match + 50% token-overlap with edge cases
- Engineering spec at `harness/SPEC.md` with a DDIA principle-transfer audit naming the 9 principles that DO NOT TRANSFER to a single-author research harness
- 11 paper-reading deep notes in `notes/`: RAG-MCP, LongFuncEval, MCPVerse, LiveMCPBench, ABC, CoIR, CodeRAG-Bench, SWE-Bench Illusion, SWE-Bench Pro, MCP-Universe, Silent Judge
- 5 landscape audits in `research/`: function-calling, MCP benchmarks, production engineering, RAG distractor, gap diagnosis
- 13 of 15 servers pinned: OCI + Aider git SHAs, postgres/brave/slack tarball SHA-256s, 8 npm/PyPI from prior install. GitHub MCP Docker digest pending.
- Apache 2.0 license
- Apache 2.0 patent grant + explicit conflict-of-interest disclosure (OCI is authored by the corresponding author; leave-OCI-out sensitivity analysis is mandatory in v1 paper)

### Pre-locked (binding; will not change after pilot data lands)

- Six falsification conditions F1-F6 per `design/FOUNDATION.md` §3
- 5pp threshold for the F1 padded-N=1 capacity test (calibrated against the 13.9% lower bound of arXiv 2510.05381's length-only degradation range)
- 0.5 Spearman rho threshold for per-server MPD stability (F2)
- 0.2 Pearson r threshold for description-similarity correlation (F3)
- Four scenario priors and the locked decision rule per scenario
- Padded-N=1 as a first-class condition, not a threats-to-validity afterthought
- Marginal Performance Delta (MPD) as the per-server metric name; causal-sounding terminology banned

### Acknowledged

- The "first to vary N" framing was killed 2026-05-21 after a landscape sweep surfaced three published papers (RAG-MCP, LongFuncEval, MCPVerse) that varied N as an independent variable. The surviving claim is the 6-condition intersection documented in `RESEARCH_DESIGN.md` §1.
- The name `mcp-bench` is taken by Accenture (arXiv 2508.20453); this project will not adopt it.

### Conflict of interest

OpenCodeIntel (OCI) is one of the five primary code-retrieval servers in the pool and is authored by the corresponding author. Disclosed in `RESEARCH_DESIGN.md` §11. Leave-OCI-out sensitivity analysis is mandatory in v1 paper.
