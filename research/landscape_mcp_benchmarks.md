---
doc: MCP benchmark landscape audit (beyond MCP-Universe / LiveMCPBench / RAG-MCP)
researched: 2026-05-21 (Thu evening)
binding: input to RESEARCH_DESIGN.md §1 novelty rewrite + competitive-intel check
---

# MCP benchmark landscape audit

Goal: enumerate every MCP-related benchmark / eval / position piece beyond the three already catalogued in `research/` (MCP-Universe, LiveMCPBench, RAG-MCP). Confirm which, if any, sweep N across ≥3 levels with per-N reporting.

## Already known (excluded from matrix)

- MCP-Universe (arXiv 2508.14704) — fixed pool, no N-sweep. [`notes/mcp-universe.md`]
- LiveMCPBench (arXiv 2508.01780) — fixed 70-server pool, top-k=5 retriever, no N-sweep. [`notes/livemcpbench.md`]
- RAG-MCP (arXiv 2505.03275) — sweeps N=1..11,100 on web-search subset, qwen-max only; registry ~4,400 servers so above N=4,400 sampled with replacement (padded duplicate schemas). [`notes/ragmcp-100.md`]

## Matrix — newly found MCP benchmarks / evals / position pieces

| # | Name | URL | Date | Pool size (fixed vs swept N) | Models | Tasks | Open? | Closeness to tool-crowding |
|---|---|---|---|---|---|---|---|---|
| 1 | **MCP-Bench** (Accenture) | [arXiv 2508.20453](https://arxiv.org/abs/2508.20453) / [github](https://github.com/Accenture/mcp-bench) | 2025-08-28 | Fixed: 28 servers / 250 tools. Notes per-server tool count variance (BioMCP 35, SciComp 26, MedCalc 22) but no systematic N-sweep | 20 LLMs incl. o3, gpt-5, llama-3.1-70b | Multi-step, cross-tool coordination | Yes | Medium — observes degradation in weaker models across single- vs multi-server settings, but no controlled N-sweep |
| 2 | **MCPVerse** | [arXiv 2508.16260](https://arxiv.org/abs/2508.16260) | 2025-08-22 (rev 2025-10-11) | **3 modes** (Oracle / Standard 32 srv·218 tools / Max-Scale 65 srv·552 tools, ~140k tokens) — qualifies as ≥3 levels with per-mode results | 8 LLMs incl. Claude-4-Sonnet, Qwen3-235B, GLM-4.5, DeepSeek-V3, GPT-4o, Gemini-2.5-Pro | General agentic (filesystem, finance, travel, news, maps) | Yes (HF + OpenReview) | **HIGH** — already states "most models exhibit performance degradation as N of available MCPs increased." Explicitly rejects retrieval. Not code-domain. |
| 3 | **ScaleMCP** (PwC) | [arXiv 2505.06416](https://arxiv.org/abs/2505.06416) | 2025-05 | 5,000 MCP servers (Fortune 1000). Sweeps synthetic-question density at 3 levels (0/5/10 per tool) and reports NDCG/Recall/MAP @K=1,5,10 | 10 LLMs (GPT-4.1, Claude 3.7, Llama 3.3 70B, etc.) + 5 embedders + 5 retrievers | Tool retrieval + agent execution | Components OSS | **HIGH** — qualifies as N-sweep, but sweeps SQ-per-tool (retriever-side) not raw N. Retrieval-as-solution framing like RAG-MCP. |
| 4 | **MCP-Atlas** (Scale AI) | [arXiv 2602.00933](https://arxiv.org/abs/2602.00933) / [leaderboard](https://labs.scale.com/leaderboard/mcp_atlas) | Leaderboard updated 2026-04-08 | Fixed: 36 servers / 220 tools, 1000 tasks (500 public). Per-task subset of 10–25 tools (3–7 targets + 5–10 distractors) — fixed distractor band, no sweep | Claude 4, Gemini 3 (Flash top at 83.6%), GPT-5, Kimi K2, GLM-4 | Multi-step tool use, distractor-aware | 500-task dataset on HF, eval container on GH | Medium — distractor-aware design but no per-N curve. Closest existing "noisy menu" framing. |
| 5 | **MCPMark** | [OpenReview](https://openreview.net/forum?id=uobROwBsJm) | 2026-01-26 | Fixed: 127 tasks across 5 domains (Notion, GitHub, Filesystem, PostgreSQL, Playwright). No N-sweep. | gpt-5-medium (top 52.56% pass@1), claude-sonnet-4, o3 | Stress-test realistic MCP use | OpenReview submission | Low — stress benchmark, not scaling |
| 6 | **MCP-Radar** | [OpenReview](https://openreview.net/forum?id=I0bbPcMeCj) / arXiv 2509.16213-ish | 2025-09-20 (rev 2026-02-11) | 507 tasks, 6 domains. Fixed pool. No N-sweep. | Closed + open LLMs (unspecified in abstract) | Math, web, email, calendar, file, terminal | OpenReview | Low |
| 7 | **MCP-AgentBench** (USTC) | [arXiv 2509.09734](https://arxiv.org/abs/2509.09734) | 2025-09-10 | Fixed: 33 servers / 188 tools, 600 queries. No N-sweep. | "Leading agents" (unspecified) | 6 query categories | Code on GH | Low |
| 8 | **MCPAgentBench** (note: different paper, near-collision name) | [arXiv 2512.24565](https://arxiv.org/abs/2512.24565) | 2025-12-31 (rev 2026-01-21) | Pool not specified in abstract; "20,000 MCP tools, 841 tasks" in derived dataset | "Latest mainstream LLMs" | Dynamic sandbox w/ distractors | Yes (GH) | Medium — distractor-aware, no explicit N-sweep |
| 9 | **OSWorld-MCP** | [OpenReview](https://openreview.net/forum?id=rceD6wwt4B) | 2026-01-26 (rev 2026-04-11) | 158 tools / 7 apps. Sweeps step budget (15→50) not N tools. | OpenAI o3, Claude 4 Sonnet | Computer-use GUI + MCP | OpenReview | Low — computer-use, step sweep ≠ N sweep |
| 10 | **ComplexMCP** | [arXiv 2605.10787](https://arxiv.org/abs/2605.10787) | 2026-05-11 (rev 2026-05-20) | 300+ tools / 7 stateful sandboxes. Compares full-context vs RAG paradigms. Mentions "action-space scale as bottleneck" but no per-N table per abstract. | Multiple (unspecified) | Software automation, interdependent tools | Seed-driven repro | Medium — names the bottleneck but no published per-N curve |
| 11 | **MCPBench** (modelscope, different from #1) | [github.com/modelscope/MCPBench](https://github.com/modelscope/MCPBench) | OSS 2025-04-14, last code 2025-04-29 | Configurable pool, no fixed sweep protocol | Unspecified | Web search, DB query, GAIA | Yes (246 stars) | Low — framework, not study |
| 12 | **MCPToolBench++** | [emergentmind summary](https://www.emergentmind.com/topics/mcptoolbench) | 2025-08-11 | ~1,500 QA pairs / 40+ tool categories drawn from 4,000-server marketplace. No per-N sweep. | GPT-4, Claude 3.7, Qwen3-coder, Qwen2.5-max, Kimi | Single-step + DAG-chain | Yes | Low |
| 13 | **Blocksworld-MCP** | [arXiv 2512.03955](https://arxiv.org/abs/2512.03955) | 2025-12-03 | Planning/control sandbox; MCP as standardized interface, not the variable | Diverse agent archs | Blocksworld planning | Yes | None — uses MCP as interface, doesn't study it |
| 14 | **Microsoft Research — "Tool-space interference in the MCP era"** | [MSR blog](https://www.microsoft.com/en-us/research/blog/tool-space-interference-in-the-mcp-era-designing-for-agent-compatibility-at-scale/) + MCP Interviewer OSS | 2025-09-11 | Surveyed 1,470 live MCP servers. Position piece, not a benchmark. Cites arXiv 2505.10570 ("up to 85% perf drop in large tool spaces") rather than running own N-sweep | None (no agent runs) | Ecosystem audit + recommendations | MCP Interviewer OSS | **HIGHEST** — closest framing to our thesis. Same language ("tool-space interference"). Authors: Fourney, Payne, Murad, Amershi. No benchmark released, no per-N curve. Position piece. |
| 15 | **GitHub blog — "Smarter Copilot with fewer tools"** | [github.blog](https://github.blog/ai-and-ml/github-copilot/how-were-making-github-copilot-smarter-with-fewer-tools/) | 2025-11-19 | Reduction from 40 → 13 default tools. Reports 2–5 pp improvement on SWE-Lancer + SWE-bench Verified with GPT-5 and Sonnet 4.5. **No per-N curve — just 2 points (40 vs 13).** Mentions embedding-routing covers 94.5% vs 87.5% LLM vs 69.0% default. | GPT-5, Sonnet 4.5 | SWE-Lancer, SWE-bench Verified | Product blog | **HIGH** — code-domain (!) and validates degradation hypothesis. Only 2 N values published, not a sweep, but real production data. |
| 16 | **Anthropic — "Advanced tool use" (Tool Search Tool)** | [anthropic.com/engineering](https://www.anthropic.com/engineering/advanced-tool-use) | 2025-11-24 | "Hundreds or thousands of tools" framing. Reports Opus 4: 49% → 74% and Opus 4.5: 79.5% → 88.1% with Tool Search Tool on. **No per-N curve.** | Claude Opus 4, 4.5 | "MCP evaluations" (unspecified) | Closed | **HIGH** — Anthropic is publicly signalling that tool-count growth is a real problem. Their fix is retrieval (Tool Search Tool). Eval set not open. |
| 17 | **Anthropic — "Code execution with MCP"** | [anthropic.com/engineering](https://www.anthropic.com/engineering/code-execution-with-mcp) | 2025-11-04 | Token savings example (150k → 2k, 98.7%) for single use case. No benchmark, no N-sweep, no accuracy claims. | n/a | n/a | n/a | Medium — adjacent narrative ("agents scale better by writing code to call tools"). Architecture push, not measurement. |
| 18 | **CodeScaleBench** (Sourcegraph) | [blog](https://sourcegraph.com/blog/codescalebench-testing-coding-agents-on-large-codebases-and-multi-repo-software-engineering-tasks) / [github](https://github.com/sourcegraph/CodeScaleBench) | 2026-03-03 | Fixed: 13 Sourcegraph MCP tools vs baseline (no MCP). Reports file recall 0.127→0.277, P@5 0.140→0.478. **Two configurations only, not an N-sweep.** | Claude Code w/ Haiku 4.5 (primary); plans Codex, Cursor, Gemini, Copilot, OpenHands | Multi-repo SWE tasks | Yes | **HIGH** — code-domain, ON/OFF MCP comparison. Closest existing code-retrieval MCP benchmark. Doesn't vary N. |
| 19 | **Maxim AI blog** | [getmaxim.ai](https://www.getmaxim.ai/blog/tool-chaos-no-more-how-were-measuring-model-tool-accuracy-in-the-age-of-mcp/) | 2025-07-17 | 48 → 25 tools, GitHub+Notion MCP. Two N values, 5 models. e.g., Claude Sonnet 4: 66.67% → 73.33%, GPT-4.1: 46.67% → 53.33%. | Claude Sonnet 4, Opus 4, 3.7 Sonnet, Gemini 2.5 Pro, GPT-4.1 | Custom test set | Closed (marketing) | Medium — 2 N values, vendor blog, but real numbers |
| 20 | **"Daily Agent" dev.to** | [dev.to/nebulagg](https://dev.to/nebulagg/mcp-tool-overload-why-more-tools-make-your-agent-worse-5a49) | 2026-03-06 | Anecdotal: full GitHub MCP toolset 71% vs minimal 95% (24pp gap). 1 author, no sweep. | Unspecified | "Representative task set" (unspecified) | Personal blog | Low — anecdote, not study |
| 21 | **Tool-to-Agent Retrieval** | [arXiv 2511.01854](https://arxiv.org/abs/2511.01854) | 2025-11-03 (rev 11-04) | Evaluated on LiveMCPBench (so 70-server pool). 8 embedders. No N-sweep, just retrieval gains (+19.4% R@5). | 8 embedding models | Tool retrieval | Per abstract | Low — retrieval-side optimization |
| 22 | **MCPSecBench / MCP-SafetyBench / MSB** | [arXiv 2508.13220](https://arxiv.org/pdf/2508.13220), [2512.15163](https://arxiv.org/abs/2512.15163), [2510.15994](https://arxiv.org/pdf/2510.15994) | 2025-08 to 2026-03 | Security-focused. Out of scope for tool-crowding (different question). | Various | Attack/defense | Mixed | None — security domain |
| 23 | **MCP Servers at First Glance** | [arXiv 2506.13538](https://arxiv.org/abs/2506.13538) | 2025-06-16 (rev 2026-04-13) | Empirical study of 1,899 MCP servers (code health, vulns). Not an agent benchmark. | n/a | Static analysis | Yes | None — server-side audit |

**Total new entries:** 23 distinct artifacts beyond the 3 already catalogued.

---

## Synthesis (≤400 words)

**1. Total MCP benchmarks beyond the 3 already known.**
23 distinct entries. Eight are agent-task benchmarks (MCP-Bench, MCPVerse, MCP-Atlas, MCPMark, MCP-Radar, MCP-AgentBench, MCPAgentBench-2, OSWorld-MCP, ComplexMCP, MCPToolBench++). Two are retrieval/scale-side (ScaleMCP, Tool-to-Agent Retrieval). Two are code-domain blogs/benchmarks (GitHub Copilot blog, Sourcegraph CodeScaleBench). Two are vendor evals (Maxim, dev.to). One is a position piece (Microsoft Research). One is an Anthropic engineering disclosure (Tool Search Tool). Plus security (3) and ecosystem audits (2).

**2. Of those, which vary N (≥3 levels, per-N reporting)?**
- **MCPVerse** — 3 modes (Oracle / Standard 218 tools / Max-Scale 552 tools), publishes per-mode accuracy. Explicit finding: "most models exhibit performance degradation as the number of available MCPs increased." **This is the single biggest threat to our novelty claim.** It is general-domain, not code-specific, and rejects retrieval.
- **ScaleMCP** — sweeps synthetic-question density at 3 levels with per-K retrieval metrics. N-sweep on retriever quality, not on raw tool count.
- **RAG-MCP** (known) — already sweeps N=1..11,100 (registry ~4,400 servers; above N=4,400 sampled with replacement).
Everything else is single-point or two-point (ON/OFF).

**3. Competitive-intel signals (people ~1 month ahead).**
- Microsoft Research (Fourney, Payne, Murad, Amershi) released the **MCP Interviewer** ecosystem audit tool in Sep 2025 with the exact term "tool-space interference." They have not run an N-sweep agent benchmark yet but have the team, brand, and harness to ship one any week. This is the most likely scooper.
- Anthropic shipped the **Tool Search Tool** (Nov 2025) with hard accuracy numbers proving the problem exists. Their eval harness is closed. They have the data, just no paper.
- GitHub Copilot team (Anisha Agarwal, Connor Peet) ran the production A/B and have 2-point data on SWE-bench Verified. Code-domain — directly adjacent to our thesis.
- Sourcegraph (Stephanie Jarmak) shipped CodeScaleBench in March 2026 with MCP ON/OFF code-retrieval numbers. Adding more N levels is one PR away for them.

**4. What Anthropic is signalling.**
Two engineering posts (Advanced Tool Use, Code Execution with MCP), both arguing that naïve loading of many MCP servers breaks accuracy and that the fix is retrieval (Tool Search Tool) or code-execution-of-tools. They have not released a benchmark. No public hires for an "MCP eval" role found in this pass.

**5. Honest take on crowding.**
Under-claimed at the **specific intersection** of (a) code-retrieval tasks, (b) ≥3 controlled N levels, (c) retriever ON/OFF as a second axis, on (d) multiple frontier models. Over-claimed at the general "more tools hurts" level — MCPVerse, GitHub Copilot, Anthropic, and Microsoft Research have all said it in print. Our defensible wedge is: **code-domain + multi-N curve + retriever-as-axis**. That gap is real but narrow, and Microsoft or Sourcegraph could close it within weeks. Move fast.
