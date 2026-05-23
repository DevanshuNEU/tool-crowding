---
doc: Minimum viable pilot v0 design
locked: 2026-05-21 Thu PM
runs: 2026-05-23 (Saturday)
budget: 144 main trials + ~30 retriever-arm + ~50 RAG-MCP replication = ~225 total
inference_cost: ~$55-85
purpose: produce a clean signal in <24hr for Monday launch
binding: yes (predictions in PRE_REGISTRATION.md depend on this design)
---

# Saturday pilot — minimum viable scope

## Why 144 trials, not 1,400

The full study (per RESEARCH_DESIGN.md) calls for ~1,400 trials across 4 frontier models and a larger query set. The pilot tests whether the effect exists at all and whether the construct (FOUNDATION §1.0) survives basic falsification. Spending 1,400 trials before the pilot signal exists is premature optimization.

If the pilot shows a clean Scenario 1 or 4 result (per PRE_REGISTRATION.md), scale Sun-Mon. If Scenario 2 or 3, the pilot IS the v1 study and we ship Monday with the smaller dataset.

## Main matrix (144 trials)

| Axis | Levels | Reasoning |
|---|---|---|
| Model | Claude Sonnet 4.6, GPT-5-class | Sonnet 4.6 = primary (closest to Anthropic-DM-recipient model). GPT-5-class = robustness check on a different model family. Opus 4.7 and Gemini 2.5 deferred to full study because cost. |
| N (installed MCPs) | 1, 5, 10, 20 | Pre-registered prediction range. N=1 is the canonical baseline; N=20 is what Claude.ai users actually run; intermediates test the curve shape. |
| Condition | unpadded (real distractors), padded-N=1 (length-matched neutral filler) | Isolates discrimination from capacity per FOUNDATION §1.0 F1 falsification. THE load-bearing axis. |
| Trial repeats | n=3 per cell | ABC R.10 floor for reporting CIs. |
| Query subset | 3 queries from QUERY_SET_HYGIENE.md pilot subset | Small enough to run Saturday; large enough to escape single-query artifacts. Full set scales after pilot. |

Total: 2 × 4 × 2 × 3 × 3 = **144 trials**.

## Padded-N=1 control specification

**Binding spec: `design/PADDING_STRATEGY.md` v1 (locked 2026-05-22 Fri AM).** That document supersedes the inline draft that lived in this section through Thu PM 2026-05-21. The pilot is bound by PADDING_STRATEGY.md; do not deviate from it for the Saturday run.

Pilot-specific items (PADDING_STRATEGY.md does not specify these because they are pilot-only, not v1-binding):

- **Per-trial token-match tolerance:** ±10% of the matching unpadded-N=20 prompt's tool-definition token count (Sat AM gate item 2 below).
- **Corpus method for the pilot:** method B (LLM-generated with QA gate) is acceptable for Saturday given the time pressure; method A (hand-curated) is preferred for the v1 launch artifact. If method B is used, the generation prompt, seed, and rejection log are committed alongside `design/fake_tool_corpus.jsonl` before the Sat AM gate.
- **Pilot gate sanity check:** fake-tool-invocation rate in padded-N=1 trials must be < 10% on the pilot's 144-trial main matrix (per PADDING_STRATEGY.md §6). Higher than that means the fillers are not behaving as neutral and the construct's validity is compromised; halt and re-tune before scaling.

Why this matters for the pilot specifically: the padded-N=1 vs unpadded-N=20 comparison is the load-bearing falsification arm for FOUNDATION §1.0 F1. If the padding strategy is wrong, F1 cannot fire correctly and the pilot's go/no-go signal is contaminated.

## Retriever robustness arm (separate, ~30 trials)

Per task #4 reframing (Thu PM): retriever-OFF is primary; ONE robustness probe with retriever-ON top-k=5.

Run only at N=20 with retriever-ON (top-k=5) on Sonnet 4.6 with 3 queries × 3 repeats × 2 (with vs without padding for symmetry with main matrix) = ~18 trials. Round to 30 to allow re-runs on failures.

If retriever-ON closes the N=1 vs N=20 gap to <2pp: state LiveMCPBench's 50% retrieval-side-error finding as the open question; the retriever solves N-effects only when it correctly surfaces the relevant tools. Our v1 contribution becomes the controlled measurement of when it doesn't.

