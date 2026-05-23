---
paper: "LiveMCPBench: Can Agents Navigate an Ocean of MCP Tools?"
arxiv: 2508.01780
arxiv_url: https://arxiv.org/abs/2508.01780
html_url: https://arxiv.org/html/2508.01780v2
read_date: 2026-05-21
read_depth: skim (abstract + HTML extraction of Sections 4.1-4.2, failure taxonomy, limitations; PDF body not fully decoded)
verdict: support
authors: Guozhao Mo, Wenliang Zhong, Jiawei Chen, Qianhao Yuan, Xuanang Chen, Yaojie Lu, Hongyu Lin, Ben He, Xianpei Han, Le Sun
version_read: v2 (2026-02-26); v1 was 2025-08-03
relevance_to_tool_crowding: HIGH (closest concurrent work; resolves the [VERIFY-LIVEMCPBENCH] open item in CLAUDE.md)
---

# LiveMCPBench (Aug 2025, v2 Feb 2026)

## What they measured

A 95-task benchmark over a fixed pool of 70 MCP servers exposing 527 tools, tested against 12 LLMs under an agent loop that **retrieves top-k tools per query via embedding similarity** (not all-tools-in-context). They report task success judged by an LLM-as-Judge (LiveMCPEval), plus a failure taxonomy. Headline: Claude-Sonnet-4 at 78.95% success; most models 30-50%.

Their framing is the right diagnosis but the wrong intervention: they correctly state existing benchmarks "typically assume single-server settings and directly inject tools into the model's context, bypassing the challenges of large-scale retrieval and multi-tool composition," and then build a benchmark that **routes around** that problem with a retriever rather than measuring degradation across it.

## Headline numbers worth memorizing

| Quantity | Value | Source |
|---|---|---|
| Servers | 70 | abstract |
| Tools | 527 | abstract |
| Tasks | 95 (from 300 candidate pool) | Section on task construction |
| Models tested | 12 | abstract |
| Claude-Sonnet-4 SR | 78.95% | leaderboard / abstract |
| Most-model SR band | 30-50% | abstract |
| Retrieval errors / total failures | 50.00% | failure taxonomy |
| Tool errors / total failures | 18.33% | failure taxonomy |
| Other errors | 18.33% | failure taxonomy |
| Query errors | 13.33% | failure taxonomy |
| Default retriever | top-5 (k=5) | Section 4.2 |
| Retrieval formula | MCP-Zero style: score = (s_server × s_tool) × max(s_server, s_tool) | Section 4.2 |

## Did they vary N as an IV?

**No.** N is fixed at 70 servers / 527 tools across every experiment. The only ablation in Section 4.2 varies **k** (number of tools retrieved per query: 1, 5, 10) and the embedding model. They never:

- Run the same task with N=10 vs N=70 vs N=200 installed servers.
- Hold the relevant servers constant and vary distractor count.
- Disable the retriever to measure what the underlying interference floor looks like.

This is exactly the gap tool-crowding owns. Their retriever is the workaround that **hides** the N-dependence by collapsing 527 tools into top-5 before the model sees them.

## Methodology choices that stood out

- **RAG-style tool retrieval is the default.** The agent never sees 527 tools in context. It sees top-5 per query, scored by `(s_server × s_tool) × max(s_server, s_tool)`. This is the MCP-Zero formula. The model is operating in a near-single-server regime *after retrieval*, which means the benchmark is measuring **retriever-quality + post-retrieval-execution**, not raw multi-tool agent capacity.
- **LLM-as-Judge oracle** (LiveMCPEval). Acknowledged as a limitation. They explicitly note "Dependence on LLM evaluation."
- **Active tool composition is a behavioral metric, not a controlled variable.** Claude-Sonnet-4 uses 2.71 tools, 5.59 executions, 2.98 retrievals per task on average. They observe correlation with success; they do not intervene on it.
- **Failure taxonomy is the most useful artifact:** Retrieve 50.00% / Tool 18.33% / Other 18.33% / Query 13.33%. **Half of all failures are retrieval failures.** That is a screaming admission that the choice of "use a retriever to flatten N" is itself a failure surface.
- **95 tasks from 300 candidate pool**, proposer-written with "LLM-assisted ideation strictly vetted for authenticity." No reported IAA. Same gap as MCP-Universe.
- **v2 added no N-sweep.** The Feb 2026 revision kept the same architecture. The gap remained open after 6 months of follow-up.

## Methodology gaps (the load-bearing ones for our story)

