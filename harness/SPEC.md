---
title: tool-crowding Harness Engineering Specification v1.1
date_locked: 2026-05-20
date_amended: 2026-05-20
status: locked; awaiting MVE build (Thu 2026-05-22 onwards)
purpose: Foundation document every line of code in tool-crowding/harness/ must comply with.
changelog: see Changelog section at bottom
---

# tool-crowding Harness — Engineering Specification

> Foundation doc. Single-author research harness. ONE laptop + optionally ONE cloud VM. 50 tasks, 15 servers, Anthropic API. 2-week MVE deadline. The deliverable is a foundation, not a fortress.

Up front: the original prompt asked me to "apply DDIA principles." Half of DDIA is cargo-cult for this project. I am calling that out in Section 1 instead of smuggling enterprise patterns in to look smart.

---

## 1. Principle-Transfer Audit

### DDIA principles (Kleppmann, "Designing Data-Intensive Applications", 2017)

| Principle | DDIA chapter | Verdict | Justification |
|---|---|---|---|
| Reliability (fault vs failure) | Ch 1 | **PARTIAL** | Transient API errors and server crashes are faults; we need retry + checkpoint. The "fault vs failure" framing (a fault is local, a failure is user-observable) DOES help when categorizing failure modes (Section 7). Beyond that, redundancy and high-availability machinery do not apply: there is one user (me), and a 6-hour outage at 2 AM is fine. |
| Scalability (load parameters, percentile latencies) | Ch 1 | **DOES NOT TRANSFER** | Load is fixed: 50 tasks × 15 servers × 5 N × 5 orderings ≈ 18.75k trials per primary sweep. There is no "scaling" axis. Percentile latencies DO transfer for SPEC RG variance reporting (cited below), but not for load planning. |
| Maintainability (operability, simplicity, evolvability) | Ch 1 | **TRANSFERS** | I will re-run this harness in 3 months when reviewers ask. Simplicity is non-negotiable for a one-person codebase. Evolvability matters because v2 expands the IV set. |
| Data models & query languages | Ch 2 | **TRANSFERS (narrow)** | The results record schema is the most important artifact in the harness; design it like a domain model. Query languages (SQL, MapReduce, Cypher) do not apply. |
| Storage & retrieval (B-trees, LSM, etc.) | Ch 3 | **DOES NOT TRANSFER** | JSONL append log on local disk. No B-trees, no LSM. If results exceed 100 MB, I am over-running. |
| Encoding & schema evolution | Ch 4 | **TRANSFERS** | Schema-versioning results records is critical. v1 analyzer must read v1 records correctly even after the schema bumps. Forward and backward compatibility rules in Section 4. |
| Replication | Ch 5 | **DOES NOT TRANSFER** | Single machine. One copy of the data. `cp` to a backup drive is "replication" enough. |
| Partitioning | Ch 6 | **DOES NOT TRANSFER** | 50 tasks fit in a list. There is nothing to partition. |
| Transactions | Ch 7 | **DOES NOT TRANSFER** | One writer (one process), append-only file. ACID is implicit via fsync on append. Two-phase commit is not relevant. |
| Trouble with distributed systems | Ch 8 | **DOES NOT TRANSFER** | One machine. There is no distributed system. Network partitions between my laptop and the Anthropic API are a "timeout" failure mode, not a Byzantine consensus problem. |
| Consensus | Ch 9 | **DOES NOT TRANSFER** | One process. No quorum. No Paxos. |
| Batch processing (MapReduce) | Ch 10 | **TRANSFERS WEAKLY** | Each cell is a "batch job" in the loose sense (offline, deterministic-ish, retryable). Spark / Flink / MapReduce patterns do NOT apply. |
| Stream processing | Ch 11 | **DOES NOT TRANSFER** | No streaming workload. Results are static after the run. |
| Observability & debugging | Ch 1 + Ch 8 | **TRANSFERS** | Tracing every tool call and every model exchange is non-negotiable. Without it, "task 23 failed at N=12" is unfixable three weeks later. |
| Idempotency | Various | **TRANSFERS** | Re-running a completed cell with identical inputs must be a no-op (content-addressed run_id, skip-if-exists). |
| Backpressure / rate limiting | Various | **PARTIAL** | Anthropic and Brave Search have rate limits. Token-bucket + exponential backoff on the API client is required. But producer/consumer queue patterns are overkill. |
| End-to-end argument (Saltzer-Reed-Clark 1984) | DDIA references it | **TRANSFERS** | Don't verify in the middle of the pipeline; verify at the boundary (the oracle, not the agent's claimed answer). |

### Reproducibility principles that matter MORE than DDIA here

These are the load-bearing references for a research harness. Citing them up front so the design is anchored in real norms, not DDIA-by-default.

