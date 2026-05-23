---
paper: "SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?"
arxiv: 2509.16941
version_read: v2 (2025-11-14)
date_read: 2026-05-21
authors: 22 authors led by Xiang Deng, Jeff Da, Edwin Pan (Scale AI)
artifact: huggingface.co/datasets/ScaleAI/SWE-bench_Pro (public set), github.com/scaleapi/SWE-bench_Pro-os, scale.com/research/swe_bench_pro
contact: jeffrey.da@scale.com
relevance_to_tool_crowding: HIGH for methodology (contamination-resistance design pattern); LOW for task reuse (different problem)
---

# SWE-Bench Pro (Scale AI, Sep 2025 v1 → Nov 2025 v2)

## What they measured

A successor to SWE-Bench Verified built explicitly for contamination resistance and task difficulty. 1,865 problems from 41 actively maintained repos, partitioned across three access tiers: public (731 from 11 GPL repos), commercial (276 from 18 startup-acquired proprietary repos), held-out (858 from 12 GPL repos, reserved for future overfitting detection). Tasks average 107.4 LOC across 4.1 files — explicitly NOT the 1-2 line fixes that make up 161 of 500 SWE-Bench Verified problems. Models cap at 50 turns; oracle is fail2pass + pass2pass test suites.

Best model: Claude Sonnet 4.5 at 43.6% public, Claude Opus 4.1 at 17.8% commercial. Frontier models drop from ~70% on SWE-Bench Verified to ~23% on Pro.

## Headline numbers worth memorizing

**Public set (731 instances, GPL repos):**
| Model | Pass@1 |
|---|---|
| Claude Sonnet 4.5 | **43.6%** |
| Claude Sonnet 4 | 42.7% |
| GPT-5 (high) | 41.8% |
| Claude Haiku 4.5 | 39.5% |
| Kimi K2 Instruct | 27.7% |
| GPT-OSS 120B | 16.2% |

**Commercial set (276 instances, proprietary):**
| Model | Pass@1 |
|---|---|
| Claude Opus 4.1 | **17.8%** |
| GPT-5 (high) | 15.7% |
| GPT-5 (medium) | 14.9% |
| Gemini 2.5 Pro | 10.1% |
| Claude Sonnet 4 | 9.1% |
| GPT-4o | 3.6% |

**The public-to-commercial drop is ~60% relative** even for the same model. Even GPL-only public sets carry contamination signal. Commercial proprietary is the cleanest measurement.

## Methodology choices that stood out

- **License as contamination shield.** GPL/copyleft public set + commercial proprietary set. Legal barrier instead of (or in addition to) temporal cutoff. Novel design pattern.
- **Per-repo cap of 100 instances.** Prevents repo-specialization gaming.
- **Min 10 LOC modification floor.** Excludes trivial fixes by design.
- **Average 107.4 LOC across 4.1 files.** Genuine multi-file work, not single-file patches.
- **Three-stage human augmentation:** problem statement + explicit requirements list + interface specification (class/function names). Tasks are scaffolded for solvability, not raw.
- **Dual fail2pass + pass2pass test oracle.** Behavior verification, not patch matching.
- **SWE-Agent scaffold (Agentless rejected for multi-file work).** Buried methodology choice with real implications.
- **50 turn cap per trajectory.**
- **Cost-capped variant at $2 per task** (Table 5). Cost as primary axis.
- **LLM-as-judge (GPT-5) for failure mode classification** with 87% alignment to human categorization.

## 25 observations easy to miss on a casual read

### The failure mode taxonomy is gold for tool-crowding

1. **Claude Sonnet 4 fails by "endless file reading" 62.6% of the time.** More than half of one of the strongest models' failures is the agent looping through file exploration without resolution. **This is tool-crowding manifesting in a single-tool benchmark.** Sonnet 4 has access to a small SWE-Agent toolset and STILL gets stuck in unproductive tool calls. At N=10 MCPs the effect should compound severely. Cite as primary evidence the mechanism exists.

2. **Context overflow is 17.0% of Sonnet 4 failures, explicitly named.** Direct empirical evidence that overflow is a measurable single-digit-percent failure mode at long-horizon SWE. Tool-crowding's overflow hypothesis is corroborated.

3. **Tool-use errors range from 17.7% (GPT-5) to 42.0% (Qwen3 32B) — a 2.4x model-class spread.** Open-source models fail tool-use ~2.4x more than GPT-5. **Tool-use failure rates depend massively on model class.** Implication: tool-crowding must test multiple model classes; frontier-only testing will understate the failure rate by 2-3x.

