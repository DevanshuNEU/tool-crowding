---
paper: "The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason"
arxiv: 2506.12286
version_read: v4 (2025-12-01) — still actively revised
date_read: 2026-05-21
authors: Shanchao Liang, Spandan Garg, Roshanak Zilouchian Moghaddam (Microsoft, by author org)
artifact: no public GitHub repo; prompts in Figures 6-7
relevance_to_tool_crowding: HIGH (shapes our query-set hygiene policy; informs cutoff date)
---

# The SWE-Bench Illusion (Liang, Garg, Moghaddam — Microsoft, Jun 2025, v4 Dec 2025)

## What they measured

Whether SOTA LLMs solve SWE-Bench Verified by *reasoning* or by *memorization*. They probe with three diagnostic tasks where genuine reasoning is impossible: file-path identification from issue text alone, function reproduction with the function body deleted, and prefix completion. High accuracy on these = memorization. They compare SWE-Bench Verified against four contamination-resistant holdouts.

Headline finding: **o3 identifies the correct buggy file path from issue text alone in 76% of SWE-Bench Verified tasks. On non-benchmark repositories, the same task drops to 53%.** That 47pp gap is the contamination footprint.

## Methodology choices that stood out

- **Three orthogonal contamination probes,** not one. Different probes catch different kinds of leakage (metadata leakage vs code-string leakage vs prefix-pattern leakage).
- **Five comparison sets, ordered by curation distance:** SWE-Bench Verified (500) → Full-SWE-Bench sample (200) → SWE-Bench Extra (217 post-cutoff issues from *same* repos) → RefactorBench (39) and SWE-Bench C# (75) → Outside-Repo Tasks (245 from numpy, scipy, pytorch, pandas, etc.).
- **5-gram overlap as a verbatim-match metric.** Direct echo of training-data signal. Δ₅ (overlap on buggy vs ground-truth) tells you whether the model's output reflects the buggy code (in repo) vs the fixed code (only in the patch). Positive Δ₅ on Verified = "the model has seen the patch."
- **10 LLMs across OpenAI + Anthropic.** GPT-4o, o3, o3-mini, o4-mini, Claude 3.5/3.7/4 Sonnet, Claude 4 Opus.
- **Single-round generation. No multi-turn. They admit this in limitations.**
- **No public code release.** Prompts are in Figures 6-7. Reproduction is non-trivial without the harness.

## Headline numbers worth memorizing

**File-path identification accuracy (best model):**
| Dataset | Accuracy | Notes |
|---|---|---|
| SWE-Bench Verified | 76% (o3) | "the contaminated benchmark" |
| Full-SWE-Bench (sample) | 71% (o3) | curation didn't add the leak; the repos did |
| SWE-Bench Extra (post-cutoff issues) | 68% (o3) | even post-cutoff issues from same repos leak 65%+ |
| RefactorBench | ~32% | handcrafted multi-file refactors |
| Outside-Repo Tasks | <53% | popular repos, no curated split |

**Function reproduction (5-gram overlap, best):**
- SWE-Bench Verified: **34.9%**
- SWE-Extra: 18.2%
- Outside-Repo: 13.9%

**Prefix completion (verbatim match per model):**
| Model | Verbatim match % |
|---|---|
| Claude 4 Opus | **31.6%** |
| Claude 4 Sonnet | 21.4% |
| GPT-4.1 | 17.4% |
| Claude 3.7 Sonnet | 12.3% |
| Claude 3.5 Sonnet | 12.1% |
| o3-mini | 11.7% |

## 15 observations easy to miss on a casual read

### The contamination is monotonically increasing per generation

1. **Claude verbatim-match scales monotonically across generations.** 3.5 Sonnet 12.1% → 3.7 Sonnet 12.3% → 4 Sonnet 21.4% → 4 Opus 31.6%. **Newer Claude models are MORE contaminated, not less.** This is the inverse of what you'd expect if Anthropic were filtering training data more aggressively. Possible explanations: (a) more code-corpus inclusion in newer training, (b) longer effective context capturing more of the patch, (c) RLHF on similar-shape problems. Paper does not adjudicate.

