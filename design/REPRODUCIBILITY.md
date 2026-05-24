---
title: REPRODUCIBILITY.md — frozen pool + controlled selection formalization
status: v1 (locked 2026-05-22 Fri AM)
binds: ABC T.6 (Frozen environment at release) + TC.1 (server SHA + descriptions + schemas hashed into run_id)
supersedes: any conflicting ad-hoc reproducibility claims elsewhere in the project
related_docs: FOUNDATION.md §4.1 T.6, RESEARCH_DESIGN.md §3 (confounders) + §11 (responsible disclosure), QUERY_SET_HYGIENE.md (contamination, pending), SERVER_POOL.md (pool spec), harness/SPEC.md (implementation)
---

# tool-crowding Reproducibility Spec v1

The benchmark is reproducible if, and only if, three properties hold:

1. **Frozen environment.** Every artifact that influences a trial outcome is pinned by content-addressable hash, and the hashes chain into a single `run_id` that names the experimental release.
2. **Controlled selection.** Per-cell distractor sampling is deterministic given `(run_id, model, N, query_id, ordering_id)`. No live registry calls during trial execution.
3. **Re-run verifiability.** A third party with the repo, the frozen Docker image, and API credentials can re-execute any trial and produce a byte-identical trace modulo the documented set of inherently-stochastic dimensions.

This document binds the harness build. Before any trial runs, `harness/preflight.py` MUST verify all three properties or abort.

The load-bearing departure from RAG-MCP, the closest published prior art: their high-N regime drew distractors from `mcp.so` at runtime, which made the experiment unreproducible the moment `mcp.so` changed; the same design also forced sampling with replacement above N=4,400 (registry has ~4,400 servers; sweep tops at 11,100), padding the prompt with duplicate schemas rather than adding distinct tools. tool-crowding closes both gaps.

---

## 1. What gets hashed into `run_id` (the chain)

```
run_id = sha256(h_pool || h_descriptions || h_queries || h_oracles || h_endpoints || h_environment || h_harness)
```

| Artifact | File | What it pins | Why it matters |
|---|---|---|---|
| Server pool | `pool/servers_pinned.yaml` | Per server: name, git SHA (source-built), npm/pip version (installable), install command, reachability tier, COI tag | RAG-MCP failure mode: unpinned registry drifted; our pool cannot. |
| Tool descriptions + schemas | `pool/descriptions.json` | Per server, captured at install: each tool's name, description, JSON schema verbatim | TC.1 requirement: description drift changes which tools compete for selection. |
| Query set | `tasks/v1/queries.jsonl` | 50 queries (v1), each with: query text, ground-truth target, difficulty-quartile tag, contamination-tier tag | SWE-Bench Pro pattern. Closes ABC R.1 + R.3. |
| Oracle | `oracles/pass_v1.py` | The pass-rate scoring function source | If the oracle changes, prior trial results are no longer comparable. |
| Model endpoints | `models/endpoints.json` | Per model: API URL, checkpoint identifier (e.g., `claude-sonnet-4-6-20260131`), temperature, max_tokens, system-prefix template, nonce-policy | Pinning the API call shape. Model checkpoints can silently roll on vendor side; see §3. |
| Environment | `environment.lock` | Docker image SHA, OS info, Python version, MCP SDK version, key library versions | Removes "works on my machine" failures. |
| Harness | `git rev-parse HEAD` at release | The harness code itself | The runner that orchestrates trials. |

All seven hashes are written into a single line in `pool/RELEASE.json`. That line, hashed, IS the `run_id`. Any artifact mutation forces a new `run_id`. There is no backwards-compatibility mode.

### Boundary condition: what about live data sources?

Some artifacts CANNOT be pinned to a fixed hash without losing semantic meaning:

- **GitHub MCP** queries hit the live GitHub API; results depend on the state of GitHub at call time.
  - Mitigation: pin queries to repos + commits that are immutable in recoverable history (GitHub Archive Program, or local clones at frozen SHAs). For query types that don't admit this, document the drift window and restrict collection to a 48-hour window.
- **Web-fetch / Brave Search distractors** are live.
  - Acknowledged drift. Distractors do not influence ground truth — only the size of the prompt and which servers crowd. Mitigation: snapshot per-trial tool-call traces; the trace itself becomes the audit artifact.
- **Anthropic prompt cache** is opaque hidden state. Same input + same temperature can produce different outputs depending on cache state.
  - Mitigation: vary system-prefix nonce per trial (per RESEARCH_DESIGN.md §3 + SPEC v1.1).

Section 3 enumerates each unpinnable dimension and its compensating control.

---

## 2. Controlled selection (the deterministic IV mechanism)

For each cell `(model, N, query_id, ordering_id)`, the harness derives a deterministic seed:

```
cell_seed = sha256(run_id || model || N || query_id || ordering_id)
```

Distractor selection within a cell:

```python
rng = SeededRNG(cell_seed)
distractor_pool = frozen_pool - {primary_for_query}
distractors = rng.sample(distractor_pool, N - 1)
final_ordering = rng.shuffle([primary_for_query, *distractors])
```

Trial seed for any per-trial randomness inside the model call (none expected at T=0, but defensive):

