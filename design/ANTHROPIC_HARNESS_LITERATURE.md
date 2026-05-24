---
title: Anthropic harness engineering — literature scan + relation to tool-crowding
date_compiled: 2026-05-21
purpose: position tool-crowding against Anthropic's public harness work; identify Fri DM targets
---

# Anthropic Harness Engineering — What They've Said, What It Means for Tool-Crowding

Anthropic has published three load-bearing pieces on agent harnesses + evals in the last 6 months. Tool-crowding sits in a gap they explicitly leave open: they make qualitative claims about scaffold design but never quantify the multi-tool dimension.

## The three Anthropic posts

### 1. "Effective harnesses for long-running agents" (Nov 26, 2025)
URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

Lead author: Justin Young. Contributors: David Hershey, Prithvi Rajasekaran, Jeremy Hadfield, Naia Bouscal, Michael Tingley, Jesse Mu, Jake Eaton, Marius Buleandara, Maggie Vo, Pedram Navid, Nadine Yasser, Alex Notov. Code RL and Claude Code teams.

**Architecture:** Two-agent system. Initializer agent (1 session) sets up environment, hands off to coding agent (subsequent sessions). Persistent artifacts: `claude-progress.txt`, `feature_list.json`, git repo, `init.sh`.

**Tools per agent:** bash, file read/edit, git, **Puppeteer MCP** (one MCP only — for end-to-end browser testing).

**Failure modes documented:**
- "Declares victory prematurely" → fixed by feature-list-as-source-of-truth
- "Leaves buggy/undocumented code" → git + progress notes
- "Confusion about running app" → `init.sh` at session start
- One-shotting causes context exhaustion mid-feature
- "Compaction alone isn't sufficient"
- JSON feature files more resistant to model corruption than Markdown

**Quantitative results:** NONE. Entirely qualitative.

**Multi-MCP discussion:** NONE. They use exactly one MCP (Puppeteer). No mention of tool selection, tool crowding, or interference.

**Code released:** `github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding`

### 2. "Harness design for long-running application development" (Mar 24, 2026)
URL: https://www.anthropic.com/engineering/harness-design-long-running-apps

Lead author: Prithvi Rajasekaran (Labs team). Acknowledgments include Mike Krieger, Justin Young, Jeremy Hadfield, David Hershey, Barry Zhang, Jake Eaton.

**Architecture:** Three-agent system (GAN-inspired). Planner agent → Generator agent → Evaluator agent. Communication via files.

**Tools per agent:**
- Planner: frontend design skill (read-only)
- Generator: git + file system
- Evaluator: **Playwright MCP** (one MCP only — for clicking through running app)

**v2 changes from v1 (Nov post):**
- Added standalone Planner agent
- Separated Generator from Evaluator (was self-evaluation)
- Removed sprint decomposition with Opus 4.6 (it "largely removed that behavior on its own")
- Moved from per-sprint to end-of-run QA
- Continuous session instead of context-reset handoff

**Quantitative results (rare, worth memorizing):**

| Task | Harness | Duration | Cost |
|---|---|---|---|
| Retro Game Maker (Opus 4.5) | Solo agent | 20 min | $9 |
| Retro Game Maker (Opus 4.5) | v1 harness | 6 hr | $200 (**22x more**) |
| Digital Audio Workstation (Opus 4.6) | v2 harness | 3 hr 50 min | $124.70 |

Detailed DAW breakdown: Planner 4.7min/$0.46, Build1 2h7m/$71, QA1 8.8m/$3.24, Build2 1h2m/$36.89, QA2 6.8m/$3.09, Build3 10.9m/$5.88, QA3 9.6m/$4.06.

**"Context anxiety" finding (Sonnet 4.5):** "agents begin wrapping up prematurely near perceived context limit. Compaction preserves continuity, it doesn't give the agent a clean slate, which means context anxiety can still persist." Opus 4.6 "largely removed that behavior on its own."

**Multi-MCP discussion:** NONE. Single MCP per agent (Playwright). No discussion of tool count, tool interference, or selection.

**Benchmark numbers:** NONE. No SWE-bench, no public benchmarks. Comparisons are qualitative on custom tasks.

**Code released:** Frontend design skill at `github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md`. No three-agent harness template released.

### 3. "Demystifying evals for AI agents" (Jan 9, 2026)
URL: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

Authors: Mikaela Grace, Jeremy Hadfield, Rodrigo Olivares, Jiri De Jonghe. Contributors: David Hershey, Gian Segato, Mike Merrill.

**Three grader types:**
- Code-based (string matching, binary tests, static analysis, outcome verification)
- Model-based (rubric scoring, NL assertions, pairwise)
- Human (SME review, crowdsourcing, spot-check)

**Metrics they recommend:**
- pass@k (probability of ≥1 success in k attempts)
- pass^k (probability of ALL k trials succeeding)
- They acknowledge non-determinism but do NOT discuss CIs or formal variance analysis

**Eight-step roadmap (zero-to-one):**
1. Start with 20-50 tasks
2. Convert manual tests to automated cases
3. Unambiguous tasks with reference solutions
4. Balanced positive + negative cases
5. Robust, isolated eval environments
6. Thoughtful graders; avoid rigid step-checking
7. Read transcripts manually
8. Monitor for eval saturation
9. Maintain with clear ownership

**Buried admission:** "Opus 4.5 initially scored 42% on CORE-Bench" until grading bugs, ambiguous specs, and "stochastic tasks that were impossible to reproduce exactly" were fixed. **Then the score jumped to 95%.** A 53pp swing from methodology corrections. This is ABC-paper territory; they cite it as a cautionary tale.

