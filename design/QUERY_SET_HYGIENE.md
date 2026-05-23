---
title: QUERY_SET_HYGIENE.md — contamination defense for the v1 query set
status: v1 (locked 2026-05-22 Fri AM)
binds: ABC R.3 (data contamination prevention) + TC.7 (query set hygiene) + TC.8 (per-repo cap) + TC.9 (three-tier access)
supersedes: RESEARCH_DESIGN.md §3 task source clause ("50 queries from CoIR StackOverflow-Python split"). See §9 below.
related_docs: MODEL_VERSIONS.md (cutoffs), REPRODUCIBILITY.md (h_queries content hash), notes/swe-bench-illusion.md, notes/swe-bench-pro.md, notes/coir.md, FOUNDATION.md §4.3 R.3 + §4.4 TC.7-TC.9
---

# tool-crowding Query Set Hygiene Spec v1

The benchmark's pass-rate is meaningful only if the model isn't recognizing the ground truth from training. This document specifies the contamination defenses that gate which queries enter the v1 set, how the set is split into access tiers, and how a re-run verifies hygiene held.

The doc is binding for the Saturday 2026-05-23 pilot, the v1 full sweep, and the Monday 2026-05-25 launch. Changes after lock require a v1.x bump in FOUNDATION.md §6.

---

## 1. The contamination threats we defend against

Three threats, each with prior-art evidence:

