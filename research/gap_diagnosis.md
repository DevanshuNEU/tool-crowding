---
doc: Why hasn't tool-crowding been done? Gap diagnosis
researched: 2026-05-21 (Thu evening)
binding: input to Sunday retro + go/no-go before Monday launch
---

# Gap diagnosis — tool-crowding

## Gold mine evidence

- **MCP launched Nov 2024; field is ~18 months behind real-user deployments.** Microsoft Research's MCP Interviewer survey (Jul 2025) cataloged 1,470 servers but ran zero N-sweep experiments; they cite external "up to 85% drop" numbers rather than measuring them ([MS Research blog](https://www.microsoft.com/en-us/research/blog/tool-space-interference-in-the-mcp-era-designing-for-agent-compatibility-at-scale/)). Academia is structurally behind the deployed-reality curve.
- **Every benchmark that names the problem routes around it.** LiveMCPBench (arxiv 2508.01780) fixes N=70 and adds a retriever; MCP-Bench (2508.20453) and MCP-Atlas (2602.00933) both fix N and don't sweep. MCPAgentBench (2512.24565) mentions "anti-interference" as a category but doesn't sweep N as the IV. The methodological pattern is "build a benchmark at one N, ship leaderboard."
- **ABC best-practices paper (arxiv 2507.02825, Jul 2025) only made N-sweep methodologically practical 10 months ago.** Before ABC's pre-registration / trivial-baselines / per-trial-CI framework, an N-sweep paper would have been hard to publish credibly. The window opened recently.
- **Padded-N=1 control is essentially absent from the literature.** Search across BFCL, ToolBench, LongFuncEval, RAG-MCP, LiveMCPBench: none isolate "long prompt with one tool" from "long prompt with N tools." The cleanest decomposition of the prompt-length confound is genuinely unclaimed.
- **No per-server / per-tool Marginal Performance Delta in any benchmark surveyed.** MCP-Bench, LiveMCPBench, MCPToolBench++ treat distractor pools as homogeneous bags. The "which specific servers are dead weight" question is unasked.

## Empty mine evidence (the part Devanshu must read)

- **LongFuncEval (arxiv 2505.10570, May 2025) already swept N from 49 to 741 tools across 6 models and found 7.59% to 85.58% degradation.** This is the most threatening signal. They varied tool count systematically, tested Mistral-large, Llama-3.1-70b, GPT-4o, ToolACE, BitAgent, Granite. GPT-4o showed "minimal drop" — model-dependent effect. The headline "tool count matters" is already published with a real N-sweep ([arxiv 2505.10570](https://arxiv.org/html/2505.10570v1)).
- **Context Length Alone Hurts LLM Performance Despite Perfect Retrieval (arxiv 2510.05381, Oct 2025) shows 13.9-85% degradation from pure prompt length** even when irrelevant tokens are masked to whitespace ([arxiv 2510.05381](https://arxiv.org/abs/2510.05381)). The degradation range *almost exactly matches* LongFuncEval's tool-count range. **Prior probability that our N-effect collapses to prompt-length confound: HIGH (probably 40-60%).** This paper is the loaded gun pointed at kill-criterion #3.
- **Berkeley Function Calling Leaderboard (BFCL) has shown for a year that "every model performs worse when given more than one tool"** — published common knowledge. The marginal contribution of one more N-sweep paper is shrinking.
- **OpenAI's published soft cap of ~20 functions** and Anthropic's tool-writing guide both treat "fewer is better" as accepted wisdom. Industry has already converged on the answer without academic measurement; the field may consider the matter qualitatively settled.
- **6-month-after-v1 inaction is a signal.** LiveMCPBench v2 (Feb 2026) added zero N-sweep despite 6 months of follow-up time. Either they tried it and the results were uninteresting, or they considered it not worth the engineering cost. Both readings hurt us.

## Renamed mine evidence (already partially covered tonight: RAG-MCP)

- **RAG-MCP (arxiv 2505.03275) varied N from 1 to 11,100 across 26 intervals for tool selection accuracy.** Single model (qwen-max-0125), single task (MCPBench web-search subset); registry holds ~4,400 servers so above N=4,400 they sample with replacement (padded duplicate schemas, defect not flagged in paper). The N-sweep IS published. The "nobody varies N" framing is dead ([already documented in notes/ragmcp-100.md](../notes/ragmcp-100.md); range verified 2026-05-21 Thu PM via HTML + 2026-05-22 Fri AM via re-pull).
- **Toolshed / RAG-Tool Fusion (arxiv 2410.14594) and Re-Invoke / tool retrieval papers** all frame the problem as "retrieval solves it" — implicitly conceding that N matters, then pivoting to retriever quality as the open question. The framing "N-sweep" is partly renamed to "tool retrieval evaluation."
- **MCPAgentBench (Dec 2025) explicitly markets "tool discrimination and anti-interference" as a benchmark category.** The vocabulary "interference" is now occupied.

## Structural reasons the gap exists

1. **Server-pool installation cost is the real bottleneck.** Running 70+ MCP servers reproducibly with SHA pins, schema hashes, oracle isolation is weeks of engineering. Academic labs don't have ops staff. This is why MCP-Universe / LiveMCPBench fix N: it's the only way to ship.
2. **Compute cost is real but not prohibitive.** Devanshu's estimate ($450 inference) is roughly right per model-cell. Cross-model × N-grid × repeats is ~$2-5k. Within reach for a solo researcher but uncomfortable for grad students.
3. **The "retriever solves it" intellectual frame.** Once you accept RAG-MCP's framing that retrieval flattens N, pure N-sweep looks like measuring a problem that already has a workaround. Reviewers will ask "why not just retrieve."
4. **Prompt-length confound is methodologically uncomfortable.** To prove N matters independent of length, you must run padded-N=1 — which most researchers don't think to do because long-context literature already established prompt-length-degradation as a known effect. The padded control is "obvious in hindsight, easy to skip."
5. **MCP-launch timing.** 18 months is the typical academic lag from infrastructure-shift to first-rigorous-paper. We're inside the window.

## Verdict

**Renamed mine with significant empty-mine risk. Confidence: 55%.** RAG-MCP + LongFuncEval already cover "N matters for tool selection." The novelty surviving is: cross-model × code-retrieval × padded-N=1 × per-server MPD. That is a real methodological contribution, but it is a narrower contribution than the launch narrative currently implies. The kill scenario is concrete and probable: if padded-N=1 collapses the curve (Context-Length-Alone paper suggests 40-60% chance), tool-crowding becomes a "we replicated a known confound" paper. **What would change my mind:** a pilot showing N-curve gap between padded-N=1 and unpadded-N=20 of >10pp on at least 2 of 3 frontier models. That gap is the project's load-bearing finding.

## Kill-criterion proposal for the pilot

**If padded-N=1 pass@1 is within 5pp of unpadded-N=20 pass@1 on at least 2 of {Sonnet 4.6, GPT-5, Gemini 2.5} in the 200-trial Thu pilot, kill the harness build.** Pivot to either: (a) per-server MPD as a standalone diagnostic tool (no N-sweep paper, just a "which MCP is dead weight" measurement utility), or (b) reframe entirely as a replication-and-extension of LongFuncEval into the code-retrieval domain (smaller paper, workshop-only, no arXiv). This kill threshold (5pp) is tighter than the existing kill criterion #3 in CLAUDE.md because Context-Length-Alone (arxiv 2510.05381) already establishes the prompt-length floor — we need a *meaningfully* larger effect to claim N matters independently, not just any non-zero gap.