2. **Different model families contaminate differently.** o3 has the highest file-path accuracy (76%) but "moderate" verbatim match. Claude 4 Opus has the highest verbatim match (31.6%) but middling file-path accuracy. Contamination has multiple signatures. A single metric will miss it.

3. **The performance hierarchy is identical across all 10 models tested:** Verified >> Full >> SWE-Extra >> Refactor ≈ C# >> Outside-Repo. The fact that *every* model shows the same ordering is strong evidence the leak is in the data, not in any single training pipeline.

### The "clean" holdouts are not actually clean

4. **Outside-Repo uses numpy, scipy, pytorch, pandas, celery, aiohttp, jupyter.** These are among the most-trained-on public repos in existence. The 53% file-path-ID is the **floor of contamination from popular-repo exposure**, not a clean reasoning baseline. The "true" reasoning baseline is probably lower than 53%. The 47pp Verified-vs-Outside gap *understates* the SWE-Bench-specific contamination.

5. **RefactorBench has only 39 tasks.** Their cleanest comparison set is the smallest. Statistical claims on RefactorBench (~32% file-path-ID) have wide CIs the paper doesn't compute.

6. **RefactorBench issue text averages 14.6 tokens vs SWE-Verified 451 tokens.** RefactorBench is 30x less context-rich. Lower scores on RefactorBench partly reflect harder-by-context, not just less-contaminated. This is a confounder the paper acknowledges but doesn't quantify.

### Methodology gaps

7. **No public code release.** Prompts are in figure plates. Replication requires re-implementing their harness from screenshots. Major reproducibility limitation for a paper claiming benchmark integrity.

8. **"Filtered accuracy" relies on "simple heuristics" to detect explicit path mentions in issue text.** They admit this. A more rigorous filter (regex + LLM judge) would likely increase the filtered set, possibly dropping accuracy estimates further. The 76% is probably a *floor*.

9. **Function reproduction tests only o3-mini from OpenAI reasoning models** due to "limited resources." The most relevant data point (do reasoning models memorize less?) is sampled with the smallest reasoning model. Open question.

10. **Single-round generation everywhere.** No multi-turn, no tool use, no retrieval. Tests the model's *cached knowledge*, which is precisely the contamination they want to detect, but says nothing about whether real agentic scaffolds (which they evaluate against) actually use that cached knowledge in production.

11. **No SWE-Bench Lite analysis.** Lite is the more commonly-used variant in product evals. Gap. Their findings may or may not transfer.

12. **No analysis of WHEN models saw the data.** They infer pretraining inclusion from temporal patterns (SWE-Extra post-cutoff drops) but never identify a specific training-data source. The "how it got in" question is unanswered.

### Adjacent literature is alive

13. **Concurrent work cited:** Ramos et al. 2025 ("Are Large Language Models Memorizing Bug Benchmarks?" arXiv:2411.13323) and Chen et al. 2025 ("Memorize or Generalize?" arXiv:2503.02296). **There is an emerging "benchmark contamination" sub-field.** Tool-crowding sits adjacent to it. A good launch post can position tool-crowding as the *multi-MCP analog* of this growing concern: not "did the model see the answer?" but "did the model see the tool?"

14. **The paper has been revised four times (v1 Jun 2025 → v4 Dec 2025).** Active iteration, likely in response to reviewer feedback. Read v4 prompts (Fig 6-7) before adopting their diagnostic protocol.

### One result that overturns assumptions

15. **SWE-Bench Extra (post-cutoff issues from same repos) STILL leaks 68% file-path-ID.** The contamination is not just "the model saw the patches" — it's "the model has internalized the repo's file structure deeply enough that even unseen issues from those repos are predictable from issue text alone." This means **a temporal cutoff is NOT sufficient to make a benchmark contamination-resistant if the repos themselves are in training data.** The repos must be unfamiliar, not just the issues. Major implication for any code-retrieval benchmark.

---

## What to steal (direct mappings to tool-crowding)