1. **No N-sweep.** Fixed at 70 throughout. See above.
2. **No padded-N=1 control.** They cannot rule out that retrieval errors are caused by raw pool size vs prompt length vs model.
3. **No distractor counterfactual.** They never test the same task with a curated 5-server set vs the full 70.
4. **No server version pinning visible** in the abstract or extracted body. Same ABC T.6 violation as MCP-Universe.
5. **Single-trial design (n=1 per task per model) implied.** No variance reported. No CIs. ABC R.10 violation.
6. **LLM-as-Judge oracle drift.** They flag it themselves under Limitations.
7. **Top-k retrieval baseline is k=5.** This is exactly the CodeRAG-Bench cliff point. They are sitting on the same critical region without naming it.
8. **The retriever IS the benchmark.** A bad retriever caps measurable success; a good retriever masks the N-stress they claim to measure. Tool-crowding's all-tools-in-context arm dodges this confound.

## What to steal

| What | Apply to tool-crowding |
|---|---|
| Failure taxonomy (Query / Retrieve / Tool / Other) | Adopt as our per-trial failure-mode label. Decompose pass@1 by these 4 buckets. |
| 70-server pool as candidate distractor population | Audit `LiveMcpTool` repo for distractor candidates compatible with our oracle. |
| MCP-Zero retrieval scoring formula | Use as one *baseline* retrieval arm; compare against all-tools-in-context arm. |
| 50% retrieval-error finding | Cite as direct evidence that retrieval is a load-bearing failure surface — which means N matters even when retrieval is used. |
| Claude-Sonnet-4 78.95% with retriever | Our pitch sharpens: when the retriever is removed (raw N in context), what happens to that 78.95%? That delta is the tool-crowding effect. |

## What they didn't measure

- Installed-tool-set effect with retriever **off**.
- N-sweep at any granularity.
- Interference between concurrently-installed servers when all are visible.
- Tool name collisions across the 70 servers (527 tools, near-certain collisions, never enumerated).
- Tool description length / format effects on retriever or model.
- Cost per task or per trial.
- Trial repetition / CIs.
- Per-server contribution (which servers are the highest-yield, which are dead weight). This is our MPD.

## One open question for tool-crowding

**Do we run our N-sweep with their retriever ON, retriever OFF, or both?**

Strong case for **both arms**:

- *Retriever-OFF arm* is the cleanest measurement of raw tool-crowding (what happens when 527 tools sit in context). This is what real Claude.ai users experience today.
- *Retriever-ON arm (MCP-Zero formula at k=5)* lets us claim head-to-head comparability with LiveMCPBench's headline. It also tests the hypothesis they implicitly assume: that retrieval **fixes** N-dependence. If their retriever still degrades with N at k=5, the field's preferred workaround is broken.

Working answer: include both, label clearly, headline the OFF arm because that is the unmeasured floor. Add to RESEARCH_DESIGN.md §4 (independent variables) as a second axis: `retriever ∈ {off, mcp-zero@k=5}`.

Action item: Thu morning, scan `LiveMcpTool` repo for ports compatible with our oracle. Same task as the MCP-Universe scan.

## Compatibility with our gap claim

**SUPPORT.** Three reasons:

1. **They explicitly state the gap:** existing benchmarks "assume single-server settings and directly inject tools." They acknowledge the problem.
2. **They don't close the gap:** by adding a retriever and fixing N at 70, they swap one fixed regime for another. They never make N a variable.
3. **Their own data corroborates our pitch:** 50% of failures are retrieval errors at N=70 with k=5. That is the exact regime CodeRAG-Bench identified as the cliff edge. The fact that retrieval-as-workaround already fails at half-rate is a screaming "this needs to be measured as a function of N" finding that they do not pursue.

The COI nuance: tool-crowding does NOT claim retrieval is broken. We claim N is unmeasured. LiveMCPBench's 50% retrieval-error finding does not contradict us; it shows the workaround is leaky, which makes our IV more interesting, not less.

## Verdict for tool-crowding

LiveMCPBench is the strongest piece of concurrent evidence we have, and it cleanly supports the gap claim without scooping us. They name the problem ("single-server assumptions," "scaled multi-server routing") and then build infrastructure that flattens N back to a fixed value via a retriever. The version-2 revision in Feb 2026 did not add an N-sweep, which means after 6 months of follow-up the gap is still open. Their 50% retrieval-error finding is a free citation hook: it shows the field's preferred workaround for tool count has a 50% failure mode on its own, and nobody has measured how that scales with N. Tool-crowding's contribution is now sharper: not just "vary N" but "vary N with and without the retriever workaround, and show both arms degrade." Resolve `[VERIFY-LIVEMCPBENCH]` in CLAUDE.md as: confirmed they do NOT sweep N; novelty claim stands; add retriever ON/OFF as a second axis in RESEARCH_DESIGN.md.

## Related

[[abc-best-practices]] [[mcp-universe]] [[swe-bench-illusion]] [[coderag-bench]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../harness/SPEC]] [[../design/SERVER_POOL]] [[../../strategy/week-1/2026-05-21]]
