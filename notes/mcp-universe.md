---
paper: "MCP-Universe: Benchmarking Large Language Models with Real-World Model Context Protocol Servers"
arxiv: 2508.14704
version_read: v1 (2025-08-20)
date_read: 2026-05-21
authors: Salesforce AI Research (Ziyang Luo et al.)
artifact: github.com/SalesforceAIResearch/MCP-Universe (Apache-2.0, 587 stars, 82 forks, v1.1.3 last released 2026-03-25)
leaderboard: mcp-universe.github.io/#results
relevance_to_tool_crowding: HIGH (current public SOTA we are competing against; their Section 4.5 is the niche we own)
---

# MCP-Universe (Salesforce, Aug 2025)

## What they measured

A 231-task benchmark across 6 domains (Web Search 55, Location Nav 45, Financial 40, Browser Auto 39, Repo Mgmt 33, 3D Design 19) using 11 real MCP servers and 133 tools. Tested 16 LLMs under ReAct scaffolding. Headline: GPT-5 at 43.72% overall success rate; Claude-4.0-Sonnet 29.44%; GPT-4o 15.58%. Three evaluator types: format (4), static (32), dynamic (48) for 84 total evaluators.

Salesforce, 12 authors, Aug 20 2025 first posted. Still active: code repo last release v1.1.3 on 2026-03-25.

## Headline numbers worth memorizing

| Model | Overall SR | Best domain | Worst domain |
|---|---|---|---|
| GPT-5 | 43.72% | Financial 67.5% | Repo Mgmt 30.3% |
| Grok-4 | 33.33% | Browser 41.0% | Repo Mgmt 12.1% |
| Claude-4.0-Sonnet | 29.44% | Financial 55.0% | Repo Mgmt 12.1% |
| GPT-4o | 15.58% | Financial 35.0% | Location 8.9% |

**Floor: GPT-4o 15.58%. Ceiling: GPT-5 43.72%. Nobody is above 50%.** The benchmark is genuinely hard.

## Methodology choices that stood out

- ReAct as universal scaffold (except GPT-OSS, which gets OpenAI Agent SDK because it cannot follow ReAct prompts; this is a quiet apples-to-oranges).
- Tasks gated to be hard *with* MCP: "If a task can be easily completed by LLMs without using MCP servers, or can be consistently solved with MCP servers within five retries, we consider it a simple task and brainstorm a new one." This is selection bias toward hard-with-MCP, which is the right bias for measuring capability ceiling, but the wrong bias for measuring tool-crowding floor.
- Execution-based evaluators with three flavors: format, static, dynamic. "Dynamic" means the evaluator re-fetches real-world ground truth at trial time (Yahoo Finance prices, GitHub repo state, etc.).
- Tasks open-sourced as JSON under `mcpuniverse/benchmark/configs/`. Harness is Python + Docker. Apache-2.0.
- Authors cross-validate each other's tasks. No external review, no IAA score reported.

---

## 25 observations easy to miss on a casual read

These are the load-bearing details. Most reviewers will skim past them. Each one matters for what tool-crowding does differently.

### Methodology gaps (the central credibility holes)

1. **No trial repetition. No variance. No confidence intervals.** 231 tasks, single run per (model, task). All headline deltas are point estimates with no error bars. This is the ABC R.10 violation, in full. Tool-crowding's n=3 minimum (per SPEC v1.1, possibly n=5 after Thu pilot) clears this bar trivially.

2. **Section 4.5 (multi-server interference) is a 3-data-point experiment.** Only Claude-4.0-Sonnet on Location Nav (22.22 → 11.11, dropping 11.11pp) and GPT-4.1 on Browser Auto (23.08 → 15.38, -7.70pp) and Financial Analysis (40.00 → 35.00, -5.00pp). They write "the benchmark can serve as a valuable testbed for evaluating the robustness of LLMs when confronted with a larger number of unrelated tools" on the strength of 3 cells. **This is the exact niche tool-crowding owns.** They opened the door and walked away.

3. **The "extended scenario" uses 7 servers, which is FEWER than the base 11.** Section 4.5 reduces server count, not increases it. They never tested all 11 servers exposed at once, never tested N=20 or N=50. Real Claude.ai usage is 10-20 servers; their hardest case is 7.

4. **The 7 servers in the extended bundle are never enumerated.** Paper says "7 servers, 94 tools" with zero specification of which 7. Not reproducible. Not in the GitHub repo's visible docs either.

