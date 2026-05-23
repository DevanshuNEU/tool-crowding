---
title: CodeRAG-Bench N-Sweep — scoping decision
status: DEFERRED (not in tool-crowding v1)
decision_date: 2026-05-21
revisit: post-launch (Week 3 retro)
---

# CodeRAG-Bench N-Sweep — Scoping Decision

## The proposed experiment

Take CodeRAG-Bench's `eval_corpora_ablations.py` "All" condition (top-1 from each of 5 sources, fixed) and turn it into an N-sweep: N=1, 2, 3, 5, 10 sources. Use their corpora, their canonical-doc oracle, run on 3 generators (GPT-4o, Claude 4.6, one open-source).

**Headline claim if it lands:** "CodeRAG-Bench fixed N=5; we swept N and pass-rate peaks at N=3, then degrades. Even passive multi-source RAG exhibits tool-crowding."

## Feasibility audit (after inspecting their repo)

Repo: `github.com/code-rag-bench/code-rag-bench` — 169 stars, 19 forks, 10 open issues, 9 commits on main.

| Asset | Available? | Implication |
|---|---|---|
| Multi-source aggregation code | YES (`eval_corpora_ablations.py`) | Reusable |
| BM25 + dense indexes pre-built | **NO** | Must re-index from 25M-doc corpus |
| Canonical-doc annotations | **NO** (must format BEIR-style from raw data) | Hours of data wrangling |
| HuggingFace datasets | YES (`huggingface.co/code-rag-bench`) | Saves data acquisition |
| Generation + execution eval | YES (in `generation/`) | Reusable |
| GPU requirement | YES | Need at least 1x A100 for indexing |
| Documentation quality | LOW (10 unresolved issues; 9 commits) | High debug risk |
| Last activity | sparse (small repo, no recent commits in extracted window) | Likely unmaintained |

## Realistic cost

| Phase | Estimate |
|---|---|
| Re-indexing 25M-doc corpus (BM25 + 3 dense embedders) | 1-2 days GPU time, ~$500 cloud |
| Canonical-doc annotation pipeline rebuild | 1-2 days human time |
| N-sweep harness modifications | 1-2 days |
| Running N-sweep across 3 generators × 5 N levels × ~500 tasks × 3 trials | 1-2 days runtime, $2-5K API |
| Analysis + write-up | 2 days |
| **Total** | **~1.5-2 weeks, $2.5-5.5K** |

Earlier estimate ("2-3 days, <$1K") was wrong. Repo is less reusable than the README implies.

## What this experiment WOULD add to tool-crowding v1

- An additional empirical data point that "more sources past K=3-5 hurts" generalizes beyond agent multi-MCP into passive RAG.
- A direct, citeable apples-to-apples comparison against the closest published prior art.
- A "we re-ran their benchmark with rigor they didn't apply" narrative.

## What it WOULD NOT add

- The core tool-crowding contribution (agent-decides multi-MCP) is conceptually different. CodeRAG-Bench has no agent-tool-choice loop. An N-sweep on their pipeline is "RAG-with-more-sources," not "MCP-with-more-servers."
- The launch story doesn't need it. The Cursor 29.44 → 26.41 result from MCP-Universe (Section 4.6) is the better opening anecdote.
- Statistical power: their tasks are smaller-N per domain than ours. Adding their corpus doesn't strengthen our headline numbers.

## Decision: DEFER

**Not in v1.** Launch Sun May 25 is non-negotiable. The CodeRAG-Bench N-sweep would push launch to at least June 3 and burn the BIP-cadence + Anthropic-DM sequencing. Not worth it.

**Revisit at Week 3 retro (2026-06-07).** If v1 lands well and pulls in feedback that demands "show me the cross-paradigm generalization," this becomes a v1.1 supplementary experiment or a separate paper:
- Title candidate: "Passive RAG crowds too: extending tool-crowding methodology to retrieval-only pipelines"
- Scope: 1 paper, separate launch, 2-week effort

## Trigger conditions to re-prioritize

Move this back into scope IF:
- Launch feedback explicitly asks "does this generalize past MCP?"
- A reviewer or competitor publishes a passive-RAG N-sweep first (citation race)
- Tool-crowding v1 lands flat and we need a follow-up artifact within 3 weeks

## What we DO need from CodeRAG-Bench for v1

We already extracted what matters: methodology gaps (no agent loop, no description competition, no fault injection, no Claude), counterintuitive findings (top-5 optimal, BM25 surprisingly competitive, code-specific embedders don't dominate), and citation hooks. These go in the paper's Related Work section, not as a new experiment.

## Related

[[../notes/coderag-bench]] [[../RESEARCH_DESIGN]] [[ANTHROPIC_HARNESS_LITERATURE]] [[../../strategy/week-1/2026-05-21]]
