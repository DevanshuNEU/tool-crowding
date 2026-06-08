# Caching modes (cache-cold vs cache-aware)

> Status: binding methodology decision (ADR). Added 2026-06-08. Decides how prompt
> caching interacts with the token x-axis and the cost of a sweep. **Decision: dual-mode.**
> Cache-cold stays the DEFAULT and the credibility/validation mode; cache-aware is an
> opt-in cost mode that preserves the honest x-axis. Not yet implemented (spec below);
> implementation is gated on (a) committing the prior agent.py work and (b) API credits
> for the output-neutrality validation. Re-hash run_id on implementation.

## Context

A single-task sweep costs ~$27 (138 trials × ~$0.20). ~59k input tokens/trial are
dominated by the tool definitions, which re-send on every turn because caching is
deliberately defeated: a 32-byte per-trial nonce in the system prompt keeps the prefix
cache-cold, and the F18 assertion (`agent.py::_assert_cache_cold`) HALTS the run if any
response reports `cache_read_input_tokens > 0` or `cache_creation_input_tokens > 0`.

Cache-cold exists for two stated reasons (REPRODUCIBILITY.md §3): (a) reproducibility
(prompt cache is opaque hidden state; same input can yield different output depending on
cache state), and (b) an "honest" token x-axis (measure the true context size the model
processed, not a cache-deflated count).

The cost research (2026-06-08, verified against live Anthropic pricing) found prompt
caching is the single largest lever: cache reads are 0.1× base input and the stable
system+tools prefix (~50k of the 59k) is reusable, so caching can cut input cost by ~67%
(≈ $27 → ≈ $9 for a full single-task sweep). The question is whether that is reachable
without sacrificing the two reasons cache-cold exists.

## Key insight: the honest x-axis survives caching

The Anthropic API returns the token breakdown as separate `usage` fields. The
uncached-equivalent context size is therefore recoverable analytically even when caching
is ON:

```
uncached_equiv = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
```

So reason (b) is NOT a reason to forbid caching: record `uncached_equiv` as the Pareto
x-axis and the x-axis is identical whether or not the cache was hit. Only reason (a),
reproducibility, is a genuine residual concern, and it is testable (see Validation).

## Decision: two modes, value-hashed into run_id

`Config.caching_mode: Literal["cache-cold", "cache-aware"] = "cache-cold"`

| | cache-cold (default) | cache-aware (opt-in) |
|---|---|---|
| Per-trial nonce | YES (32-byte, defeats cache) | NO per-trial nonce; the cacheable prefix is the system + tool definitions |
| `cache_control` markers | none | on the system + tools prefix (the stable, immutable part) |
| F18 assertion | HALT on any cache read/creation | inverted: cache hits are EXPECTED; record the breakdown, do not halt |
| Pareto x-axis (`context_input_tokens`) | `Σ input_tokens` (already uncached) | `Σ uncached_equiv` (mode-invariant) |
| Cost | full price every turn | ~0.1× on cached prefix reads after the first write |
| Role | credibility + validation; the headline confound control | cheap large sweeps once validated against cache-cold |

Cache-cold remains the default so the existing confound-control story (and the resume
bullet) is unchanged; cache-aware is never the silent default.

## Why mode must hash into run_id

Different caching mode = a different experiment identity (different prefix construction,
different nonce policy, different x-axis derivation). `caching_mode` is value-hashed by
`compute_run_id` (it is a non-path Config field, so it participates automatically once
added). This is an identity-rule addition; document it in the CHANGELOG alongside the
`orderings` addition (both 2026-06-08).

## Schema impact (v1.4, additive)

Record the breakdown so cache-aware runs are auditable and `uncached_equiv` is
recomputable:

- `Trial.cache_read_input_tokens: int = 0`
- `Trial.cache_creation_input_tokens: int = 0`

Both optional with default 0 (a MINOR bump per SPEC.md §4: add `_migrate_v1_3_to_v1_4`
setting both to 0; cache-cold trials legitimately carry 0). `context_input_tokens` keeps
its meaning (uncached context size); in cache-aware mode it is the sum of `uncached_equiv`
per turn, so the x-axis is comparable across modes.

## Implementation spec (for when this is built)

1. `config.py`: add `caching_mode` field (Literal, default "cache-cold"). Optional
   `TC_CACHING_MODE` env override mirroring the other runtime knobs.
2. `agent.py`:
   - nonce: emit the per-trial nonce only in cache-cold; in cache-aware, build the
     system+tools prefix without it and attach `cache_control: {"type": "ephemeral"}` to
     the last block of the tools/system prefix (render order is tools → system →
     messages, so the marker sits at the front).
   - assertion: branch `_assert_cache_cold`. cache-cold = current halt behavior;
     cache-aware = record `cache_read_input_tokens` / `cache_creation_input_tokens`,
     accumulate `uncached_equiv` into `in_tokens`, no halt.
   - token recording: in cache-aware, `turn_in = input + cache_read + cache_creation`
     for the x-axis; also persist the raw read/creation sums onto the Trial.
3. `results.py`: add the two v1.4 fields + the migration.
4. Tests ($0): mode default is cache-cold; `caching_mode` changes run_id; in a mocked
   cache-aware response with cache_read>0, no halt fires and `uncached_equiv` is summed
   correctly; cache-cold still halts on a cache hit.

## Validation gate (REQUIRED before trusting any cache-aware result; credit-gated)

Output-neutrality protocol: run K ≥ 5 cells in BOTH modes on the same config and assert
the per-trial outcomes match — `pass`, `solving_server`, `error_type`, and the ordered
sequence of `tool_calls[].server_called`. If they match, caching is a pure cost
optimization and cache-aware results are trustworthy; report the realized cache-hit rate
as a covariate. If they diverge, caching perturbs behavior → keep cache-cold for that
arm. This gate is the empirical answer to reason (a).

## Risks and mitigations

- **Cache changes outputs (reason a).** Mitigated by the validation gate above; until it
  passes, cache-aware numbers are not citable.
- **Cross-mode cost incomparability.** Mitigated by recording `caching_mode` in run_id +
  Trial and reporting the x-axis as `uncached_equiv` (mode-invariant).
- **Cache-hit-rate variance (TTL, API load).** It is real experimental variability;
  `cost_usd` and the token breakdown are recorded per trial, so it is auditable, not
  hidden. The x-axis (uncached_equiv) is unaffected by hit rate.
- **Headline confusion.** Default stays cache-cold; the paper's headline + the cache-cold
  fail-closed story are unchanged. Cache-aware is explicitly a cost mode for scale.

## Cost projection (verified pricing, labelled assumptions)

Assuming ~50k stable prefix of the ~59k input [ASSUMPTION; verify from one real trial's
breakdown]: cache-aware drops per-trial input from ~$0.177 to ~$0.042 (prefix at 0.1×,
~9k variable at 1×) → per trial ~$0.065 incl. output → ~$9 for the 138-trial full sweep,
~67% off. On the tiny `nsweep-minimal` (8 trials) the saving is smaller because the prefix
write (1.25×) amortizes over fewer reads; the lever pays off most on large sweeps.

Related: [[REPRODUCIBILITY]] (§3 cache-cold rationale), [[TOOL_RESULT_CAP]] (sibling
runtime knob), `harness/tcrun/agent.py` (F18), `~/DevVault/tool-crowding/cost-cutting-research-2026-06-08.md`.