| What | How to apply |
|---|---|
| **5-gram overlap as contamination metric** | Before locking the tool-crowding query set, run a 5-gram overlap test on each query's ground-truth answer string against the publicly known model corpora. Drop queries with overlap above a threshold. |
| **Three-probe diagnostic protocol** | Apply file-path-ID + function-reproduction probes to our query set during a pilot. Any query that hits >50% accuracy without retrieval is leaking. |
| **Multi-set comparison shape** | Our query set should have at least three contamination tiers: post-cutoff issues from public repos (low confidence clean), private/internal codebase queries (mid), and synthetic queries against the OCI repo itself (high confidence clean). Compare pass-rate by tier. |
| **Monotonic-contamination-across-generations finding** | Test multiple model generations in tool-crowding, not just frontier. The trend across generations is itself a finding. |
| **Repo-level contamination, not issue-level** | Our query repos must be ones the model has NOT been heavily trained on. OCI is private and recent: ideal. numpy/scipy/pytorch are NOT ideal as query targets. |
| **Cutoff date policy** | Pin the query set to issues/code post the latest model's training cutoff. AND restrict repos to lower-traffic ones, not heavily-trained-on ones. |

## What they didn't measure / where they stopped

- **No MCP, no retrieval, no tools.** Their entire methodology is single-turn closed-book. They never ask: does retrieval rescue or worsen contamination effects? That is precisely tool-crowding's territory.
- **No multi-tool dimension.** They have one task type (SWE-Bench-style) and probe contamination. They never ask whether tool routing decisions are themselves contaminated by training on similar tool names.
- **They don't propose a clean benchmark, just diagnose existing ones.** No constructive contribution besides "future benchmarks need temporal controls + cross-repo validation."

## One open question this raises for tool-crowding

**Does multi-MCP retrieval AMPLIFY or DAMPEN contamination signals?**

Two hypotheses:
- **Amplify:** more tool calls → more opportunities to load contaminated context → memorized answer triggered more often → high N inflates pass-rate via memorization, not retrieval skill.
- **Dampen:** more tools → more retrieval noise → memorized answer suppressed by surface-pattern matching against irrelevant tools → high N depresses pass-rate even when memorization would have worked.

Tool-crowding can answer this by **comparing pass-rate at N=1 (single retrieval server) vs N=10 (with distractors) on contaminated tasks (numpy/scipy/pytorch queries) vs clean tasks (OCI queries).** If the contamination delta narrows at high N, distractors are dampening memorization. If it widens, distractors are amplifying.

This is a **second figure for the paper**, not the headline figure. Worth Section 5 ("Contamination as a confound for tool-crowding interpretation").

## Actions pulled out of this read

1. **Adopt the 5-gram overlap metric** for query-set hygiene. Add to `design/QUERY_SET_HYGIENE.md` (new doc, Thu).
2. **Restrict query target repos** to: (a) OCI itself (private, recent), (b) low-traffic post-cutoff repos. Explicitly exclude numpy/scipy/pytorch/pandas/celery/aiohttp/jupyter from query target set. Update `design/SERVER_POOL.md` query repos section.
3. **Set query temporal cutoff** to latest evaluated model's training cutoff date (Claude 4.5/4.6/4.7 cutoff: TBD verify). Issues/code older than this are inadmissible.
4. **Plan a contamination ablation as Section 5** of the tool-crowding paper: N=1 vs N=10 pass-rate on contaminated-task tier vs clean-task tier. Decide Thu whether to scope this into v1 or defer to v2.
5. **Cite Liang et al. as the methodological precedent** for contamination-resistance discipline. Frames tool-crowding as the multi-MCP analog of their benchmark-contamination work.
6. **Read concurrent contamination papers** (Ramos 2024 arXiv:2411.13323, Chen 2025 arXiv:2503.02296) before locking the query set. These will sharpen the cutoff/repo-exclusion policy further.

## Related

[[abc-best-practices]] [[mcp-universe]] [[coderag-bench]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../design/SERVER_POOL]] [[../../strategy/week-1/2026-05-21]]
