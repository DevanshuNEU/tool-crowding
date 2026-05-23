---
paper: MCPVerse
arxiv: 2508.16260
url: https://arxiv.org/abs/2508.16260
github: https://github.com/hailsham/mcpverse
read_date: 2026-05-21
read_depth: deep
purpose: hypothesize Claude-4-Sonnet improvement before Sat pilot surfaces same
versions_compared: v1 (57.81/61.01/57.77) vs v2 (62.3/62.4/44.2)
---

# MCPVerse — Deep Read

## TL;DR (for skim)

1. **Real paper**, arxiv 2508.16260, code at github.com/hailsham/mcpverse. 250 tasks, 65 MCP servers, 552 tools.
2. **The "57.77 → 61.01 improvement" is a v1 framing issue.** In v1: Oracle=57.81, Standard=61.01, Max-Scale=57.77. That is Oracle → Standard → Max-Scale, NOT monotonic with N. v2 (current) numbers: Oracle=62.3, Standard=62.4, Max-Scale=44.2. The "tools grow, accuracy grows" reading collapses in v2.
3. **Standard mode = UNION of every Oracle minimal toolset.** So Standard is a strict superset of Oracle tools + distractors. Refutes my pre-read hypothesis (a) "Oracle has ground-truth context Standard lacks." Both modes are tool-blind, model picks unaided.
4. **Verdict: most likely (c) data sparsity + (b) capability ceiling, with (a) ruled out and (d) partially true.**
5. **For our pilot:** the Sonnet-improves claim is fragile across paper versions, has no significance test, no multi-trial averaging, and was reframed by the authors themselves between v1 and v2. We should not treat it as established prior. Pre-register the prediction either way.

---

## Q1. Where is MCPVerse published?

**Arxiv only, not peer-reviewed.**

- arxiv: https://arxiv.org/abs/2508.16260 (v1 2025-08-22, v2 current)
- OpenReview submission: https://openreview.net/forum?id=BjZvLXvLZW (status: submitted, not accepted)
- Code: https://github.com/hailsham/mcpverse
- Hugging Face mirror: https://huggingface.co/papers/2508.16260
- Authors: "hailsham" lab (anonymous-style GitHub handle, no major-lab affiliation surfaced)

Caveat: this is a preprint with an open OpenReview thread. No venue acceptance. The numbers shifted materially between v1 and v2 (see Q3), which is a yellow flag for citing it as established.

## Q2. What are Oracle / Standard (218) / Max-Scale (552) modes?

Verbatim definitions from v1:

- **Oracle Mode:** "we load only the minimal set of MCPs required to solve a given problem. While multiple solution paths might exist, we annotate one feasible path for each question and mount only the corresponding MCPs."
- **Standard Mode (32 MCPs, ~218 tools, ~44k tokens):** "designed for a 64k-token context length... The toolset in this mode is the **union of the minimal tool sets required for each task in Oracle Mode**."
- **Max-Scale Mode (65 MCPs, 552 tools, ~140k tokens):** "all 65 MCPs with 550+ tools simultaneously."

**Critical methodological finding (refutes my pre-read hypothesis (a)):**

