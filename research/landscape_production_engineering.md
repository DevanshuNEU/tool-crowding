---
doc: Production engineering reality — what tool-builders say publicly about tool-crowding
researched: 2026-05-21 (Thu evening)
binding: input to DM framing + RESEARCH_DESIGN.md "why this matters now" paragraph
---

# Production engineering reality check — tool-crowding in the wild

Question this doc answers: *Do the people who ship MCP-using agents in production talk publicly about an N-effect, and if so, what have they said?*

Short answer: **Yes, loudly, for the past 9 months.** The community has converged on "too many tools hurts" as folk wisdom, and three of the biggest shippers (GitHub Copilot, Block/Goose, Anthropic itself) have published either numbers, knobs, or design patterns that assume the effect is real. What's missing is a clean controlled benchmark — which is the gap tool-crowding fills.

---

## Evidence matrix

| # | Source | URL | Date | Author/role | Verbatim claim | Direct or indirect |
|---|--------|-----|------|--------------|----------------|--------------------|
| 1 | GitHub Blog | https://github.blog/ai-and-ml/github-copilot/how-were-making-github-copilot-smarter-with-fewer-tools/ | 2025-11-19 | Anisha Agarwal & Connor Peet (GitHub Copilot eng) | "giving an agent too many tools doesn't always make it smarter. Sometimes it just makes it slower" ... "In offline benchmarks, we observed a 2–5 percentage point decrease in resolution rate on benchmarks including SWE-Lancer when the agent had access to the full built-in toolset" ... reduced **40 built-in tools to 13 core**, +2–5pp on SWE-Lancer/SWEbench-Verified, –400ms TTFT | **DIRECT** — controlled comparison, named benchmarks, named models (GPT-5, Sonnet 4.5) |
| 2 | Anthropic Engineering | https://www.anthropic.com/engineering/code-execution-with-mcp | 2025-11-04 | Adam Jones & Conor Kelly (Anthropic) | "Today developers routinely build agents with access to hundreds or thousands of tools across dozens of MCP servers." ... "as the number of connected tools grows, loading all tool definitions upfront and passing intermediate results through the context window slows down agents and increases costs." Proposes code-execution-with-MCP as a workaround: "reduces the token usage from 150,000 tokens to 2,000 tokens — a time and cost saving of 98.7%" | **INDIRECT** — frames the problem and ships a workaround; no controlled N-sweep |
| 3 | Anthropic Engineering | https://www.anthropic.com/engineering/writing-tools-for-agents | 2025-09-11 | Ken Aizawa et al. (Anthropic) | "Too many tools or overlapping tools can also distract agents from pursuing efficient strategies." ... "Your AI agents will potentially gain access to dozens of MCP servers and hundreds of different tools." | **INDIRECT** — official Anthropic guidance treats the effect as known; no number attached |
| 4 | Simon Willison's blog | https://simonwillison.net/2025/Aug/22/too-many-mcps/ | 2025-08-22 | Simon Willison | "Adding just the popular GitHub MCP defines 93 additional tools and swallows another 55,000" tokens ... "LLMs are known to perform worse the more irrelevant information has been stuffed into their prompts." ... "MCPs which are a constant cost and garbage in my context. Use GitHub's MCP and see 23k tokens gone." | **INDIRECT** — token-cost arithmetic, not accuracy measurement; influential opinion piece |
| 5 | Block Engineering | https://engineering.block.xyz/blog/blocks-playbook-for-designing-mcp-servers | 2025-06-16 | Salman Mohammed & Kalvin Chau (Block) | Linear MCP went from "30+ tools" mirroring API endpoints down to **two tools** (`execute_readonly_query`, `execute_mutation_query`). Rationale: "This reduction in tools means the model can now find the necessary parameters by checking the description of a single, relevant tool instead of choosing from numerous specific ones." Asking "what issues is bob@example.com working on" previously took "4–6 tool calls". | **INDIRECT** — design rebuild driven by selection-confusion, no controlled accuracy numbers published |
| 6 | Cursor (product behavior) | https://forum.cursor.com/t/mcp-server-40-tool-limit-in-cursor-is-this-frustrating-your-workflow/81627 + https://github.com/cursor/cursor/issues/3369 | 2025 (recurring) | Cursor users + docs | Cursor **hard-caps active MCP tools at 40**; ships only the first 40 to the agent. Reasoning per docs: context-window management. Forum users want it lifted; community-built `mcp-hub-mcp` exists as workaround | **DIRECT** as a shipped knob; **INDIRECT** as evidence of accuracy effect (no Cursor staff published numbers) |
| 7 | Anthropic Claude Code (GitHub Issues) | https://github.com/anthropics/claude-code/issues/16218 (Per-Agent MCP Scoping) | 2025 | Community + maintainers | "MCP tool definitions are loaded into every context (main agent + all sub-agents spawned via Task()), and with many tools across multiple MCP servers, this consumes 15–20% of context capacity before any conversation begins." | **DIRECT** as token accounting; the feature request itself is evidence the team treats this as a real cost |
| 8 | RAG-MCP paper (arXiv 2505.03275) | https://arxiv.org/abs/2505.03275 | 2025-05 | academic | Stress test varies MCP count 1→11,100 in 26 intervals; RAG-tool-retrieval gets 43.13% vs 13.62% baseline selection accuracy, –50%+ prompt tokens. Cited approvingly by production posts (e.g. Writer's gateway post) | **DIRECT** academic but referenced as the canonical "this is real" anchor by industry blogs |
| 9 | Writer Engineering | https://writer.com/engineering/rag-mcp/ | 2025 (late) | Writer eng | "When too many tools become too much context" — reframes RAG-MCP findings into a gateway-pattern recommendation; argues for retrieval-over-tools | **INDIRECT** — industry adoption of RAG-MCP framing |
| 10 | Jenova.ai | https://www.jenova.ai/en/resources/mcp-tool-scalability-problem | 2025 | vendor blog (mcp-tool product) | "Accuracy on correct tool selection dropped from ~95% with a focused toolset to ~71% with the full GitHub MCP server loaded — a 24-point accuracy gap caused purely by context bloat with no change to the model, task, or system prompt." | **DIRECT** number but vendor-incentivized — not peer-reviewed, exact methodology not published |
| 11 | DEV community (AWS Heroes) | https://dev.to/aws-heroes/mcp-tool-design-why-your-ai-agent-is-failing-and-how-to-fix-it-40fc | 2025 | community engineer | "Performance degrades sharply past 20 tools, and the failure is not gradual; it's a cliff." Pet Store API experiment: 107 tools = total failure, 20 tools = 19/20, 10 tools = perfect | **DIRECT** controlled experiment but uninflected by peer review; toy domain (Pet Store) |
| 12 | Cline docs | https://docs.cline.bot/mcp/mcp-overview | ongoing | Cline team | Cline ships MCP integration with awareness of tool-budget concerns; ecosystem chatter around scoping per workspace. Less explicit than GitHub/Block but the product UX (per-server toggles) implies the design constraint | **INDIRECT** — shipped knob, no published number |

