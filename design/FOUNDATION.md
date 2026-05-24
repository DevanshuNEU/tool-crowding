---
title: tool-crowding methodology FOUNDATION (binding for v1)
date_locked: 2026-05-21 (Thursday EOD)
status: BINDING — overrides any SPEC/RESEARCH_DESIGN item in conflict
synthesis_sources: 5 paper notes + Anthropic harness literature + design docs
purpose: gate before harness implementation begins
---

# tool-crowding Methodology Foundation

This document is the binding methodology gate. No harness code starts until every item below is either satisfied-by-design or has an explicit pending action with an owner and a date.

---

## 1. Problem statement (revised 2026-05-21 Thu PM after landscape sweep)

### 1.0 Construct definition (locked 2026-05-21 Thu PM)

> **Tool-crowding** is operationalized as **discrimination interference**: the degradation in tool-selection accuracy attributable to the presence of other concurrently-installed tools whose descriptions are semantically similar enough to compete with the correct tool for selection, isolated from prompt-length effects via padded-N=1 controls.
>
> This is distinct from four related constructs that prior work has measured: (a) **capacity** (context-budget overflow, isolated by Chroma and arXiv 2510.05381 for text retrieval), (b) **latency/cost** (more tools means more setup, separate axis), (c) **tool-call execution failures** (parameter errors after selection, downstream), and (d) **end-task pass rate** (downstream of correct retrieval). Tool-crowding measures only the selection step under fixed budget.
>
> **What this construct predicts** (testable on the Saturday pilot):
> 1. Pass@1 degrades non-linearly with N when N grows in a semantically-overlapping pool of installed MCP servers.
> 2. Per-server Marginal Performance Delta is stable across re-runs (Spearman rho > 0.5) because some servers genuinely compete with others more than uniform noise would predict.
> 3. Padded-N=1 pass@1 does NOT account for the full effect within 5pp on at least 2 of 3 frontier models (otherwise the construct collapses to capacity).
> 4. Description-similarity (cosine of embedding centroids) correlates with MPD: servers with more semantically-overlapping descriptions to neighbors hurt more.
>
> **What this construct does NOT measure**: MCP server quality in isolation, latency, cost, tool-call execution correctness, end-task pass rate given correct retrieval, agentic planning ability.
>
> **Falsification conditions** (these are the kill criteria of §3, restated as construct claims):
> - **F1.** Padded-N=1 fully explains the effect within 5pp on at least 2 frontier models. The construct collapses to capacity. Project pivots to methodology-port + per-server diagnostic.
> - **F2.** Per-server MPD Spearman rho < 0.3 across re-runs. The construct lacks operational reality. Project pivots to global N-effect-only framing.
> - **F3.** Description-similarity-MPD correlation is r < 0.2. The construct's mechanism (semantic competition) is not the right one. Pivot to ordering effects or quality effects.

### 1.1 What we extend

