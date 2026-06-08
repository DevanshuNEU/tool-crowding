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