| Threat | Evidence in our notes | Defense layer |
|---|---|---|
| **Memorization of ground-truth code.** The model has seen the target snippet verbatim during training, returns it without retrieval skill. | Liang et al. ([arXiv 2506.12286](https://arxiv.org/abs/2506.12286)) — Claude 4 Opus shows 31.6% verbatim 5-gram match on SWE-Bench Verified prefix completion. Contamination is **monotonically increasing per Claude generation** (3.5 Sonnet 12.1 → 4 Opus 31.6). Newer Claude is more contaminated, not less. | Defenses 1 + 3 + 4. |
| **Repo-level familiarity.** The model has been trained extensively on the source repo's file structure, predicts file paths from issue text alone without retrieval. | Liang et al. observation #15 (`notes/swe-bench-illusion.md` line 94): SWE-Bench Extra (post-cutoff issues from same repos) still leaks **68% file-path-ID accuracy** vs ~53% on Outside-Repo. **Temporal cutoff is NOT sufficient if the repos themselves are in training data.** | Defense 2 (low-traffic repo restriction) is the load-bearing defense for this threat. |
| **Future leakage.** Once we publish v1 queries, vendors retrain. v1.1 / v2 re-eval needs a contamination-resistant remainder. | SWE-Bench Pro's held-out tier (858 instances, 12 GPL repos reserved) per `notes/swe-bench-pro.md` line 76. | Defense 6 (three-tier access). |

The defenses below are **layered**: each closes a partial gap; the combination is what makes contamination meaningfully bounded. None alone is sufficient.

---

## 2. Defense 1: temporal cutoff

### Binding date

**Queries must be sourced from content (commits, issues, docs, code) published strictly after 2026-01-31.**

This is the latest training-data cutoff across the v1 model panel, per `design/MODEL_VERSIONS.md` (verified 2026-05-21 against `docs.anthropic.com/en/docs/about-claude/models/overview`): Claude Opus 4.7 and Sonnet 4.6 both have training-data cutoff "Jan 2026," treated as the last day of the published month (`MODEL_VERSIONS.md` line 22).

### Why this date specifically

For the panel (Opus 4.7, Sonnet 4.6, GPT-5-class, Gemini 2.5-class), the binding cutoff is the **maximum** of all four models' training-data cutoffs. We are using 2026-01-31 based on the two Anthropic models. GPT-5 and Gemini 2.5 cutoffs are **not yet recorded** in `design/MODEL_VERSIONS.md` and are an open verification action (§11). If either turns out to be later than 2026-01-31, this date moves forward and v1 queries must be re-screened.

### Per-tier date bands

- **Public tier (30 queries):** content published strictly after 2026-01-31. Binding.
- **Held-back tier (10 queries):** content published strictly after 2026-04-30 (3-month buffer past cutoff for future re-eval defense). Stricter than public tier on purpose.
- **Sealed tier (10 queries from OCI proprietary):** any date — OCI is a private codebase authored by the corresponding author, not in any public training corpus (`design/SERVER_POOL.md` COI disclosure). Date constraint is N/A for this tier.

### How a query's date is verified

Every candidate query carries a `source_publication_date` field in the query manifest (`tasks/v1/queries.jsonl`). The date is the **earliest verifiable commit date** of the ground-truth code on the public source (e.g., GitHub commit history, GitHub issue creation timestamp). The harness rejects any query whose date is on or before the binding cutoff for that query's tier.

---

## 3. Defense 2: low-traffic repo restriction

Temporal cutoff alone is insufficient. Per `notes/swe-bench-illusion.md` line 94: even POST-cutoff issues from familiar repos leak heavily because the model has internalized the repo's file structure during pretraining on the repo's older code.

### Excluded source repos (banned for v1 public + held-back tiers)

The following repos are **not eligible** as query sources. They are among the most-trained-on public Python codebases in existence; per Liang et al.'s Outside-Repo tier construction, even on these "non-benchmark" repos contamination is ~53%, which we treat as the floor for repo familiarity:

- numpy
- scipy
- pytorch
- pandas
- celery
- aiohttp
- jupyter / jupyterlab
- requests
- flask
- django
- tensorflow
- scikit-learn
- matplotlib
- seaborn

This list is not exhaustive. The general rule: any repo with > 10k GitHub stars OR > 1M downloads/month on PyPI is presumed in training data and excluded.

### Eligible source repos (criteria, not enumerated list)

- < 10k GitHub stars
- < 1M PyPI downloads/month (if applicable)
- Active maintenance in the 2026-02-01-onwards window (commits, issues, releases)
- License is GPL-2.0, GPL-3.0, LGPL, or AGPL (Defense 4)
- Per-repo cap of 5-10 queries (Defense 5)

A candidate repo enumeration pass is an open action (§11). The pilot may begin with as few as 3 eligible repos; v1 launch needs ~5-10 across the 30 public-tier queries.

### Why this is co-equal with temporal cutoff, not subordinate

Liang et al. found that SWE-Bench Extra (post-cutoff issues from same repos) leaks 68% file-path-ID vs the ~53% floor on Outside-Repo tasks. **The repo-familiarity effect is roughly the same magnitude as the test-set-leakage effect.** A query that satisfies temporal cutoff but uses a familiar repo gets us roughly half the way to a clean measurement. Both defenses must hold.

---

## 4. Defense 3: 5-gram contamination check

Per `notes/swe-bench-illusion.md`: the SWE-Bench Illusion authors use 5-gram overlap as a verbatim-match metric to detect whether the model's output reflects training-set ground truth. We apply the same metric **proactively** — as a screen on candidate queries before they enter the set.

### Algorithm

For each candidate query:

1. Extract `ground_truth_code` — the function body or snippet the agent must retrieve.
2. Tokenize using the model's tokenizer (one of the four panel models; report which).
3. Strip low-entropy tokens: whitespace, comments, common keywords (`def`, `return`, `import`, `class`, `for`, `if`, `else`, `try`, `except`, `with`, common builtins).
4. Extract all 5-grams from the remaining (high-entropy) token stream. A 5-gram is a contiguous sequence of 5 tokens.
5. For each 5-gram, search:
   - GitHub Code Search (via `gh search code` or the REST API)
   - Common-Crawl-indexed web (via Google Custom Search API or equivalent)
6. Count high-entropy 5-grams that return ≥ 1 public hit.

### Reject threshold

**A query is rejected if 2 or more high-entropy 5-grams hit public sources.** Single-hit queries pass (a single 5-gram coincidence is plausible for any non-trivial code); multi-hit queries are likely lifted from training-set-adjacent content.

### Why 5-grams and not n-grams of other lengths

5-grams are the SWE-Bench Illusion choice (`notes/swe-bench-illusion.md` line 23 and the prefix-completion methodology). They are short enough to be common in any non-trivial code, long enough to be distinctive in combination. Bigrams would have too many false positives; 10-grams would have too many false negatives. We adopt the precedent rather than re-derive.

### Tokenizer choice

Use the **strictest** (longest-output-tokenization) tokenizer in the panel. Empirically this tends to be the GPT-class `tiktoken` cl100k or o200k encodings, which produce more, finer-grained tokens than the Anthropic or Gemini tokenizers. A 5-gram in tiktoken is shorter (more specific) than a 5-gram in Anthropic's tokenizer; rejecting on the stricter metric is conservative.

Document the chosen tokenizer in the query manifest header.

### What "search returns a hit" means operationally

A hit is a single result returned by GitHub Code Search OR Google Custom Search with the 5-gram as an exact phrase query (quotation marks around the 5-gram). Stack Overflow hits count. Personal blog hits count. Cached commits in archive.org count. The bar for "publicly known" is wide on purpose.

---

## 5. Defense 4: license filter (GPL-only for public tier)

Per `notes/swe-bench-pro.md` lines 47 + 73: GPL/copyleft license is a contamination shield because major commercial training pipelines have policies (or stated policies) of avoiding GPL code due to license-compatibility concerns. The legal barrier is additive to the temporal cutoff and the low-traffic restriction.

### Binding rule

**Public tier (30 queries) sources MUST be GPL-2.0, GPL-3.0, LGPL, or AGPL licensed.** Verified by:

1. The repo's root LICENSE file (one of the GPL family)
2. The repo's `package.json` / `pyproject.toml` / `setup.py` license field (one of the GPL family)
3. Spot-check for license-header comments at the top of files containing the ground-truth code

If any of the three sources disagree, the query is rejected (license ambiguity is a red flag).

### Why GPL specifically, not "any license"

Permissively-licensed code (MIT, Apache 2.0, BSD) is freely included in training corpora. Some vendors include GPL too, but the public stance is generally "we avoid GPL." The asymmetry is real: GPL code is on average less-included than permissively-licensed code in training corpora. This is the defensible empirical claim; it's not "GPL is never in training data," it's "GPL is less likely than MIT or Apache 2.0 to be in training data."

This is SWE-Bench Pro's design pattern (`notes/swe-bench-pro.md` line 47): "License as contamination shield. GPL/copyleft public set + commercial proprietary set. Legal barrier instead of (or in addition to) temporal cutoff. Novel design pattern."

### Held-back tier

Same GPL constraint applies, with the additional 2026-04-30 temporal cutoff (Defense 1 per-tier).

### Sealed tier (OCI proprietary)

GPL constraint does not apply — the repo is private (not in any public corpus by construction). The sealed tier is the legal-barrier-clean tier by virtue of being unreachable, not by license.

---

## 6. Defense 5: per-repo cap

Per `notes/swe-bench-pro.md` lines 47 + 79 (SWE-Bench Pro caps at 100/repo on a 1,865-query benchmark across 41 repos) and FOUNDATION.md TC.8 (adapted for our scale): **no more than 5-10 queries per source repo.**

### Why a cap

If the model has memorized one source repo's structure deeply, that repo's queries will be systematically easier. Diversity reduces the influence of any single repo on aggregate pass-rate. Same reasoning as cross-validation folds.

### Implementation

The query manifest tracks `source_repo` per query. Pre-flight verifier counts queries per repo; if any count exceeds 10 (public tier) or 7 (held-back tier; tighter because the held-back tier is smaller), the verifier fails and queries.jsonl cannot be committed for that tier.

For a 30-query public tier, this implies ≥ 3 distinct source repos (30/10 = 3). For a 10-query held-back tier, ≥ 2 distinct source repos. Practically: aim for 5-10 source repos for the public tier, 3-5 for held-back.

---

## 7. Defense 6: three-tier access

Per `notes/swe-bench-pro.md` line 76 (SWE-Bench Pro's held-out tier as benchmark-longevity bet) and FOUNDATION.md TC.9: three tiers, each with a distinct purpose.

| Tier | Count | Purpose | Released? | Date band | License | Repo source |
|---|---|---|---|---|---|---|
| **Public** | 30 | The headline v1 numbers. Anyone reproduces. Anyone adversarially trains on these going forward. | Yes — committed to `tasks/v1/queries.jsonl` on Mon May 25 launch. | post-2026-01-31 | GPL family | Low-traffic eligible (Defense 2) |
| **Held-back** | 10 | Reserved for v1.1 / v2 re-eval when models have likely been trained on the public tier. Defends against retraining-on-tool-crowding. | No — committed to `tasks/v1/held_back.jsonl` but `.gitignore`-d in the public repo. Devanshu retains. Released at v2 launch or 12 months from v1 launch, whichever comes later. | post-2026-04-30 | GPL family | Low-traffic eligible |
| **Sealed (OCI)** | 10 | Methodology disclosure only; never released as data. Used in the paper's COI sensitivity analysis (RESEARCH_DESIGN.md §11 "leave-OCI-out") to demonstrate that the N-curve survives without OCI being a query target. | No — only the methodology of generation is described publicly. Queries themselves are private. | N/A | N/A | OCI proprietary |

### How the tiers compose on launch

Mon May 25 public launch ships only the public tier. The methodology of the held-back and sealed tiers is described in the launch artifact ("we held back 10 queries for v1.1 re-eval; we also generated 10 OCI-internal queries for COI sensitivity") with sample sizes but no content.

Any cell that involves OCI as primary server runs queries from all three tiers. The leave-OCI-out sensitivity analysis runs queries from public + held-back only (excludes OCI-as-primary-server cells); the headline N-curve must survive this analysis with the qualitative slope preserved or the COI is load-bearing for the result.

---

## 8. Source of queries (overrides RESEARCH_DESIGN.md §3)

### What's changing

RESEARCH_DESIGN.md §3 (locked Day 1 / 2026-05-20) says: *"50 queries from CoIR (StackOverflow-Python split), pre-selected by retrieval-difficulty quartile (12-13 per quartile, top quartile excluded as too-hard)."*

This is **superseded** by the Thu PM 2026-05-21 deep-read of CoIR (`notes/coir.md`). Key finding from that read (line 65): *"Default leaning: (c), skip CoIR entirely and stick to SWE-Bench-Pro-style post-cutoff issue mining, because the contamination story is cleaner."*

Reason: CoIR's component datasets (CosQA 2021, CodeSearchNet 2019, APPS) all predate any model in our panel's training cutoff. Every model has near-certainly seen these queries. Using them as v1 queries undermines every other defense in this document.

### What replaces it

**Post-cutoff issue mining from low-traffic GPL repos.** The mining procedure:

1. Enumerate candidate source repos (Defense 2 eligibility). Tooling: `gh search repos` filtered by license + stars.
2. For each candidate repo, pull issues + PRs opened on or after 2026-02-01 (1 day past cutoff).
3. For each issue/PR, identify the canonical bug/feature pair: the issue text, the patch, and the modified function(s).
4. Construct a query as: `(natural-language description from issue) → (ground-truth: the modified function in the merged patch)`.
5. Score each candidate query on: difficulty (per-quartile by snippet length), retrieval-friendliness (single function vs multi-file), license check, 5-gram check.
6. Accept queries that pass all defenses; sort into tiers by date band.
7. Sealed tier: parallel procedure on OCI's private commit history.

This is the SWE-Bench Pro pattern (`notes/swe-bench-pro.md` line 16) at our scale.

### What this implies for RESEARCH_DESIGN.md

The §3 task source clause needs a one-line amendment pointing here. The "difficulty quartile" framing survives (we still bucket by difficulty); only the SOURCE of queries changes from CoIR to post-cutoff issue mining. This is a follow-up edit, not blocking for this doc.

---

## 9. Verification workflow (before queries.jsonl is locked)

The harness's preflight check refuses to start the pilot unless every item below has passed. Each check has a script in `harness/preflight/<check>.py`.

1. **Date check.** Every query's `source_publication_date` is strictly after the tier's binding cutoff (public 2026-01-31; held-back 2026-04-30; sealed N/A).
2. **License check.** Every query's `source_repo` has a verified GPL-family license. Three-source verification (LICENSE file + manifest + header). Sealed tier exempt.
3. **Repo eligibility check.** Every query's `source_repo` is not in the banned-repos list (Defense 2). Star count and download count are within thresholds.
4. **5-gram check.** Every query's ground-truth code has ≤ 1 high-entropy 5-gram public hit. Cached results from GitHub Code Search + Google Custom Search are committed to `tasks/v1/contamination_audit.jsonl` for reproducibility.
5. **Per-repo cap check.** No source repo contributes > 10 public-tier queries or > 7 held-back-tier queries.
6. **Tier-count check.** Public tier has exactly 30, held-back exactly 10, sealed exactly 10. Hard counts, no fuzz.
7. **Tokenizer cache check.** Every query carries pre-computed token counts under the panel's tokenizers for use in PADDING_STRATEGY.md §4 token-matching.

The output of these seven checks is a `tasks/v1/verification_report.md` committed alongside `queries.jsonl`. The report is part of the public launch artifact; it documents the defenses in a reviewer-readable form.

---

## 10. Failure modes during query construction

| Failure | Detection | Response |
|---|---|---|
| Cannot find 30 eligible queries that pass all defenses | Verification step 6 fails (tier-count short) | Relax difficulty-quartile constraints first (allow easier queries); then expand eligible-repo list (add 5-10 more candidate repos). Do NOT relax temporal cutoff, license, or 5-gram check. |
| A query passes all defenses but post-launch a reader reports it's in a public corpus we missed | Public report after launch | Move query to a `tasks/v1/retracted.jsonl` file; re-aggregate the affected cells; publish v1.1 with the same `run_id` semantics + a CHANGELOG entry. Per REPRODUCIBILITY.md §6 v1.x versioning. |
| A held-back query leaks before its release window | External publication or repo scrape | Treat the leaked query as public-tier-equivalent for v2 purposes; the held-back tier shrinks. Document. |
| Vendor cutoff dates revised (Anthropic or other) | Re-verification trigger per MODEL_VERSIONS.md line 47 | Re-screen all queries against the new max-cutoff. Any query that no longer satisfies its tier's date band is dropped. Re-aggregate. |
| GPT-5 or Gemini 2.5-class cutoff turns out to be later than 2026-01-31 | Open verification action (§11) | Adopt the new max-cutoff as the binding date. Re-screen public tier; the queries' source_publication_date column tells us which queries survive. |

---

## 11. Open verification actions

These must close before `tasks/v1/queries.jsonl` is committed for the launch run. They are not blockers for the Saturday pilot (which uses a 3-query subset per `design/PILOT_V0.md`) but they are blockers for the Monday launch.

1. **Verify GPT-5 training cutoff.** Search OpenAI's docs for the official cutoff. Update `design/MODEL_VERSIONS.md`. Owner: Devanshu. Due: before queries.jsonl lock.
2. **Verify Gemini 2.5-class training cutoff.** Search Google's docs for the official cutoff. Update `design/MODEL_VERSIONS.md`. Owner: Devanshu. Due: before queries.jsonl lock.
3. **Enumerate eligible source repos.** Pull a list of 20-30 candidate repos satisfying Defense 2 (low-traffic + GPL + active in post-2026-02-01 window). Owner: Devanshu. Due: Fri PM (today).
4. **Pilot-subset queries (3 queries).** Mine 3 queries against the eligible-repo list for the Sat pilot. Run the full verification workflow (§9) on them. Commit to `tasks/v1/queries.jsonl` as a 3-row file for the pilot run. Owner: Devanshu. Due: Fri PM (today) or Sat AM at the latest.
5. **Launch-subset queries (30 public + 10 held-back + 10 sealed = 50 total).** Mine + verify after the pilot is green. Owner: Devanshu. Due: Sun for Mon launch.
6. **Failure-mode taxonomy LLM-judge prompt.** PILOT_V0.md pre-flight item; not strictly query-hygiene but tightly coupled to the failure-mode tags on each query trial. Owner: Devanshu. Due: Fri PM.

---

## 12. What this document does NOT cover

- **Reproducibility / `run_id` chain.** See `design/REPRODUCIBILITY.md` §1 (queries.jsonl participates as `h_queries` in the 7-artifact chain).
- **Padded-N=1 control padding strategy.** See `design/PADDING_STRATEGY.md`.
- **Per-server tool descriptions.** See `design/SERVER_POOL.md` + the v1.2 `pool/descriptions.json` artifact in REPRODUCIBILITY.md §1.
- **Statistical analysis of pass-rate by tier.** See RESEARCH_DESIGN.md §4 (MPD, paired bootstrap, Bonferroni). The contamination-tier comparison (public vs held-back vs sealed) is mentioned as a paper section in `notes/swe-bench-illusion.md` "What to steal" #5 ("Pilot a contamination ablation as Section 5 of the paper"); v1 decision deferred.
- **COI sensitivity (leave-OCI-out).** See RESEARCH_DESIGN.md §11. The sealed tier supports this analysis but the analysis itself lives in §11.
- **Re-aggregation procedure on a v1.1 retraction.** See REPRODUCIBILITY.md §6 v1.x versioning.

---

## 13. Why this scope, not more

The doc is binding for a 50-query v1 set, not for a generic code-retrieval benchmark. At this scale, several pieces that SWE-Bench Pro can afford (their 1,865-query scale supports 41 repos, 100/repo cap, three full tiers of 731 / 858 / 276) compress to smaller versions for tool-crowding (5-10 repos, 7-10/repo cap, three tiers of 30 / 10 / 10). The defenses are the same shape; the magnitudes are scaled.

The doc deliberately does NOT specify which exact 30 queries we'll use, only the gates each candidate must pass. The mining is a separate execution step (§11 actions 4 + 5) done by Devanshu over the weekend. Specifying queries in this doc would couple the methodology spec to a particular content slice and create a release-coordination problem.

---

## Related

[[FOUNDATION]] [[REPRODUCIBILITY]] [[PADDING_STRATEGY]] [[MODEL_VERSIONS]] [[SERVER_POOL]] [[PILOT_V0]] [[PRE_REGISTRATION]] [[../RESEARCH_DESIGN]] [[../notes/swe-bench-illusion]] [[../notes/swe-bench-pro]] [[../notes/coir]] [[../notes/coderag-bench]] [[../notes/abc-best-practices]]