> **What we extend.** Multi-tool interference has been measured before, in three published N-sweeps and two padded-length controls. RAG-MCP (Gan and Sun, arXiv 2505.03275, May 2025) varied N from 1 to 11,100 across 26 intervals on web-search tasks using qwen-max-0125 alone, achieving 43.13% tool-selection accuracy with semantic prefiltering and approximately 50% prompt-token reduction; their registry has roughly 4,400 servers, so above N=4,400 they sample with replacement, padding the prompt with duplicate schemas rather than adding new tools (a defect their paper does not flag). LongFuncEval (Kate et al., arXiv 2505.10570, Apr 2025) swept tool counts of 49, 102, 207, 417, and 741 across 9 models including GPT-4o, reporting 7.59% to 85.58% accuracy degradation on Booking.com REST API tasks with a per-position correct-tool placement control. MCPVerse compared three fixed conditions (Oracle, 218 tools, 552 tools) on general agent tasks and stated verbatim that "most models exhibit performance degradation as the number of available MCPs increased," with Claude-4-Sonnet as a counterexample improving 57.77 to 61.01. For padded-length controls, Chroma's Context Rot study and Liu et al. (arXiv 2510.05381, Oct 2025) ran whitespace-padded and attention-masked variants on text-retrieval tasks, demonstrating that context length alone causes 13.9% to 85% degradation independent of distractor content.
>
> **What tool-crowding does that prior work does not.** This benchmark addresses a specific 6-condition intersection that the prior-art coverage map leaves open: (1) code-retrieval as the task domain rather than web-search, booking APIs, or general agent tasks; (2) a frontier-model panel including Claude Opus 4.7, Sonnet 4.6, GPT-5-class, and Gemini 2.5-class rather than single-model or non-frontier-mixed panels; (3) the padded-N=1 prompt-length control adapted from Chroma's text-retrieval methodology into the MCP tool-context regime, where no prior work has isolated prompt-length from distractor-count for tools specifically; (4) per-server Marginal Performance Delta as a published per-server diagnostic that no MCP benchmark currently reports; (5) full server SHA plus tool-description and JSON-schema hashing into run_id for reproducibility, which neither RAG-MCP nor LongFuncEval nor MCPVerse implements; (6) a second experimental axis varying retriever ON versus OFF, motivated by LiveMCPBench's finding that 50% of failures in their 70-server top-k=5 retrieval regime are retrieval-side errors. The combined contribution is a methodological harness plus dataset that future code-retrieval MCP studies can use to replace ad-hoc fixed-pool comparisons with principled N-curves, accompanied by a frontier-panel pilot.
>
> **Mechanism evidence is unchanged.** The thesis that multi-MCP interference exists in production remains supported by 6 independent data points surfaced during the 5-paper read: Cursor underperformance (29.44 vs 26.41 in MCP-Universe), Sonnet 4 endless file reading (62.6% of failures in SWE-Bench Pro), Sonnet 4 context overflow (17.0% of failures), CodeRAG-Bench top-5 cliff, MCP-Universe Repo Management being the worst domain (max 30.30%, min 12.12%; GitHub MCP has 30+ tools), and tool-use error spread across model classes (17.7% GPT-5 to 42.0% Qwen3 32B). Plus 5 production-engineering anchors that did not exist when the original FOUNDATION was locked: GitHub Copilot publicly reduced default toolset 40→13 for +2-5pp on SWE-Lancer and SWE-bench-Verified (Nov 2025); Anthropic's Code Execution with MCP post reports 150k→2k token reduction; Block restructured Linear MCP from 30+ to 2 tools; Cursor ships a hard 40-tool cap; Simon Willison's "Too many MCPs" post made it canonical hallway-talk in Aug 2025. The mechanism is real and acknowledged across multiple vendors. What tool-crowding adds is a controlled measurement of the curve between the binary cap points that vendors ship.
>
> **The narrative pivot.** The original "first to vary N as an IV" framing is no longer defensible. The replacement: tool-crowding closes a specific 6-condition intersection that the prior-art coverage map leaves open, and ships a reproducible harness that other MCP studies can build on. If the 200-trial pilot on 2026-05-23 shows padded-N=1 pass@1 within 5pp of unpadded-N=20 pass@1 on at least 2 of the 3 frontier models, the project pivots from "headline finding" to "methodology porting tool plus per-server MPD diagnostic," and the launch narrative emphasizes the harness over the empirics.

Old (May 20) thesis is preserved in `RESEARCH_DESIGN.md`. The revised statement above supersedes it and is what goes in the v1 paper abstract and launch post.

---

## 2. Validation summary (revised 2026-05-21 Thu PM)

**Thesis narrowed, not killed.** Five primary papers + three Anthropic engineering posts read on Thursday daytime had the N-as-IV gap. The Thu-evening landscape sweep then found three additional papers that DO vary N (RAG-MCP, LongFuncEval, MCPVerse) and two that DO run padded-length controls for text (Chroma Context Rot, arXiv 2510.05381). The blunt "first to vary N" framing is dead. The 6-condition intersection (code-retrieval × frontier panel × padded-N in tool regime × per-server MPD × pinned versions × retriever ON/OFF) remains open across the full landscape audit. Mechanism evidence is independently real.

### 2a. Already-done: prior N-sweep and padded-control work (revised landscape)

The work tool-crowding extends rather than originates.

