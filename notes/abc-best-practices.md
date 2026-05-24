---
paper: "Establishing Best Practices for Building Rigorous Agentic Benchmarks"
arxiv: 2507.02825
version_read: v5 (2025-08-07)
date_read: 2026-05-21
relevance_to_tool_crowding: critical (methodology gate before harness build)
---

# ABC: Best Practices for Building Rigorous Agentic Benchmarks

## What they measured

Not a benchmark itself. A meta-evaluation of 10 existing agentic benchmarks against a 42-item checklist. They quantify how much each unaddressed item distorts reported pass-rate (e.g., CVE-Bench overestimates by 32.5%, KernelBench by ~31%, OSWorld *under*estimates by 28%). Then they propose the Agentic Benchmark Checklist (ABC) as a pre-publication gate.

## Methodology choices that stood out

- **Binary scoring per item.** No partial credit. Either the benchmark satisfies the rule or it doesn't. Forces decisions instead of hedging.
- **Three-dimension factorization:** Task Validity (10 items, T.1-T.10), Outcome Validity (19 items, O.a-O.i), Benchmark Reporting (13 items, R.1-R.13). Each dimension has a separate average score.
- **Validity = "solvable iff capability present."** Task validity violation = task isn't measuring what you think. Outcome validity violation = pass-rate doesn't reflect actual success.
- **Quantitative validation per identified flaw.** They don't just list issues. For every flaw, they re-ran the benchmark with the fix and measured the delta. CVE-Bench case study: applying ABC dropped agent success rates by 10%.
- **Trivial-baseline test (R.13) as a smoke detector.** If an empty-response agent or random-guess agent scores high, the benchmark is broken. τ-bench: 38% from empty responses.

## What to steal (direct mappings to tool-crowding)

| ABC item | What it forces tool-crowding to do |
|---|---|
| **T.1** (pin tool versions) | Already in SPEC: `servers_pinned.yaml` with SHAs. v1.2 item (a) extends this to hash the file itself into `run_id`. |
| **T.4** (cleanup between trials) | Add explicit state-reset between trials: clear server caches, restart MCP processes if any leak state, nonce-per-trial (already in SPEC v1.1). |
| **T.5** (isolate from ground truth) | Oracle pass criteria (`harness/oracles/pass_v1.py`) must not be visible to any installed server. Specifically: don't install an MCP that can read `tasks/v1/queries.jsonl` ground-truth fields. |
| **T.6** (frozen environment) | Server SHAs + tool descriptions + JSON schemas frozen at run start. Hash all three into `run_id`. Network calls to live registries forbidden. |
| **T.9** (oracle solver) | Per N level, prove at least one agent + tool combo *can* solve the task. If pass-rate is zero at N=10 we need to distinguish "interference broke it" from "task was impossible." |
| **T.10** (inspect outliers in pilot) | Use the 200-trial Thu pilot to flag queries where pass-rate is 0/n or n/n. Both are suspicious. |
| **O.b.2 / O.b.3** (no success by guessing) | Pass-rate evaluation must not allow trivial-string-match wins. If an agent dumps a generic file list and the oracle accepts it, the benchmark leaks. |
| **O.g.2** (irrelevant states detect side-effects) | Measure *unintended* tool calls. At high N, an agent picking the wrong tool is the failure mode we care about. The harness must log every tool call, not just the "winning" one. |
| **O.g.3** (state space complex enough) | Query set must require multi-step retrieval / specific repo paths. If pass-rate is achievable by random pickaxe, N effect is uninterpretable. |
| **O.c.1** (LLM-as-judge pilot) | If we use any LLM judge for pass (we shouldn't if avoidable), pilot the judge's accuracy and self-consistency first. Prefer programmatic oracles. |
| **R.10** (statistical significance) | Already in SPEC: MDE table, n=3 currently, pilot pending. Don't ship a leaderboard without CIs. |
| **R.13** (trivial baselines) | Mandatory: padded-N=1 control (already planned) + a "no MCP tools, pure LLM" baseline + a "single-server-only" baseline per code-retrieval MCP. If the padded-N=1 control passes higher than N=10, that *is* the headline. |
| **R.3** (data contamination prevention) | Query set must use repos/issues post-cutoff of every model evaluated. SWE-Bench Illusion (Thu paper) will sharpen this. |

## What they didn't measure / where they stopped

- **No multi-tool / multi-MCP framing anywhere.** ABC treats "tools" as a fixed integration the benchmark designer chose. T.1 pins versions but doesn't consider *how many* tools are installed as a variable. Their universe is N=fixed.
- **No notion of tool-space interference, namespace collision, or description competition.** The Microsoft Research tool-space paper (775 colliding names) is orthogonal to ABC. ABC is silent on the failure modes tool-crowding measures.
- **CVE-Bench case study is single-domain (security).** Doesn't generalize the methodology to code-retrieval. We're the first to apply ABC discipline to a code-retrieval-meets-multi-MCP harness.
- **No guidance on N as an independent variable.** Specifically: how to keep T.6 (frozen environment) when the independent variable *is* the environment composition. Our answer: pin every server in the pool, hash the pinning file, vary only which subset is exposed per trial.

## One open question this raises for tool-crowding

**T.6 says "freeze the environment at release time."** But tool-crowding's whole premise is that the environment (installed server set) is dynamic by design. **What does "frozen" mean when the IV is environment composition?**

Our working answer: freeze the *pool* (servers_pinned.yaml with SHAs + descriptions + schemas, all hashed into run_id), and treat the *selection* (which N of those are exposed per trial) as the controlled variable. Every (run_id, trial_id, N, selection_seed) tuple must reproduce bit-identical inputs.

This is what v1.2 SPEC item (a) is already addressing for `run_id`. Worth a short ADR-equivalent note in `design/REPRODUCIBILITY.md` before harness code starts Thu.

## Action items pulled out of this read

1. **Add R.13 trivial baselines to the experiment matrix** (alongside padded-N=1): pure-LLM no-tools, single-server-only. SPEC currently has padded-N=1 only.
2. **Confirm O.g.2 logging in harness:** every tool call (not just terminal ones) is recorded with `(trial_id, step, server, tool, args_hash)`. Verify SPEC has this.
3. **Draft `design/REPRODUCIBILITY.md`** Thu morning before harness code, formalizing the "frozen pool + controlled selection" answer to T.6.
4. **Decide whether any LLM-as-judge is used.** Prefer programmatic oracles (string match on file path / function name retrieved). If LLM judge is unavoidable for any task, schedule the O.c.1 pilot.
5. **Re-read SPEC v1.1 against the full ABC checklist** after all 5 papers are done. This is the methodology doc skeleton task.

## Related

[[mcp-universe]] [[swe-bench-illusion]] [[coderag-bench]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../harness/SPEC]]
