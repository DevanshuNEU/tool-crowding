# Exploratory probe data (frozen figure provenance)

These four `trials.jsonl` files are the raw per-trial records of the exploratory
probes summarised in [`../../../FINDINGS.md`](../../../FINDINGS.md). They are committed
here, and only here, so that `analysis/plot_interaction.py` regenerates the figure from
a clean clone with **zero API spend**.

The full `results/` tree stays gitignored by FAIR policy (results are reproducible from
`run_id`, not committed). These specific records are the exception: they are the input
to a committed figure, so they are versioned as provenance. They are append-only and
must not be edited; re-running the probe would produce a new `run_id` directory under
the gitignored `results/`, not a rewrite here.

## What each directory is

All four probes share one task (a conceptual question about how the self-hosted
nutrition app `wger` syncs its ingredient database upstream; ground truth
`sync_ingredients_bulk_or_api_task`, introduced post the model cutoff). The grounded
route is `github_mcp`; `deepwiki` is the pre-registered **lure** distractor (a doc-Q&A
synthesizer), never a valid grounded answer route. All probes: Claude Sonnet 4.6,
temperature 0, retriever OFF, no-MCP baseline 0/5 (so any pass is tool-sourced).

| directory | run_id (prefix) | N | distractor pool | task framing | agent persona | trials |
|---|---|---|---|---|---|---|
| `count-null_n6-dissimilar_named_code-retrieval` | `a49638ca` | 6 | 5 dissimilar | target named | code-retrieval | 5 |
| `similarity-null_n4-similar_named_code-retrieval` | `534949d5` | 4 | deepwiki + git + fs | target named | code-retrieval | 5 |
| `ambiguity-only_n4-similar_ambiguous_code-retrieval` | `18a07436` | 4 | deepwiki + git + fs | ambiguous | code-retrieval | 5 |
| `interaction_n4-similar_ambiguous_neutral` | `c6d2dae3` | 4 | deepwiki + git + fs | ambiguous | neutral | 4 |

## The signal (verified against these files)

- Mis-routing (a tool call to a non-grounded server) is **0** in the first three
  conditions. Raw tool calls touch only `github_mcp`.
- It appears **only** in the fourth condition (ambiguous task + neutral persona):
  2 of 4 trials touched a distractor, and 1 of 4 solved through `deepwiki`
  (`solving_server == "deepwiki"`).

This is a falsification of the naive "more tools or similar tools breaks routing"
reading, plus a single directional signal for the framing x ambiguity interaction. The
interaction rests on **one** lure-solve event, which landed on ordering 0 (a position-bias
confound). It is exploratory, not a result. See `FINDINGS.md` and `../../../RESULTS.md`.