**Multi-tool / multi-MCP eval coverage:** LIMITED. One coding example mentions `read_file, edit_file, run_tests` but no systematic multi-tool evaluation strategies discussed.

**Benchmarks they trust:** SWE-bench Verified, Terminal-Bench, τ2-Bench, BrowseComp, WebArena, OSWorld.

**Benchmarks they DON'T trust:** anything where "a 0% pass rate across many trials" appears — "most often a signal of a broken task."

**Frameworks mentioned:** Harbor, Braintrust, LangSmith, Langfuse, Arize Phoenix.

**Key admission of their own thinness:** No formal statistical methodology, no inter-rater reliability metrics (beyond a passing mention of "inter-annotator agreement"), no quantitative benchmarking of eval quality itself.

## Anthropic's SWE-bench scaffold (for context)

Anthropic publicly states their SWE-bench Verified results use **two tools only**: bash + file editor (string replacement). No MCP. No tool selection. Stated explicitly: "The scaffolding we built for a Claude 3-level intelligence is a cage for a Claude 4-level one."

URL: https://www.anthropic.com/news/swe-bench-sonnet

This is the official "Art of Subtraction" framing — newer models need SIMPLER harnesses, not more elaborate ones.

## What this means for tool-crowding

### The narrative gift

**Anthropic publicly argues "fewer tools is better." They never quantify it. We quantify it.**

That is the launch hook. They give us the qualitative claim; we provide the empirical curve. This positions tool-crowding as the rigorous benchmark behind their public direction — collaborative, not adversarial.

### The narrative challenge

**Anthropic's harness work is single-MCP, not multi-MCP.** In Nov 2025 they use Puppeteer alone. In Mar 2026 they use Playwright alone. **Their official position is essentially: don't install multiple MCPs in the first place.**

Counter-argument: real users (Claude.ai, Claude Code, Cursor, etc.) DO install many MCPs because no one knows yet what the floor is. Tool-crowding measures where the floor is. The Anthropic posts are about *vendor-built* harnesses; tool-crowding is about *user-installed* MCP environments. Different operating point, both legitimate.

### Specific findings that align with us

1. **"Context anxiety" finding (Mar 2026) supports our context-overflow mechanism.** Their Sonnet 4.5 observation maps to our N-vs-token-budget hypothesis.
2. **"More capable models need simpler scaffolds" implies a generation-by-N interaction.** Tool-crowding should test multiple model generations, not just frontier. (Already in plan from SWE-Bench Illusion read.)
3. **Their 22x cost ratio between solo and full harness ($9 → $200)** legitimizes our cost-as-secondary-axis. Pass-rate × cost × N is a Pareto-frontier paper, not a single-metric paper.
4. **The "CORE-Bench 42% → 95% from methodology fixes" admission** is the strongest argument we have for tool-crowding's discipline. They tell on themselves: their own internal evals had 53pp of methodological noise. ABC-paper territory.

### Specific gaps we own

1. **Anthropic publishes no quantitative scaffold comparison.** Their Mar 2026 cost table is the closest, and it's solo-vs-3agent, not N-tool-sweep.
2. **No multi-MCP study from Anthropic anywhere.** Despite owning the protocol.
3. **No CIs, no statistical power analysis in Anthropic evals.** Even the Demystifying Evals post is methodologically thin.
4. **No public Claude × MCP × N=10 measurements.** This is precisely tool-crowding's territory.

### Tool-crowding paper positioning

**Section 1 opening:** "Anthropic, the creator of MCP, ships their flagship long-running agent with one MCP per agent (Puppeteer Nov 2025, Playwright Mar 2026). Their SWE-bench scaffold uses two non-MCP tools. Yet real users install 10-20 MCPs into Claude.ai today. This gap — between the vendor-tested minimum and the user-deployed maximum — is the empirical question."

**Related Work positioning:** Cite all three posts. Frame tool-crowding as the *quantitative complement* to their qualitative work. Co-cite Microsoft Research tool-space (775 colliding names, the IV) + Anthropic engineering posts (the qualitative claim) → tool-crowding (the measurement).

## Implications for Fri private DM target selection

Strong candidates (in order):

1. **Jeremy Hadfield** — co-authored all three posts. Recurring name. Most invested in harness + evals across the year. Likely the right intersection of MCP-harness-evals.
2. **David Hershey** — co-authored both harness posts. Senior signal. Less evals-specific.
3. **Prithvi Rajasekaran** — lead on Mar 2026 post. Currently in Labs. Active. Most likely to engage publicly.
4. **Justin Young** — lead on Nov 2025 post. Code RL team. Focused on harness rather than evals.
5. **Jesse Mu** — co-contributor on Nov post. Known publicly. Higher visibility.

**Recommendation: target Jeremy Hadfield first.** Three-post signal is unmatched. Pitch should frame tool-crowding as the quantitative measurement behind his team's qualitative direction.

Backup: David Hershey for senior-signal reach; Prithvi Rajasekaran for Labs/MCP-specific intersection.

## Tertiary literature worth noting (not load-bearing for v1)

- **Confucius Code Agent** (arXiv:2512.10398) — "Scalable Agent Scaffolding for Real-World Codebases" — Dec 2025. Read post-launch if relevant.
- **"Putting It All into Context"** (arXiv:2505.08120) — LCLMs simplifying agents. Skim.
- **"awesome-harness-engineering"** GitHub list — community resource. Useful for finding adjacent work.
- **InfoQ April 2026 coverage** of Anthropic three-agent harness — secondary source, validates the public reach of their work.

## Related

[[CODERAG_NSWEEP_SCOPE]] [[../notes/abc-best-practices]] [[../notes/mcp-universe]] [[../notes/swe-bench-illusion]] [[../notes/coderag-bench]] [[../RESEARCH_DESIGN]]