| Source | What they did | What they did NOT do |
|---|---|---|
| **RAG-MCP** (Gan & Sun, arXiv 2505.03275, May 2025) | N=1 to **11,100** across 26 intervals on MCPBench web-search subset (range confirmed Thu PM via HTML LaTeX source); ~50% prompt-token reduction via semantic prefilter; 43.13% tool-selection accuracy vs 13.62% baseline | qwen-max-0125 only; **sampled with replacement** (registry has only ~4,400 servers, so N>4,400 is padded with duplicate schemas — not flagged in paper); no code-retrieval; no padded-N=1 control; no per-server MPD; no version pinning; Figure 3 heatmap has no error bars (~1 trial per cell) |
| **LongFuncEval** (Kate et al., arXiv 2505.10570, Apr 2025) | N=49 to 741 (5 levels), 9 models incl. GPT-4o, 7.59-85.58% degradation on Booking.com APIs, per-position alpha control | not code-retrieval; alpha controls position not prompt-length; no per-server MPD; no version pinning |
| **MCPVerse** (arXiv 2508.16260) | 3 conditions (Oracle / Standard=218 / Max-Scale=552), n=250 single-trial T=0.1, no CIs. v1 Sonnet trajectory 57.81 / 61.01 / 57.77 = **inverted-U** with 3.24pp Max-Scale degradation. v2 trajectory 62.3 / 62.4 / 44.2 = **cliff** with 18pp Max-Scale crash | discrete not continuous N; no padded-length control; v1-v2 numerical divergence on same benchmark = instability signal; single-trial no error bars; no per-server MPD; no model-version pinning. **Supports our thesis when read carefully, doesn't contradict** |
| **Chroma Context Rot** | Padded-distractor controls on text retrieval, distractor x length interaction shown | text not tools; not MCP; not code-retrieval |
| **arXiv 2510.05381** (Liu et al., Oct 2025) | Whitespace + attention-mask padding shows 13.9-85% length-only degradation | text retrieval only; no MCP / tools |
| **LiveMCPBench** (arXiv 2508.01780) | top-k=5 retriever over 70 servers / 527 tools, 50% retrieval-error in failure taxonomy | no N-sweep; multi-model but no code-retrieval focus; retriever-as-given not as IV |
| **Anthropic Tool Search Tool (Nov 2025)** | Opus 4: 49%→74%; Opus 4.5: 79.5%→88.1% | closed internal eval; not published; no curve; no methodology |
| **GitHub Copilot 40→13 tools (Nov 2025)** | +2-5pp on SWE-Lancer + SWE-bench-Verified; -400ms TTFT | binary cap not curve; SWE-Lancer / SWE-bench scope only |

### 2b. Direct gap-confirmation evidence (preserved from Thu daytime read)

The papers that originally motivated the project, where tool-crowding extends rather than replaces.

| Source | Closest experiment | What they didn't do |
|---|---|---|
| MCP-Universe (Salesforce) | Section 4.5 multi-server | Only 3 data points, 7 servers max, no enumeration, no randomization, no SHA pinning |
| CodeRAG-Bench (CMU+UW) | Section 4 "Open Retrieval" | Fixed N=5 sources, no agent choice, no order randomization, no description competition |
| SWE-Bench Pro (Scale AI) | SWE-Agent default toolset | Multi-FILE degradation visible (>3 files = drop) but never reframed as multi-TOOL analog |
| SWE-Bench Illusion (Microsoft) | Three contamination probes | Single-turn, no retrieval, no tools at all |
| ABC (Zhu et al.) | CVE-Bench case study | 33% overestimation reduction, but single-domain, no multi-tool axis |
| Anthropic Nov 2025 harness | 2-agent + Puppeteer MCP | One MCP per agent, no quant comparison |
| Anthropic Mar 2026 harness | 3-agent + Playwright MCP | One MCP per agent, qualitative only |
| Anthropic Jan 2026 evals | pass@k + pass^k roadmap | No formal stats, no multi-tool eval |

### Mechanism-visibility evidence (the thing already exists; we measure it)