1. **SPEC Research Group (SPEC RG) methodology**. Specifically: variance reporting (median + IQR over multiple samples, not single-shot), environment capture in every result record, percentile latency over average latency. See Kounev et al., "A Framework for Quantitative Analysis," and the SPEC RG benchmarking principles. Sources: [research.spec.org](https://research.spec.org/) and the methodology in [v.Kistowski et al., "Variations in Variability"](https://research.spec.org/icpe_proceedings/2015/proceedings/p145.pdf).

2. **ML Reproducibility Checklist** (Pineau et al., NeurIPS 2020). Mandatory checks: dataset version, code version, environment, hyperparameters, hardware, statistical significance. Adopted by NeurIPS / ICML / ICLR. Source: [Pineau et al., "Improving Reproducibility in Machine Learning Research"](https://www.jmlr.org/papers/v22/20-303.html).

3. **ACM Artifact Review and Badging (v1.1, 2020)**. Three badges (Available, Functional, Reusable). To earn Reusable, the artifact must be documented, version-pinned, and re-executable by an independent party. Source: [acm.org/publications/policies/artifact-review-and-badging-current](https://www.acm.org/publications/policies/artifact-review-and-badging-current).

4. **FAIR data principles** (Wilkinson et al., Sci Data 2016). Findable, Accessible, Interoperable, Reusable. Results JSONL must satisfy F (DOI on release), A (public repo), I (open schema), R (with full provenance). Source: [Wilkinson et al., Nature Sci Data](https://www.nature.com/articles/sdata201618).

The harness must satisfy these. DDIA is a useful taxonomy but not the spec.

---

## 2. Non-Functional Requirements (NFRs)

MoSCoW order. Each is one-line testable.

### Must

- **M1**: Every run produces a deterministic results row given the `run_id`. The `run_id` is content-addressed over the 7-artifact chain in `design/REPRODUCIBILITY.md §1` (servers_pinned + descriptions + queries + oracles + endpoints + environment + harness) plus the non-path Config fields (seed, N, runs_per_cell, model, host, tool_listing_strategy). Determinism is checked by recomputing `run_id` at preflight and aborting on mismatch.
- **M2**: A crashed run resumes from the last completed cell without re-running completed cells (idempotency via content-addressed `run_id` + `cell_id`).
- **M3**: All results are append-only JSONL with a `schema_version` field on every record.
- **M4**: Every tool call has a per-call audit record in the trace file.
- **M5**: Re-running an experiment with identical resolved Config (CLI/YAML fields PLUS the content hashes of every artifact path the Config references) produces identical `run_id`s. v1.2 amendment: see Section 8 Identity rule + `design/REPRODUCIBILITY.md`.
- **M6**: Every result record captures the environment fingerprint (Python version, package hashes, OS, model snapshot id, server SHAs).
- **M7**: An oracle version is recorded in every trial; oracle code is version-pinned and lives in `harness/oracles/`.
- **M8**: API rate-limit and 5xx errors trigger exponential backoff with jitter (base 1s, factor 2, max 5 retries, max wait 60s).

### Should

- **S1**: Total trial cost for the MVE ≤ $200.
- **S2**: Single trial p95 wall-clock ≤ 60 seconds (1,400 MVE trials complete in < 24 hours).
- **S3**: All MCP server installs are version-pinned by git SHA (for source installs) or npm version-lock (for npx servers).
- **S4**: A failed cell can be re-run in isolation without re-running the whole sweep (cell-level granularity).

### Could

- **C1**: A notebook at `analysis/dashboard.ipynb` reads `results/<run_id>/results.jsonl` and produces the N-curve and Pareto plot.
- **C2**: Live progress reporting (% complete, ETA) via `tqdm` in stdout.
- **C3**: A `tcrun status <run_id>` subcommand reports per-cell completion state.

### Won't

- **W1**: Multi-machine distributed execution. Justification: coordination overhead dominates research-iteration time on a 6,250-trial primary sweep that runs in a day on one machine. If trials become 6 million, revisit.
- **W2**: A web UI. Justification: a Jupyter notebook + matplotlib produces every artifact a reviewer would ask for.
- **W3**: A database (Postgres / Mongo / etc.). Justification: 18k records of ~5 KB each = 90 MB. JSONL with `jq` outperforms any database for this size at single-user.
- **W4**: A plugin system for the server pool. Justification: the pool is fixed in `design/SERVER_POOL.md`; v2 expansion is a code edit, not a runtime config.
- **W5**: Real-time streaming of results to anywhere. Justification: results land on disk and analysis is offline; "live dashboards" are a category error for batch research.
- **W6**: Multi-model and multi-host sweeps in the MVE. Justification: scope creep. Primary is Claude Sonnet 4.6 + Claude Desktop; secondary sweeps happen post-MVE only if the MVE is green.
- **W7**: A custom MCP client. Justification: the official `mcp` Python package is fine and reading its source is faster than wrapping it.

---

## 3. Architecture

### Component diagram

```
                     ┌────────────────┐
                     │  CLI / YAML    │
                     │  (Click+Pydantic)
                     └────────┬───────┘
                              │
                              ▼
                     ┌────────────────┐
                     │  Orchestrator  │
                     │  (cell loop +  │
                     │   resume logic)│
                     └─┬────────────┬─┘
                       │            │
            ┌──────────▼──┐   ┌─────▼─────────┐
            │ TaskLoader  │   │ ServerPool    │
            │ (CoIR subset│   │ Manager       │
            │  v1: 50 q.) │   │ (install +    │
            └──────────┬──┘   │  health-check)│
                       │      └─────┬─────────┘
                       │            │
                       ▼            ▼
                    ┌─────────────────┐
                    │  AgentHarness   │ ◄── Anthropic API
                    │  (Sonnet 4.6 +  │
                    │  MCP loop +     │
                    │  tool-call log) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  ResultWriter   │ ─► results.jsonl
                    │  (schema +      │ ─► trace.jsonl
                    │   JSONL append) │ ─► summary.json
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Analyzer      │ ─► figures/
                    │ (Jupyter +      │
                    │  pareto.py +    │
                    │  mpd.py)        │
                    └─────────────────┘
```

### Per-component responsibility statements

**TaskLoader** (`tcrun/tasks.py`)
- Responsibility: Load the locked v1 task set (50 CoIR queries) into typed `Task` objects.
- Inputs: `tasks/v1/queries.jsonl`
- Outputs: `List[Task]` where `Task = (task_id, query, ground_truth_snippet, ground_truth_symbol, difficulty_bucket)`
- Failure modes: file not found, JSONL parse error, ground-truth missing fields. All raise `TaskLoadError` and halt the run.
- MUST NOT: mutate tasks at runtime; do retrieval-time filtering; depend on the model or server set.

**ServerPoolManager** (`tcrun/servers.py`)
- Responsibility: install, version-pin, health-check, and teardown the 15 MCP servers per cell. Hermetic per cell (fresh subprocess tree per cell).
- Inputs: server list (names from config), pinning table (SHAs/versions)
- Outputs: a dict `{server_name → (subprocess.Popen handle, MCP client connection)}`
- Failure modes: install failure (subprocess returncode≠0); health-check timeout; server zombie (heartbeat fails after 60s)
- MUST NOT: share server subprocesses across cells; assume servers are already installed; talk to the LLM.

**Orchestrator** (`tcrun/orchestrator.py`)
- Responsibility: enumerate cells from config, dispatch one trial at a time, handle resume-from-checkpoint, manage per-cell server pool lifecycle.
- Inputs: validated `Config` object
- Outputs: writes to results.jsonl as each trial completes
- Failure modes: catastrophic API/server failure → halt; non-catastrophic → log failure-mode tag on the trial, continue to next trial.
- MUST NOT: silently swallow exceptions; modify task data; cache results between cells without a content-addressed key.

**AgentHarness** (`tcrun/agent.py`)
- Responsibility: run the Anthropic API + MCP tool-use loop for a single trial. Return a `Trial` record.
- Inputs: `(Task, ServerPool, model_snapshot_id, sampling_params, seed, tool_listing_strategy)`
- Outputs: `Trial` (full schema in Section 4); writes a `trace.jsonl` per trial
- Failure modes: API 4xx/5xx, context-overflow, tool-call timeout, hallucinated tool name, agent gives up
- MUST NOT: judge correctness (that is the oracle's job); modify ground truth; cache responses (the harness is reproducibility-first, not throughput-first).

**ResultWriter** (`tcrun/results.py`)
- Responsibility: validate `Trial` against Pydantic schema and append to `results.jsonl`. Maintain `summary.json` as a running aggregate.
- Inputs: `Trial` object
- Outputs: append to disk; flush after every write (fsync).
- Failure modes: schema validation error (halt and dump raw record to `corrupt-results.jsonl`); disk-full (halt immediately).
- MUST NOT: silently drop records; rewrite history; aggregate beyond per-cell sums.

**Analyzer** (`tcrun/analysis/`)
- Responsibility: read `results.jsonl`, produce N curves, Pareto frontier, MPD table, failure-mode breakdown. Notebook-driven.
- Inputs: one or more `results.jsonl` files
- Outputs: PNG / PDF figures in `figures/`; markdown tables in `paper/`
- Failure modes: schema-version mismatch (fall back to v1 reader); missing fields (log + skip row)
- MUST NOT: re-run trials; touch the harness state; assume any specific dataframe library beyond pandas + matplotlib.

**CLI / Config** (`tcrun/cli.py`, `tcrun/config.py`)
- Responsibility: parse CLI args, load YAML config, validate via Pydantic, hand off to Orchestrator. Compute the canonical `run_id` as SHA-256 of the resolved canonical Config JSON.
- Inputs: argv or YAML file path
- Outputs: validated `Config` + `run_id`
- Failure modes: invalid args → exit 2; invalid YAML → exit 2; missing required field → exit 2
- MUST NOT: dispatch trials; allow ambiguity in `run_id` derivation (must be content-addressed).

---

## 4. Data Schema (the most load-bearing section)

### `Trial` record (one per trial; appended to `results.jsonl`)

Pydantic v2 model. Field-by-field:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class ServerEntry(BaseModel):
    server_name: str         # e.g., "github_mcp"
    server_version: str      # git SHA or npm-lock entry
    tool_count: int
    description_tokens: int

class ToolCall(BaseModel):
    step: int                # 1-indexed within the trial
    tool_name: str
    was_valid: bool          # tool exists in server_set
    was_hallucinated: bool   # tool not in any installed server
    latency_ms: int
    input_tokens: int        # tokens added to context by this call
    output_tokens: int       # tokens returned by the tool
    error: str | None = None # server-side error message if any

class SamplingParams(BaseModel):
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 4096

class EnvFingerprint(BaseModel):
    os: str
    python_version: str
    package_hash: str        # SHA-256 of sorted pip freeze
    machine_id: str          # anonymized hash of hostname
    git_sha: str             # of tool-crowding/harness

class Trial(BaseModel):
    # identity
    schema_version: str = "1.2"          # v1.2 added embedder fields (2026-05-25)
    harness_version: str
    run_id: str              # content-addressed, full run
    cell_id: str             # content-addressed, single (N, server_set, ordering)
    trial_id: str            # content-addressed, single (cell_id, task_id, seed)
    started_at: datetime
    finished_at: datetime

    # what was tested
    task_id: str
    task_version: str        # e.g., "coir-stackoverflow-py-v1"
    task_difficulty: Literal["easy", "medium", "hard"]
    model_id: str            # "claude-sonnet-4-6"
    model_provider: Literal["anthropic", "openai", "google"]
    model_snapshot_id: str   # "claude-sonnet-4-6-20260315"
    sampling_params: SamplingParams
    server_set: list[ServerEntry]
    N: int                   # cardinality of server_set
    primary_server: str      # which code-retrieval server is being tested
    ordering_seed: int       # 0-4
    # v1.2 alignment: literal narrowed to match Config.tool_listing_strategy.
    # Legacy `rag-mcp` and `mcp-zero` values (never written in practice) are
    # normalized to `retriever-on` by the v1.1→v1.2 migration in read_jsonl.
    tool_listing_strategy: Literal["full", "retriever-on", "oracle-filter"]
    pass_criterion_id: str   # e.g., "symbol-plus-50pct-overlap-v1"

    # what happened
    # context_input_tokens = usage.input_tokens
    #                      + usage.cache_read_input_tokens
    #                      + usage.cache_creation_input_tokens
    # With per-trial nonce (Section 5 rule 4), the latter two should be 0 on every
    # response; F18 halts the run if not. This definition is belt-and-suspenders for
    # cache-leak detection AND preserves the Pareto x-axis even if a nonce slip occurs.
    context_input_tokens: int
    context_output_tokens: int
    tool_calls: list[ToolCall]
    first_correct_tool_step: int | None  # null if never correct
    pass_: bool = Field(alias="pass")    # 'pass' is a Python keyword
    error_type: Literal[
        "none",
        "wrong_answer",
        "wrong_tool",
        "context_overflow",
        "hallucinated_tool_name",
        "latency_timeout",
        "server_fault",
        "api_fault",
        "agent_gave_up",
        "harness_bug",
    ]
    error_detail: str | None = None
    cost_usd: float

    # padded-N=1 control flags (schema v1.1; see design/PADDING_STRATEGY.md)
    is_padded_n1: bool = False           # this trial's server_set is the padded-N=1 condition
    fake_tool_invoked: bool = False      # the agent called a filler tool during this trial
    padding_skipped: str | None = None   # e.g., "budget_negative"; null when padding executed normally

    # embedder identity (schema v1.2; load-bearing for retriever-ON arm + A1/A5
    # detection per design/REPRODUCIBILITY.md §1 h_embedder row). Defaults
    # match the v1 primary pinned in models/embedder.json so v1.0/v1.1
    # migrations are clean. Orchestrator/agent_factory MUST override these
    # from the resolved Config.embedder pin so the row reflects the configured
    # embedder regardless of whether retriever-on actually invoked it.
    embedder_provider: Literal["openai", "voyageai", "bge"] = "openai"
    embedder_model: str = "text-embedding-3-large"
    embedder_snapshot: str = "text-embedding-3-large"
    embedder_dimension: int = 3072

    # provenance
    trace_path: str          # "results/<run_id>/traces/<trial_id>.jsonl"
    seed: int
    oracle_version: str      # "pass_v1.py@sha256:abc..."
    env: EnvFingerprint
```

### Schema evolution rules

1. **`schema_version` is `MAJOR.MINOR`** (semver-lite).
2. **MINOR bump**: add optional fields with sensible defaults. Old analyzers ignore unknown fields. Examples shipped: v1.1 added 3 padding-control fields; v1.2 added 4 embedder fields (`embedder_provider`, `embedder_model`, `embedder_snapshot`, `embedder_dimension`) defaulting to the v1 primary pin.
3. **MAJOR bump**: incompatible change (rename, type change, removal). Requires a migration script in `harness/migrations/v1_to_v2.py` and a documented rationale in the migration's docstring. Old data is migrated forward, never deleted.
4. **Never delete a field**: deprecate via `# DEPRECATED, do not use in new code` comment. Old records keep the field.
5. **`harness_version`** is separate from `schema_version`: harness can ship a bug-fix release without bumping schema; schema bumps without harness bumps are also allowed (analyzer-only changes).
6. **The analyzer dispatches on `schema_version`**: `tcrun.results.read_jsonl` chains migrations forward (`v1.0 → v1.1 → v1.2`) so any supported source hydrates to `CURRENT_SCHEMA_VERSION`. Pre-v1.2 records with the legacy `tool_listing_strategy` values `"rag-mcp"` or `"mcp-zero"` (never written by the harness, but reserved on the literal pre-v1.2) are normalized to `"retriever-on"` in the v1.1→v1.2 step. v1 reader is frozen the day the first MVE result lands.

Second-best alternative: protobuf with `reserved` for deleted fields. Rejected because JSON Schema + Pydantic is enough at this volume and protobuf adds tooling overhead (compilation step, language bindings) for zero practical benefit at 18k records.

---

## 5. Reproducibility Protocol

Numbered. Each rule is testable.

1. **Seeding**:
   - `seed` is passed via CLI / YAML. Default 42.
   - Seeded: `random`, `numpy.random`, `secrets`-free.
   - NOT seeded: Anthropic API responses (the API is non-deterministic even at `temperature=0`; see [Anthropic determinism note](https://docs.anthropic.com/en/docs/build-with-claude/output-determinism)).
   - **Mitigation**: `temperature=0` + multiple samples per trial when measurement variance matters. Report median + IQR per SPEC RG variance principle. In the MVE: 3 orderings per cell (same task, different tool ordering); aggregate via paired bootstrap.
   - The seed is part of `trial_id` content addressing.

2. **Version pinning** (binding source: `design/REPRODUCIBILITY.md §1`):
   - Python: `pyproject.toml` + `requirements.lock` (uv lock or pip-compile). Lock file committed.
   - MCP servers: each server has a pinned SHA (for git-installable) or npm-lock entry (for npx). Table lives in `design/SERVER_POOL.md` (pinning table); harness reads `tcrun/servers_pinned.yaml` which is generated from it. v1.2: the contents of `servers_pinned.yaml` participate in `run_id` (Section 8 Identity rule).
   - Tool descriptions + JSON schemas: captured at install into `pool/descriptions.json`. v1.2 addition per TC.1 (FOUNDATION.md §4.4). Contents participate in `run_id`.
   - Model snapshots: always reference the dated snapshot id (`claude-sonnet-4-6-20260131` per `design/MODEL_VERSIONS.md`), never the floating alias (`claude-sonnet-4-6`). If Anthropic deprecates a snapshot mid-run, the harness halts (failure mode F16).
   - Model endpoints: `models/endpoints.json` pins per-model API URL, snapshot id, temperature, max_tokens, system-prefix template, nonce-policy. v1.2 addition. Contents participate in `run_id`.
   - Environment: `environment.lock` pins Docker image SHA, OS, Python version, key library versions. v1.2 addition. Contents participate in `run_id`.

3. **Environment capture**:
   - Captured into every `Trial.env` field: OS (`platform.platform()`), Python version, hash of sorted `pip freeze`, anonymized machine_id (SHA-256 of hostname), git SHA of `tool-crowding/harness/`.
   - Captured per run (in `summary.json`): RAM (`psutil.virtual_memory().total`), CPU info, network latency p50 to `api.anthropic.com` (3 pings before the run starts), wall-clock start/end UTC.

4. **Hermetic execution**:
   - Each CELL spawns a fresh subprocess tree of MCP servers. Teardown after the cell completes (or fails).
   - No shared mutable state between cells beyond append-only `results.jsonl`.
   - The Anthropic API client uses a fresh session per cell (HTTPX connection-pool isolation).
   - **A unique system-prefix nonce per TRIAL (NOT per cell) forces cache-cold on every API call.** Per Section 6 of RESEARCH_DESIGN.md, prompt-cache hits are a controlled confounder. With a per-cell nonce, trials 2-50 within a cell would hit the cache on the system + tool-list prefix (~5-10k tokens at higher N), silently deflating `context_input_tokens` (the Pareto x-axis). Per-trial nonce eliminates this. Cost: ~$35 over the MVE for foregone cache discount; acceptable for measurement integrity.

5. **Variance protocol**:
   - 5 paired orderings per cell (in MVE: 3 per cell to fit time budget; bump to 5 for the full sweep).
   - Report median + 95% CI from paired bootstrap (B=10,000 resamples).
   - Citation: SPEC RG P5 — multiple measurements, percentile reporting, no single-shot claims. See [research.spec.org RG methodology](https://research.spec.org/).
   - All raw per-trial records are kept; aggregate stats are derived in the analyzer, never written to disk by the harness.

6. **Ground truth**:
   - Oracle is a Python function `pass_v1.pass_criterion(returned_snippet: str, task: Task) -> bool`.
   - Oracle code lives in `harness/oracles/pass_v1.py` and is version-pinned by its SHA-256, recorded in every `Trial.oracle_version`.
   - Oracle audit protocol: a 10-query held-out gold set is checked by hand once at MVE start; if oracle disagrees with hand-labeling on > 1 of 10, fix oracle and bump version (`pass_v2.py`). Old data is annotated with both `pass_v1` and `pass_v2` outcomes in the analyzer; results filter by version.
   - The oracle is independent of the model under test (no LLM-as-judge in v1). Rule-based to avoid The Silent Judge ([arXiv 2509.26072](https://arxiv.org/abs/2509.26072)) failure modes.

---

## 6. Observability

### Per-run trace file format

Path: `results/<run_id>/traces/<trial_id>.jsonl`. JSONL, one record per event.

Event types (`type` field):
- `prompt`: the user message + system prompt + tool-list manifest sent to the model
- `assistant_text`: the model's text response (between tool calls or final)
- `tool_call_request`: the model invokes a tool (full args)
- `tool_call_response`: the tool returns (full payload, possibly truncated to 4k chars with `truncated: true`)
- `api_error`: any 4xx/5xx from Anthropic with status + body
- `oracle_evaluation`: the oracle's verdict + reasoning if rule-based
- `trial_complete`: the final Trial record

Common fields on every event: `trial_id`, `step`, `timestamp_utc`, `event_type`.

### Per-cell summary

Path: `results/<run_id>/cells/<cell_id>.json`. Aggregates 5 orderings into:
- `pass_rate` (median + 95% CI bootstrap)
- `mean_input_tokens`
- `error_type_histogram`
- `n_completed_trials` / `n_expected_trials`

### Aggregate dashboard

`analysis/dashboard.ipynb`. Single notebook. Reads any `results/<run_id>/results.jsonl`. Cells:
1. Load + filter by schema_version
2. N curves per primary server (figure 1)
3. Pareto frontier (figure 2)
4. MPD table (table 1)
5. Failure-mode breakdown (table 2)
6. Padded-N=1 control comparison (figure 3, sanity check)

Second-best alternative: a real dashboard service. Rejected (W2).

### Failure triage flowchart

```
A trial failed. What now?
│
├── error_type == "harness_bug"
│   └── INVALIDATES RUN. Halt sweep. Fix code. Re-run from cell_id.
│
├── error_type == "api_fault"
│   ├── Retry was attempted? → yes → mark trial, continue
│   └── Retry was not attempted? → harness bug, halt
│
├── error_type == "server_fault"
│   ├── Single trial → mark, continue
│   └── ≥ 3 consecutive on same server → halt, investigate server
│
├── error_type == "wrong_tool" / "hallucinated_tool_name" / "context_overflow" / "agent_gave_up"
│   └── This IS the phenomenon under measurement. Continue.
│
└── error_type == "latency_timeout"
    └── Mark, continue; check if cluster of timeouts on Anthropic side.
```

---

## 7. Failure Mode Catalog

Each row is a failure mode that I will encounter. Detection is precise. Recovery is precise.

| # | Symptom | Category | Detection | Recovery | Invalidates run? |
|---|---|---|---|---|---|
| F1 | MCP server install fails (npm 404, git clone error) | Server | subprocess.returncode ≠ 0 | Halt the run; report which server failed | No (pre-run; nothing logged yet) |
| F2 | Server health-check fails (no MCP handshake response in 30s) | Server | timeout in `mcp.connect()` | Mark CELL as harness-failure, skip cell, log | Cell-level only |
| F3 | Server returns malformed JSON-RPC | Server | `mcp` library raises ValidationError | Mark trial as `server_fault`, continue | No |
| F4 | Server subprocess zombie (alive but unresponsive) | Server | per-call timeout 30s + heartbeat fails after 60s | kill -9, restart server, retry trial once, then mark `server_fault` | No |
| F5 | Anthropic API 429 rate-limit | API | response.status_code == 429 | Exponential backoff (1s, 2s, 4s, 8s, 16s, max 60s) up to 5 retries, then mark `api_fault` | No |
| F6 | Anthropic API 5xx server error | API | response.status_code 500-599 | Same backoff as F5 | No |
| F7 | Anthropic API client timeout | API | httpx.TimeoutError | Retry once with same params, then mark `api_fault` | No |
| F8 | Context-overflow (input tokens > model's context window) | API | response error `context_length_exceeded` | Mark trial as `context_overflow` failure | No (this IS measurable phenomenon) |
| F9 | Agent gives up (returns text without ever calling a tool, oracle returns false) | Agent | no `tool_call_request` events in trace AND oracle false | Mark trial as `agent_gave_up` | No |
| F10 | Wrong-tool selected (correct tool was never called, oracle false) | Agent | `first_correct_tool_step is None` and oracle false | Mark trial as `wrong_tool` | No (phenomenon) |
| F11 | Hallucinated tool name (model invokes a tool not present in server_set) | Agent | tool_name not in installed_tools_set | Mark `was_hallucinated=true` on the ToolCall, mark trial as `hallucinated_tool_name` if it dominates | No (phenomenon) |
| F12 | Tool call hangs (server takes > 30s) | Server | per-call timeout | Cancel call, log, mark trial as `latency_timeout` | No |
| F13 | Harness uncaught exception (KeyError, NoneType.attr, etc.) | Harness | sys.excepthook | Log full traceback, mark trial as `harness_bug`, halt run | YES |
| F14 | Disk full while writing | Harness | OSError ENOSPC on append | Halt immediately; preserve partial results.jsonl; emit warning | Cell-level (last cell unflushed) |
| F15 | Schema validation fails on result write | Harness | Pydantic ValidationError | Dump raw record to `corrupt-results.jsonl`, halt run | YES |
| F16 | Model snapshot silently rotated (Anthropic deprecates or auto-rotates) | API | response `model_id` ≠ requested `model_snapshot_id` | Halt run, report to user, prompt to update Config | YES (silently corrupts results) |
| F17 | Oracle false-positive / false-negative discovered post-run | Oracle | hand-audit of 10 held-out queries | Halt run, fix oracle, bump version, re-run | YES (results require new oracle_version annotation) |
| F18 | Anthropic prompt-cache hit despite per-trial nonce (indicates nonce-generation bug or insufficient entropy) | API + Harness | `usage.cache_read_input_tokens > 0` OR `usage.cache_creation_input_tokens > 0` on any response | **Halt the run** (per-trial nonce should make caching impossible); mark trial as `harness_bug`; investigate nonce generation before resuming. All trials in flight since the last successful nonce-cold response are suspect | **YES** (entire run, until nonce-generation audited) |
| F19 | Network drop mid-cell | Network | repeated F5/F7 within 60s | Pause cell for 5 min, resume; if still failing, halt cell | No |
| F20 | OS process limit hit (too many subprocesses) | OS | OSError EAGAIN on Popen | Halt run, document, restart with --max-concurrent-servers | YES if mid-cell |

---

## 8. Configuration & CLI

### CLI shape

```bash
tcrun --task-set v1 \
      --primary-servers oci,github_mcp,git_mcp \
      --distractors filesystem,memory,seq_thinking,time,sqlite \
      --N 1,5,10 \
      --runs-per-cell 3 \
      --model claude-sonnet-4-6-20260315 \
      --host claude-desktop \
      --seed 42 \
      --out results/exp-mve-001/
```

Other subcommands:
- `tcrun resume <run_id>` — pick up from last completed cell
- `tcrun status <run_id>` — report per-cell completion
- `tcrun verify <run_id>` — re-run 5 random trials and check schema + determinism

### YAML config equivalent (`configs/mve.yaml`)

```yaml
task_set: v1
primary_servers: [oci, github_mcp, git_mcp]
distractors: [filesystem, memory, seq_thinking, time, sqlite]
N: [1, 5, 10]
runs_per_cell: 3
model: claude-sonnet-4-6-20260315
host: claude-desktop
seed: 42
out: results/exp-mve-001/
include_padded_n1_control: true
oracle: pass_v1
```

Invocation: `tcrun --config configs/mve.yaml`.

### Identity rule (v1.2 amendment)

**Both invocations resolve to the SAME canonical `Config` object.** The `run_id` is derived from the **resolved canonical Config** — the canonical Config where every path-typed field is augmented with the SHA-256 of the file at that path.

```python
def compute_run_id(config: Config) -> str:
    resolved = config.model_dump()
    for field_name in config.PATH_FIELDS:  # path-typed fields registered on the Pydantic model
        path = resolved[field_name]
        resolved[field_name] = {
            "path": path,
            "sha256": file_sha256(path),
        }
    canonical = json.dumps(resolved, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

The path-typed fields that participate in `run_id`:

| Config field | What it references | Why it must be content-hashed |
|---|---|---|
| `servers_pinned` | `tcrun/servers_pinned.yaml` | Mutations to SHAs or versions silently change which server code runs (TC.1). |
| `task_set` | `tasks/v1/queries.jsonl` | Mutations to the query set change ground truth and difficulty distribution (ABC R.3). |
| `oracle` | `tcrun/oracles/pass_v1.py` | Mutations to the oracle change pass/fail outcomes for archived trials (ABC R.10). |
| `descriptions` (v1.2) | `pool/descriptions.json` | Description drift changes which tools compete for selection (TC.1). |
| `endpoints` (v1.2) | `models/endpoints.json` | API call shape determines model behavior. |
| `environment` (v1.2) | `environment.lock` | Closes the "works on my machine" gap. |
| `harness_version` (v1.2) | git SHA of harness checkout at run start | The runner itself can change behavior between runs. |
| `padding_corpus` (v1.2) | `design/fake_tool_corpus.jsonl` | Padded-N=1 filler entries (per `design/PADDING_STRATEGY.md §3`). Mutations change which fillers a padded trial sees. |

Non-path Config fields (`seed`, `N`, `runs_per_cell`, `model`, `host`, `tool_listing_strategy`, `include_padded_n1_control`, etc.) are hashed directly into the canonical Config; mutations change `run_id`.

**Identical resolved canonical Config → identical `run_id` → `tcrun resume <run_id>` is a no-op for completed cells.** Different in any field (Config OR artifact contents) → different `run_id` → fresh run, no resume.

Canonicalization: sort all keys, normalize all paths, drop comments. Use `json.dumps(..., sort_keys=True, separators=(',', ':'))`. `file_sha256` reads the file in binary mode and returns the lowercase hex digest.

`design/REPRODUCIBILITY.md §1` is the authoritative source for the 7-artifact chain. This identity rule implements it inside the Config layer; the artifact chain in REPRODUCIBILITY.md is the same hash function, viewed from the artifact side rather than the Config side. Either viewpoint produces the same `run_id`.

Second-best alternative: argparse-only without YAML. Rejected because YAML configs commit to version control and reproduce verbatim; CLI invocations are ephemeral.

---

## 9. Directory Structure

```
tool-crowding/harness/
├── SPEC.md                    ← this file
├── README.md                  ← quickstart + reproducibility instructions
├── pyproject.toml             ← Python deps (uv-managed)
├── requirements.lock          ← frozen versions
├── configs/
│   ├── mve.yaml               ← the 2-week MVE config
│   └── full-sweep.yaml        ← v2, post-MVE
├── tcrun/                     ← Python package
│   ├── __init__.py
│   ├── cli.py                 ← Click + dispatch
│   ├── config.py              ← Pydantic Config + run_id hashing
│   ├── tasks.py               ← TaskLoader
│   ├── servers.py             ← ServerPoolManager + pinning lookup
│   ├── servers_pinned.yaml    ← server SHAs/versions (generated from design/SERVER_POOL.md)
│   ├── orchestrator.py        ← cell loop + resume logic
│   ├── agent.py               ← Anthropic + MCP loop
│   ├── results.py             ← Pydantic schemas + JSONL writer
│   ├── retry.py               ← backoff + jitter helpers
│   ├── env.py                 ← EnvFingerprint capture
│   ├── oracles/
│   │   ├── __init__.py
│   │   └── pass_v1.py
│   └── migrations/
│       └── (empty until schema bumps)
├── tasks/
│   └── v1/
│       ├── queries.jsonl       ← 50 CoIR queries + ground truth
│       └── README.md          ← provenance of queries
├── results/
│   └── <run_id>/
│       ├── results.jsonl
│       ├── summary.json
│       ├── cells/
│       │   └── <cell_id>.json
│       └── traces/
│           └── <trial_id>.jsonl
├── server_cache/               ← optional: cached server installs (gitignored)
└── analysis/
    ├── dashboard.ipynb
    ├── readers/
    │   └── v1.py               ← schema_version=1.* reader
    ├── pareto.py
    ├── mpd.py
    └── README.md
```

Why this layout: separates code (`tcrun/`) from data (`tasks/`, `results/`) from analysis (`analysis/`). Each result `run_id` is self-contained and shareable as a zipped artifact (FAIR + ACM Reusable badge).

---

## 10. Anti-Over-Engineering Guardrails

A list of things I am NOT allowed to build in v1. Each has a simpler alternative noted.

- **No web UI.** If you find yourself wanting one: open `analysis/dashboard.ipynb`.
- **No database.** Postgres/SQLite/Mongo are banned. JSONL append log + `jq` queries are the database. If you find yourself wanting SQL: load into a Pandas DataFrame in the notebook.
- **No async framework beyond what asyncio gives you.** No `trio`, no `anyio` adapters, no `celery`, no `dramatiq`. If you find yourself wanting one: rethink whether you actually need concurrency at all (the bottleneck is the Anthropic API, not local compute).
- **No abstraction over the MCP client.** Use the official `mcp` Python package directly. If you find yourself writing a wrapper class: stop and inline the calls.
- **No plugin system.** Servers are a hardcoded list in `servers_pinned.yaml`. If you find yourself wanting plugins: edit the list.
- **No metrics service.** No Prometheus, no Grafana, no StatsD. If you find yourself wanting metrics: `tqdm` + `summary.json` + the notebook.
- **No Docker / k8s.** `uv venv` + `npx`. One process tree per cell. If you find yourself wanting containers: revisit only if a server requires it (e.g., Atlassian MCP) and Dockerize that one.
- **No DI framework.** Plain function calls and Pydantic objects. If you find yourself wanting `dependency-injector` or similar: stop; pass arguments.
- **No ORM.** Pydantic + JSONL is the data layer. If you find yourself wanting an ORM: see "no database" above.
- **No protobuf / Avro / Thrift / Cap'n Proto.** JSON Schema versioned via `schema_version`. If you find yourself wanting wire-format optimization: this is single-machine, single-user, 90 MB of data.
- **No retry-policy framework.** A 40-line `retry.py` is enough. If you find yourself reaching for `tenacity`: that's fine actually, it's 200 LOC and battle-tested; use it. But do not wrap it in your own abstraction.
- **No event bus / pub-sub.** The orchestrator calls functions directly. If you find yourself wanting message queues: research harness, not microservices.
- **No "engine" pluggability.** One model provider in v1 (Anthropic). Add OpenAI when the time comes; don't pre-build the abstraction.
- **No config-of-configs.** YAML config drives the run. If you find yourself writing a schema for the schema: stop.

---

## 11. MVE-Shaped Minimum

The smallest harness that satisfies the spec for the 2-week MVE.

| # | File | Estimated LOC | Responsibility |
|---|---|---|---|
| 1 | `tcrun/cli.py` | 120 | Click CLI + YAML loader + dispatch to orchestrator |
| 2 | `tcrun/config.py` | 180 | Pydantic Config + run_id/cell_id/trial_id content addressing |
| 3 | `tcrun/orchestrator.py` | 280 | Cell loop, resume logic, server-pool lifecycle |
| 4 | `tcrun/agent.py` | 380 | Anthropic API + MCP loop, tool-call logging, trial construction |
| 5 | `tcrun/results.py` | 220 | Pydantic Trial schema, JSONL writer, schema validation |
| (data) | `tcrun/servers.py` | 200 | ServerPoolManager (install, health-check, teardown) |
| (data) | `tcrun/tasks.py` | 80 | TaskLoader |
| (data) | `tcrun/oracles/pass_v1.py` | 60 | pass_criterion function |
| (data) | `tcrun/retry.py` | 40 | Backoff + jitter |
| (data) | `tcrun/env.py` | 50 | EnvFingerprint capture |
| (analysis) | `analysis/dashboard.ipynb` | ~250 equivalent | Notebook: load + N curves + Pareto + MPD |

**Code total: ~1,608 LOC.** Slightly over 1,500. Cut 100 LOC by combining `retry.py` + `env.py` into a single `utils.py`. Then ~1,500. Pass.

The MVE ships when these 5 files exist and the dashboard renders the go/no-go plot on real data.

---

## 12. Verification Checklist

20 boxes. Run before merging any harness PR to main.

- [ ] New code does not change results schema without a `schema_version` bump
- [ ] New code path has a corresponding entry in the Section 7 failure-mode catalog
- [ ] Re-running last week's MVE config with this code produces identical `run_id` and identical `pass`/`error_type` outcomes (within documented API non-determinism: ≤ 5% Hamming distance over 50 trials)
- [ ] Every result record passes Pydantic validation on read (analyzer test)
- [ ] `requirements.lock` is updated and committed
- [ ] No new dependency exceeds 2 MB in wheel size without justification
- [ ] No new dependency is unmaintained (last commit > 12 months)
- [ ] All new public functions have type hints
- [ ] All new public functions have at least one happy-path test
- [ ] All new failure paths log to the trace before raising / returning
- [ ] `tcrun --help` runs and lists the new flag (if any)
- [ ] `tcrun --config configs/mve.yaml` resolves to the same `run_id` as before, OR the diff is intentional and noted in the PR
- [ ] `tcrun status <prior_run_id>` still works (no regression on resume)
- [ ] Notebook `analysis/dashboard.ipynb` runs top-to-bottom on the prior MVE results without error
- [ ] No new MCP server added without a `servers_pinned.yaml` entry
- [ ] No `try: ... except Exception: pass` blocks added
- [ ] No `print()` calls in non-CLI code (use the trace logger)
- [ ] `tcrun verify <run_id>` re-runs 5 random trials and they pass schema validation
- [ ] Anti-over-engineering guardrails (Section 10) all still hold
- [ ] No new file exceeds 500 LOC

---

## Over-Engineering Attack

### Hostile critique (300 words)

This spec is a 5,000-word foundation document for a single-author 2-week research harness that will run roughly 1,400 trials. The author has already locked the research design, locked the server pool, and now locks the engineering principles. That's three "locked" documents before a line of code is written. The Pydantic Trial schema is 30 fields including five different IDs (run_id, cell_id, trial_id, oracle_version, harness_version), an EnvFingerprint with package_hash captured per trial, and per-tool-call audit records. The failure mode catalog has 20 entries with detection, recovery, and invalidation-status columns. The directory structure prescribes the analyzer's per-schema-version reader modules before the schema has ever evolved. The configuration system supports both CLI and YAML with content-addressed run_id derivation by SHA-256 hash. The MVE estimates 1,608 LOC and proposes cutting one utility file to reach 1,500. The 20-item verification checklist demands type hints, happy-path tests, dependency size limits, and "no print calls outside CLI code" for a one-person research harness that ships in two weeks. The schema evolution policy distinguishes MINOR from MAJOR bumps with migration directories pre-created. This is the engineering discipline of a 50-person platform team applied to a one-person evaluation script. The "no over-engineering" guardrails (Section 10) explicitly ban 14 specific anti-patterns, which means 14 anti-patterns are top-of-mind enough to warrant a guardrail, which means the author was at risk of building them. The opportunity cost is the paper itself: every hour spent on harness scaffolding is an hour not spent reading the 5 must-read papers, picking the Anthropic engineer for the Friday DM, or running the actual experiment. Strip the spec to a single file that loads CoIR, calls Anthropic, writes JSONL. Skip the schema versioning until v2. Ship in 5 days. Iterate.

### Rebuttal (300 words)

Concede: 20 verification-checklist items is excess for a 2-week MVE; trim to 8. The per-schema-version analyzer readers are premature; one reader is fine until the first MINOR bump. `tcrun verify` subcommand and `tcrun status` subcommand are nice-to-have, not Must.

Defend: the schema is load-bearing. The Trial record is the unit of measurement that the paper depends on. Skipping `schema_version` saves zero engineering time and creates a real risk that v1 results become unreadable when I bump fields after MVE. The version-addressed `run_id` is what makes the resume-from-crash logic correct; without it, a re-run with one different flag silently mixes data. The failure-mode catalog is load-bearing because research harnesses live or die on whether the experimenter can categorize failures. Without `error_type` as an enum, RQ2 (which failure mode dominates?) cannot be answered from the data; it would require post-hoc grep-archaeology three months later when reviewers ask.

The 14 anti-pattern guardrails are exactly the discipline that prevents the spec from becoming what the reviewer accuses it of. Naming them up front is the cheapest form of self-policing: the day I find myself reaching for Prometheus, I read Section 10 and stop.

The 5,000-word doc takes 90 minutes to write and is read once or twice during the build. The build is 8-10 days of coding. The doc-to-code ratio is fine. Compare against the alternative: rebuild the harness mid-paper because the schema couldn't evolve, or because resume logic was bolted on after the first crash, or because I couldn't tell which failures were measurement signal vs harness bugs. Those rebuilds cost weeks, not hours.

### Five concrete cuts if the MVE slips past 2 weeks

1. **Drop the `tcrun verify` and `tcrun status` subcommands**. The base `tcrun --config` and `tcrun resume <run_id>` are enough.
2. **Drop the EnvFingerprint.package_hash field**. Replace with a single `requirements.lock` commit per run.
3. **Drop the per-schema-version reader directory**. Single reader until the first bump.
4. **Drop the cell-level `summary.json`**. The analyzer can compute summaries on the fly from `results.jsonl`.
5. **Drop the padded-N=1 control from the MVE if time is critical**. Move it to v1.1 (the first post-MVE iteration). It is in the spec because it's load-bearing for the paper, but the MVE can validate the thesis without it.

---

## Kill-If-You-See-This

Five signals during implementation that mean "stop, you are building the wrong thing":

1. **You are writing a config schema for the config schema.** If `tcrun/config.py` exceeds 250 LOC, you are over-spec'd. The Config is meant to be a flat Pydantic model with 12 fields, not a tree of nested generators.

2. **You are wrapping the MCP client.** If `agent.py` contains `class MCPClientWrapper:` or `class ToolDispatcher:`, stop. Call the `mcp` library functions directly.

3. **You are building a retry-policy framework.** If `retry.py` exceeds 50 LOC, stop. `tenacity` does this; or 20 lines of `for attempt in range(5): try: ... except: time.sleep(2**attempt * (1 + random.random()*0.1))`.

4. **You are designing for "future model providers."** If `agent.py` has an abstract base class for "LLMProvider" with a v1 that only ever implements Anthropic, delete it. One provider, one file. Abstract when the second provider exists.

5. **You are writing a test that asserts on the Anthropic API's exact output.** The API is non-deterministic. Test that the agent loop calls the API, that the trace is well-formed, and that schema validation passes. Do not test that "the model picks GitHub_search for query 17"; that is the dependent variable of the experiment.

---

## Related

- `[[../RESEARCH_DESIGN]]` — the locked research design (this spec implements it)
- `[[../CLAUDE]]` — project operating manual and kill criteria
- `[[../design/SERVER_POOL]]` — the 15-server pool spec (pinning table feeds `tcrun/servers_pinned.yaml`)
- `[[../design/REPRODUCIBILITY]]` — 7-artifact identity chain consumed by the harness

---

## Changelog

### v1.2 — 2026-05-22 (Fri AM, harness build day 1)

Two amendments to the v1.1 spec, locked Fri AM of harness build day 1 (per FOUNDATION.md §6 item 2).

- **Item (a) applied — `run_id` extension to artifact content chain.** Section 8 Identity rule rewritten. Previous v1.0 derivation (`SHA-256(canonical_config_json)`) hashed Config paths but missed mutations to the files at those paths (servers_pinned.yaml, queries.jsonl, pass_v1.py, etc.), creating a silent-corruption hole: a YAML edit could change server SHAs while leaving `run_id` unchanged. v1.2 derivation augments the canonical Config by replacing every path-typed field with `{"path": ..., "sha256": file_sha256(path)}` before hashing. The 7-artifact chain in `design/REPRODUCIBILITY.md §1` is the binding source; the SPEC's Identity rule implements it from the Config side. M1 + M5 + Section 5 rule 2 updated to reference REPRODUCIBILITY.md and to add the v1.2 path-typed fields (`descriptions`, `endpoints`, `environment`, `harness_version`, `padding_corpus`).

- **Item (b) applied — padded-N=1 control padding strategy formalized.** Binding spec is `design/PADDING_STRATEGY.md` v1 (Fri AM). Three Trial-schema fields added (Section 4): `is_padded_n1: bool`, `fake_tool_invoked: bool`, `padding_skipped: str | None`. Schema is a MINOR bump per Section 4 schema evolution rules (new optional fields with sensible defaults; backwards-compatible read). The padded-N=1 condition uses neutral-tool-shaped fillers drawn from a length-matched corpus (`design/fake_tool_corpus.jsonl`), deterministic per `cell_seed`, within ±10% token-match of the unpadded-N=20 condition for the same `(query_id, ordering_seed)` pair. PILOT_V0.md's inline draft is superseded by PADDING_STRATEGY.md.

- **No new failure modes.** F18 (cache-leak detection) and F16 (model snapshot rotation) compose with v1.2 amendments without modification. PADDING_STRATEGY §6 adds a non-halting flag (`fake_tool_invoked`) rather than a new failure category.

- **No anti-over-engineering guardrails violated.** §10 guardrails reviewed against v1.2 changes: no new framework, no new abstraction layer, no new dependency. `file_sha256` is 5 LOC of stdlib `hashlib`.

### v1.1 — 2026-05-20 (same day as v1)

Audit follow-up after mentor review of v1. Three issues raised; verified against source text before applying.

- **Issue 3 applied (cache nonce scope).** Changed nonce scope from per-CELL to per-TRIAL (Section 5 rule 4). With per-cell nonce, trials 2-50 within a cell would share the system-prefix nonce and hit the Anthropic prompt cache on the system + tool-list prefix. Cached tokens are recorded under `usage.cache_read_input_tokens`, not `usage.input_tokens`. The original `context_input_tokens` field had no explicit definition, so a naive implementer recording `usage.input_tokens` alone would silently deflate the Pareto x-axis. Per-trial nonce + explicit definition of `context_input_tokens` (Section 4 schema comment) closes the gap. Cost impact: ~$35 over the MVE for foregone cache discount.

- **F18 rewritten.** With per-trial nonce, any cache-read or cache-creation activity in an API response indicates a nonce-generation bug. F18 now halts the run (was: "log but don't fail") and treats the in-flight trials as suspect.

- **`context_input_tokens` definition added.** Inline comment in the Section 4 schema: `total attended = usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens`. Belt-and-suspenders even with per-trial nonce.

- **Issue 1 not applied (MCP wrapper).** Mentor misread Section 10. The "no abstraction over the MCP client" rule and Kill Signal #2 are class-targeted ("wrapper class", "class MCPClientWrapper", "class ToolDispatcher"). A pure `classify_tool_event(exc: Exception) -> ErrorType` helper function is not a wrapper class; it does not intercept MCP calls, does not add cross-cutting concerns, and does not abstract away the mcp library's API surface. Failure-mode detection (F2, F3, F4, F11, F12) requires this classification regardless. No edit needed; the mentor conflated "any helper that touches mcp" with "abstraction over mcp."

- **Issue 2 not applied (variance / power).** Analysis delivered to chat. MDE table at ρ_BN=0.7 ranges from 10pp (n=5, ρ_w=0.3) to 14.5pp (n=3, ρ_w=0.9). At ρ_BN=0.5, MDE reaches ~16pp. n=5 saves only ~1pp over n=3 because m=50 queries is the binding constraint. Recommendation: a 200-trial pilot (~$30, half day) to estimate ρ_w and ρ_BN empirically before locking the MVE n. Devanshu decides.

### v1.0 — 2026-05-20

Initial spec lock.
