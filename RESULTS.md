# Results

> **STATUS: EXPLORATORY (probe phase).** No pre-registered, confirmatory results exist
> yet. What follows is directional signal from cheap falsification probes, not effect
> sizes. Any headline claim requires the pre-registered pilot in
> [`design/PRE_REGISTRATION.md`](design/PRE_REGISTRATION.md), which has not been funded
> or run.

The full writeup, setup, per-probe table, and threats-to-validity live in
[`FINDINGS.md`](FINDINGS.md). This file is the one-line entry point.

## Headline (exploratory)

Across four cheap probes on one post-cutoff task (Claude Sonnet 4.6, temperature 0,
retriever OFF, n=4-5 per condition):

- **Server count does not degrade tool routing.** N=6 dissimilar distractors -> 0
  mis-routing.
- **Surface similarity alone does not either**, when the target is named in the task.
- **Task ambiguity alone does not either**, under a code-retrieval agent persona.
- Mis-routing appears **only** under the interaction of an **ambiguous task and an
  under-specified (neutral) agent persona**: 2/4 trials touched a distractor and 1/4
  solved through the `deepwiki` lure.

The figure is [`figures/interaction_mis_routing.png`](figures/interaction_mis_routing.png),
regenerated at $0 from the committed probe records (see the README's "Reproduce the
exploratory figure" step).

## Pre-registered gate: the no-MCP floor holds on the Stage-1 anchors (2026-06-11 UTC)

Before any confirmatory Stage-1 spend, the pre-registration requires a no-MCP floor: with no tools at all, the model must not be able to name the target function, so that any later pass is tool-sourced. The gate was run on the 5 named Stage-1 anchors (paperless-ngx, calibre, weblate, ansible, synapse) at the Stage-1 temperature of 1.0, Claude Sonnet 4.6. Raw records: [`harness/analysis/gate_data/`](harness/analysis/gate_data/).

- **No tools (N=0): 0 of 5 passed.** In all 5 trials the model gave up (`agent_gave_up`) rather than inventing a symbol. The gate holds.
- **Positive control (N=1, `github_mcp` only): 2 of 2 completed trials passed** (calibre, ansible). The other 3 ended in `api_fault` (two 429 rate limits at 30,000 input tokens per minute, one connection error), so they carry no retrieval verdict. This arm checks that the anchors are retrievable at temperature 1.0; it is not a score for the server.
- **Where the floor leaked.** An earlier 2-trial smoke run on a different task passed with no tools: its target, `visit_call` in pylint, can be guessed from naming convention ("visits Call nodes" suggests `visit_<NodeType>`). The Stage-1 anchors were chosen to have names that cannot be derived that way, and the gate run above is the check that this worked.

Spend: $1.50 for the gate run and $0.21 for the smoke run. This is a gate check, not a result: it reports no Marginal Performance Delta and no per-server comparison, and the confirmatory Stage-1 run has not happened.

## What this is and is not

- It **is** a rigorous falsification of the naive "more tools / similar tools breaks
  selection" hypothesis, and the evidence that motivated the pivot to a framing x
  ambiguity design.
- It is **not** an effect size. The interaction rests on a single lure-solve event that
  landed on ordering 0 (position bias is an unmodelled confound), one task, one model.

## Limitations

- n = 4-5 per condition; one query; one model; temperature 0 (deterministic per ordering).
- The framing factor was post-hoc, not in the original pre-registration.
- `deepwiki` responses were live, not snapshot-pinned (a hosted-server non-determinism
  vector).
- The crowding-axis curve over N is wired (`harness/configs/nsweep-minimal.yaml`) but not
  yet run; it is gated on API credits.

## Confound controls in place

Even at probe scale, measurement integrity is enforced, not assumed: prompt caching is
defeated per trial by a 32-byte system-prompt nonce **and** a fail-closed assertion that
halts the entire run if any response reports a cache read or cache-creation token;
temperature and seed are pinned; raw uncached input tokens are recorded per trial. See
`harness/tcrun/agent.py` (F18) and `design/REPRODUCIBILITY.md`.