Oracle does NOT include ground-truth hints. The model still has to pick tools unaided. The ONLY difference between Oracle and Standard is the **size of the tool menu**. Oracle's menu is the per-task minimal set; Standard's menu is the union of all those minimal sets across the 250 tasks (so for any given task, Standard contains the correct tools + a bunch of other tasks' correct tools acting as distractors).

This means: **Oracle → Standard is exactly the discrimination-interference axis we care about.** Same model, same task, same metric, more distractors. That makes MCPVerse a much more direct prior for our pilot than I'd assumed before reading.

## Q3. Reproduce the Claude-4-Sonnet number

**v1 Table 2 (the version Devanshu's earlier agent cited):**

| Mode | Avg | L1 | L2 | L3 |
|---|---|---|---|---|
| Oracle | 57.81 | 68.33 | 53.49 | 51.61 |
| Standard | **61.01** | 70.00 | 56.59 | 61.01 |
| Max-Scale | **57.77** | 66.66 | 55.04 | 51.61 |

**v2 Table 2 (current arxiv version):**

| Mode | SR | L1 | L2 | L3 |
|---|---|---|---|---|
| Oracle | 62.3 | 71.6 | 62.7 | 52.5 |
| Standard | 62.4 | 75.9 | 60.4 | 50.9 |
| Max-Scale | 44.2 | 45.8 | 40.5 | 46.2 |

**Re-reading the v1 trajectory:** 57.81 (Oracle, ~minimal) → 61.01 (Standard, 218) → 57.77 (Max-Scale, 552). That is NOT monotonic improvement with N. It is a **non-monotonic bump at the middle scale**, then degradation. The "Sonnet improves with N" framing the earlier agent flagged is selective — it picks the Oracle → Standard step but ignores Standard → Max-Scale, where Sonnet ALSO degrades by 3.24 points.

**v2 trajectory is even harsher to the original claim:** 62.3 → 62.4 → 44.2. The Oracle → Standard bump shrinks to +0.1 (statistical noise on n=250). Max-Scale collapse is now -18.2 points.

Metric: binary outcome accuracy, pass@1, single trial per task, temperature 0.1. No error bars. No multi-seed reporting. n=250 → standard error ≈ ±3% at 50% accuracy, so a 0.1-point Oracle→Standard gap is well within noise.

## Q4. Authors' hypothesis for the Sonnet improvement

v2 quote (verbatim): *"The three gainers—Claude-4-Sonnet, Qwen3-235B-2507, and GLM-4.5—are recent releases within the past four months, positioned for agentic use; their higher Standard scores indicate stronger exploration and exploitation of a large-scale tool space."*

v1 quote (verbatim, more specific): *"The performance increase for Claude-4-Sonnet suggests that, given sufficient context-handling capacity, the agentic model can absorb richer tool descriptions and, when blocked, actively pivot to alternative tools and strategies instead of stalling."*

**Figure 4/5 case study:** Claude's Oracle-mode attempt blocks on a `validate`/`filter` type-mismatch (auth_token type incompatible). In Standard, the model pivots to a `fetch`-based alternative path that wasn't mounted in Oracle. Author claim: the union toolset opens an escape hatch the minimal set forecloses.

**Why I now think this is partly real but overclaimed:**
- If Oracle's minimal set is annotator-picked and the annotator chose ONE solution path, Oracle can be artificially constrained relative to the model's actual capability. Sonnet's "improvement" in Standard is partly **Oracle being too narrow**, not Standard being objectively easier.
- This is a benchmark-construction artifact, not a tool-crowding property of the model. It means **Oracle is not the true "best case" baseline** — it's an annotator-chosen single-path baseline.

## Q5. Other models' three-mode curves

v1 (most complete cross-model comparison):

| Model | Oracle | Standard | Max-Scale |
|---|---|---|---|
| Claude-4-Sonnet | 57.81 | **61.01** ↑ | 57.77 ↓ |
| GLM-4.5 | 55.0 | 59.1 ↑ | - |
| Qwen3-235B-2507 | 44.8 | 53.2 ↑ | - |
| DeepSeek-R1 | 50.77 | 50.28 ≈ | - |
| Gemini-2.5-Pro | 48.25 | 47.33 ↓ | 42.28 ↓ |
| DeepSeek-V3 | 49.55 | 37.58 ↓ | - |
| GPT-4o | 51.32 | 26.83* ↓ | - |
| Qwen3-30B | 33.31 | 22.58 ↓ | - |
| Kimi-K2 | 55.84 | 16.34* ↓ | - |

(* = prompt-based function calling, not native. GPT-4o and Kimi-K2 hit API tool-count limits and were forced to a different evaluation harness, which is why those drops are huge and not directly comparable.)

**Three models show Oracle→Standard improvement: Claude-4-Sonnet, GLM-4.5, Qwen3-235B.** All three are 2025 agentic releases. The pattern is real enough that it deserves a hypothesis, but the explanation could easily be "Oracle's single-annotated-path is too narrow for strong models" rather than "tools-don't-crowd-strong-models."

## Q6. Models tested + version pinning

**No proper version pinning.** The paper uses "Claude-4-Sonnet" as a label without specifying claude-sonnet-4-20250514 vs claude-sonnet-4-5-20251001 etc. GPT-4o is pinned (GPT-4o-20241120). Qwen, DeepSeek, Kimi versions are partial (Qwen3-235B-2507, DeepSeek-V3.1-Terminus, Kimi-K2-0711).

**Temperature settings (Appendix C):**
- Claude-4-Sonnet, DeepSeek, Gemini: T=0.1
- Qwen3 series: T=0.7
- Kimi-K2-0711: T=0.6

(Variable temperature across models is a methodology issue — Qwen at 0.7 is being judged more stochastically than Claude at 0.1.)

**Implication for us:** "Claude-4-Sonnet" in MCPVerse v1 was likely claude-sonnet-4-20250514 (paper drafted Aug 2025, Sonnet 4.5 released Oct 2025). v2 might be 4.5. Our Saturday pilot is **Sonnet 4.6**, which is generationally ahead of either. Treating MCPVerse's Sonnet-4 result as a prior for our Sonnet 4.6 result is shaky.

## Q7. Tasks/queries

- **n=250** total tasks
- Two types: Information Retrieval, System Operation
- Three complexity levels: L1, L2, L3
- Annotators (undergraduate-level or above) select MCPs from the hub, design tasks, verify (1) valid solution path, (2) objective answers, (3) realistic scenarios, (4) cannot be solved without tools.
- **No contamination policy mentioned.** No held-out split. The MCP definitions are public, so any model trained post-MCP-launch may have seen them.
- Time-sensitive tasks use scripts to fetch real-time ground truth at eval time.
- **No multi-trial reporting. No seed variance. No confidence intervals. No limitations section.**

## Q8. Implications for our pilot

**Pre-read hypothesis (a) — methodology artifact from Oracle containing ground-truth context:** ❌ **REFUTED.** Standard is the strict superset of Oracle's union. Oracle does not contain hints. Both modes are tool-blind.

**Hypothesis (b) — real behavioral finding (Sonnet's training makes it robust to distractors):** ⚠️ **Partially supported, but weakly.** Three 2025 agentic models show the bump. Authors claim "exploration of larger tool space." But the same Sonnet ALSO degrades 3.24 points (v1) or 18.2 points (v2) from Standard to Max-Scale. So even Sonnet has a discrimination ceiling — the curve is **inverted-U, not monotonic**. The "improvement with N" frame is wrong; the truth is "the L1 218-tool point is a sweet spot, after which all models including Sonnet crash."

**Hypothesis (c) — data sparsity / noise:** ✅ **Strongly supported.** n=250, single trial, no error bars. SE ≈ ±3% at 50% accuracy. The v1 Oracle→Standard bump of +3.2 is borderline-significant; the v2 bump of +0.1 is **flat-out noise.** That the same paper produced 57.81→61.01 in v1 and 62.3→62.4 in v2 (same benchmark, same model name, ~6 month gap) suggests the result is not stable across runs.

**Hypothesis (d) — query-distribution artifact:** ⚠️ **Partially true.** Standard is the union of all 250 tasks' minimal sets, so it is heavily biased toward the kinds of tools the annotators happened to need. Tasks that need niche tools see Oracle as just-right; tasks that share tools with many other tasks see Standard as familiar. **The "distractors" in Standard are not random — they are other-task-correct tools.** Some of those may transfer.

**Best-explanation verdict (ranked):**
1. **(c) data sparsity** — the result is within noise on n=250 once you look at v2.
2. **(d) query-distribution artifact** — Standard's distractors are themselves "real" tools the model has been trained to recognize, not random noise. Less interfering than random distractors would be.
3. **(b) capability** — partial. Sonnet does seem to have a real advantage at 218 tools, but it ALSO crashes at 552 tools, so the framing "Sonnet improves with N" is selectively true and overall false.
4. **(a) methodology artifact** — refuted by the union construction.

**Concrete decisions for the Saturday pilot:**

- **Do not kill the project.** MCPVerse is not the counterexample we feared. Once you read past the abstract, Sonnet still degrades at high N (Max-Scale), and the Oracle→Standard bump is within noise in v2. The discrimination-interference effect is preserved.
- **Do reframe one section of RESEARCH_DESIGN.md.** The novelty claim should explicitly handle MCPVerse: "MCPVerse varies N across 3 modes (32 → 218 → 552 tools) on 250 tasks but reports a single trial per task and no significance test; their Oracle→Standard 'improvement' for Claude-4-Sonnet (+3.2 v1, +0.1 v2) is within sampling noise. We address this by running k trials per condition and reporting CIs."
- **Pre-register the prediction:** "If Sonnet 4.6 shows monotonic improvement Oracle→Standard→Max-Scale across our N range with non-overlapping CIs, we reframe to discrimination-capability-divergence study (not interference study). If Sonnet shows inverted-U with degradation at high N, MCPVerse's claim is refuted and our finding is confirmed. If flat with overlapping CIs, we are noise-bounded and need n>250."
- **Watch for the Max-Scale pattern.** If our pilot's high-N condition shows the v2-style 18-point collapse, that is the publishable finding — every model including Sonnet degrades past some N, and the question is where the cliff is for Sonnet 4.6.
- **Multi-trial protocol is now non-negotiable.** MCPVerse's main weakness is single-trial. Our pilot needs k=3 minimum per (model, N) cell so we can put error bars on every claim. Make this an explicit "what MCPVerse should have done" sales point.

## Open follow-ups (not for tonight)

- Pull MCPVerse v2 case-study figure to see the exact alternative-path Sonnet found — is it a genuine capability or a benchmark loophole?
- Email hailsham authors via OpenReview to ask: (i) version string for Claude-4-Sonnet, (ii) why numbers shifted between v1 and v2.
- Consider replicating their Oracle→Standard cell with Sonnet 4.6 + k=10 trials to put error bars on their headline claim. This would be a small standalone contribution if results disagree.

Related: [[RESEARCH_DESIGN]] [[FOUNDATION]] [[notes/ragmcp-100]] [[notes/longfunceval-deep]] [[notes/mcp-universe]]