5. **Distractor order is fixed, never randomized.** No counterbalancing. Tool position bias in in-context selection is documented (LiteLLM, Microsoft Research) and they don't measure it. Our SPEC has order randomization with n trials per cell.

6. **Server versions are not pinned to commits or SHAs.** "Authentic API endpoints" means GitHub MCP server in their March 2026 v1.1.3 release is a different SHA than what the August 2025 paper measured. ABC T.6 explicitly violated. Their leaderboard numbers are not comparable across the release timeline of their own repo.

7. **Dynamic evaluators are not reproducible across time.** "Real-time correct answers" + Yahoo Finance prices + GitHub repo state + Google Search results = ground truth drifts daily. They claim "stable evaluation results across different timestamps" but the mechanism cannot deliver that. A model evaluated in Aug 2025 and again in May 2026 against the same task gets different ground truth.

8. **No discussion of how distractor servers are selected in Section 4.5.** Repo docs don't address it either. The selection mechanism for the most important experiment in the paper is undocumented.

9. **No measure of context length at failure threshold.** Section 4.3 plots token growth vs step count for Claude-4.0-Sonnet only. No per-model context curves. No intervention experiment varying context as IV. They observe correlation, never measure causation.

10. **Cost is never reported.** Total API spend across 231 tasks × 16 models × ReAct steps. Probably $5K-$20K. Reviewers cannot estimate replication cost. Our SPEC commits to publishing per-trial token counts and cost estimates.

### Measurement biases that distort the leaderboard

11. **Claude is benchmarked WITHOUT extended thinking.** Footnote in Table 4: "We do not use the thinking mode." Claude-4.0-Sonnet's 29.44% is its worst-case scaffold. GPT-5 gets reasoning by default. The headline comparison is structurally unfair to Claude.

12. **AE vs SR gap exposes evaluator strictness.** Claude-4.0-Sonnet scores 50.61% on Average Evaluator (proportion of evaluators passed per task) but only 29.44% on Success Rate (all evaluators passed = 1 task). Models partially complete tasks; the binary all-or-nothing oracle masks it. Their headline numbers are a measurement choice, not raw capability. Tool-crowding should report both AE-equivalent (per-evaluator partial credit) and SR.

13. **Format evaluators (4 of 84) penalize reasoning models.** o3 hits 73.50% on format, Claude-4.0-Sonnet 98.29%. Reasoning models output more, less rigidly. If you drop the format gates, the ranking changes. They report SR without this caveat.

14. **GPT-OSS uses a different scaffold (OpenAI Agent SDK) because it cannot follow ReAct prompts.** No normalization across scaffolds. The GPT-OSS column in any table is not comparable to the rest of the row.

15. **Repository Management is the worst domain across the board** (max 30.30% for GPT-5, 12.12% for Claude-4.0 and Grok-4). GitHub MCP has the highest tool count in the entire benchmark (30+ tools). The "worst domain = highest tool count" correlation is the tool-crowding effect appearing inside their own data, never named.

16. **Cursor Agent (Claude-4.0-Sonnet backbone) scores 26.41%, lower than basic ReAct on the same model at 29.44%.** Enterprise scaffold with more tools and more agentic infrastructure underperforms a vanilla ReAct loop. Buried in Section 4.6. **This is tool-crowding manifesting in a shipped product agent and they do not interpret it as such.** Major citation opportunity for the tool-crowding paper.

### Sample design and statistical issues

17. **231 tasks across 6 domains is imbalanced.** Web Search 55, 3D Design 19. The 3D Design column has 19-task power. A 5pp delta in 3D Design is well below MDE.

18. **30 sub-task types listed across domains.** 4-5 sub-types per domain (route planning / optimal stops / location searching / place finding, etc.). Per-sub-type counts are not reported, so most sub-types likely have 4-12 tasks. Sub-type-level claims are statistically meaningless.

19. **Exploration agent results are within sampling noise.** Section 4.4 reports +7.69pp (Browser Auto, GPT-4.1) and declines on other model-domain pairs. With n=39 trials in Browser Auto domain, the MDE at typical proportions is ~14pp. They report deltas below the MDE they never compute.

20. **Summarization agent gives mixed results,** which (correctly) tells you context length is not the dominant failure mode. If it were, summarization would universally help. Their own data quietly contradicts the Section 4.3 long-context narrative.

### Things they don't discuss at all

21. **Tool description format is never shown.** No example of how the MCP server's tool schema is serialized into the prompt. No discussion of description length, JSON-vs-text, ordering, or truncation. This is a Microsoft Research multi-MCP paper's central concern (775 colliding names) and MCP-Universe is silent on it.