```
trial_seed = sha256(cell_seed || repetition_id)
```

**Properties:**
- Same `run_id` + same `(model, N, query_id, ordering_id)` produce the same distractor set and ordering. Deterministic.
- Different `run_id` produces different seeds across the board. Results across `run_id`s are not directly comparable; they are different experiments.
- 5 paired random orderings per cell (ordering_id ∈ 0..4) — pre-registered in RESEARCH_DESIGN.md §3.

**No live registry calls during trial execution.** The pool is locked. Distractor selection is RNG-driven from the frozen pool. This is the load-bearing reproducibility property — and the one prior art directly fails on.

### Padded-N=1 case

The padded-N=1 condition uses the same cell_seed mechanism. The distractor count is zero; instead, the prompt is padded with neutral-tool-shaped descriptions to match the token count of the unpadded-N=20 condition. The specific padding strategy (which neutral descriptions, how token-matched) is v1.2 SPEC item b — separate doc.

---

## 3. Unpinnable dimensions and their compensating controls

Some sources of variance cannot be hash-pinned. We control them explicitly.

| Dimension | Why unpinnable | Compensating control | Reportable proxy |
|---|---|---|---|
| Model API checkpoint roll | Vendor may silently update the model behind a stable identifier | Capture `model_api_response_fingerprint` per trial (Anthropic exposes via headers; OpenAI exposes `system_fingerprint`). Flag mid-collection-window shifts. Re-collect affected cells or version-bump. | Per-cell fingerprint distribution, supplementary table. |
| Anthropic prompt cache | Opaque hidden state affecting output and latency | Unique system-prefix nonce per trial forces cache-cold. | Latency p50/p95 per cell with nonce variation as covariate. |
| Live MCP tool responses (GitHub MCP, Brave Search, etc.) | Underlying API state drifts | Snapshot per-trial tool-call traces. Distractors do not influence ground truth. For primary servers, pin to immutable-history queries or document drift window. | Trial trace file is the audit artifact. |
| API rate limits, intermittent 5xx | Stochastic from vendor side | T.2 (bounded-retry policy, fail-closed on persistent unavailability). Log every retry with timestamps. | Retry rate per cell, supplementary. |
| Time-of-day / API load variance | Vendor-side latency varies | Distribute trials uniformly across a 48-hour collection window per RESEARCH_DESIGN.md §3. | Time-of-day stratification of latency, supplementary. |
| Stochastic tool servers (rare) | Some MCPs use random tie-breaking, e.g., embedding-based retrievers with non-deterministic ANN | Audit at install; for any server with intrinsic randomness, set a per-server config seed and pin it in `servers_pinned.yaml`. If no seed knob exists, document and disclose. | Per-server determinism tier in `SERVER_POOL.md`. |

A dimension that lands in this table is by definition not part of the `run_id` hash. It is part of the experiment, not part of the release identity. Updates to a compensating control require a v1.x bump; updates to which dimensions live here require a major version bump (v2.x).

---

## 4. Re-run protocol (the "anyone can reproduce" guarantee)

Three levels of reproducibility, each with a published verification target.

### 4.1 Single-trial replay

```bash
$ tool-crowding reproduce <trial_id>
```

The harness:
1. Reads the trial result file at `data/trials/<trial_id>.json`.
2. Verifies that its embedded `run_id` matches the current `pool/RELEASE.json`'s computed `run_id`.
3. Reconstructs `cell_seed` from `(run_id, model, N, query_id, ordering_id)`.
4. Re-executes the trial against the same model endpoint and pinned servers.
5. Compares output to the committed trial log.

**Pass criteria:** tool-call sequence matches byte-for-byte, modulo the unpinnable dimensions in §3.

**Replication-rate-as-meta-metric:** the v1 release notes report the empirical replication rate on a random 5% sample of trials. Target: **≥ 99%.** If empirical replication < 99%, the harness has uncontrolled randomness we have not catalogued; do not ship until investigated and either (a) catalogued in §3 with a compensating control or (b) eliminated.

### 4.2 Cell replay

```bash
$ tool-crowding reproduce-cell --model <m> --N <n> --query <q>
```

Re-executes all 5 ordering trials in the cell. Aggregates pass-rate. Compares to the cell's committed aggregate. **Pass criteria:** within paired-bootstrap 99% CI of the committed aggregate.

### 4.3 Headline N-curve replay

```bash
$ tool-crowding reproduce-headline
```

Re-executes the primary N-curve cells: Sonnet 4.6 × N ∈ {1, 5, 10, 15, 20} × 50 queries × 5 orderings × 5 primary servers = 6,250 trials.

**Target:** a third party with the repo + frozen Docker image + API credentials reproduces the headline N curve within **24 hours of compute and < $200 API budget.** This target is mirrored in RESEARCH_DESIGN.md verification checklist.

---

## 5. Failure modes and detection

