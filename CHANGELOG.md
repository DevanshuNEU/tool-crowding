# Changelog

All notable changes to tool-crowding are documented here. Format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed — pin `typer<0.26` to keep `CliRunner.isolated_filesystem` available (2026-05-26)

- Typer 0.26.0 (released 2026-05-26) replaced its `CliRunner` with a fresh `typer._click.testing.CliRunner` that no longer inherits from `click.testing.CliRunner`, so `isolated_filesystem()` is no longer a method. CI installed typer 0.26.0 transitively (pyproject had `typer>=0.12` with no upper bound) and 5 tests in `tests/test_cli.py` failed with `AttributeError: 'CliRunner' object has no attribute 'isolated_filesystem'`. Added an upper bound `typer>=0.12,<0.26` to unblock CI. Follow-up migration tracked in [#1](https://github.com/DevanshuNEU/tool-crowding/issues/1) (replace `runner.isolated_filesystem()` with pytest's `tmp_path` + `monkeypatch.chdir`).

### Fixed — `snapshot_server_descriptions` error classification (2026-05-26)

- `tcrun/snapshot.py::snapshot_server_descriptions` only caught `asyncio.TimeoutError` + `OSError` at the spawn site. When the MCP subprocess spawned successfully but died during `initialize()` (today's real-world git_mcp 404: npx exits non-zero → MCP client surfaces `McpError("Connection closed")` wrapped in `ExceptionGroup` from its anyio task group), the group escaped as an unhandled 9KB traceback instead of a clean `SnapshotError` — and `snapshot_all_descriptions`'s graceful-per-server-failure contract silently dropped because the bare `except Exception` it relies on doesn't match `ExceptionGroup`.
- Two new helpers in `snapshot.py`:
  - `_first_leaf_exception(eg)` walks a (possibly nested) `BaseExceptionGroup` and returns a representative leaf, preferring non-cancellation leaves (anyio cancels sibling tasks when one raises the real failure, so the cancellation is downstream noise).
  - `_await_classified(coro, *, pin_name, stage, timeout_s=None)` is the single classification chokepoint — catches `TimeoutError`, `McpError`, `OSError`, `BaseExceptionGroup`, and generic `Exception`, wraps each into `SnapshotError(f"{pin}: {stage}: ...")` with `raise from` preserving the original cause, and re-raises `asyncio.CancelledError` unchanged so structured-concurrency teardown still works.
- `snapshot_server_descriptions` now classifies all four await sites (`stdio_client` spawn, `ClientSession` open, `initialize`, `list_tools`) through the helper. Stage names — "failed to spawn subprocess", "MCP session open", "MCP initialize", "MCP list_tools" — appear verbatim in the SnapshotError message so the failure mode is identifiable from logs alone.
- `tcrun/servers.py` now also re-exports `McpError` from `mcp` (with a placeholder `class McpError(Exception)` in the mcp-not-installed branch so `except McpError` always resolves to a real class).
- 9 new tests in `tests/test_snapshot.py`: 3 direct tests of `_first_leaf_exception` (nested-group walk, prefer-real-over-cancellation, all-cancellation fallback), and 6 snapshot-level tests covering McpError-during-initialize, McpError-during-list_tools, ExceptionGroup-wrapping-McpError (the actual today's failure mode), generic-Exception-during-list_tools fallback, CancelledError propagation, and cancel-only-group propagation.

### Fixed — `_pip_freeze` bound to running interpreter (2026-05-26)

- `tcrun/env.py::_pip_freeze` invoked `pip freeze` via `$PATH`, which resolves to whichever `pip` happens to be first on the shell's PATH (homebrew/system) instead of the venv that's actually running `tcrun`. Same root cause poisoned both call sites: `EnvFingerprint.package_hash` (hashed into every `Trial.env`) and `environment.lock.pip_freeze` (content-hashed into `run_id` via `Config.PATH_FIELDS`). Surfaced when the first real `tcrun snapshot-env` invocation captured a 33-package homebrew env instead of the venv's 59-package tcrun environment. Now `[sys.executable, "-m", "pip", "freeze"]`, so the captured deps always belong to the interpreter that's running. Regression test in `tests/test_env.py` asserts the subprocess argv starts with `sys.executable`.

### Added — install-time artifact generators: `tcrun snapshot-env` + `tcrun snapshot-descriptions` (2026-05-26)

- `tcrun/snapshot.py`: deterministic generators for the two install-time artifacts that participate in `run_id` via `Config.PATH_FIELDS` (per `design/REPRODUCIBILITY.md §1`):
  - `write_env_lock(out, *, servers_yaml_path=None)` writes `environment.lock` with `{schema_version, os, python_version, harness_git_sha, pip_freeze[], docker_images{}}`. No `captured_at` field on purpose — re-running on an unchanged environment produces byte-identical output and keeps `run_id` stable. Docker digests are captured via `docker image inspect`; absent/un-pulled images are logged + omitted rather than halting (the lock file is bootstrap, not a runtime gate).
  - `snapshot_server_descriptions(pin)` opens a fresh MCP session (its own `AsyncExitStack` over `stdio_client` + `ClientSession`), calls `list_tools`, returns `{server_name, install, pin, tools[{name, description, inputSchema}]}` with tools sorted alphabetically. Doesn't reuse `ServerPoolManager._spawn_one` because that consumes the `list_tools` result for smoke verification and discards the tool definitions we need.
  - `update_descriptions_file(out, server_name, entry)` is the incremental merge primitive — load existing JSON (or fresh skeleton), upsert one server, sort servers alphabetically, atomic-write via tmp+rename. Lets `--server NAME` mode bootstrap `pool/descriptions.json` one server at a time.
  - `snapshot_all_descriptions(servers_yaml, out)` iterates `servers_pinned.yaml` with per-server graceful failure; returns `(final_descriptions, [(server, reason)])` so a single un-runnable server doesn't block the rest of the snapshot.
- `cli.py`: two new subcommands.
  - `tcrun snapshot-env [--out environment.lock] [--servers-pinned PATH]` — one-shot library install command. Re-run when Python deps or docker images change.
  - `tcrun snapshot-descriptions --config CFG (--server NAME | --all) [--out pool/descriptions.json] [--timeout SECONDS]` — `--server`/`--all` are mutually exclusive; missing both raises. `--all` exits non-zero if any server failed but still writes the partial file.
- `SPEC.md §8` CLI command listing extended to include the new `snapshot-*` subcommands plus the previously-undocumented `runid`/`reproduce`/`validate`.
- 27 new tests in `tests/test_snapshot.py` (library: env.lock determinism + docker capture happy/absent/sorted, tool serialization tolerance, pin identity ordering, single-server snapshot happy/empty/timeout/spawn-error, descriptions file create/merge/overwrite/atomic/corrupt-recovery, snapshot-all happy + partial failure; CLI: snapshot-env smoke, mutually-exclusive arg validation, single-server dispatch via patched `snapshot_server_descriptions`).

### Added — default Orchestrator factories: `tcrun run` dispatches trials end-to-end (2026-05-26)

- `tcrun/runner.py`: new wiring module sitting between `Orchestrator` and `AgentHarness`. Two factory builders + a thin bridge class:
  - `make_default_pool_factory(config)` returns the orchestrator's `pool_factory` callable: `(server_names) -> AsyncContextManager[dict[str, ServerSession]]`. One hermetic `ServerPoolManager` per group per SPEC.md §5 rule 4.
  - `make_default_agent_factory(config, *, env=None, anthropic_client=None, embedder=None, harness_version=None)` returns a closure satisfying the orchestrator's contract `(pool_sessions, embedder_spec) -> AgentRunner`. Run-scoped resources (endpoint pin, oracle SHA, env fingerprint, embedder client, harness version) are resolved once at factory-build time; never re-resolved per trial.
  - `AgentRunner` is the bridge: converts the orchestrator's `(cell, query)` call shape into a `TrialInputs` and delegates to `AgentHarness.run_trial`. Stateless beyond construction.
- `cli.py::run` and `cli.py::resume` now wire both default factories into the `Orchestrator`. `tcrun run --config configs/mve.yaml` dispatches trials end-to-end (previously bailed at first group with no factories).
- Loud-failure guarantees baked in:
  - `endpoints.json` missing the `cfg.model` row → `EndpointResolutionError` at factory-build time, not at first dispatch.
  - `tool_listing_strategy: retriever-on` with no buildable embedder (missing `OPENAI_API_KEY`, missing SDK extra) → raises at factory-build time, not at first trial.
  - `Query.difficulty_quartile` outside `{q1, q2, q3, q4}` → raises (no silent fallback to "medium").
- 17 new tests in `tests/test_runner.py` covering: endpoint resolution (happy + 3 failure modes), difficulty mapping, oracle version format, `AgentRunner` `TrialInputs` assembly, retriever-on embedder pre-build (happy + propagated failure), retriever-off embedder skip, pool-factory dict yield, end-to-end orchestrator dispatch with mocked harness, and the new orchestrator loud-fail.

### Changed

- `Orchestrator._run_group` no longer silently returns when `pool_factory` or `agent_factory` is `None`. It now raises `OrchestratorHalt` with a pointer to `tcrun.runner`. Production misconfigurations fail loudly instead of letting `tcrun run` exit "successfully" with zero trials. Enumeration / checkpoint tests are unaffected (they exercise the constructor without calling `.run()`).

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
