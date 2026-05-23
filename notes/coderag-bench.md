---
paper: "CodeRAG-Bench: Can Retrieval Augment Code Generation?"
arxiv: 2406.14497
version_read: v2 (2025-02-26)
date_read: 2026-05-21
authors: Zora Zhiruo Wang, Akari Asai, Xinyan Velocity Yu, Frank F. Xu, Yiqing Xie, Graham Neubig, Daniel Fried (CMU + UW per author org)
artifact: code-rag-bench.github.io (project page); GitHub link in project page; reproducible codebase claimed
relevance_to_tool_crowding: HIGH (closest published prior art to our specific niche; mechanism is different but problem is adjacent)
---

# CodeRAG-Bench (Wang et al., CMU + UW — Jun 2024 v1, Feb 2025 v2)

## What they measured

Can RAG help code generation? Six task categories × 10 retrievers × 10 generators × 5 retrieval corpora. 9k+ tasks total across HumanEval, MBPP, LiveCodeBench, DS-1000, ODEX, RepoEval, SWE-bench-Lite, CodeSearchNet-Py. Headline: retrieval helps a lot when corpus quality is right (HumanEval 75.6% → 92.6% with gold docs), helps SWE-bench-Lite from 2.3% → 30.7%, but generators consistently fail to use long context well.

## Mechanism difference vs tool-crowding

CodeRAG-Bench is **passive RAG**: retrieve documents (5 sources, top-K), prepend to prompt, generate. Tool-crowding is **active multi-MCP**: agent decides which tool to call, with what arguments, in sequence. Same underlying problem (context augmentation) different agent contract. **CodeRAG-Bench's "open retrieval" section is the closest experimental analog to multi-MCP but stops well short of it.** Their agent never chooses among retrievers; they pre-aggregate top-1 from each source. Tool-crowding's contribution is the *agent-decides* dimension.

## Headline numbers worth memorizing

**Retrieval performance (NDCG@10, average across tasks):**
- SFR-Mistral-7B (best overall): **67.0%**
- Voyage-code-2 (best proprietary): 63.7%
- BM25 (sparse baseline): 57.7%
- **Sparse-vs-dense gap is only 9.3pp.** Smaller than most people assume.

**End-to-end with gold documents (pass@1):**
| Dataset | Baseline | + Gold | Δ |
|---|---|---|---|
| HumanEval (GPT-4o) | 75.6% | 92.6% | +17.0pp |
| SWE-bench-Lite (GPT-4o) | 2.3% | 30.7% | +28.4pp |
| ODEX-hard (DeepSeekCoder) | 17.2% | 24.1% | +6.9pp |

**Real RAG (not gold), best combinations:**
- HumanEval + StarCoder2 + BM25/Voyage: 52.6%
- ODEX-hard + GPT-3.5: 24.1%
- RepoEval + StarCoder2 + OpenAI-emb + rerank: 53.9%
- SWE-bench-Lite + GPT-4o + retrieval: 21.0%

## Methodology choices that stood out

- **Five retrieval corpora at vastly different scales:** programming solutions (1.1k docs), online tutorials (79.4k), library documentation (34k), Stack Overflow (23.5M from RedPajama), GitHub (1.7M from RedPajama). Total ~25M docs.
- **Top-5 documents is the optimal default.** Tested 1, 2, 5, 10. **Past 5, performance drops.** Direct empirical support for context overflow hypothesis.
- **Chunking matters more than retriever choice.** 200-800 tokens optimal. Pre-retrieval chunking > post-retrieval chunking.
- **"Canonical document" annotations per task** establish the gold-doc upper bound. This is their oracle, not a learned retriever.
- **Generation: temperature 0.2, top_p 0.95, single sample.** No best-of-N nucleus exploration. Numbers are best-case-single-sample.
- **SWE-bench-Lite uses n=21 sampling + majority-vote reranking** (Aider-style). Without that scaffold, raw pass rate is 1-2%. The 21.0% headline is a scaffold-tuned number, not raw model capability.

## 25 observations easy to miss on a casual read

### The scale of the corpus mismatch nobody addresses

1. **23.5M Stack Overflow + 1.7M GitHub = 99.99% of all docs in the corpus.** Programming solutions are 0.005%. Library docs are 0.14%. Yet small-corpus retrievers (programming solutions) score near-perfectly. **Retrieval quality scales inversely with corpus size when content is dense.** The benchmark conflates this with retriever capability.

2. **Top-5 documents is the optimal default; past 5 it hurts.** Tested 1, 2, 5, 10. They never test 20, 50, 100. **This is the most directly tool-crowding-relevant finding in the entire paper:** even passive RAG with friendly aggregation degrades past a small N. Multi-MCP's effect should be at least this large, probably larger because each MCP brings descriptions + arguments not just inert text.

### Counterintuitive retriever findings

