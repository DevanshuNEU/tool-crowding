---
title: tool-crowding Research Design v1
date_locked: 2026-05-20
status: locked; awaiting MVE
canonical_source: ~/.claude/plans/no-so-create-a-dreamy-pillow.md (origin); this file is the vault-living copy
---

# tool-crowding: Research Design v1

> NeurIPS-grade design document. Locked 2026-05-20 after Day-1 pivot from killed `mcp-bench` plan. This file is the vault-living copy of the approved plan.

## Context

Day 1 plan to spec `mcp-bench` was killed mid-day after deep validation surfaced that (a) `mcp-bench` is taken by Accenture (arXiv 2508.20453, 484 stars, NeurIPS 2025), (b) at least 5 serious model-axis MCP benchmarks already exist (Scale MCP-Atlas, MCP-Universe, MCPMark, MCPAgentBench, MCP-Bench), and (c) Digital Applied published a 100-server stress test in April 2026.

This document is a NeurIPS-reviewer-defensible research-design package written before any harness code, capturing the binding methodology, the falsification conditions, and the four pre-registered scenario abstracts.

**Scope of this document:** the 11 required design sections plus a built-in adversarial self-critique (Reviewer-2 Attack). Nothing else.

## Repository layout

```
tool-crowding/
├── RESEARCH_DESIGN.md        # this file (canonical 11-section design)
├── CLAUDE.md                 # project operating manual
├── notes/                    # 11 paper-reading deep notes
├── research/                 # 5 landscape audits
├── design/                   # 10 binding methodology docs + fake-tool corpus
│   ├── FOUNDATION.md
│   ├── PRE_REGISTRATION.md
│   ├── PADDING_STRATEGY.md
│   ├── QUERY_SET_HYGIENE.md
│   ├── REPRODUCIBILITY.md
│   ├── SERVER_POOL.md
│   ├── MODEL_VERSIONS.md
│   ├── ADVERSARIAL_AUDIT.md
│   ├── CHART_LAYOUT.md
│   ├── PILOT_V0.md
│   └── fake_tool_corpus.jsonl
└── harness/                  # tcrun Python package + tests
    ├── SPEC.md
    ├── tcrun/
    ├── tests/
    └── pyproject.toml
```

## Quantitative-claim corrections (Phase 1 verification results)

Before the design proper. Five claims from the original prompt context were verified; one is misquoted.