---

## Synthesis (≤400 words)

**1. Is there a public consensus that "too many tools hurts"?** Yes. The shape of consensus is "selection accuracy degrades as N grows + context bloat is real," reached independently across Anthropic (Sep & Nov 2025 engineering posts), GitHub (Nov 2025), Block (Jun 2025), Simon Willison (Aug 2025), Cursor's product behavior (cap = 40), and the RAG-MCP arXiv paper. Nobody who ships these systems disputes this. The fights are about *what to do* (retrieval, gateways, code execution, server scoping, sub-agents) not *whether the phenomenon is real*.

**2. Has anyone published a number?** Three real ones, one suspicious one:
- **GitHub:** 40→13 tools, +2–5pp on SWE-Lancer and SWEbench-Verified (GPT-5 + Sonnet 4.5), –400ms TTFT. This is the cleanest production number that exists.
- **Block:** 30+ → 2 tools on Linear MCP. Qualitative, no accuracy delta.
- **RAG-MCP arXiv:** 43.13% vs 13.62% selection accuracy across an N=1→11,100 sweep (academic).
- **Jenova.ai:** 95% → 71% with GitHub MCP loaded. Vendor blog, methodology unpublished — treat as a directional anchor only.

**3. Has anyone shipped a "max N" knob?** Yes: **Cursor (cap=40)** is the canonical example. Claude Code/Anthropic's answer is structural rather than a cap — sub-agents with isolated tool sets + the code-execution-with-MCP pattern. GitHub Copilot's answer was to ship a smaller default toolset and add adaptive tool clustering / embedding-guided routing. Block's answer was tool-design philosophy (layered tools).

**4. If they ship but don't publish numbers, what does it mean?** (a) competitive moat — partially, especially for Cursor and Anthropic which avoid disclosing internal evals; (b) not real — ruled out by the convergence of mitigations across competitors; (c) not measured cleanly — most likely. The shippers know it's real because they see it in dogfooding and user reports, but they've shipped mitigations rather than benchmarks. **GitHub's Nov 2025 post is the first major production team to publish controlled-comparison numbers.**

**5. Anthropic-DM-reception test.** Honest read: Jeremy Hadfield / David Hershey would not say "we've been waiting for someone to do this" (Adam Jones and Ken Aizawa have already published the framing pieces — Anthropic knows). They also wouldn't say "we measured this and it's nothing" (their public guidance contradicts that). The likely reaction is closer to: *"interesting — does your code-retrieval setup isolate the N-effect from the well-known context-bloat confound? Where does it diverge from RAG-MCP-100?"* That's a survivable question if RESEARCH_DESIGN.md's §1 novelty paragraph is honest about RAG-MCP overlap and the N-sweep × code-retrieval × multi-model differentiator is sharp.

---

## Top 3 most useful quote-anchors (for DM + RESEARCH_DESIGN §1 "why this matters now")

1. **GitHub Copilot, 2025-11-19** — "*giving an agent too many tools doesn't always make it smarter. Sometimes it just makes it slower*" + the 40→13 / +2–5pp / –400ms numbers. URL: https://github.blog/ai-and-ml/github-copilot/how-were-making-github-copilot-smarter-with-fewer-tools/
2. **Anthropic Engineering (Adam Jones, Conor Kelly), 2025-11-04** — "*Today developers routinely build agents with access to hundreds or thousands of tools across dozens of MCP servers*" + the 150k → 2k token reduction. URL: https://www.anthropic.com/engineering/code-execution-with-mcp
3. **Simon Willison, 2025-08-22** — "*Adding just the popular GitHub MCP defines 93 additional tools and swallows another 55,000*" tokens; Cursor/Amp usable window ≈176k. URL: https://simonwillison.net/2025/Aug/22/too-many-mcps/

## Bonus anchors (for harness/comparison)

- **RAG-MCP arXiv 2505.03275** — already in your novelty audit; the N=1→11,100 sweep is the prior art to beat. https://arxiv.org/abs/2505.03275
- **Block Engineering, 2025-06-16** — 30+ tools → 2 tools on Linear MCP. https://engineering.block.xyz/blog/blocks-playbook-for-designing-mcp-servers
- **Anthropic "Writing effective tools for agents," 2025-09-11** — "*Too many tools or overlapping tools can also distract agents from pursuing efficient strategies.*" https://www.anthropic.com/engineering/writing-tools-for-agents