1. **Cursor (Claude-4.0) 26.41% vs ReAct (Claude-4.0) 29.44%** — 2.97pp loss to enterprise scaffold on the same model. Tool-crowding in production. MCP-Universe Section 4.6.
2. **Sonnet 4 "endless file reading" = 62.6% of failures** in SWE-Bench Pro. The dominant failure mode of a strong model is unproductive tool exploration. With one tool. N=10 will compound.
3. **Sonnet 4 context overflow = 17.0% of failures** explicit in SWE-Bench Pro. Direct support for the overflow mechanism.
4. **CodeRAG-Bench: top-5 docs optimal, past 5 hurts.** Even passive RAG with friendly aggregation degrades past small N. Multi-MCP effect should be at least this large.
5. **MCP-Universe: Repo Management = worst domain (max 30.30%, min 12.12%)**. GitHub MCP has 30+ tools, highest in the benchmark. Worst domain = highest tool count. The effect appears inside their own data, never named.
6. **Tool-use error spread: 17.7% (GPT-5) to 42.0% (Qwen3 32B)** in SWE-Bench Pro. Model-class matters; frontier-only testing understates by 2-3x.

### The narrowed corner verdict (revised 2026-05-21 Thu PM)

**Multi-MCP is a narrowed corner, not an empty one.** The N-as-IV question has been answered three times (RAG-MCP, LongFuncEval, MCPVerse). The "more tools hurts" mechanism is in the open conversation across Anthropic, GitHub Copilot, Block, Cursor, and Simon Willison's writing. What remains genuinely open is the specific 6-condition intersection in §1: code-retrieval × frontier panel × padded-N in tool regime × per-server MPD × pinned versions × retriever ON/OFF. Microsoft Research's MCP Interviewer OSS tool plus their "tool-space interference" Sep 2025 position piece means a benchmark from MSR is plausibly weeks away. Sourcegraph's CodeScaleBench (Mar 2026) is one PR away from adding N levels. **Tool-crowding's runway in this niche is short.**

### What changed about the validation status

Two N-sweep counterexamples on frontier models surfaced in the landscape audit:

1. **LongFuncEval: GPT-4o degraded only 12.88%** vs Llama-3.1-70B at 69.61% on the same N-sweep. However, GPT-4o was tested on 9 cells (3 N levels x 3 alpha positions) while other models on 25 cells, undersampling the tail at the 16K and 65K levels where lost-in-the-middle bites hardest. The 12.88% is on a sparser grid than the comparison points — directional, not like-for-like.
2. **MCPVerse: Claude-4-Sonnet trajectory is inverted-U / cliff, not monotonic improvement.** v1 Sonnet 57.81 (Oracle) → 61.01 (Standard) → 57.77 (Max-Scale): a 3.24pp degradation at high N. v2 same task: 62.3 → 62.4 → 44.2, an 18pp crash. The v1-v2 numerical divergence on a single-trial n=250 benchmark with no CIs is itself a stability signal: their finding is not robust. Both versions support our thesis (Max-Scale degrades) when the per-N trajectory is read carefully, not just the headline.

Neither finding kills the project. Both materially narrow the headline. The mechanism evidence in §1 (6 data points + 5 production-engineering anchors) remains intact.

---

## 3. Kill criteria and remaining risks (revised 2026-05-21 Thu PM)

A project ends if any of these become true. Reviewed weekly at retro.