3. **Code-specific embedders (Codesage, Jina-v2-code, Voyage-code-2) don't beat the general-purpose SFR-Mistral.** SFR-Mistral 67.0% > Voyage-code-2 63.7% > others. The "code retrieval needs code-specific embedders" assumption is empirically wrong on this benchmark. Methodology implication for tool-crowding: don't assume code-specific MCPs are obviously better in the server pool; benchmark them.

4. **BM25 (sparse, 57.7%) is within 9.3pp of the best dense retriever.** For basic-programming tasks BM25 sometimes beats dense. Lexical overlap is still load-bearing on simple problems. This complicates the "use better retrievers" narrative.

5. **Reranking with 200-800 token chunks "greatly degrades results."** Non-obvious — most engineering assumes reranking always helps. They show it can hurt within their pipeline.

### Generation-side failure modes that scale with context

6. **"Models tend to generate over-complicated programs"** when given retrieval context. DeepSeekCoder specifically becomes "ungrammatically repetitive" with context. This is a generation pathology that tool-crowding's high-N regime will trigger harder. Cite as evidence that more context is not free.

7. **Even with gold documents, HumanEval ceiling is 92.6%, not 100%.** The 7.4pp generation ceiling on the easiest task is a useful upper bound. Tool-crowding's pass rates will never approach 100% even with perfect retrieval; cite this for calibration.

8. **SWE-bench-Lite gold lift is +28.4pp (2.3 → 30.7).** Even with the right files literally in context, the model fails most of the time. **For complex tasks, retrieval is necessary but far from sufficient.** This bounds how much of tool-crowding's pass-rate variance is attributable to retrieval at all.

### Methodology choices that distort comparison

9. **SWE-bench-Lite uses n=21 sampling + majority vote.** Without it, raw pass rate is 1-2%. They report the 21.0% scaffold-tuned number. This is buried. If we compare tool-crowding numbers to CodeRAG-Bench SWE-bench-Lite, we must report whether ours uses similar scaffolding or not.

10. **Generation is single-sample (temperature 0.2, top_p 0.95), no best-of-N for most tasks.** Their numbers are conservative-decode-single-shot. Best-of-N inflates everything by 5-20pp typically.

11. **No Claude models in the LLM lineup.** Tested GPT-3.5, GPT-4o, Command-R, Llama3-8B, StarCoder2-7B, CodeGemma-7B, CodeLlama 7B/34B, DeepSeekCoder 7B/33B. **Anthropic is entirely absent from a benchmark that has been v2-revised in Feb 2025.** Major gap.

12. **No Voyage-large or Voyage-3 embedders.** They test Voyage-code-2 (2024). Voyage-3 (mid-2024) and Voyage-3-large (late-2024) likely outperform. Stale embedder lineup in v2.

13. **Python only.** Not multilingual, not multi-language-mix. Tool-crowding's case study can claim same scope without apology.

### The "Open Retrieval" section is the relevant analog and it stops short

14. **Section 4 aggregates top-1 from each of 5 sources** ("All" condition). This is the closest experimental design to multi-MCP. But it is **not** agent-decides; it is pre-retrieve-then-prepend. **The agent never chooses which tool to call.** Tool-crowding's whole contribution is moving the choice into the agent's loop.

15. **No N-sweep on number of sources.** Their multi-source experiment always uses 5. They never test "what if 3 sources, what if 10 sources, what if 20." This is the obvious next experiment they didn't run.

16. **No source-order randomization.** "All" aggregates in a fixed order. Position bias unmeasured.

17. **No measure of source competition at the agent level.** Their generator sees a flat prepended block of 5 chunks. There is no notion of "the agent picked the wrong source" because no choice was made.

### What v2 changed (and what we should check)