22. **Tool name collision is never mentioned.** Across 11 servers and 133 tools, collisions (e.g., `search` in multiple servers, `create_issue` patterns) must exist. Never enumerated, never measured.

23. **Per-task tool-call count distribution is missing.** "Average steps for successful tasks" is reported (GPT-5: 8.22, o3: 4.82) for successful tasks only. Failed-task step distribution would reveal whether failures are early-give-up or late-loop. Hidden.

24. **No inter-annotator agreement on task validity.** "Cross-checked by other authors" is the entire validation protocol. ABC T.7/T.8 violations.

25. **The Discord channel is the main feedback loop** (discord.gg/t9tU77GF). Worth lurking pre-launch to see what users complain about. Likely contains tool-installation pain, evaluator brittleness, distractor selection questions, all evidence that supports the tool-crowding pitch.

---

## What to steal

| What | From where | Apply to tool-crowding |
|---|---|---|
| Execution-based evaluators (format / static / dynamic) | Section 3 | Adopt format + static. Avoid dynamic (drift problem). |
| Apache-2.0 task JSONs | repo: `mcpuniverse/benchmark/configs/` | Reuse a subset of their code-retrieval-adjacent tasks if compatible with our oracle. Cite. |
| Public leaderboard format | mcp-universe.github.io | Same shape: model row, domain columns, single SR number. |
| Domain × model heatmap | Figure 5 (their main result) | Our headline: N-level × model heatmap (their innovation rotated 90 degrees). |
| Open task JSON schema | `category, question, mcp_servers, output_format, evaluators` | Compatible structure; ours adds `n_distractors_required`, `oracle_v`, `provenance_hash`. |
| Cursor underperformance result (29.44 → 26.41) | Section 4.6 | Cite as real-world tool-crowding evidence. Our v1 paper opens with this. |

## What they didn't measure / where they stopped

The whole shape of tool-crowding's niche, summarized:

- **They fix N (number of installed servers) per task.** We sweep N.
- **Section 4.5 is a token gesture at multi-server interference.** 3 data points, never enumerated, never randomized, never reproduced. We make it the entire thesis.
- **They never decompose failure mode.** Tool selection vs description competition vs context overflow vs timeout: all lumped under "low success rate." We decompose.
- **They never pin server versions.** We pin SHAs + descriptions + schemas, hash all into `run_id` (v1.2 SPEC item).
- **They never publish trial counts or CIs.** We commit to n ≥ 3 per cell with explicit MDE.

## One open question this raises for tool-crowding

**Should we benchmark on MCP-Universe's tasks directly?**

Pros: Apache-2.0, already validated, comparable to their leaderboard, immediate apples-to-apples on the "multi-server interference" gap they admit but don't solve. The Cursor 29.44 → 26.41 result is a free citation hook.

Cons: their tasks are designed for a fixed-N setting and may not stress N-variance well. Their oracle is binary; we want per-evaluator partial credit. Their dynamic evaluators drift.

**Working answer:** Pick a code-retrieval-adjacent subset of their Repo Management tasks (since Repo Mgmt is their worst domain and exactly our case study), port to our oracle (static only, no dynamic), and run our N-sweep on that subset *plus* our own query set. This gives us a direct head-to-head on a shared task pool while keeping the methodological upgrades.

Action item: Thu morning, scan `mcpuniverse/benchmark/configs/repo_management/` and identify ports candidates. Decision by Fri.

## Actions pulled out of this read

1. **Scan MCP-Universe's GitHub repo task JSONs** (Thu morning) for Repo Management tasks that port cleanly to our oracle. Target: 5-10 reusable tasks.
2. **Lurk MCP-Universe Discord** for failure-mode complaints; harvest 3-5 quotes for the launch post on Sun.
3. **Cite Cursor 29.44 → 26.41 as the opening anecdote** in the tool-crowding paper / launch post. The shipped-product evidence is stronger than any controlled-experiment opener.
4. **Build the head-to-head leaderboard table** for the launch: tool-crowding-N (our sweep, n=3+ per cell, server SHAs pinned) vs MCP-Universe (theirs, fixed N, no SHAs, single trial). Same models, same task subset where possible.
5. **Cross-reference with their 17 open GitHub issues** for unresolved methodology critiques to incorporate or cite.

## Related

[[abc-best-practices]] [[swe-bench-illusion]] [[coderag-bench]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../harness/SPEC]] [[../design/SERVER_POOL]]