| Risk | Status (2026-05-21 Thu PM, post-landscape-audit) | Kill trigger |
|---|---|---|
| Someone publishes a multi-MCP N-sweep first | **PARTIALLY FIRED**: RAG-MCP, LongFuncEval, MCPVerse already swept N. Reframed: kill only if someone publishes our specific 6-condition intersection (code-retrieval × frontier × padded-N × MPD × pinned × retriever ON/OFF) before our v1 | external publication of the intersection before our Monday launch |
| Mechanism doesn't reproduce in our harness pilot | unknown until Sat pilot | pilot pass-rate at N=1 vs N=10 shows < 5pp delta with overlapping CIs on ≥2 of 3 frontier models |
| **Pure prompt-length explanation (tightened)** | unknown until Sat pilot | **padded-N=1 pass@1 within 5pp of unpadded-N=20 pass@1 on ≥2 of {Opus 4.7, Sonnet 4.6, GPT-5-class}**. 5pp threshold calibrated against the 13.9% lower bound of arXiv 2510.05381's length-only degradation range — we need an effect meaningfully larger than the known long-context floor, not just any non-zero gap |
| Frontier-model robustness invalidates panel | Partial support that doesn't hold up to deep read (Thu PM): LongFuncEval GPT-4o 12.88% drop was on a sparse 9-cell grid (other models on 25-cell), undersampling the tail. MCPVerse v1 Sonnet "improvement" was inverted-U with 3.24pp Max-Scale degradation; v2 shows 18pp cliff. Direction supports our thesis, does not contradict. | if pilot N=1 vs N=20 deltas are < 5pp on Sonnet 4.6 AND GPT-5-class, pivot to per-server MPD as the diagnostic value-add |
| Discipline cost exceeds solo capacity | unknown | full ABC + 10 TC items + n=3 + 3-tier access takes > 4 weeks for v1 |
| Anthropic / Microsoft Research publish first | MSR Interviewer + "tool-space interference" position piece + Anthropic Tool Search Tool internal numbers are all live; **MSR benchmark plausibly weeks away** | Anthropic OR MSR publishes a quantitative N-sweep covering ≥3 of our 6 conditions before our Monday launch |
| Cursor / Claude.ai change defaults to single-MCP-per-task | speculative | product change announced; tool-crowding becomes historical |
| Query set has unfixable contamination | unknown until 5-gram pilot | > 30% of queries fail the 5-gram contamination check |

**One kill criterion partially fired** (the "first" framing is dead; reframed kill is intersection-specific). **No fatal kill triggers active as of Thu PM.** The tightened padded-N kill is the load-bearing test; it fires or clears on Saturday's 200-trial pilot.

---

## 4. Tailored ABC checklist for tool-crowding

ABC (Zhu et al. 2025) defines 42 binary items across three dimensions. Tool-crowding adds 10 items (TC.1-TC.10) for the multi-MCP-specific axes ABC doesn't cover. Each item below is scored:

- **SAT-D** = satisfied by design (in SPEC / RESEARCH_DESIGN; verify in implementation)
- **PEND** = pending action, with owner + due date
- **N/A** = does not apply to tool-crowding
- **BLOCK** = blocked, needs decision before harness build

### 4.1 Task Validity (T.1 - T.10)

Goal: tasks are solvable iff the agent has the target capability.

| Item | ABC Rule | tool-crowding status | Action |
|---|---|---|---|
| **T.1** | Pin tool versions in prompts | **SAT-D** (servers_pinned.yaml with SHAs in SPEC v1.1) | Implement Fri; extend to hash file into run_id (v1.2 item a) |
| **T.2** | API availability + rate limit handling | **PEND** | Add rate-limit monitor + bounded-retry policy to harness Fri; fail-closed on persistent unavailability |
| **T.3** | Detect API interruption, terminate | **PEND** | Define MCP heartbeat protocol; terminate trial + flag on > 3 consecutive failures |
| **T.4** | Clean state between tasks | **SAT-D partial** (nonce-per-trial in SPEC v1.1) | Implement: MCP process restart between trials + cache clear + agent context fresh per trial |
| **T.5** | Isolate agent from ground truth | **SAT-D** | Constraint: no installed MCP may have file-read access to `tasks/v1/queries.jsonl`. Audit at trial setup. |
| **T.6** | Frozen environment at release | **PEND** | Write `design/REPRODUCIBILITY.md` Fri AM: "frozen pool + controlled selection" formalization. Hash SHAs + descriptions + schemas all into run_id. |
| **T.7** | Verify ground truth annotation | **PEND** | Solo reviewer (Devanshu). Pilot: have one Claude-judge cross-check 20% sample. Target 90%+ agreement. |
| **T.8** | Verify task setup | **PEND** | Pre-flight verifier: confirms N servers exposed, correct query loaded, oracle ready. Implement Fri. |
| **T.9** | Oracle solver demonstrates solvability | **PEND** | Per N level, at least one (model, config) must achieve > 0 pass on each query at N=1 to prove task is solvable. Pilot reveals. |
| **T.10** | Inspect pilot outliers | **PEND** | Fri pilot: 200 trials. Flag 0/n and n/n queries. Drop or fix. |