If retriever-ON does NOT close the gap: stronger result; the retriever workaround is insufficient at N=20 for code-retrieval, validating the harness as a measurement tool independent of retrieval.

**NOT a symmetric two-axis design.** Asymmetric: retriever-OFF curve (4 N levels) + 1 retriever-ON point (at N=20). Preserves trial budget.

## RAG-MCP replication cell (separate, ~50 trials)

Per task #5: external validity probe.

Run at N=10, 100, 1000 on Sonnet 4.6 with their setup (sampling with replacement permitted because they did it; we are testing model-class generalization of their finding). 3 N levels × 3 queries × 3 repeats × 2 conditions (with and without their RAG-MCP retriever) = 54, round to 50.

**Cap at N=1000.** Their N goes to 11,100, but our deep-verify (Thu PM) confirmed the registry has only ~4,400 servers, meaning above N=4,400 they are padded with duplicate schemas. Above N=1000 is below the duplicate threshold and tests the cleanest regime of their methodology.

Expected: our Sonnet 4.6 pass@1 at N=10 should be within 10pp of qwen-max-0125 at the same N if the effect generalizes across model classes. If tighter: external validity. If wildly different: model-class moderation finding (relevant for Scenario 4).

## Trial-level logging schema (per FOUNDATION §4 TC.4)

Per trial, log:
- `trial_id` (uuid)
- `run_id` (hash of servers_pinned.yaml + queries.jsonl + oracle script)
- `model`, `model_version`, `temperature`, `seed`
- `N`, `condition` (unpadded/padded), `retriever_state`, `query_id`, `repeat_idx`
- For every step: `(step_idx, server_called, tool_called, args_hash, response_summary, latency_ms, error_or_null)`
- Per trial: `pass_bool`, `pass_reason` (from oracle), `total_tokens_in`, `total_tokens_out`, `total_steps`
- `failure_mode` (per FOUNDATION §4.5 taxonomy, assigned by LLM-judge with human spot-check Sat PM)

This is the data substrate for everything downstream: per-server MPD, description-similarity correlation, failure-mode decomposition, length-vs-discrimination decomposition.

## Resource budget

| Component | Trials | ~Tokens/trial | ~Cost |
|---|---|---|---|
| Main matrix | 144 | 2-4k | $30-50 |
| Retriever arm | 30 | 2-4k | $8-15 |
| RAG-MCP replication | 50 | 2-4k | $12-20 |
| **Total** | **224** | | **$50-85** |

Wall-clock estimate: 4-6 hours with proper parallelization (8 concurrent trial runners). Aim to run between 9am-3pm Saturday.

## Pre-flight checklist (must clear by Friday EOD)

- [ ] Padded-N=1 padding strategy implementation (neutral-tool-shaped per above) — Fri PM
- [ ] Server pool installed and pinned per design/SERVER_POOL.md — Fri PM
- [ ] Trivial baselines wired (random-tool-call, no-MCP, single-server) — Fri PM
- [ ] PRE_REGISTRATION.md committed (this is locked) — Thu PM ✓
- [ ] Cost monitor + bounded retry policy live — Fri PM
- [ ] Trial logging schema above implemented and tested — Fri PM
- [ ] Oracle script tested on at least 1 query at N=1 — Fri PM
- [ ] LLM-judge prompt for failure-mode taxonomy drafted (per FOUNDATION §4.5) — Fri PM

## Sat AM go/no-go gate

Before kicking off the pilot, verify:
1. Oracle correctly grades at least one passing trial and one failing trial on the smoke-test data.
2. The padded-N=1 condition produces a prompt that is within 10% token-length of the unpadded-N=20 condition (the whole point of the control).
3. Logging captures the full step-level tool-call log on the smoke test.
4. The cost monitor halts the run if extrapolated cost exceeds $150.

If any of these fail, do not start the 144-trial run. Fix and re-gate.

## Related

[[PRE_REGISTRATION]] [[FOUNDATION]] [[SERVER_POOL]] [[../notes/ragmcp-100]] [[../notes/livemcpbench]] [[../notes/longfunceval-deep]] [[../notes/mcpverse-deep]] [[../RESEARCH_DESIGN]]