4. **Wrong solution dominates: Opus 4.1 50.3%, GPT-5 39.5%.** Even with tools working correctly, models produce syntactically valid but functionally wrong patches half the time. This bounds how much of tool-crowding's variance is attributable to tools vs reasoning.

5. **Per-model failure profiles are sharply different.** Opus → wrong solution + syntax errors. GPT-5 → tool-use + wrong solution. Sonnet 4 → endless file reading + context overflow. Gemini → balanced across tool/syntax/solution. **Tool-crowding should report per-model failure decomposition, not just pass rate.** Their taxonomy is reusable.

### Contamination-resistance as additive defense layers

6. **GPL/copyleft license as contamination shield is a novel methodology pattern.** The legal barrier prevents commercial corpora inclusion. Layered on top of temporal cutoff (SWE-Bench Illusion's defense), this is additive contamination resistance.

7. **Held-out repository tier (858 instances, 12 GPL repos) is a Scale-AI bet on benchmark longevity.** Public set saturates; held-out gets released for overfitting checks. Tool-crowding can adopt this pattern: hold back 20-30% of query set for future re-evaluation when current models saturate.

8. **Commercial set (276 instances, 18 proprietary startups) is the cleanest measurement.** Researchers can submit but not inspect codebases. Closed-evaluation pattern. Tool-crowding's analog: keep a private "stress-test" tier with sealed ground truth that authors run for any submitted model.

9. **Per-repo cap of 100 instances.** Methodology choice tool-crowding should match. Query set should cap N per source repo.

### Multi-file as a hidden N-effect

10. **Multi-file task performance degrades sharply past 3 files.** Frontier models maintain >10% at 10+ files; open-source models approach 0%. **Number of files is acting like number of tools in a way nobody calls out.** Tool-crowding could test for this analog: pass-rate as a function of #-files-in-canonical-answer for the same model.

11. **They explicitly reject Agentless scaffolding for multi-file work.** SWE-Agent (more tools, more scaffold) beats Agentless (minimal scaffold) at high task complexity. **This is a data point AGAINST Anthropic's "fewer tools is better" framing at high task difficulty.** Probable crossover: simple-task SWE-bench Verified favors minimal scaffold; complex-task SWE-Bench Pro favors richer scaffold. Tool-crowding's N-sweep could find the crossover point. **This becomes a tool-crowding section: "When does more tools help?"**

### Statistical and methodology gaps

12. **No trial repetition mentioned.** Same gap as MCP-Universe. Pass@1 reported without CIs. ABC R.10 violated.

13. **All models use same prompt.** Fair across models, but no normalization for model-specific scaffolding (Claude thinking mode, etc.). Same caveat as everywhere else.

14. **22 authors, Scale AI.** Big institutional weight. Tool-crowding cannot match resourcing. But citation weight matters: SWE-Bench Pro will be the heavy referee for agentic SWE for 2+ years. Strategic to converge methodology so we're cite-compatible.

15. **Per-language distribution uneven: Python > JS/TS > Go.** Java/C++/Rust underrepresented. Limitation acknowledged. Tool-crowding inherits this if reusing tasks.

### Specific quotes worth keeping

16. **"161 out of 500 SWE-Bench Verified tasks are trivial one-to-two-line fixes."** Direct slam at prior benchmark. Quote-worthy for tool-crowding's related work.

17. **"Real software engineering tasks may have a variety of correct solutions, even if they do not pass the original tests."** Self-aware meta-limitation. Tests are incomplete oracles. Tool-crowding faces this too, should cite as we make the same trade-off.

18. **Cost-capped results at $2 limit (Table 5).** Cost is treated as a primary axis. Validates tool-crowding's "cost × N × pass-rate" Pareto framing.

### The empty corner: multi-MCP

19. **No multi-tool / multi-MCP discussion anywhere.** SWE-Agent's tool set is whatever SWE-Agent provides. **None of the five papers in this reading list engage with multi-MCP as an IV.** Tool-crowding is genuinely in an empty corner.

20. **Section 7.2 (future work) proposes "Collaborative Development Scenarios... multiple agents or human-agent collaboration"** but not implemented. Multi-agent is on their roadmap; multi-MCP per agent is not. Tool-crowding doesn't conflict, complements.

### Reusable artifacts

21. **HuggingFace dataset `ScaleAI/SWE-bench_Pro`** is the canonical download. Worth examining whether any GPL public tasks have file-discovery components compatible with tool-crowding's code-retrieval framing.

22. **GitHub repo `scaleapi/SWE-bench_Pro-os`** for the harness code. Apache or similar license likely.

23. **Pre-built docker images "promised but not detailed."** Reproducibility commitment with delivery gap. Same pattern as CodeRAG-Bench.

24. **Contact: jeffrey.da@scale.com.** Worth knowing if we ever need to coordinate with Scale on methodology compatibility.

25. **Scale AI's leaderboard maintenance is implied long-term commitment.** Tool-crowding could position to be Pro-comparable: same task framing, same oracle style, same access tiers. Lower friction for cross-benchmark adoption.

---

## What to steal (direct mappings to tool-crowding)

| What | How to apply |
|---|---|
| **License-as-contamination-shield** | Query set tier with GPL repos as legal-barrier-clean tier; layer on top of temporal cutoff |
| **Three-tier access (public / held-out / commercial)** | Adopt at smaller scale: public query set + held-back ~20% for re-eval when models saturate + optional private "submit your model, we run it" tier |
| **Per-repo cap on instances** | Cap per-repo at 5-10 queries to prevent specialization |
| **Failure mode taxonomy with LLM judge + human alignment** | Adopt their 6 categories (wrong solution, tool-use error, syntax error, incorrect file, endless file reading, misunderstood problem). Add tool-crowding-specific: tool collision, wrong-tool selection, description competition. LLM judge with human spot-check (target 80%+ alignment). |
| **Cost-capped variant** | Run primary at unbounded turns; secondary at $2 budget per trial. Pareto frontier on pass-rate × cost × N. |
| **fail2pass + pass2pass behavioral oracle** | Better than string match. For tool-crowding queries with code-retrieval answers, the oracle verifies the *retrieved content's behavior* (compiles + tests pass) not the literal file path matched. |
| **Three-stage human augmentation pattern** | Tool-crowding queries should be scaffolded for solvability, not raw. Problem statement + retrieval requirements + expected answer interface. |
| **Multi-file = multi-tool analog** | Their multi-file degradation curve (>3 files = drop) is a structural analog to tool-crowding's N. Cite as parallel mechanism. |

## What they didn't measure / where they stopped

- **No multi-MCP, no multi-tool-server framing.** Same empty corner as everywhere else.
- **No N-as-IV anywhere.** Their "complexity" axis is file count and LOC, not tool count.
- **No trial repetition / CIs.** Pass@1 only.
- **No tool description quality discussion.** Same blindspot as MCP-Universe.
- **No within-task tool sequencing analysis.** Failure mode categories are aggregate; no time-series of tool calls.

## One open question this raises for tool-crowding

**Should tool-crowding converge methodology with SWE-Bench Pro for cross-benchmark adoption?**

Pro is positioned to be THE long-horizon SWE benchmark for the next 2+ years. Scale AI maintains it. If tool-crowding adopts:
- Same failure mode taxonomy (with tool-crowding additions)
- Same fail2pass + pass2pass oracle style
- Same three-tier access pattern (scaled down)
- Same per-repo cap
- Same cost-capped variant

Then tool-crowding becomes Pro-compatible without colliding. Researchers using Pro for benchmark X can use tool-crowding for multi-MCP X' with shared vocabulary. This is the strategic move.

The alternative (purely original methodology) is more defensible against "you just copied Pro" but at the cost of cross-benchmark adoption.

**Recommendation:** adopt their failure taxonomy + oracle style + tier pattern. Cite explicitly. Frame tool-crowding as the multi-MCP layer in the same family. **This is a Section 3 ("Methodology") decision, not v1-blocking.**

## Actions pulled out of this read

1. **Adopt SWE-Bench Pro's failure mode taxonomy** (with tool-crowding additions: collision, wrong-tool-selection, description-competition). Update RESEARCH_DESIGN.md failure-mode section.
2. **Adopt fail2pass + pass2pass oracle pattern** for any tool-crowding queries where it applies (i.e., retrieval-then-code-execution chains).
3. **Adopt three-tier access pattern** scaled down: 60% public, 20% held-out, 20% optional sealed-evaluation tier.
4. **Adopt per-repo cap** (5-10 queries per source repo).
5. **Add cost-capped variant** to experiment matrix: $2 per trial budget, parallel to unbounded-turn variant.
6. **Inspect HuggingFace ScaleAI/SWE-bench_Pro public set** for any tasks with retrieval-shaped subproblems we could use as tool-crowding queries with their permission (Thu morning, low priority).
7. **Add "When does more tools help?" as a tool-crowding paper section.** Their SWE-Agent > Agentless finding is a real crossover-point question we can characterize with the N-sweep.

## Related

[[abc-best-practices]] [[mcp-universe]] [[swe-bench-illusion]] [[coderag-bench]] [[../RESEARCH_DESIGN]] [[../design/SERVER_POOL]] [[../design/ANTHROPIC_HARNESS_LITERATURE]] [[../../strategy/week-1/2026-05-21]]
