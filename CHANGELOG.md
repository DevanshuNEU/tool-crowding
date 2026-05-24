# Changelog

All notable changes to tool-crowding are documented here. Format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Pending for v0.2.0-pilot (planned 2026-05-27):

- `harness/tasks/v1/queries.jsonl` populated with the three-tier query set per `design/QUERY_SET_HYGIENE.md` (30 public + 10 held-back + 10 sealed)
- 144-trial pre-registered pilot results in `results/<run_id>/`
- Headline chart with paired-bootstrap confidence intervals (matplotlib code per `design/CHART_LAYOUT.md`)
- arXiv preprint draft in a separate paper repo
- GitHub MCP Docker image digest pinned in `servers_pinned.yaml` (Docker daemon 500 error during initial pull on 2026-05-23)
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
