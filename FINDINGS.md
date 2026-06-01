# Exploratory Findings — probe phase (2026-05-31)

> **STATUS: EXPLORATORY.** These are small-N probes (4–5 trials each, one query, one
> model, temperature 0) run to detect signal and falsify cheaply *before* the
> pre-registered pilot. They are **not** pre-registered results and report **no**
> effect sizes. Any headline claim requires the factorial pilot described below,
> pre-registered before confirmatory data (per `design/PRE_REGISTRATION.md`).

## TL;DR

Across four cheap probes the headline moved twice, and landed somewhere more
interesting than where it started:

1. **Server count** does not degrade tool selection (N=6 dissimilar distractors → 0 mis-routing).
2. **Surface tool similarity** with a *named* target does not either (N=4 similar distractors → 0 mis-routing).
3. **Task ambiguity alone**, with a code-retrieval agent persona → still 0 mis-routing.
4. **Task ambiguity + a neutral agent persona** → the lure bites: a doc-Q&A distractor solved the task, and distractor exploration rose from 0/5 to 2/4 trials.

The operative variable is an **interaction: task-target ambiguity × agent framing.**
Frontier tool discrimination is robust *unless* the task is ambiguous about its
target **and** the agent's role is under-specified. Either anchor — a code-retrieval
persona, or a target named in the query — restores clean discrimination.

This contradicts a naive "too many tools breaks selection" reading and is not the
same effect as prior art measures (see below).

## Setup

- **Task:** a conceptual question about how a self-hosted nutrition app keeps its
  ingredient database synced upstream. Ground truth: `sync_ingredients_bulk_or_api_task`
  in `wger-project/wger` (AGPL-3.0), introduced 2026-04-10 (post the model training
  cutoff). The query never names GitHub, a file, or the repo.
- **Grounded route:** `github_mcp` (`search_code` + `get_file_contents`). **Lure:**
  `deepwiki` (`ask_question`, a doc-Q&A synthesizer that answers in one call and, when
  asked, returns the exact symbol). `deepwiki` is a **pre-registered lure distractor**,
  never a valid grounded answer route.
- **Pre-run gates (all passed):** 5-gram contamination 0/8 public hits; no-MCP baseline
  0/5 (the model cannot name the symbol from memory and could not even identify the app);
  deepwiki lure confirmed live (fresh index, returns the symbol).

## The four probes

| run_id | distractors | task | agent persona | lured (deepwiki solve) | trials touching a distractor |
|---|---|---|---|---|---|
| `a49638ca` | 5 dissimilar (N=6) | github-named | code-retrieval | 0 | 0/5 |
| `534949d5` | deepwiki+git+fs (N=4) | github-named | code-retrieval | 0 | 0/5 |
| `18a07436` | deepwiki+git+fs (N=4) | **ambiguous** | code-retrieval | 0 | 0/5 |
| `c6d2dae3` | deepwiki+git+fs (N=4) | **ambiguous** | **neutral** | **1/4** | **2/4** |

Under the neutral persona the model called `deepwiki` and solved through it on one
ordering, and touched `filesystem_mcp` on another before recovering — versus zero
distractor calls in 57 tool calls under the code-retrieval persona on the identical
task and server set.

## Instrument

Schema v1.3 adds **`Trial.solving_server`** — the server whose tool result carried the
answer symbol — and **`ToolCall.result_contained_target`**. This makes mis-routing a
first-class measured signal: `deepwiki` = lured, `github_mcp` = grounded, `null` on a
pass = a parametric/no-retrieval pass (the no-MCP baseline rules this out here). Without
it, a synthesizer-sourced "pass" would be indistinguishable from grounded retrieval.

The agent persona is runtime-swappable via `TC_SYSTEM_PROMPT_VARIANT`
(`code-retrieval` | `neutral`), resolved into the Config and hashed into `run_id`.

## Threats to validity (why this is a signal, not a result)

- n = 4–5, one query, one model, temperature 0 (deterministic per ordering). The single
  lure-solve landed on ordering 0; ordering/position bias is a plausible partial driver
  and is itself worth measuring.
- `deepwiki` responses are live, not snapshot-pinned — a hosted-server non-determinism
  vector (to be added to `design/ADVERSARIAL_AUDIT.md`).
- The framing factor is **post-hoc**, not in the original pre-registration.

## Next: the pre-registered factorial pilot

A 2×2, locked before confirmatory data:

- **Factor A** — agent persona: `{code-retrieval, neutral}`
- **Factor B** — task framing: `{target-named, ambiguous}`
- n ≥ 10–20 per cell at temperature > 0; paired-bootstrap CIs (B = 10,000); ≥ 5–10
  queries across low-traffic post-cutoff repos; multiple frontier models.
- Primary metric: solving-server attribution (SSA) + distractor-call rate.

**Prior art to distinguish.** MetaTool (ICLR 2024) measures single-step Correct Selection
Rate over a synthetic tool list with the target name removed; MCP-Atlas (2026) measures
coverage over same-server distractors in a live setting. Neither factorizes count vs
similarity vs the framing×ambiguity interaction, and neither carries the two negative
controls (count-null, named-similarity-null) that make the interaction attributable here.