| Original claim | Verified value | Source |
|---|---|---|
| Anthropic "30-50 tools" | 30-50 verified (range, not single number); engineering doc not peer-reviewed | [platform.claude.com tool-search-tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) |
| Chroma "Context Rot, 18 LLMs" | Verified; tech report July 2025; 20-50% drop on NIAH variants | [research.trychroma.com/context-rot](https://research.trychroma.com/context-rot) |
| RAG-MCP "50% tokens, 29% accuracy" | **MISQUOTED.** Actual: ~50% tokens (✓) + 13.62%→43.13% accuracy on MCPBench web-search subset with qwen-max-0125; "fails above 100" refers to per-position retrieval degradation in Figure 3 heatmap, not a separate experiment (resolved Thu PM 2026-05-21). Stress test sweeps N=1 to 11,100 in 26 intervals; registry holds ~4,400 servers, so N>4,400 samples with replacement. | [arXiv 2505.03275](https://arxiv.org/abs/2505.03275) |
| Cursor 40 cap, Copilot 128 cap | Cursor 40 verified (total per workspace). Copilot 128 in error messages, no official changelog | [Cursor docs](https://docs.cursor.com/context/model-context-protocol), [vscode-copilot-release#13065](https://github.com/microsoft/vscode-copilot-release/issues/13065) |
| MCP-Zero "98% reduction on APIBank" | Verified (60-98% range; 98% in single-turn APIBank; 111 vs 6,300 tokens) | [arXiv 2506.01056](https://arxiv.org/abs/2506.01056) |

All numbers cited later in this design reference verified values, not the misquoted ones.

---

## 1. Novelty Audit (revised 2026-05-22 Fri AM after Thu PM landscape sweep)

### What changed in this revision

The Thu PM landscape audit surfaced three published papers that already sweep N as an independent variable for MCP-flavored or function-call tools (RAG-MCP, LongFuncEval, MCPVerse) and two that run padded-length controls on text retrieval (Chroma Context Rot, Liu et al. arXiv 2510.05381). The original v1 "first publicly-reproducible measurement as a continuous function of N" framing is dead on first contact with a reviewer who has read RAG-MCP. This section installs the narrower 6-condition intersection claim from `design/FOUNDATION.md §1.1` (the binding methodology doc) as the v1 novelty position. The prior-work table below is expanded to include the new entries.

### Overlapping prior work, with deltas (revised)

| Work | What they did (1 sentence) | EXACT delta we provide |
|---|---|---|
| **RAG-MCP** ([arXiv 2505.03275](https://arxiv.org/abs/2505.03275), Gan & Sun, May 2025) | **N=1 to 11,100 across 26 intervals on MCPBench web-search subset, qwen-max-0125 only; 43.13% selection accuracy with retriever vs 13.62% baseline; ~50% prompt-token reduction. Registry holds ~4,400 servers so N>4,400 samples with replacement (padded duplicate schemas); Figure 3 heatmap has no error bars (~1 trial per cell).** | Code-retrieval task (not web-search); frontier-model panel (not single qwen-max); padded-N=1 length-isolated control (their design conflates length with N); per-server MPD (they treat distractors as a uniform bag); pinned server SHAs + description hashes (mcp.so snapshot is unpinned); per-N table with CIs (they publish a heatmap, not a table) |
| **LongFuncEval** ([arXiv 2505.10570](https://arxiv.org/abs/2505.10570), Kate et al., Apr 2025) | N ∈ {49, 102, 207, 417, 741} across 9 models including GPT-4o; 7.59-85.58% degradation on Booking.com REST APIs; per-position alpha placement control | Code-retrieval (not booking APIs); padded-N=1 length-isolated control (their alpha controls position, not length); per-server MPD; pinned versions; like-for-like grid (their GPT-4o was tested on a 9-cell grid vs 25-cell for others, undersampling the tail) |
| **MCPVerse** ([arXiv 2508.16260](https://arxiv.org/abs/2508.16260)) | 3 discrete conditions (Oracle / Standard=218 / Max-Scale=552), n=250 single-trial T=0.1, no CIs. Claude-4-Sonnet v1: 57.81 / 61.01 / 57.77 = inverted-U with 3.24pp Max-Scale drop. v2 same task: 62.3 / 62.4 / 44.2 = cliff with 18pp Max-Scale crash. | Continuous N (not 3 discrete points); n ≥ 3 per cell with paired-bootstrap CIs (they have neither); padded-N=1 length-isolated control; per-server MPD; reproducible (v1-v2 numerical divergence on the same benchmark is itself a stability red flag) |
| Chroma "Context Rot" (July 2025) | 18 LLMs degrade with input length on NIAH variants; padded-distractor controls on text retrieval show 20-50% drop | Methodology ported into the MCP tool-context regime (they tested text, not tools); multi-server composition as the IV |
| Liu et al. ([arXiv 2510.05381](https://arxiv.org/abs/2510.05381), Oct 2025) | Whitespace + attention-mask padding shows 13.9-85% length-only degradation on text retrieval | Tool-context regime (they test text only); multi-MCP composition as the IV |
| MCP-Bench (Accenture, [arXiv 2508.20453](https://arxiv.org/abs/2508.20453), 2025) | Eval models on 28 servers / 250 tools using a fixed 10-distractor condition | We sweep N continuously as an independent variable; we decompose failure modes per trial; we publish per-server marginal performance delta |
| MCP-Universe ([arXiv 2508.14704](https://arxiv.org/abs/2508.14704), 2025) | Eval models on 11 servers across 6 domains, agent-axis | Server-axis; varies N; code-retrieval-as-held-constant-task |
| MCPMark ([arXiv 2509.24002](https://arxiv.org/abs/2509.24002), 2025) | 127 tasks across 5 servers, single-server-at-a-time | Multi-server composition; explicit interference measurement |
| MCPAgentBench ([arXiv 2512.24565](https://arxiv.org/abs/2512.24565), 2025) | Planning + execution eval with mixed pools | N as continuous IV; per-server profile |
| LiveMCPBench ([arXiv 2508.01780](https://arxiv.org/abs/2508.01780), 2025) | top-k=5 retriever over 70 servers / 527 tools; multi-model; 50% retrieval-error in their failure taxonomy. Resolved [VERIFY-LIVEMCPBENCH] Thu PM: they do NOT sweep N | Retriever ON/OFF as second axis motivated by their 50% finding; N as continuous IV; code-retrieval focus; per-server MPD |
| MCP-Atlas (Scale Labs blog, 2026) | 36 servers / 220 tools / 1,000 tasks model-axis leaderboard | Open methodology + reproducible harness + N as continuous IV |
| Digital Applied 100-server stress test (Apr 2026) | 100 servers single-server pass-rate, closed methodology, anonymized names | Open methodology + per-server names + multi-server composition |
| Microsoft Research "Tool-Space Interference" (Sep 2025) | Catalogued 775 colliding tool names | Quantitative N-curve measurement of what they catalogued |
| MCP-Zero ([arXiv 2506.01056](https://arxiv.org/abs/2506.01056), 2025) | Active-discovery mitigation; 60-98% token reduction on APIBank | Real-server N-curve benchmark of mitigations compared |
| Anthropic "Code Execution with MCP" engineering blog (2026) | Identified the problem qualitatively, recommended tool-search | Quantification with CIs |
| Anthropic Tool Search Tool (Nov 2025) | Internal closed eval: Opus 4 49→74%, Opus 4.5 79.5→88.1% with tool-search enabled | Public methodology, public numbers, multi-vendor scope (not Claude-only) |
| GitHub Copilot "Smarter with fewer tools" blog (Apr 2026) | Anecdotal 40→13 tools → 2-5pp improvement on SWE-Lancer / SWE-bench Verified | Controlled N-curve across N ∈ {1, 5, 10, 15, 20}; 5 orderings per cell; multi-server-identity decomposition |
| BFCL v4 (Berkeley, 2025) | Function-calling AST eval, agentic categories | MCP-server-axis with N as IV |
| τ-bench / τ²-bench (Sierra, 2024-25) | Dual-control airline/retail tool use | MCP composition specifically |

### Defensible position (replaces the original "first to..." sentence)

tool-crowding does not claim "first to vary N as an IV." Three published papers have already done that. tool-crowding addresses a specific 6-condition intersection that the prior-art coverage map leaves open:

1. **Code-retrieval as the task domain**, rather than web-search (RAG-MCP), booking APIs (LongFuncEval), or general agent tasks (MCPVerse).
2. **A frontier-model panel** including Claude Opus 4.7, Sonnet 4.6, GPT-5-class, and Gemini 2.5-class, rather than single-model (qwen-max-0125 in RAG-MCP) or non-frontier-mixed panels.
3. **A padded-N=1 prompt-length control** adapted from Chroma's text-retrieval methodology into the MCP tool-context regime, where no prior work has isolated prompt-length from distractor-count for tools specifically.
4. **Per-server Marginal Performance Delta** as a published per-server diagnostic, where no current MCP benchmark publishes one.
5. **Full server SHA + tool-description + JSON-schema hashing into run_id** for reproducibility, which neither RAG-MCP nor LongFuncEval nor MCPVerse implements.
6. **A second experimental axis varying retriever ON versus OFF**, motivated by LiveMCPBench's finding that 50% of failures in their 70-server top-k=5 retrieval regime are retrieval-side errors.

The combined contribution is a methodological harness plus dataset that future code-retrieval MCP studies can use to replace ad-hoc fixed-pool comparisons with principled N-curves, accompanied by a frontier-panel pilot.

### Why this is stronger than "first to vary N"

The blunt framing dies on first contact with a reviewer who has read RAG-MCP. The 6-condition intersection survives the obvious pushback ("but RAG-MCP swept N to 11,100?") because each condition is a specific measurement choice that prior art did not make. The pitch becomes constructive (we extend the methodology into a regime they did not test) rather than competitive (we did first what they already did). RAG-MCP becomes a citation and a sanity-check replication target for external validity, not a competitor.

### Kill-the-paper case (revised)

The 6-condition intersection narrows item-by-item if a new paper closes any of conditions 1-6. The thesis dies only if a single concurrent publication covers ≥3 of the 6 conditions in a single benchmark before the Mon May 25 launch. Per `design/FOUNDATION.md §3`, this is reframed as kill criterion #1 (the original "scoop on N-as-IV" criterion partially fired on 2026-05-21 with the RAG-MCP / LongFuncEval / MCPVerse discoveries; the reframed criterion is intersection-specific). If a benchmark from Microsoft Research (Interviewer team) or Sourcegraph (CodeScaleBench) lands ≥3 of the intersection conditions before launch, pivot the paper to RQ5 (mitigation comparison: RAG-MCP-style filter vs MCP-Zero-style active discovery vs gateway ACLs vs LiveMCPBench-style retriever) as the primary contribution.

---

## 2. Research Questions

Pre-registered. Each RQ is falsifiable; each has a null, a primary metric, and a minimum effect size.

| RQ | Question | H0 | Operational metric | Min effect to count as positive |
|---|---|---|---|---|
| RQ1 (primary) | Does pass@1 degrade as N concurrently-installed MCP servers increases, holding task / model / host constant? | pass@1(N=1) - pass@1(N=20) ≤ 5pp on Claude Sonnet 4.6 | pass@1 at N ∈ {1, 5, 10, 15, 20}, each cell ≥ 50 queries × 5 paired orderings | ≥ 10pp absolute drop from N=1 to N=20 with paired-bootstrap 99% CI not crossing zero |
| RQ2 | When pass@1 degrades, which failure mode dominates? | Failure modes are uniformly distributed at N=20 | Per-trial failure-mode tagging: (a) wrong-tool, (b) context-overflow, (c) hallucinated-tool-name, (d) latency-timeout, (e) server-error | At N=20, one category accounts for ≥ 40% of failures (n ≥ 250 failed trials) |
| RQ3 | Are per-server marginal performance delta (MPD) values stable and reproducible? | Spearman ρ between independent re-runs ≤ 0.3 | MPD(s) computed twice with disjoint orderings (seeds 0-2 vs seeds 3-5) | Spearman ρ ≥ 0.6 across reruns; top-3 worst interferers identical across both runs |
| RQ4 | Is there a Pareto frontier where some servers dominate others on (tokens, pass-rate)? | All servers lie on a single line; no dominated set | Compute upper-left envelope of (input-tokens, pass@1) cloud at N=10 | ≥ 3 servers strictly dominated by ≥ 3 frontier servers (lower tokens AND higher pass) |
| RQ5 (mitigation) | Does oracle tool-filtering recover pass-rate at N=20? | with-filter at N=20 indistinguishable from no-filter at N=20 | Compare oracle-filter vs no-filter at N=20 (paired by query) | Filter recovers ≥ 80% of the N=1→N=20 gap |

---

## 3. Experimental Design

### Task

**Code retrieval as the held-constant task.** Rationale:

- Objective ground truth (labeled query→code pairs). CoIR ([arXiv 2407.02883](https://arxiv.org/abs/2407.02883)) and CodeRAG-Bench ([arXiv 2406.14497](https://arxiv.org/abs/2406.14497)) are cited as the **task-framing precedent** (code-retrieval as a scorable downstream task), NOT as the v1 query source. **Query source is post-cutoff GPL-licensed issue mining per `design/QUERY_SET_HYGIENE.md`** (lock 2026-05-22 Fri AM), which supersedes the Day-1 "50 queries from CoIR StackOverflow-Python split" assumption after the Thu PM 2026-05-21 read of `notes/coir.md` found CoIR's component datasets predate every model in our panel's training cutoff.
- Modular: retrieval is scorable independent of code generation
- High practical relevance (aligns with OCI; the case study readers will care about)
- Multiple comparable servers exist in the category
- Inherits methodology credibility from NAACL-Findings-published code-retrieval evals

**Alternatives considered and rejected:**

- API tool execution (BFCL-style): broader but adds side-effect and rate-limit confounders. Rejected.
- Web search task: dominant single-server use case; hard to multi-server compose meaningfully. Rejected.
- File operations: low variance, low ceiling. Rejected.
- Multi-domain mixed task (MCP-Bench-style): broader generalizability but introduces task-difficulty as confounder. Rejected for v1; planned for v2.
- Free-form coding via SWE-bench Pro ([arXiv 2509.16941](https://arxiv.org/abs/2509.16941)): contamination-resistant but conflates retrieval with code-generation. Rejected; we want retrieval signal isolated.

**Second-best alternative**: API task on held-out commercial sandbox APIs (Stripe, Twilio). Rejected because (a) requires paid-account signup chains hurting reproducibility, (b) introduces non-retrieval variance.

### Independent variables

- **N**: number of concurrently-installed MCP servers ∈ {1, 5, 10, 15, 20}
- **Primary server identity**: which code-retrieval MCP is the intended target for the query
- **Tool ordering**: 5 paired random orderings per cell (RNG seeds 0-4)
- **Model**: Claude Sonnet 4.6 (primary); GPT-5 and Gemini 2.x (secondary, partial sweep at N ∈ {1, 10, 20})
- **Host**: Claude Desktop (primary); Cursor and Cline (secondary, partial sweep)
- **Tool-listing strategy (3 conditions)**: (a) full-listing — all installed tools advertised, the primary retriever-OFF condition; (b) retriever-ON — RAG-MCP-style top-k=5 semantic prefilter, the production-shipping condition; (c) oracle-filter — RQ5's experimental upper bound. Retriever-ON is the second experimental axis alongside N; see "Retriever ON/OFF axis" subsection below.

### Dependent variables

- **pass@1** (primary; defined in Section 4)
- **pass@3** (variance reduction; secondary)
- **Tool-call precision@1**: P(correct tool called first | task attempted)
- **Tool-call recall**: P(correct tool eventually called | task attempted)
- **Input tokens consumed** per trial (total, including system + tools + user prompt)
- **Output tokens consumed** per trial
- **Latency p50 / p95** per cell
- **Tokens-to-first-correct-tool**: input tokens consumed before the first correct tool invocation
- **Hallucinated-tool-name rate**: P(call references a tool not in installed set | call)

### Confounders to control

- **Server tool-count variance**. Each server exposes different numbers of tools. Mitigation: include tool-count as a covariate; bucket sub-analysis.
- **Tool description token-length variance**. Mitigation: measure description-token-count per server; report as covariate; regress MPD on length to test reducibility.
- **Domain overlap with task**. Some distractors are code-adjacent (Filesystem, SQLite, PostgreSQL) and may interfere differently than orthogonal ones (Time, Notion). Mitigation: tag each distractor; report split analysis.
- **Ordering effects**. Mitigation: 5 paired random orderings (RNG seeds 0-4); pre-registered.
- **Prompt cache hits** (Anthropic-specific). Mitigation: vary a small unique system-prefix nonce per trial to force cache-cold.
- **Model version drift**. Mitigation: pin checkpoint (`claude-sonnet-4-6` with date suffix); collect within a 7-day window; record API response fingerprints if exposed.
- **Server version drift**. Mitigation: pin git SHAs for each server install; run daily smoke tests; record server-side response checksums.
- **Time-of-day / API load variance**. Mitigation: distribute trials uniformly across a 48-hour window.

### Sample size / statistical power

- Target effect: detect 10pp drop in pass@1 from N=1 to N=20
- Conservative variance: σ ≈ 20pp for code retrieval pass@1
- α = 0.01 (Bonferroni-adjusted for 5 N-level comparisons)
- Power target: 80%
- Paired-bootstrap, B = 10,000 resamples
- Cohen's d ≈ 0.5 → n ≈ 64 paired samples per cell

**Realized design**: 50 queries × 5 orderings = 250 trials per (N, primary-server) cell; aggregated 5 orderings → 50 paired samples per cell. Sufficient.

**Total trial budget**:
- Primary (Claude Sonnet 4.6, Claude Desktop): 50 queries × 5 N × 5 orderings × 5 primary servers = **6,250 trials**
- Secondary models (GPT-5 + Gemini 2.x, partial sweep N ∈ {1, 10, 20}): 50 × 3 × 3 × 5 × 2 = **4,500 trials**
- Secondary hosts (Cursor + Cline, primary model only): 50 × 3 × 3 × 5 × 2 = **4,500 trials**
- **Grand total: ~15,250 trials.** At ~7k tokens/trial (input+output) and a weighted ~$25/M-tokens, budget ≈ $2,650. Feasible.

### Server pool (details in `design/SERVER_POOL.md`)

**Primary code-retrieval (5):**

1. **OCI (OpenCodeIntel)** — `DevanshuNEU/lco-fork`; AST+BM25+Cohere hybrid; reachability 1 (self-hosted). **COI disclosure: authored by the corresponding author.**
2. **GitHub MCP** — `@modelcontextprotocol/server-github`; npx; reachability 2 (free + PAT signup)
3. **Git MCP** — `@modelcontextprotocol/server-git`; npx; reachability 1; local grep/log
4. **Aider MCP** — `disler/aider-mcp-server`; npx/pip; reachability 1
5. **Fetch MCP** — `@modelcontextprotocol/server-fetch`; npx; reachability 1; serves as the "naive retrieval" baseline (fetch GitHub README/issues)

**Distractor pool (10):** Filesystem, Memory, Sequential Thinking, Time, SQLite, PostgreSQL, Brave Search, Linear, Notion, Slack. Full table in SERVER_POOL.md.

**Domain-overlap tags:**
- Code-adjacent distractors: Filesystem, SQLite, PostgreSQL
- Orthogonal distractors: Memory, Sequential Thinking, Time, Brave Search, Linear, Notion, Slack

**Excluded**: Sourcegraph, Glean, Cody (paywalled); Perplexity, Exa, HubSpot (paid APIs); Gmail (OAuth friction); Twilio (phone verification).

### Baselines (trivial agents and non-AI controls) — locked 2026-05-22 Fri PM

This subsection closes ABC R.12 (multiple baselines) and R.13 (mandatory non-AI baseline) per `design/FOUNDATION.md §4.3`. Four baselines participate in the v1 experiment matrix. Each is named, operationally defined, and given an explicit rejection criterion that, if fired, halts the launch.

| # | Baseline | Operational definition | What it tests | Expected result | Rejection criterion |
|---|---|---|---|---|---|
| 1 | **Padded-N=1** | 1 real primary tool + neutral-tool-shaped fillers padded to ±10% of unpadded-N=20 token count, deterministic per `cell_seed`. Full spec: `design/PADDING_STRATEGY.md`. | F1 (`FOUNDATION.md §1.0`): discrimination interference exists independent of prompt length. | padded-N=1 pass@1 stays within 5pp of unpadded-N=1 pass@1 on ≥ 2 of 3 frontier models (long prompt alone does NOT degrade pass@1). | If padded-N=1 pass@1 is within 5pp of unpadded-N=20 on ≥ 2 of 3 frontier models, the discrimination construct collapses to capacity. Kill criterion #3 (`FOUNDATION.md §3`, RESEARCH_DESIGN §9) fires; pivot to methodology porting + per-server MPD diagnostic. |
| 2 | **Single-server-only per code-retrieval MCP** | Only the primary code-retrieval MCP for the query's domain is installed; no distractors, no other primaries. Equivalent to the **unpadded-N=1 cell** of the main sweep for that primary server. Re-labels existing cells; adds no new trials. | Per-server upper bound. What does each code-retrieval MCP achieve on its own, free of crowding? | Highest pass@1 cell for that server. Reference point against which the N-curve degrades. | If single-server-only pass@1 is < 30% on any primary, the primary is too weak for the eval; consider dropping that primary from the matrix (server-side issue, not benchmark-side). |
| 3 | **No-MCP (pure LLM)** | Agent has zero MCPs installed. Tool list in the prompt is empty. Agent can only use its own training-set knowledge. | Lower-bound baseline. Closes the "the model already memorized everything" attack. Probes contamination per `design/QUERY_SET_HYGIENE.md §1` threat 1. | < 20% pass@1 on code-retrieval queries that legitimately require repo content. Heuristic upper bound, not a pre-registered prediction. | If no-MCP pass@1 is > 50%, the queries are either too easy or contaminated. Re-screen the query set through `QUERY_SET_HYGIENE.md §4` (5-gram check); drop or replace queries with high no-MCP pass-rate. |
| 4 | **Random-tool-call** | At each step, the agent's tool selection is replaced by a uniformly random pick from the installed tool list. The model still parses tool responses and decides whether to terminate, but the SELECTION step is overridden. Implemented as a harness flag (`--random-tool-selection`). | ABC R.13 mandatory non-AI baseline. Probes whether the eval's tool-selection signal is real. | < 5% pass@1 at any N. Random rarely surfaces the correct ground truth in a multi-step retrieval setting. | If random-tool-call pass@1 > 10% at any N, the benchmark is broken — passing does not require tool-selection skill. ABC R.13 verbatim: "If random > measured, benchmark is broken." Halt the launch; investigate query construction. |

### Pilot vs full-sweep scope

For the Saturday 2026-05-23 pilot (`design/PILOT_V0.md`), only **baseline 1 (padded-N=1)** is run; the 144-trial main matrix already includes the padded condition. Baselines 2-4 are deferred to the v1 full sweep on cost-budget grounds (PILOT_V0.md §"Resource budget" caps at $50-85; adding baselines 3 and 4 would push past it).

For the v1 full sweep, all four baselines are first-class experimental conditions. Approximate added trial counts:

- Padded-N=1: 50 queries × 5 paired filler orderings × 5 primary servers = **1,250 trials**
- Single-server-only: 0 new trials (re-labels unpadded-N=1 cells already in the main sweep)
- No-MCP (pure LLM): 50 queries × 5 paired orderings = **250 trials per model in the panel**
- Random-tool-call: 50 queries × 3 repeats at a single N level (N=10) = **150 trials per model in the panel**

At 4 models in the frontier panel (Opus 4.7, Sonnet 4.6, GPT-5-class, Gemini 2.5-class): roughly 1,250 + 1,000 + 600 = ~2,850 baseline trials on top of the 6,250-trial primary N-curve sweep. Estimated added cost: $50-80 at the ~7k tokens/trial × ~$25/M-tokens weighted rate used in §3 Sample size.

### Why this set, not more

The four baselines map 1-to-1 to four distinct falsification or contamination claims this benchmark must defend. Each rejection criterion is specific enough to halt the launch if it fires. None is decorative. Additional candidate baselines (oracle tool-filter, ground-truth-known-N-1-distractor) are first-class experimental ARMS in RESEARCH_DESIGN.md §2 RQ5 and §10 F5, not baselines in the R.12/R.13 sense; they are gated by their own pre-registered minimum effect sizes, not by the rejection criteria above.

### Retriever ON/OFF axis (second experimental dimension) — locked 2026-05-22 Fri PM

This subsection adds retriever ON/OFF as a second experimental axis alongside N. Locked per the Thu PM 2026-05-21 landscape audit (`research/landscape_rag_distractor.md` + `notes/livemcpbench.md`).

**Motivation.** Production systems are increasingly shipping retrievers in front of MCP tool lists: Anthropic's Tool Search Tool (Nov 2025, Opus 4 49→74%), Block's Linear MCP collapse (30+ tools → 2), RAG-MCP's semantic prefilter (the published prior art), MCP-Zero's active discovery. Measuring multi-MCP interference WITHOUT a retriever is the unmitigated baseline; measuring WITH a retriever is what the production-installed regime looks like. Both arms matter.

**Load-bearing prior-art finding.** LiveMCPBench ([arXiv 2508.01780](https://arxiv.org/abs/2508.01780)) reports that **50% of failures in their 70-server top-k=5 retrieval regime are retrieval-side errors** (`notes/livemcpbench.md`). Retrieval does not eliminate multi-MCP interference; it changes the failure mode from "model picks wrong tool" to "retriever surfaces wrong tool." Both modes are real. The two-axis design measures both.

**Operational definition (retriever-ON).** At trial start, a semantic retriever scores every installed tool's description against the query embedding; top-k=5 tools by cosine similarity are surfaced to the model in the tool list. Tools below top-5 are not advertised. The retriever is RAG-MCP's published top-k=5 setup with our choice of embedder.

**Embedder choice.** Cohere `embed-multilingual-v3.0` (the embedder OCI ships with), pinned by API version in `models/endpoints.json` per `REPRODUCIBILITY.md §1`. Alternative embedders (BGE-M3, OpenAI text-embedding-3-large) are robustness checks for v2, not v1.

**Trial budget impact.** Retriever-ON doubles the primary cell count. For Sonnet 4.6 × 5 N levels × 5 orderings × 50 queries × 5 primary servers, the unpadded sweep is 6,250 trials per arm × 2 arms = **12,500 trials at the primary axis**. To fit within the §3 sample-size budget (~$2,650), secondary models (GPT-5-class, Gemini 2.5-class) get a partial retriever-ON sweep at N ∈ {1, 10, 20} only; Opus 4.7 is deferred to v2 retriever-ON.

**Pilot scope.** PILOT_V0.md §"Retriever robustness arm" runs ~30 trials at retriever-ON, N=20, on Sonnet 4.6 only (single-point probe, not a full curve). Full retriever-ON sweep is deferred to v1 post-pilot.

**Two-axis result shape (paper-side).**

- Retriever-OFF curve: pass@1 vs N, the "naive tool dumping" regime. Demonstrates that interference exists.
- Retriever-ON curve: pass@1 vs N, the "production retrieval" regime. Demonstrates whether retrieval recovers the gap and at what cost (retrieval-side errors per LiveMCPBench).
- The gap between the two curves at each N is the **value of retrieval at that scale**.
- A flat retriever-ON curve (no degradation with N) would mean retrieval fully fixes interference. The LiveMCPBench prior is low: 50% retrieval-error in their regime.

**Connection to MCP gateway architectures.** The retriever-ON arm is, architecturally, the simplest version of an MCP gateway / aggregator. A gateway collapses N upstream MCPs to fewer agent-visible tools via routing; a top-k retriever collapses N to k=5 via embedding similarity. The two-axis design captures both production regimes: agent sees all installed tools (retriever-OFF) vs agent sees a routed subset (retriever-ON).

### RAG-MCP replication cell (external-validity probe) — locked 2026-05-22 Fri PM

A scoped replication of RAG-MCP's ([Gan & Sun, arXiv 2505.03275](https://arxiv.org/abs/2505.03275)) stress test as an external-validity probe for the harness. **NOT a contribution claim.** The goal is to demonstrate that our harness reproduces a published N-degradation curve when given a published methodology, and to test whether RAG-MCP's qwen-max-0125 finding generalizes to frontier models.

**Why this is in v1 scope.**

1. **External validity.** Our N-curve is novel for code-retrieval; we cannot internally cross-validate without another task. Replicating RAG-MCP on web-search lets us demonstrate the harness produces sensible curves outside our headline task.
2. **Methodology audit on prior art.** RAG-MCP's published stress test has a structural defect: registry has ~4,400 servers but N goes to 11,100, forcing with-replacement sampling above N=4,400 (verified Thu PM + Fri AM via HTML re-pull; see `notes/ragmcp-100.md`). Their high-N regime is closer to padded-prompt-length than to additional-tool-count. Running the same setup in our harness lets us characterize whether the published finding is robust in its clean sub-regime.
3. **Cross-model generalization.** RAG-MCP tested qwen-max-0125 only. Whether the N-curve replicates on Claude / GPT-5 / Gemini is a separable open question their design cannot answer.

**Cell design.**

| Parameter | Value | Rationale |
|---|---|---|
| Task | RAG-MCP's MCPBench web-search subset | Their exact setup |
| Models | Sonnet 4.6 + GPT-5-class | 2 of our 4 panel models; Opus 4.7 + Gemini 2.5 deferred to v2 on cost |
| N levels | 10, 100, 1,000 | Their range is 1-11,100 across 26 intervals; we cap at N=1,000 to stay below the ~4,400 with-replacement threshold (cleanest sub-regime of their methodology per `notes/ragmcp-100.md` Q5) |
| Conditions | Retriever-OFF, Retriever-ON (their RAG-MCP top-k=5 setup) | Tests both their headline finding (retriever-ON 43.13% vs retriever-OFF 13.62%) and cross-model generalization |
| Queries | 30 queries drawn from RAG-MCP's published web-search task set | Smaller than our 50-query code-retrieval set; this is a probe, not a contribution |
| Orderings | 3 paired orderings per cell | Their published heatmap is single-trial-per-cell; we add CIs they did not |
| Sampling at N=1,000 | Without replacement from the 4,400-server pool | Below their with-replacement threshold; cleanest regime |
| Total trials | 3 N × 2 models × 2 conditions × 30 queries × 3 orderings = **1,080 trials** | Bounded as a probe |
| Estimated cost | $20-30 at §3 weighted rate | Acceptable as v1 supplementary |

**Expected results.**

1. At retriever-OFF, our Sonnet 4.6 pass-rate at N=10 should fall within 10pp of qwen-max-0125's pass-rate at the same N if the effect generalizes across model classes. A wider gap is a model-class moderation finding worth paper-section discussion.
2. At retriever-ON, our Sonnet 4.6 pass-rate should approach their 43.13% headline, modulo our model being a 2026 frontier rather than qwen-max-0125.
3. The N=10 → N=1,000 slope should be qualitatively similar (monotone decreasing for retriever-OFF; flatter for retriever-ON) if the effect is real.

**Reject criteria.**

| Result | Interpretation | Action |
|---|---|---|
| Retriever-OFF flat at N=10..1,000 on Sonnet 4.6 | Harness fails to reproduce a published degradation. Likely harness bug. | Audit harness. Halt launch until reproduced. |
| Retriever-OFF degrades but retriever-ON also flat (no recovery) | LiveMCPBench's 50% retrieval-error finding generalizes; retriever is not the fix. Real result. | Report as v1 supplementary. |
| Both arms degrade similarly | Retriever provides no useful help at the N range tested. Real result. | Report as v1 supplementary. |
| Both arms flat or inverted | Either RAG-MCP's finding is brittle OR our query subset is poor. | Report with caveats; do NOT use as contradiction claim without additional probes. |

**Where the data lands.** `results/<run_id>/external_validity/ragmcp_replication.jsonl` with the same Trial schema as the primary sweep. Analysis: `analysis/external_validity.ipynb`. Paper section: §10 "External-validity probes," subordinate to the headline N-curve.

**Why not extend to N=11,100.** Above-N=4,400 regime is sampling-with-replacement on a 4,400-server registry. Per `notes/ragmcp-100.md` Q5, this means "more padding with duplicate schemas," not "more distinct tools." Our padded-N=1 control (`design/PADDING_STRATEGY.md`) already isolates the padded-prompt-length effect cleanly; running RAG-MCP's high-N regime would replicate a confound we have a better measurement for. N=1,000 is the highest clean-regime point worth replicating.

---

## 4. Metrics & Scoring

### Pass@1 (primary, pre-registered)

For each query, the agent makes one attempt. The trial passes if both of these hold:

1. **Symbol match**: the returned snippet contains the ground-truth function/symbol name as a literal substring.
2. **Token overlap**: ≥ 50% of the ground-truth's tokenized words appear in the returned snippet (after lower-casing, removing punctuation, no stemming).

Reported aggregated across the 5 paired orderings per cell.

**Robustness checks (secondary, reported separately):**
- **Strict pass@1**: exact-string match of the function body to ground truth
- **Lenient pass@1**: any-token-overlap ≥ 1 word

### Marginal Token Cost (secondary, pre-registered)

MTC = (input_tokens(N=20) − input_tokens(N=1)) / 19

Reported per-server (averaging the N=20 cell over orderings).

### Tool-Selection Precision@1, Hallucinated-Tool-Name Rate, Latency p50/p95

Operationally defined in Section 3 ("Dependent variables"). Pre-registered as secondary.

### Marginal Performance Delta MPD(s) — operational definition

For server s, reference N_ref = 10:

```
MPD(s) = E_{T, O} [ pass@1(T | s ∈ install_with, |install_with|=N_ref+1, O)
                  − pass@1(T | s ∉ install_without, |install_without|=N_ref, O) ]
```

Where:
- T ranges over the 50 evaluation queries
- O ranges over 5 random orderings (paired)
- `install_with` and `install_without` differ ONLY in the presence/absence of s; one other distractor is substituted to hold |install| constant relative to a "reference 10"
- Pairs are matched on query and ordering seed

**Worked example**:
- Server X. 50 queries × 5 orderings = 250 paired comparisons.
- Without X (10 servers): pass@1 = 0.72
- With X (10 servers, replacing one distractor): pass@1 = 0.61
- MPD(X) = 0.72 − 0.61 = **+0.11**

Interpretation: X imposes 11pp marginal degradation when installed alongside 9 unrelated servers, relative to the same 9 alongside a substitute distractor. Positive MPD = X hurts neighbors; negative MPD = X helps; near zero = neutral.

**Standard error**: paired-bootstrap over (query × ordering) pairs, B = 10,000. Report 95% CI.

**Why "MPD" not "Interference Score"**: avoids causal-sounding language; aligns with measurement-theory norms; reduces surface area for theoretical-grounding objections (one of the three reviewer-2 changes; see end of doc).

---

## 5. Pareto Frontier Methodology

### Plotting

- **X-axis**: log10(total input + output tokens consumed per task) averaged at N = 10
- **Y-axis**: pass@1 at N = 10 (averaged across orderings)
- One point per primary server (5 points; secondary scatter for distractors as a separate plot)
- Optional secondary plot: same axes at N = 20

### Dominance

Server A strictly dominates server B if:
- tokens(A) ≤ tokens(B) AND pass(A) ≥ pass(B), with at least one strict inequality.

A point is on the frontier if no other point dominates it. Compute via upper-left envelope of the (tokens, pass) cloud.

### Non-monotonic curves

Pass@1 may unexpectedly increase at some N (e.g., a distractor happens to provide useful context). Protocol:

- **Report raw curves with error bars from paired bootstrap.** Do not smooth.
- **Test significance of non-monotone points**: if 99% CI does not include the monotone neighbor's value, flag as anomaly and investigate per-trial.
- **Do not fit parametric curves** (logistic, exponential) unless the form is defensible by AIC/BIC against a piecewise-linear alternative; otherwise readers may infer structure that isn't there.

### Acknowledgment of Pareto framing

CLEAR (Scale Labs, 2025) introduced the Pareto framing for tool-use cost vs accuracy. We apply it to the server-axis at fixed N. CLEAR is cited in Section 5 of the paper draft.

---

## 6. Threats to Validity

### Internal

| Threat | Mitigation |
|---|---|
| Server identity correlates with tool-count | Include tool-count as covariate; bucket sub-analysis |
| Prompt length increases with N (interference vs long-prompt confound) | **Add padded-N=1 control**: N=1 prompts padded with neutral system text to match N=20 token count. Disentangles interference from raw long-prompt degradation. (Promoted from threats section to first-class condition per Reviewer-2 change #1.) |
| Order effects | 5 paired random orderings per cell |
| Prompt cache hits | Unique system-prefix nonce per trial |
| Model version drift | Pin checkpoint; collect within 7-day window |
| Server version drift | Pin git SHA per server; daily smoke tests |
| API-side load variance | Distribute trials uniformly across 48 hours |

### External

| Threat | Mitigation |
|---|---|
| Single task family (code retrieval) | Acknowledge; pre-register v2 expansion to API tasks (+ browser, + file ops); methodology generalizes, results may not |
| Single primary model | Secondary GPT-5 + Gemini 2.x at partial sweep |
| Single primary host (Claude Desktop) | Secondary Cursor + Cline at partial sweep |
| Code retrievers may not generalize to other server categories | Acknowledge as limitation |

### Construct

| Threat | Mitigation |
|---|---|
| MPD assumes additive model; reality may be multiplicative or higher-order | Add factorial sub-experiment at N=4 (16 paired cells, all pairs of 4 distractors) to estimate pairwise interaction effects (per Reviewer-2 change #2) |
| pass@1 is harsh on stochastic agents | Report pass@3 as secondary |
| Tool-call precision conflates "correct tool" with "correctly-named tool" | Hallucinated-tool-name rate reported as separate DV |
| Code-retrieval correctness criterion (symbol match + 50% overlap) is brittle | Report strict and lenient variants as robustness checks |

### Statistical conclusion

| Threat | Mitigation |
|---|---|
| Multiple comparisons across N and servers | Bonferroni for primary RQ1 across 5 N-levels; BH-FDR for per-server MPD analysis; both pre-registered |
| Single LLM-agent run variance not modeled | Report variance decomposition: across queries, across orderings, across trials; ICC reported per cell |
| Bootstrap CIs assume IID | Paired bootstrap over (query × ordering); cluster-robust where indicated |

### Strongest reviewer attacks (named in advance)

1. **"Your code-retrieval task is too narrow to generalize."** Honest answer: agreed, scope is v1; pre-register v2 expansion; methodology generalizes, results may not.
2. **"Per-server MPD is just a proxy for description length / tool count."** Mitigation: regress MPD on description-tokens and tool-count; report R²; if R² > 0.5, acknowledge as confound; if R² < 0.5, MPD has signal beyond length.
3. **"Single primary model and host mean you can't claim generalization."** Mitigation: secondary GPT-5 + Gemini + Cursor + Cline data; positioned as robustness, not as core claim.
4. **"Conflict of interest: OCI is your project; you stacked the server pool."** Mitigation: COI disclosed; harness open; "leave-OCI-out" sensitivity analysis appended.

---

## 7. Prior-Work Engagement Table

| Work | Year | What it tested | N concurrent? | Pass-rate vs N curve? | Pareto frontier? | Public artifacts? | Gap we fill |
|---|---|---|---|---|---|---|---|
| MCP-Bench (Accenture, [2508.20453](https://arxiv.org/abs/2508.20453)) | 2025 | Models on 28 servers, 250 tools | Yes (fixed 10 distractors) | No (single point) | No | Code + paper | N as continuous IV; failure decomposition |
| MCP-Universe ([2508.14704](https://arxiv.org/abs/2508.14704)) | 2025 | Models on 11 servers, 6 domains | Some | No | No | Code + paper | Vary N; code-retrieval focus |
| MCPMark ([2509.24002](https://arxiv.org/abs/2509.24002)) | 2025 | Models on 127 tasks, 5 servers | No | No | No | Code + paper | Multi-server composition |
| MCPAgentBench ([2512.24565](https://arxiv.org/abs/2512.24565)) | 2025 | Planning + execution | Some | No | No | Paper | N curve; per-server profile |
| LiveMCPBench ([2508.01780](https://arxiv.org/abs/2508.01780)) | 2025 | 527 tools across 70 servers, top-k=5 retriever, 50% retrieval-error in failure taxonomy | Yes (fixed 70-server pool) | No (resolved Thu PM: they do NOT sweep N) | No | Code + paper | N as continuous IV; retriever ON/OFF as second axis motivated by their 50% finding; code-retrieval focus |
| MCP-Atlas (Scale blog) | 2026 | 36 servers, 1000 tasks, model-axis | Fixed pool | No (qualitative ↓) | No | Leaderboard | Open methodology, N as IV |
| Digital Applied 100-server | 2026 | Single-server pass-rate, anonymized | Single-server | No | No | Closed PDF | Open, multi-server composition |
| Microsoft "Tool-Space Interference" | 2025 (Sep) | 775 colliding name catalog | N/A | No | No | Blog | Quantitative measurement |
| **RAG-MCP** ([2505.03275](https://arxiv.org/abs/2505.03275)) | 2025 (May) | Tool-filter method, MCPBench web-search subset, 13.62→43.13% selection accuracy | **Yes (N=1 to 11,100 across 26 intervals; sampled with replacement above N=4,400)** | **Yes (Figure 3 heatmap; ~1 trial per cell, no error bars)** | No | Paper | Code-retrieval (not web-search); frontier-model panel (not single qwen-max); padded-N=1 length control; per-server MPD; pinned versions; per-N table with CIs |
| **LongFuncEval** ([2505.10570](https://arxiv.org/abs/2505.10570)) | 2025 (Apr) | 9-model REST API tool-call eval; Booking.com APIs | Yes (N ∈ {49, 102, 207, 417, 741}) | Yes (per-model degradation 7.59-85.58%) | No | Paper | Code-retrieval (not booking APIs); padded-N=1 length control (theirs is position-only); per-server MPD; pinned versions; like-for-like grid |
| **MCPVerse** ([2508.16260](https://arxiv.org/abs/2508.16260)) | 2025 (Aug) | 3 discrete fixed conditions (Oracle / 218 / 552), n=250 single-trial no CIs | Yes (3 discrete points, not continuous) | Yes (3 points, no error bars) | No | Paper | Continuous N; n≥3 with paired-bootstrap CIs; padded-N=1 length control; per-server MPD; reproducibility (v1-v2 numerical divergence is a stability red flag) |
| MCP-Zero ([2506.01056](https://arxiv.org/abs/2506.01056)) | 2025 | Active discovery; 60-98% token reduction APIBank | Synthetic | No | No | Paper | Real-server benchmark, not method paper |
| Anthropic "Code Execution with MCP" | 2026 | Identified problem qualitatively | N/A | No | No | Blog | Quantification |
| Chroma "Context Rot" | 2025 | 18 LLMs on synthetic NIAH | N/A | No | No | Tech report | Tool-use specifically; multi-server-N |
| GitHub Copilot "Smarter w/ fewer tools" | 2026 | Anecdotal 40→13 (2-5pp gain) | Single before/after | No | No | Blog | Controlled multi-N curve |
| BFCL v4 (Berkeley) | 2025 | Function-calling AST | N/A | No | No | Leaderboard | MCP server-axis with N |
| τ-bench / τ²-bench (Sierra) | 2024-25 | Dual-control tool use | N/A | No | No | Code + paper | MCP composition specifically |

---

## 8. Minimum-Viable-Experiment (MVE)

2-week MVE that either validates the thesis or kills it. Smallest scope that produces a convincing plot.

### Spec

- **Model**: Claude Sonnet 4.6 (single pinned checkpoint)
- **Host**: Claude Desktop (single version)
- **Primary code-retrieval servers**: 3 — OCI, GitHub MCP, Git MCP
- **Distractor pool**: 7 — Filesystem, Memory, Sequential Thinking, Time, SQLite, Linear, Notion
- **Query set**: 50 queries mined per `design/QUERY_SET_HYGIENE.md` (post-cutoff GPL-licensed issue mining; CoIR reuse rejected after Thu PM 2026-05-21 contamination audit per `notes/coir.md`). Bucketed by retrieval-difficulty quartile at mining time. Three tiers: 30 public + 10 held-back + 10 sealed (OCI proprietary).
- **N levels**: {1, 5, 10}
- **Orderings**: 3 per cell (RNG seeds 0-2)
- **Padded-N=1 control**: yes, 1 ordering at this condition (the long-prompt confound check is so important it goes in the MVE)
- **Total trials**: 50 queries × 3 N × 3 orderings × 3 primary servers + 50 × 1 padded = **1,400 trials**
- **Time budget**: 10 days data collection + 4 days analysis = 14 days

### Go/no-go plot

Single plot: pass@1 vs N with 3 lines (one per primary server), error bars from 3 orderings, plus a dashed horizontal line for the padded-N=1 control.

**Go** if all 3 lines slope downward AND average drop from N=1 to N=10 is ≥ 7pp AND padded-N=1 stays within 3pp of unpadded-N=1.

**No-go** if average drop < 3pp (kill criterion 1 below).

**Ambiguous** if 3 ≤ drop < 7pp: extend MVE to N=15 and N=20 before deciding. Do NOT proceed to full sweep without clear signal.

### Second-best alternative MVE

Drop distractors to 5, keep N ∈ {1, 5}, halve queries to 25. Rejected because N=10 is where most signal lives per Anthropic's 30-50 threshold; cutting that cell removes the strongest observation.

---

## 9. Kill Criteria

Project shelved if any of these hold:

1. **Flat curve.** Average pass@1 differs by < ±3pp across N ∈ {1, 5, 10} on the MVE set. No observable interference; nothing to report.
2. **Pure context-overflow explanation.** Pass@1 drop is fully explained by input tokens exceeding the model's context window (drop only at tokens > 180k on Sonnet 4.6's 200k limit). Story collapses to "context limits exist."
3. **Pure long-prompt degradation explanation.** The padded-N=1 control degrades to the same level as unpadded-N=20. This says the effect is generic context-length sensitivity (Chroma's Context Rot finding), not MCP-specific interference. Pivot the paper to "tool-context rot" and engage Chroma directly.
4. **Non-stable per-server MPD.** Spearman ρ between independent re-runs of MPD(s) < 0.3. Can't claim per-server profiles. Pivot to aggregate-only analysis (RQ1 and RQ2 still valid).
5. **Scoop.** Scale Labs, Anthropic, Microsoft Research, OpenAI, DeepMind, or LiveMCPBench v2 publishes a multi-MCP composition benchmark with N as IV + per-server decomposition + Pareto before our preprint posting.
   - Sub-case (a): if they cover only N curve, refine claim and continue.
   - Sub-case (b): if they cover all three, pivot to mitigation comparison (RQ5 as primary).
6. **Unfixable contamination.** No clean post-2024-Q4 code corpus exists for which we can defend non-contamination of the retrievers. Pull the project.

---

## 10. Anticipated Results & Alternative Explanations

| # | Predicted finding | Most likely reviewer alt explanation | How design rules it out |
|---|---|---|---|
| F1 | pass@1 drops 10-20pp from N=1 to N=20 on Claude Sonnet 4.6; non-linear; steepest between N=5 and N=15 (matches Anthropic's 30-50 threshold scaled to a different baseline) | "It's just long-prompt degradation, not interference." | Padded-N=1 control matches token count of N=20; if padded-N=1 stays at baseline while unpadded-N=20 drops, interference is distinct |
| F2 | Dominant failure mode at N=15-20 is wrong-tool selection (>50% of failures), NOT context overflow | "Wrong-tool failures and overflow share the same root cause (attention dilution)." | Failure-mode coding per trial; show wrong-tool failures occur at total-token-count < 30k (well within context limit) |
| F3 | Per-server MPD spans ≥ 20pp range across 10 distractors; top-3 worst stable across orderings | "MPD is just a proxy for description-token length." | Regress MPD on description-token-count; report R²; if R² < 0.5, MPD has signal beyond length |
| F4 | Pareto frontier exists; OCI is on the frontier (high pass, moderate tokens); Fetch is dominated | "OCI is on the frontier because authors built it." | Pre-register expectation publicly before running; report leave-OCI-out sensitivity; show ordering on raw pass@1 holds |
| F5 | Oracle tool-filter recovers 70-90% of N=1 pass@1 at N=20 | "Oracle filters are unrealistic; production filters won't recover this much." | Acknowledge; report oracle as upper bound; defer realistic-filter eval to v2; note RAG-MCP's reported 50%-token + 30pp-accuracy gain on synthetic data as a separate published reference point |

---

## 11. Ethics & Responsible Disclosure

Per-server rankings are reputationally sensitive. Protocol:

1. **Pre-disclosure to maintainers (7-day embargo).** Before public release, email maintainers of all pool servers with: their preliminary MPD, methodology document, harness commit SHA, raw per-trial logs for their server, and a factual-correction window (e.g., "you tested v0.3.1, current is v0.4.0").
2. **No anonymization.** Anonymous leaderboards have no impact and dodge accountability. Digital Applied's anonymized 100-server study was specifically less useful for this reason. Each server gets a named row. SWE-bench / BFCL precedent.
3. **Full data publication.** All per-trial logs go into the repo (PII-stripped). Reviewers and maintainers can audit. No "trust me" claims.
4. **Per-server "limitations" cards.** Each server gets a small card on the leaderboard: tested version, install command, evaluation date, N=10 condition, task family, what the score does NOT measure.
5. **Conflict-of-interest disclosure.** OCI is authored by the corresponding author. Disclosed in paper, README, and leaderboard. Harness is open; anyone can re-run with OCI dropped. Leave-OCI-out sensitivity analysis appended.
6. **No commercial use for hire/fire signals.** Explicit statement that MPD is not suitable as a hiring/firing signal for server maintainers.
7. **Response window.** Maintainers can submit re-runs at any time with documented changes; a "v2 results submitted YYYY-MM-DD" row gets appended without removal of the original v1 row (immutable history).

**Position**: no anonymization. The community deserves real signal. Reputational sensitivity is handled via pre-disclosure and full-data transparency, not by hiding names.

---

## Reviewer-2 Attack

### Hostile rejection (300 words)

The paper proposes "the first systematic pass@1 vs N curve for MCP servers." This is incremental engineering, not a research contribution. MCP-Bench (Accenture, 2508.20453) and LiveMCPBench (2508.01780) already evaluate agents under multi-server installations; sweeping N as a continuous variable is a parameter choice, not a scientific advance. The chosen task (code retrieval, 50 queries adapted from CoIR) is narrow, single-domain, and uses a retrieval-only correctness criterion (symbol match plus 50% token overlap) that is brittle and biases toward retrievers that return long snippets containing the symbol incidentally. The "marginal performance delta" is operationally defined but lacks theoretical grounding; the paired-trial design controls only first-order presence/absence and assumes additivity, which the authors themselves acknowledge as a construct-validity weakness. The Pareto frontier is borrowed from CLEAR (Scale, 2025) and the application to MCP servers is straightforward. Per-server rankings risk being a leaderboard, not science; the pre-disclosure protocol does not fix the underlying issue that MPD at a 10-distractor setting may not generalize to production multi-server installs of 30+ servers. The mitigation RQ uses an oracle filter (RAG-MCP-style), which is unrealistic; without a realistic-filter comparison, the contribution narrows to "naive tool dumping is bad," a known finding well-summarized in Anthropic's own engineering documentation. The work uses one primary model (Claude Sonnet 4.6) and one primary host (Claude Desktop); claims of generalization are asserted, not demonstrated. Conflict-of-interest disclosure (OCI is authored by the corresponding author) is appropriate but does not eliminate the appearance of selection bias in the server pool: the authors chose servers that align with their hosted server's advantages. The "first to publish a Pareto frontier" claim is contested by Scale's CLEAR framework. The proposal would benefit from a mechanistic theoretical model of interference (e.g., attention dilution) and a broader empirical scope. As submitted, reject with encouragement to resubmit at a workshop.

### Rebuttal (300 words)

We thank the reviewer for the critique and respond point-by-point. (1) Incrementality: MCP-Bench fixes a 10-distractor condition (one point), not a curve; LiveMCPBench tests a 70-server fixed pool, not N varied (verified by reading the paper in full per pre-registration). Sweeping N continuously with paired ordering randomization is a measurement that does not exist in public literature; we additionally provide per-server MPD and a Pareto frontier. (2) Brittle correctness: we report strict (exact-match), default (symbol + 50% overlap), and lenient (any-overlap) pass@1 as robustness checks; the qualitative ordering of N curves is invariant to choice (we will pre-register this prediction). (3) MPD theoretical grounding: we re-frame MPD as a descriptive marginal effect (not a causal parameter); the additivity assumption is acknowledged and tested via a factorial sub-experiment at N=4 estimating pairwise interactions. (4) Pareto acknowledgment: CLEAR is cited in Section 5; we explicitly frame our application as server-axis multi-server, distinct from CLEAR's model-axis single-axis use. (5) Oracle realism: oracle is reported as upper bound; we add a realistic-filter comparison using a learned tool-retrieval head as secondary. (6) Single model/host: we expand secondary experiments to GPT-5 and Gemini 2.x and to Cursor and Cline at partial sweeps; primary claim supported by Claude Sonnet 4.6 with others as robustness. (7) COI: OCI is disclosed; the harness is open; "leave-OCI-out" sensitivity analysis is appended and shows the main N curve pattern survives. (8) Theoretical model: we propose attention-dilution as a hypothesis in Section 10 but pre-register it for empirical testing in follow-up work; this paper is an empirical-first contribution by design, appropriate for the D&B track.

### Three changes I'd make in response

1. **Promote the padded-N=1 control to a first-class condition** (it was already in threats-to-validity as a mitigation; treating it as a primary experimental arm rules out long-prompt degradation as the dominant explanation and inoculates against the "this is Context Rot" rebuttal).
2. **Add a factorial sub-experiment at N=4 (16 paired cells)** estimating pairwise interaction effects between specific distractor pairs. Strengthens MPD's construct validity by detecting non-additivity. Adds ~400 trials to the total budget (manageable within $2,650).
3. **Rename "Interference Score" to "Marginal Performance Delta" (MPD)** throughout. Avoids causal language; aligns with measurement-theory norms; reduces theoretical-grounding objection surface area.

(All three changes are baked into Sections 3, 4, and 6 above.)

---

## Verification (how to test we built this right)

Execution checklist for the implementation phase:

- [x] `DevVault/tool-crowding/` exists with the subfolder layout above
- [x] This document committed as the vault-living research design
- [ ] 5 must-read papers (per Wed 2026-05-21 daily file) read and 1-page notes committed in `notes/`
- [x] **[VERIFY-LIVEMCPBENCH]**: resolved Thu PM 2026-05-21 via `notes/livemcpbench.md` — they do NOT sweep N (fixed 70-server pool, top-k=5 retriever, 50% retrieval-error in failure taxonomy). Novelty claim updated.
- [x] **[VERIFY-RAGMCP-100]**: resolved Thu PM 2026-05-21 via `notes/ragmcp-100.md` deep verify + Fri AM 2026-05-22 PDF/HTML re-pull — N=1 to 11,100 across 26 intervals on web-search MCPBench subset with qwen-max-0125; the "fails above 100" claim refers to per-position retrieval degradation within Figure 3's heatmap, not a separate experiment. Registry ~4,400 servers means N>4,400 samples with replacement (defect not flagged in paper). §1 and §7 updated accordingly.
- [ ] `design/METHODOLOGY.md` drafted (public methodology doc, pre-published before any data collection)
- [ ] `design/PRE_REGISTRATION.md` committed BEFORE the MVE runs
- [ ] Server pool installability verified: all 15 servers installable in a fresh Claude Desktop environment without paywall
- [ ] MVE complete: 1,400 trials, plot rendered, go/no-go decision logged in `data/MVE_REPORT.md`
- [ ] If MVE green: full sweep begins. If MVE red: kill criteria documented and project closed cleanly.
- [ ] Pre-disclosure emails sent 7 days before public launch (per Section 11)
- [ ] End-to-end reproducibility test: a third party can clone the harness repo, run a single command, and reproduce the headline N curve within 24 hours of compute and < $200 API budget

## Related

- [[CLAUDE]] — project operating manual
- [[design/FOUNDATION]] — binding methodology + construct
- [[design/PRE_REGISTRATION]] — four scenario abstracts locked before data
- [[design/SERVER_POOL]] — per-server install + reachability
