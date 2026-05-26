# Changelog

All notable changes to tool-crowding are documented here. Format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — DeepWiki MCP wiring: hosted-HTTP transport + 3-primary `mve.yaml` (2026-05-26)

- Closes the deepwiki wiring sprint open-looped in the prior CHANGELOG entry. `tcrun/servers.py` now supports a fourth install type, `hosted-http`, for MCP servers that speak Streamable HTTP (DeepWiki is hosted by Cognition Labs at `https://mcp.deepwiki.com/mcp`; no auth; not addressable via stdio or docker). `_spawn_one` bifurcates by install type: stdio-class installs go through `stdio_client(params)` as before; hosted-http installs go through `streamablehttp_client(url)` (already shipped in the `mcp` Python SDK; unpacks a 3-tuple `(read, write, get_session_id)` instead of the stdio 2-tuple). New module-level constant `HOSTED_HTTP_BUNDLE_FILES` mirrors the snapshot manifest captured by `server-pool/_capture_deepwiki_snapshot.py`. New helpers `hosted_http_params_for(pin)` (mirror of `stdio_params_for`), `compute_snapshot_sha256(snapshot_dir)`, and `verify_snapshot_integrity(pin, harness_root)` (REPRODUCIBILITY.md §5: snapshot drift halts the run; the integrity check fires inside `_spawn_one` before any network contact).
- `PinnedServer` gains 3 fields: `url`, `snapshot_path`, `snapshot_sha256`. `verify_pins` gains a fourth branch requiring all three for `install: hosted-http`. `ServerPoolManager.__init__` gains an optional `harness_root` parameter (defaults to `yaml_path.parent.parent`; tests pass `tmp_path` explicitly) so the snapshot integrity check can resolve `snapshot_path` relative to a known base.
- `tcrun/servers_pinned.yaml`: new `deepwiki` row in `primary_servers` between `github_mcp` and `git_mcp` (mirrors the chart-primary order locked in `design/CHART_LAYOUT.md §54`). Pin metadata: `url: https://mcp.deepwiki.com/mcp`, `snapshot_path: server-pool/deepwiki-snapshot-2026-05-26`, `snapshot_sha256: sha256:ce939ade8c67f9c34cb3ed36a5cc041e52c5e6ec15bc842dc7a1a38634413355`, `snapshot_captured_at: 2026-05-26`, `pinned_at: 2026-05-26`, `auth: none`, `reachability: 2`, `domain_overlap: primary`.
- `harness/server-pool/deepwiki-snapshot-2026-05-26/` (gitignored per `harness/server-pool/` rule): captured initialize handshake + tools/list + one representative-query trace (against `modelcontextprotocol/servers`, a neutral repo NOT in our task set, so the snapshot doesn't leak our query repos to DeepWiki logs). Server self-identifies as `DeepWiki v2.14.3, protocolVersion 2025-11-25`. 3 tools confirmed: `read_wiki_structure`, `read_wiki_contents`, `ask_question` (matches `design/SERVER_POOL.md` row 10). Bundle hash recorded in `SHA256` sentinel file (excluded from the bundle hash itself to avoid self-reference).
- `pool/descriptions.json`: new `deepwiki` block inserted in alphabetical order at the top. 3 tools serialized in the project's `{description, inputSchema, name}` shape (output schemas and FastMCP meta stripped to match the convention used by the other 7 servers).
- `harness/configs/mve.yaml`: `primary_servers` flipped from `[github_mcp, git_mcp]` to `[github_mcp, deepwiki, git_mcp]`. Closes the 2-primary gap and matches the locked 3-primary cross-primary comparison.
- Tests: +21 in `tests/test_servers.py` covering load (3 new fields), `verify_pins` (4 hosted-http branches: missing url, missing snapshot_sha256, missing snapshot_path, all-three-present), `hosted_http_params_for` (returns URL container; rejects non-hosted-http; raises on missing url), `stdio_params_for` rejects hosted-http, `compute_snapshot_sha256` (determinism, content-sensitivity, missing-file raise), `verify_snapshot_integrity` (passes with correct sha; raises on drift, missing dir, missing bundle files; skips non-hosted-http), `install_server` is no-op for hosted-http, and end-to-end pool spawn (mocked `streamablehttp_client`: records the URL it was called with; halts on snapshot drift before any network contact; httpx-side connect errors surface as `ServerInstallError`). 257 → 278 passing.
- Path B (2026-05-26): pilot sweep using deepwiki is gated on a written permission response from Cognition Labs per their Platform ToS §2.3 ("expressly approved by Cognition in writing"). The wiring lands now because transport infrastructure is reusable regardless of which hosted server we end up with. Only one snapshot-capture burst hit `mcp.deepwiki.com` during this sprint (3 requests total: initialize + tools/list + one neutral-repo sample query). No sweep traffic. Email draft + contingency tree live at `DevVault/tool-crowding/cognition-permission-email-draft.md` (vault, not in this repo). If Cognition denies, drop deepwiki and revert to 2-primary cross-primary comparison; the wiring code stays useful for the next hosted MCP server we adopt.
- Carried-forward cleanups still open: `servers_pinned.yaml` oci-move (relocate `oci` from `primary_servers` to `distractors` to mirror locked SERVER_POOL.md); orchestrator `primary_server` filter (`tcrun/orchestrator.py::enumerate_cells` does not yet enforce query-primary alignment); runtime snapshot integrity check is currently only invoked from `_spawn_one` (not from `install_server`), which is appropriate for now.

### Fixed — `mve.yaml primary_servers` drops `oci` (COI defense); deepwiki deferred to a wiring sprint (2026-05-26)

- `mve.yaml primary_servers` was `[oci, github_mcp, git_mcp]`. Listing OCI as a query-primary violates the author-disclosure rule (FOUNDATION.md §249, SERVER_POOL.md author disclosure, QUERY_SET_HYGIENE.md §192) and makes the leave-OCI-out COI defense structurally impossible. Updated to `[github_mcp, git_mcp]`.
- Locked SERVER_POOL.md (2026-05-25 PM) names 3 query-primaries: `github_mcp`, `deepwiki`, `git_mcp` (per `design/CHART_LAYOUT.md §54`). `deepwiki` is NOT in this change because it is not yet wired into the harness — `tcrun/servers_pinned.yaml` has no `deepwiki` entry, `pool/descriptions.json` has no deepwiki tool descriptions, and `tcrun/servers.py` does not yet support hosted Streamable HTTP transport (DeepWiki is hosted, not stdio/Docker). New open loop: deepwiki wiring sprint; on landing, `primary_servers` becomes `[github_mcp, deepwiki, git_mcp]`. `tcrun/servers_pinned.yaml` also still lists `oci` in its `primary_servers` section — separate cleanup (move to `distractors`) since the lookup is name-based and the section label is documentation only.
- Local-only companion (file is gitignored per release-via-HF-Datasets plan): `tasks/v1/queries.jsonl` 21 public-tier rows re-curated off `oci` to a repo-stratified 7/7/7 split across `{github_mcp, deepwiki, git_mcp}` — per-repo pylint 2/2/1, visidata 2/2/1, buildbot 1/1/2, psycopg 1/0/1, archinstall 1/2/2, quartile-balanced so each primary covers q1-q4 (github q1:2/q2:1/q3:3/q4:1; deepwiki q1:3/q2:1/q3:2/q4:1; git q1:3/q2:2/q3:1/q4:1). The per-query field is metadata (the orchestrator does not filter trials on it; smoke.yaml header notes this as a pending enforcement step). DeepWiki labels are kept in the local file as the intended natural-fit hypothesis ahead of the wiring landing.
- 257/257 tests still pass. No tests added; the Pydantic schema (`tcrun/tasks.py::Query.primary_server`) remains a permissive `str` because the valid-set constraint is documented at the design-doc layer, not the type layer.

### Fixed — model_id `claude-sonnet-4-6-20260131` did not exist; corrected to `claude-sonnet-4-6` (2026-05-26)

- `models/endpoints.json` + `configs/mve.yaml` + `configs/smoke.yaml` pinned the model as `claude-sonnet-4-6-20260131`. Anthropic returned 404 `not_found_error: model: claude-sonnet-4-6-20260131`. Probe of `https://api.anthropic.com/v1/models` confirmed the correct identifier is `claude-sonnet-4-6` (no date suffix). Sonnet 4.6 has not yet been promoted to a dated snapshot — older models like `claude-sonnet-4-5-20250929` use the dated form, current frontier models don't. Surfaced 2026-05-26 by the first live smoke after the auth + env-override fixes unblocked the path.
- Caveat for reproducibility: `claude-sonnet-4-6` may be a floating alias rather than a frozen snapshot. The run_id chain captures the model_id string verbatim, so if Anthropic later releases `claude-sonnet-4-6-<date>`, our captured snapshot is the un-dated form. Migrate to the dated ID when one is published.

### Fixed — removed `top_p` from API calls + SamplingParams (Sonnet 4.6+ rejects both `temperature` and `top_p` together) (2026-05-26)

- `tcrun/agent.py::_invoke_api` sent both `temperature=0.0` and `top_p=1.0` on every API call. Sonnet 4.6 returns 400 `invalid_request_error: temperature and top_p cannot both be specified for this model`. Surfaced immediately after the model_id fix landed.
- With `temperature=0.0` (our deterministic-dispatch default per pre-registration), `top_p` is a no-op anyway. Removed the `top_p` kwarg from the `client.messages.create` call. Removed the `top_p` field from `SamplingParams` (`tcrun/results.py`) so Trial rows don't record a value we never sent — recording `top_p=1.0` while the API used Anthropic's own internal default would be a reproducibility lie.
- No new tests; the existing smoke + 257-test suite covers the schema migration (no tests referenced `SamplingParams.top_p`; the field was effectively dead code).

### Fixed — `.env` now overrides shell-exported credentials, with a loud warning on drift (2026-05-26)

- `tcrun/cli.py::_load_env` previously called `load_dotenv(dotenv_path=env_path)` with `override=False` (python-dotenv's default). A stale `export ANTHROPIC_API_KEY=...` line in the user's shell rc (`~/.zshrc`, `~/.bashrc`) would silently shadow the value in `.env` — every subprocess inherits the shell env, dotenv refuses to overwrite, and Anthropic returns 401 against a key the dashboard swears is live. Surfaced 2026-05-26: a freshly-rotated key in `harness/.env` produced 401s for 30 minutes of debugging because `~/.zshrc:11` exported a long-revoked key into every shell. The harness's reproducibility chain depends on `.env` being the source of truth for credentials — silent shell-leak means two machines with different `.zshrc` files would produce different `run_id`s for the same checked-in config.
- Fix: `_load_env` now calls `load_dotenv(..., override=True)` so `.env` wins. Before the override, it reads the file values via `dotenv_values` and compares to `os.environ`; any key whose shell value differs from the `.env` value triggers a stderr WARNING naming the key (with the last 4 chars of each, never the full secret) + a one-line remediation hint ("Remove the stale export from your shell rc"). This keeps the surprise loud rather than silent.
- 2 new tests in `tests/test_cli.py`: `test_load_env_dot_env_overrides_shell_export` (stale shell key + fresh .env → .env wins, WARNING in stderr) + `test_load_env_no_warning_when_shell_matches_dotenv` (matching values → no spurious warning).

### Fixed — agent.py re-raises F13 exceptions instead of swallowing into `error_type="harness_bug"` (2026-05-26)

- `tcrun/agent.py::AgentHarness.run_trial` caught every non-(CacheLeakHalt, APIFault, ServerFault, TimeoutError) exception in the agent loop, set `error_type = "harness_bug"`, built a Trial row with `cost_usd=0` + `tool_calls=[]`, and returned it. The comment on line 288 promised "will halt"; the code didn't deliver. Same pattern at the oracle-call site (line 297-299) caught oracle exceptions into `error_type = "harness_bug"` instead of propagating.
- The orchestrator's `_run_trial_with_sem` only halts on exceptions it actually sees. With the agent swallowing F13s, every cell that hit a run-wide failure (auth, malformed credentials, harness-side bug) wrote a fake-completion row and the summary reported `n_completed=N` with `running_cost_usd=$0`. Surfaced 2026-05-26 on the first live smoke (5 trials × `anthropic.AuthenticationError` → 5 "completed" rows; tool_crowding had no way to distinguish "5 trials passed" from "5 trials never made an API call").
- Fix: both sites now re-raise. `categorize()` (tcrun/retry.py) returns `"persistent_failure"` for any class outside `(APIFault, ServerFault)`, and `Orchestrator._run_trial_with_sem` already raises `OrchestratorHalt` on that category. So re-raising at the agent layer is the minimum change that wires the existing halt path through.
- 2 new tests in `tests/test_agent.py`: `test_run_trial_re_raises_on_unhandled_api_exception` (injects a non-APIFault Exception into `client.messages.create`, expects propagation) + `test_run_trial_re_raises_on_oracle_exception` (oracle raises; expects propagation). 253 → 255 passing.

### Added — Phase 2 smoke config + task file (2026-05-26)

- `harness/configs/smoke.yaml` and `harness/tasks/smoke.jsonl` (single-query): minimal plumbing-validation config for Phase 2 step 2. Cell math: 1 primary (git_mcp) × 1 N × 1 query × 5 orderings × 1 rep = 5 trials. No padded control, no baselines, retriever-off, runs_per_cell=1. Designed for ~$0.15 worst case at Sonnet 4.6. Smoke is plumbing-only: orchestrator does not enforce alignment between the cell's `primary_server` and the query's `primary_server`, so using a git_mcp cell on an oci-targeted query is legal and produces a clean Trial row regardless of oracle score.

### Fixed — docker MCP server pinning end-to-end: yaml field-name mismatch + invalid `docker run` reference (2026-05-26)

- `servers_pinned.yaml` used `docker_image` and `image_digest` for `github_mcp`, but `tcrun/servers.py::load_pinned_servers` read `docker_digest` — so the docker fields had never actually been loaded into `PinnedServer`. `verify_pins(...)` would have raised `ServerPinMismatch("docker install requires docker_digest pin")` for any pinned docker server because `pin.docker_digest` was always `None`. Latent since the docker branch landed; surfaced only when `github_mcp`'s digest finally got pulled (Docker daemon HTTP 500 had blocked the capture since 2026-05-23).
- `stdio_params_for(pin)`'s docker branch built `docker run --rm -i <bare-sha256>` from `pin.docker_digest or "latest"`. A bare digest is not addressable by `docker run` — the canonical form is `<image>@sha256:<hex>`. Even after fixing the field-name bug, every docker spawn would have failed.
- Fix: `PinnedServer.docker_digest` renamed to `image_digest`; new `docker_image` field. `load_pinned_servers` reads both. `verify_pins` requires both for `install: docker`. `stdio_params_for` builds `f"{pin.docker_image}@{pin.image_digest}"`; raises `ServerInstallError` if either is missing (defense-in-depth — `verify_pins` is the contract gate, but the snapshot path doesn't run it).
- `tcrun/snapshot.py::_pin_identity` renamed `pin.docker_digest` → `pin.image_digest` to match.
- 6 new tests in `tests/test_servers.py`: `verify_pins` rejects partial docker pin (image-only, digest-only); accepts both-present; `load_pinned_servers` reads `docker_image` + `image_digest` from yaml; `stdio_params_for` builds the digest-pinned reference; raises on missing fields.

### Changed — 5 npm-distributed MCP servers migrated to official `mcp/*` Docker images (2026-05-26)

- `npx -y @modelcontextprotocol/server-{git,fetch,sequentialthinking,time,sqlite}` is 404 on npm as of 2026-05-26 (audited against the npm registry directly). All 5 packages have official Docker images at `mcp/*` on Docker Hub (modelcontextprotocol-owned). Migrated `tcrun/servers_pinned.yaml` to `install: docker` for each, pinned by image digest. `github_mcp` digest also captured (was TBD since 2026-05-23 Docker daemon outage). See `DevVault/tool-crowding/server-pool-audit-2026-05-26.md` for the upstream-npm failure evidence + migration rationale.
- `environment.lock` regenerated: `docker_images` count 0 → 6.
- `pool/descriptions.json` bootstrapped via `tcrun snapshot-descriptions --all`: 7 servers populated (5 newly-docker'd: git_mcp/fetch_mcp/sequential_thinking_mcp/time_mcp/sqlite_mcp; plus filesystem_mcp + memory_mcp on npx). Remaining failures are pre-existing and unblocked by this work: `github_mcp` (needs `GITHUB_PERSONAL_ACCESS_TOKEN` for MCP handshake), `aider_mcp`/`oci` (need `server-pool/` clones), `postgres_mcp`/`brave_search_mcp`/`slack_mcp` (`stdio_params_for` has no `install: tarball` branch yet), `linear_mcp`/`notion_mcp` (`package: TBD`, OAuth-deferred post-pilot).

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