| Failure | Detection | Response |
|---|---|---|
| Server SHA drift | Daily smoke test (`harness/smoke/<server>.py`) computes current SHA + description hash, compares to pinned values | Halt collection. Bump v1.x or freeze new `run_id`. |
| Schema drift on a pinned server | Tool description / JSON schema captured at install differs from currently-advertised schema | Halt. Pin new descriptions. Recompute `run_id`. |
| Model checkpoint roll | `model_api_response_fingerprint` shifts mid-collection-window | Flag. Re-collect affected cells. Document in CHANGELOG. |
| Oracle bug discovered post-release | Issue / community report | Patch in v1.1; re-score all trials (the trial traces are pinned; only the oracle changed); publish v1.1 numbers alongside v1.0 immutably. |
| Query contamination discovered post-release | 5-gram check or community report | If isolated: drop query + re-aggregate. If systemic: v2.x cycle, draw from held-back 20% tier (TC.9). |
| Trial result missing `run_id` | Preflight check at result emission | Reject trial. Investigate harness bug. |

### Halt criteria

Any of these aborts the collection run before further trials execute:

- `run_id` mismatch between any artifact and `pool/RELEASE.json`
- Smoke test failure on any pinned server
- Model API returning a different `system_fingerprint` mid-collection
- Greater than 5% trial-emission failures in a rolling 100-trial window

---

## 6. Versioning policy

- **v1.0** (Mon May 25 public launch): the initial frozen release. `run_id` locked. Public.
- **v1.x** (methodology fixes): oracle patches, smoke-test additions, compensating-control tightening. Backwards-comparable trial traces because the `run_id` does not change semantically — same pool, same queries, same model endpoints. Patch number documents the fix.
- **v2.x** (scope expansion): new servers, new queries, new models, new tasks. New `run_id`. Documented migration notes. Held-back 20% query tier (TC.9) reserved for v2 re-eval to defend against contamination of the public v1 tier.

A bumped `run_id` is a hard break. Results across `run_id`s are not aggregated. The public leaderboard names the `run_id` next to every row.

---

## 7. What this document does NOT cover

- **Contamination defense.** See `QUERY_SET_HYGIENE.md` (5-gram check, GPL filter, post-cutoff queries, three-tier access). Pending Fri PM.
- **COI sensitivity.** See `RESEARCH_DESIGN.md §11` (leave-OCI-out analysis).
- **Responsible disclosure.** See `RESEARCH_DESIGN.md §11` (7-day pre-disclosure to maintainers).
- **Statistical analysis.** See `RESEARCH_DESIGN.md §4` (MPD, paired bootstrap, Bonferroni).
- **Padded-N=1 padding strategy.** See v1.2 SPEC item b (next doc).

---

## 8. How this binds harness day 1

Mandatory implementation gates before the harness runs any pilot trial:

1. **`harness/preflight.py`** MUST verify all seven hashes and assemble `run_id`. Aborts on mismatch.
2. **`harness/seed.py`** MUST implement `cell_seed = sha256(run_id || model || N || query_id || ordering_id)` exactly as §2 specifies.
3. **`harness/smoke/<server>.py`** for each pinned server MUST be runnable and produce a SHA + description hash for comparison against pinned values.
4. **Trial result schema** MUST embed `run_id`, `cell_seed`, `trial_seed`, and `model_api_response_fingerprint` (where exposed). Results without these fields are rejected at emission time.
5. **CI** MUST run `tool-crowding reproduce` on a known committed trial as part of the release pipeline. Failure blocks release.

These five gates are how the harness build inherits the reproducibility spec without restating it.

---

## 9. Open questions for harness build (resolve during day 1-2)

1. **Where do server smoke tests live and when do they run?** Proposal: `harness/smoke/<server>.py`, run by cron daily during the collection window; pre-trial smoke check on every fresh harness invocation.
2. **How do we handle legitimate server upgrades mid-collection?** Proposal: freeze v1.0 numbers, open v1.1 with a clear CHANGELOG migration note. Do not aggregate v1.0 and v1.1 cells. Re-collect affected cells under v1.1 `run_id`.
3. **API price changes during collection?** Cost is logged per trial as an observed value, not pinned. Document in limitations.
4. **Vendor adds a "fingerprint not available" mode mid-collection?** Halt that model's collection; document; do not silently lose the fingerprint check.

These four go in `harness/SPEC.md` as items to resolve during the harness build, not blocking this doc.

---

## 10. Why this scope, not more

This doc deliberately does NOT cover contamination, COI, statistical analysis, or padded-N=1 padding strategy. Each lives in its own file. The reason: reproducibility, contamination, and statistical analysis are three orthogonal axes that conflate when bundled into one doc. ABC treats them as three of its four primary dimensions (T = task validity, O = outcome validity, R = reporting; reproducibility lives across T and R). Keeping them separate makes each independently auditable by a reviewer, and makes the binding-document hierarchy in FOUNDATION.md §4 (T / O / R / TC) clean to reference.

---

## Related

[[FOUNDATION]] [[../RESEARCH_DESIGN]] [[SERVER_POOL]] [[../harness/SPEC]] [[QUERY_SET_HYGIENE]] [[PILOT_V0]] [[PRE_REGISTRATION]] [[../notes/abc-best-practices]] [[../notes/swe-bench-pro]] [[../notes/swe-bench-illusion]] [[../notes/ragmcp-100]]