### 4.2 Outcome Validity (O.a.* - O.i.*, 19 items)

Goal: pass-rate truly indicates task success.

| Item | ABC Rule | tool-crowding status | Action |
|---|---|---|---|
| O.a.1 | Semantic-equivalent ground truth (whole string) | **N/A** | Tool-crowding uses behavioral oracle, not whole-string match |
| O.a.2 | Handle redundant words (whole string) | **N/A** | Same |
| O.b.1 | Negation modifiers (substring) | **N/A** | Same |
| O.b.2 | Prevent listing-all-answers exploit | **PEND** | Audit query set for "agent dumps everything and passes" failure mode |
| O.b.3 | Prevent success by guessing | **PEND** | Audit query set; require multi-step retrieval where guessing < 5% baseline |
| O.c.1 | LLM-as-judge pilot | **N/A unless adopted** | Default: programmatic oracle. If any LLM-judge used, pilot first per ABC. |
| O.d.1 | Manual test case verification | **SAT-D** (adopting SWE-Bench Pro fail2pass + pass2pass) | Implement per-query test annotations |
| O.d.2 | Coverage + complexity metrics | **PEND** | Report cyclomatic complexity + coverage per test suite |
| O.e.* | Fuzz testing (3 items) | **N/A** | Not using fuzz oracle for v1 |
| O.f.1 | Cover all branches in e2e | **SAT-D** | Each trial IS an e2e. Coverage across N levels. |
| O.f.2 | Eliminate non-determinism | **SAT-D** | Server SHAs pinned + model temperature 0 + nonce-per-trial + fixed seed for trial ordering |
| O.g.1 | Ground-truth state includes all outcomes | **PEND** | Define per-query "acceptable answer set" (file paths or content variants) |
| **O.g.2** | **Irrelevant states detect side effects** | **PEND** **(critical)** | **Log EVERY tool call with `(trial_id, step, server, tool, args_hash)`, not just terminal calls. This is how we measure wrong-tool-selection.** |
| O.g.3 | State space complex enough | **SAT-D** | Query set requires multi-step retrieval; random pickaxe baseline < 5% |
| O.h.1 | Specify output format assumptions | **PEND** | Output format spec per query type |
| O.h.2 | Avoid success by guessing | (duplicate of O.b.3) | Same audit |
| O.i.1 | Metric correlates with reasoning process | **SAT-D** | Pass-rate measures retrieval correctness; AE measures partial credit |

### 4.3 Reporting (R.1 - R.13)

Goal: communicate limitations and findings responsibly.

| Item | ABC Rule | tool-crowding status | Action |
|---|---|---|---|
| **R.1** | Open-source dataset | **SAT-D** | Public on launch under permissive license (TBD: MIT or Apache 2.0) |
| **R.2** | Open-source harness | **SAT-D** | `github.com/DevanshuNEU/tool-crowding`, public on launch |
| **R.3** | Data contamination prevention | **SAT-D** | GPL public tier + post-cutoff queries + OCI proprietary tier. Layered defense per SWE-Bench Pro + SWE-Bench Illusion. |
| **R.4** | Consistent update plan | **PEND** | Versioning policy doc: v1.x methodology fixes, v2.x scope expansion. Held-back 20% query tier for future re-eval. |
| **R.5** | Clearly specify capabilities | **SAT-D** | Stated: "interference among multiple installed MCP servers on code-retrieval tasks under varying N" |
| **R.6** | Construct validity | **PEND** | Explicit Section 3 in paper: what tool-crowding measures and does not measure (not "MCP quality", not "code retrieval quality alone") |
| R.7 | Document mitigation efforts | **PEND** | Per-limitation mitigation section in paper |
| R.8 | Qualitative limitation evidence | **PEND** | Per-limitation qualitative discussion |
| R.9 | Quantitative limitation evidence | **PEND** | Per-limitation quantitative impact estimate |
| **R.10** | Statistical significance | **SAT-D** (n ≥ 3 per cell, MDE table in SPEC v1.1) | Report CIs on every headline number; pilot Fri to lock n |
| R.11 | Clear interpretation guidelines | **PEND** | Glossary of metrics + their CIs in paper |
| **R.12** | Baseline comparisons | **SAT-D** (locked 2026-05-22 Fri PM) | Four baselines locked + operationally defined in `RESEARCH_DESIGN.md §3 Baselines`: padded-N=1, single-server-only per code-retrieval MCP, no-MCP-at-all, random-tool-call. Each has an explicit rejection criterion that halts the launch if fired. |
| **R.13** | Trivial agents / non-AI baselines | **SAT-D** (locked 2026-05-22 Fri PM) | Random-tool-call baseline locked in `RESEARCH_DESIGN.md §3 Baselines` row 4 with reject criterion: if random-tool-call pass@1 > 10% at any N, the benchmark is broken (ABC R.13 verbatim); halt launch. |