18. **v1: June 2024. v2: Feb 2025.** Between revisions: LiveCodeBench was added explicitly for post-cutoff contamination resistance (echoing SWE-Bench Illusion's concerns). Other deltas unclear without diffing v1/v2 directly.

19. **No v3 since Feb 2025.** With 16 months of model progress since v2, their numbers are likely stale. Claude 4.x, GPT-5, Gemini 2.5 absent.

### Adjacent literature

20. **They cite Aider-style 21-sample majority vote without engaging with whether it inflates apparent capability.** Aider is a community tool; using its scaffolding in a research benchmark is a methodology choice worth interrogating.

21. **No discussion of cost.** Five retrievers × ten generators × eight tasks × averaged metrics is computationally expensive. No total spend reported. Likely $10K-$50K range.

### Architectural blind spots

22. **No notion of retrieval-tool description.** In MCP, the agent reads a tool description before deciding to call it. In CodeRAG-Bench, the retriever has no "description" the agent sees. The agent doesn't know what each source covers. Microsoft's tool-space-interference work (775 colliding tool names) is invisible here because there are no tool names at all.

23. **No latency/cost dimension per retriever.** Section 3.3 Table 4 reports encoding/search latency, but it's not a primary metric. In multi-MCP, latency matters because each tool call is a network round-trip. CodeRAG-Bench's single-batch retrieval erases this.

24. **No "what if some retrievers are broken" robustness study.** They assume all 5 sources work. Real MCP deployments have failing servers, rate limits, timeouts. Tool-crowding should include this as a fault-injection variant.

25. **They have a reproducible codebase** at code-rag-bench.github.io with a "unified interface" promised. Worth examining for: (a) how they implement multi-source aggregation, (b) whether their corpus indexes are downloadable as a clean re-use pool for our own retrieval baselines, (c) whether their canonical-document annotations are open. **If their canonical docs are open and per-task, we can use them as a code-retrieval ground truth for the tool-crowding query set.**

---

## What to steal (direct mappings to tool-crowding)

| What | How to apply |
|---|---|
| **Top-K curve showing degradation past K=5** | Our N-sweep is the multi-MCP equivalent. Cite their K-curve as the precedent for "more is not better." |
| **Gold-document upper bound discipline** | For every query in our set, annotate the "canonical answer documents." If pass-rate with canonical docs is X%, our retrieval ceiling is X%. Anything below is retrieval+generation loss. |
| **NDCG@10 + pass@1 as paired metrics** | Tool-crowding reports both retrieval quality (was the right file in the retrieved set?) and downstream task success (did the agent solve the issue?). Pair them. |
| **LiveCodeBench-style post-cutoff control** | We already need this from SWE-Bench Illusion. Reinforced here. |
| **Their canonical-document annotations (if open)** | Potential ground truth source for our query set's "correct retrieval target." |
| **The "models generate over-complicated programs with context" finding** | We should log output complexity (LOC, AST node count) per trial. If tool-crowding's high-N regime amplifies this, it is a second, qualitative tool-crowding mechanism beyond pass-rate. |
| **Their corpus indexes (if downloadable)** | Pre-built BM25 + dense indexes for HumanEval/MBPP/SWE-bench-Lite corpora. Saves us infrastructure cost on retrieval-only baselines. |

## What they didn't measure / where they stopped

- **Agent decides, not researcher decides.** Their multi-source experiment pre-aggregates top-1 from each of 5 sources. Tool-crowding lets the agent choose tools dynamically.
- **No N-sweep.** Fixed at 5 sources. Tool-crowding sweeps N.
- **No source-order randomization.** Tool-crowding randomizes.
- **No tool descriptions in the loop.** CodeRAG-Bench has no notion of an agent reading a tool's spec and deciding. Tool-crowding's whole point is that descriptions compete for attention.
- **No fault injection.** Sources always work. Tool-crowding can include "some servers are broken / slow / wrong" as a robustness sweep.
- **No Claude.** Major gap given Claude's code performance.
- **No latency dimension.** Multi-MCP's network cost is invisible here.

## One open question this raises for tool-crowding

**Should we re-run CodeRAG-Bench's open-retrieval setup with our N-sweep protocol?**

Specifically: take their 5-source "All" condition and turn it into an N-sweep (N=1, 2, 3, 5, 10, 20 sources). Use their corpora, their generators, their canonical-doc oracle. This produces a direct, citeable apples-to-apples result: **"CodeRAG-Bench fixed N=5; we sweep N and find pass-rate peaks at N=3 then degrades."** If true, it's a 5-line tweet headline.

This is a much smaller experiment than the full tool-crowding harness because it reuses CodeRAG-Bench's infrastructure. Could be done as a "warm-up paper" or Section 6 of the main paper.

Cost: if their indexes are downloadable, probably <$1K to run on top 3 generators. Time: 2-3 days.

**Decision Thu morning:** Inspect their GitHub repo. If reproducibility is good, scope this as Section 6 / supplementary contribution. If not, skip.

## Actions pulled out of this read

1. **Inspect code-rag-bench.github.io GitHub repo** for: corpus index downloadability, canonical-doc annotation format, multi-source aggregation code. (Thu morning.)
2. **Decide whether to run the N-sweep on their "All" setup** as a Section 6 of tool-crowding. Quick win if their infra is reusable.
3. **Add output-complexity logging** to harness SPEC v1.2: per-trial LOC, AST node count, response token count. If high-N degrades these, second mechanism revealed.
4. **Pair NDCG@10 with pass@1** as standard reported metrics, not just pass-rate. Retrieval-quality vs end-task-success decomposition is missing in MCP-Universe.
5. **Add fault-injection variant** to RESEARCH_DESIGN.md: "what if 1 of N servers is broken / slow / returns garbage?" This is an obvious tool-crowding extension CodeRAG-Bench didn't do.
6. **Test Claude models explicitly** in tool-crowding — they're absent from CodeRAG-Bench v2 (Feb 2025) and underweighted in MCP-Universe. The Claude-on-tools gap is real.

## Related

[[abc-best-practices]] [[mcp-universe]] [[swe-bench-illusion]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../design/SERVER_POOL]] [[../harness/SPEC]] [[../../strategy/week-1/2026-05-21]]