### 4.4 tool-crowding extensions (TC.1 - TC.10)

Items ABC doesn't address but multi-MCP requires.

| Item | Rule | Status | Source |
|---|---|---|---|
| **TC.1** | Server SHA + tool descriptions + JSON schemas all hashed into `run_id` | **SAT-D** (locked 2026-05-22 Fri AM) | Closed by `design/REPRODUCIBILITY.md §1` (7-artifact chain) + `harness/SPEC.md v1.2` (Section 8 Identity rule). T.6 extended for multi-server. |
| **TC.2** | Distractor order randomized with n trials per (model, N, query) cell | **SAT-D** | MCP-Universe gap; SPEC v1.1 |
| **TC.3** | Tool description token-length measured as covariate | **PEND** | CodeRAG-Bench chunking finding; add to per-trial logging |
| **TC.4** | Tool-call log at EVERY step (extends ABC O.g.2) | **PEND** | Critical for wrong-tool-selection measurement |
| **TC.5** | Cost-capped variant ($2 per trial) parallel to unbounded | **SAT-D** | SWE-Bench Pro Table 5; Anthropic Mar harness 22x cost ratio |
| **TC.6** | Per-model failure decomposition (taxonomy below) | **SAT-D** | SWE-Bench Pro 6-category + 4 tool-crowding additions |
| **TC.7** | Query set hygiene: 5-gram contamination check + GPL-only target tier + temporal cutoff | **SAT-D** (locked 2026-05-22 Fri AM) | Closed by `design/QUERY_SET_HYGIENE.md` (6 layered defenses, 3-tier access, verification workflow). SWE-Bench Illusion + SWE-Bench Pro patterns adopted. CoIR override applied to RESEARCH_DESIGN.md §3 + §8 same day. |
| **TC.8** | Per-repo cap (5-10 queries per source repo) | **SAT-D** | SWE-Bench Pro pattern |
| **TC.9** | Three-tier access (public + held-back ~20% + sealed evaluation tier) | **SAT-D** | SWE-Bench Pro pattern, scaled down |
| **TC.10** | Native MCP heartbeat + fail-injection variant (1 of N servers broken / slow / wrong) | **PEND v2** | CodeRAG-Bench gap; defer to v1.1 if v1 lands |

### 4.5 Failure mode taxonomy (extends SWE-Bench Pro)

For per-model decomposition in the paper. Categories from SWE-Bench Pro (1-6) + tool-crowding additions (7-10).

1. **Wrong solution** — syntactically valid but functionally wrong
2. **Tool-use error** — incorrect tool invocation, parameters, sequencing
3. **Syntax error** — output unparseable
4. **Incorrect file/target** — right intent, wrong target
5. **Endless file reading** — non-productive exploration loop
6. **Misunderstood problem** — wrong objective interpreted
7. **Tool-name collision** — picked wrong tool when names competed *(tool-crowding addition)*
8. **Description competition** — picked wrong tool because description was more salient *(tool-crowding addition)*
9. **Context overflow** — context window exceeded *(tool-crowding addition; subset of SWE-Bench Pro's category 5 made explicit)*
10. **Latency timeout** — tool call exceeded budget *(tool-crowding addition)*

LLM-judge with human spot-check, target 85%+ alignment (SWE-Bench Pro achieved 87%).

### 4.6 Scoring

Counted as of 2026-05-22 Fri PM (after the R.12 + R.13 trivial-baselines lock and the TC bookkeeping pass):
- ABC items applicable: 30 of 42 (12 are N/A for tool-crowding's oracle style)
- ABC items SAT-D: 16 of 30 applicable (53.3%) — was 14 Thu PM; +R.12, +R.13 today
- ABC items PEND: 14 of 30 applicable (46.7%) — was 16 Thu PM
- ABC items BLOCK: 0 of 30
- tool-crowding additions: 10
- tool-crowding SAT-D: 8 of 10 (80%) — was 6 Thu PM; +TC.1 (REPRODUCIBILITY.md + harness/SPEC.md v1.2), +TC.7 (QUERY_SET_HYGIENE.md) today
- tool-crowding PEND: 2 of 10 (20%) — TC.4 (per-step tool-call logging — implementation-side, closed by harness build) + TC.10 (heartbeat + fail-injection — v1.1 / v2 deferral acknowledged)

**No item is blocked. 14 ABC items + 2 TC items are pending. Most pendings close inside the harness build (Sat) and pilot (Sat).**

---

## 5. Pre-disclosure protocol

Per-server rankings are reputationally sensitive. The 7-day pre-disclosure embargo per `../RESEARCH_DESIGN.md` §11 applies before any public release: maintainers receive their preliminary MPD, the methodology document, the harness commit SHA, raw per-trial logs for their server, and a factual-correction window. No anonymization. Each server gets a named row with a "limitations" card. Conflict-of-interest disclosure stands across the corresponding-author's affiliation with OCI.

Maintainer corrections flow through the maintainer-disclosure issue template; immutable v1 rows remain even after v2 re-runs land.

---

## 6. Open gates before harness build

In priority order. Top-to-bottom.

1. **Write `design/REPRODUCIBILITY.md`** formalizing "frozen pool + controlled selection" for T.6. (1-2 hours.)
2. **Apply v1.2 SPEC items** before any trial run: (a) extend `run_id` to hash `servers_pinned.yaml` + `tasks/v1/queries.jsonl` + `harness/oracles/pass_v1.py`; (b) specify padded-N=1 control padding strategy (neutral-tool-shaped descriptions recommended). (1 hour.)
3. **Lock the trivial-baseline list** (R.13): padded-N=1, single-server-only per code-retrieval MCP, no-MCP, random-tool-call. Add to RESEARCH_DESIGN.md experiment matrix. (30 min.)
4. **Write `design/QUERY_SET_HYGIENE.md`** specifying 5-gram contamination check + GPL-only filter + temporal cutoff date. (1 hour.)
5. **Revise DM drafts** against `bip/linkedin-tone.md` with honest "designed + pilot running" framing. (1 hour Thu PM.)
6. **VERIFY-LIVEMCPBENCH** (arxiv 2508.01780): do they vary N or use fixed 70-server pool? (30 min.) Refines "first to" claim.
7. **VERIFY-RAGMCP-100** (arxiv 2505.03275): is "fails above 100" in paper text or only blog? (30 min.) Updates prior-work table.
8. **Confirm Claude 4.7 training cutoff** for temporal-cutoff policy. (10 min web search.)
9. **Read `bip/linkedin-tone.md`** once before DM rewrite. (10 min.)
10. **Decide private-share mechanism** for draft (private GitHub invite vs PDF vs Notion). (5 min.)

**Estimated total: ~6-7 hours of work before Fri harness build starts in earnest.** Doable Thu evening if done now.

---

## 7. Related

[[../notes/abc-best-practices]] [[../notes/mcp-universe]] [[../notes/swe-bench-illusion]] [[../notes/coderag-bench]] [[../notes/swe-bench-pro]] [[ANTHROPIC_HARNESS_LITERATURE]] [[CODERAG_NSWEEP_SCOPE]] [[../RESEARCH_DESIGN]] [[../harness/SPEC]] [[SERVER_POOL]]
