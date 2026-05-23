---
title: tool-crowding Adversarial Audit
date_locked: 2026-05-23 (Sat AM, pre-pilot)
status: forward-defensive; v1 mitigation status per attack
companion: SYSTEM_DESIGN.md §1.1 Gap 2; RESEARCH_DESIGN.md §6 Threats to Validity
purpose: anticipate optimization pressure from MCP server maintainers and characterize benchmark survivability
---

# Adversarial Audit

> "If I were an MCP server maintainer trying to game tool-crowding's MPD ranking, what would I do, and does the benchmark survive it?"

Six attack vectors. For each: plausibility, detection signal in our data, v1 mitigation, deferred mitigation if any. Tone is forward-defensive. Every attack is admitted as possible; the design's response is named.

---

## A1. Description keyword stuffing

**Attack.** Maintainer pads the tool description with code-retrieval keywords ("search", "code", "repository", "function", "symbol") to lift cosine similarity to the query embedding and surface above peers under retriever-ON.

**Plausibility: HIGH.** This is the cheapest, most obvious attack. It is the SEO of MCP.

**Detection.** Three signals jointly. (a) Description-token-count covariate (per `RESEARCH_DESIGN.md §3` confounders). A server whose description is in the top decile of token length and the top decile of MPD favorability is a flag. (b) Description-similarity-to-query-corpus centroid (per `FOUNDATION.md §1.0` P4): outliers above the description-corpus mean by >2σ are flagged. (c) Per-server MPD gap between retriever-ON and retriever-OFF: a server that gains under retriever-ON but is neutral under retriever-OFF is gaming the embedder, not the model.

**Rejection criterion.** A server with (description-token-count >2σ above pool mean) AND (retriever-ON MPD >0.10 favorable) AND (retriever-OFF MPD ≤0.0) is reported with an explicit "embedding-favorable description outlier" footnote on the leaderboard. We do not silently rank such servers.

**v1 mitigation.** SAT-D: covariate regression in `analysis/figures.py`; flag emitted in leaderboard JSON.
**v1.1 mitigation.** Adversarial-description robustness re-run with shuffled keyword stripping (replace top-10 query-relevant keywords with synonyms; re-score). Deferred.

---

## A2. Description shortening

**Attack.** Maintainer ships a deliberately short description to dodge attention dilution and avoid being the "longest" distractor in N>10 pools.

**Plausibility: MED.** Plausible for a sophisticated maintainer who has read our paper. Less plausible than A1 because short descriptions hurt independent discoverability.

**Detection.** Description-token-count covariate again. A server in the bottom decile of token length with the bottom decile of MPD harm (favorable MPD) is flagged. Cross-check against retriever-ON MPD: short descriptions hurt the retriever's recall, so retriever-ON MPD should be neutral-to-unfavorable for an A2 attacker even when retriever-OFF MPD is favorable.

**Rejection criterion.** A server with (description-token-count <0.5σ below pool mean) AND (retriever-OFF MPD <-0.05 favorable) is reported with "minimal-description outlier" footnote. We additionally publish a regression of MPD on description-token-count with R²; if R²>0.5, the per-server MPD ranking is qualified across the leaderboard, not just for individual servers.

**v1 mitigation.** SAT-D: covariate regression already in §6 threats table.
**v1.1 mitigation.** Length-normalized MPD as a secondary metric. Deferred.

---

## A3. Tool-name avoidance

**Attack.** Maintainer picks tool names that do not collide lexically with the primary code-retrieval tool's names ("scope_grep" instead of "search_code") to dodge name-collision failure-mode tagging while the descriptions still compete semantically.

**Plausibility: MED-HIGH.** Easy to do. MSR's 775-collision catalog (RESEARCH_DESIGN.md §1) makes name-collision a salient axis maintainers are likely to optimize on.

**Detection.** Failure-mode taxonomy in `FOUNDATION.md §4.5` distinguishes (7) tool-name collision from (8) description competition. A server with low (7) but high (8) is an A3 candidate: the names are non-colliding but the descriptions still bid for selection. Crossing this with description-similarity (P4) gives the discriminating signal: A3 attackers have low name-collision rate AND high description-similarity to primary AND favorable MPD.

**Rejection criterion.** Per-server failure-mode decomposition is reported. A server whose interference is dominated by category (8) is named in the limitations card with "semantic-only competition" tag. This is informational, not punitive: A3 is not gaming, it is the construct doing its job.

**v1 mitigation.** SAT-D: failure-mode taxonomy categories 7 and 8 separable in the per-trial log.
**v1.1 mitigation.** None needed; A3 is in-construct, not adversarial.

---

## A4. Version-pin gaming

**Attack.** Maintainer keeps a "good" old version pinned in `servers_pinned.yaml` for the benchmark while shipping breaking changes downstream. The published MPD becomes stale relative to what users actually install.

**Plausibility: LOW-MED.** Requires explicit coordination with us; also defeats the maintainer's own users (we don't pin private forks).

**Detection.** `servers_pinned.yaml` SHAs are content-hashed into `run_id` (TC.1, satisfied by `design/REPRODUCIBILITY.md §1`). Any pinned-version change derives a new `run_id` and a new leaderboard row; the original v1 row stays (per RESEARCH_DESIGN.md §11 item 7). A divergence between pinned-SHA and the latest published SHA on the server's repo is surfaced as a "version-age days" column on the leaderboard.

**Rejection criterion.** Servers with pinned-SHA >90 days behind their public latest at re-run time are reported with a "version-age >90d" footnote and a stale-version flag. Quarterly re-run policy (Gap 6 in SYSTEM_DESIGN.md §1.2) forces a refresh.

**v1 mitigation.** SAT-D: SHA pinning in `servers_pinned.yaml`; content-hashed into `run_id`.
**v1.1 mitigation.** Automated GitHub-API check for latest SHA at every analysis run; emit version-age column to leaderboard JSON. Manual for v1.0.

---

## A5. Description near-duplicate spoofing

**Attack.** Two near-identical descriptions get equally-bad MPDs that mask the underlying competition. Or, conversely, a maintainer ships description copy that closely mimics a popular peer to ride its discoverability, knowing pairwise interference between near-dupes is high but their joint exclusion lifts both.

**Plausibility: MED.** This is a real failure mode of pairwise MPD: A and B may each look "bad" only because of each other; removing one rescues the other.

**Detection.** The factorial N=4 sub-experiment (Reviewer-2 change #2 in `RESEARCH_DESIGN.md`) estimates pairwise interaction terms. Near-duplicate pairs surface as a large positive interaction term (MPD(A|B)+MPD(B|A) significantly worse than MPD(A)+MPD(B)). Description-similarity P4 also flags semantically near-identical pairs at the embedding level pre-trial.

**Rejection criterion.** Any server pair with pre-trial description cosine similarity >0.85 is reported as "near-duplicate pair" on the leaderboard with a joint MPD footnote. The factorial sub-experiment's per-pair interaction terms are published.

**v1 mitigation.** Description-similarity matrix pre-computed in `design/SERVER_POOL.md`; flagged pairs surface in the data card.
**v1.1 mitigation.** Drop-one re-runs for flagged pairs to confirm causal direction. Deferred.

---

## A6. Community PR amplification (replication-run gaming)

**Attack.** Maintainer recruits friends to submit positive replication runs via `tcrun submit` (v1.1 community PR contributions) to skew aggregate leaderboard means in their favor.

**Plausibility: LOW for v1.0 (no `tcrun submit` yet); MED for v1.1+.** Becomes more plausible as the community contribution surface opens.

**Detection.** All `tcrun submit` PRs preserve the original v1 row immutably (§11 item 7). Submitted runs land as separate rows with submitter identity, run_id, server SHAs, model fingerprint. Aggregate leaderboard means are computed only over v1 + officially-blessed re-runs, NOT community submissions; community runs are shown in a separate panel.

**Rejection criterion.** Community runs are never silently aggregated into the headline ranking. A server with N>3 community submissions all favoring it within a 30-day window triggers a "submission-cluster" flag pending review. We require submitter-environment fingerprint (model API version, host version, server SHA, cell_seed) to match a published reference cell for the submission to count.

**v1 mitigation.** N/A in v1.0 (`tcrun submit` is v1.1).
**v1.1 mitigation.** Submitter-fingerprint validation gate in `tcrun submit`. Separate community panel from canonical leaderboard. Cluster-flag heuristic.

---

## Summary table

| Attack | Plausibility | Primary detector | v1 status | Deferred |
|---|---|---|---|---|
| A1 keyword stuffing | HIGH | Length covariate × retriever-ON gap | SAT-D | Adversarial-description re-run |
| A2 description shortening | MED | Length covariate + retriever-OFF gap | SAT-D | Length-normalized MPD |
| A3 name-collision avoidance | MED-HIGH | Failure-mode tags (7) vs (8) | SAT-D | None needed (in-construct) |
| A4 version-pin gaming | LOW-MED | SHA in run_id + version-age column | SAT-D | Auto-SHA-check |
| A5 description near-duplicates | MED | N=4 factorial pairwise terms + P4 | Partial | Drop-one for flagged pairs |
| A6 PR amplification | LOW v1.0 / MED v1.1+ | Submitter-fingerprint validation | N/A v1.0 | v1.1 `tcrun submit` gate |

---

## Position

Every attack is possible. The benchmark's first-order defense is not detection of the attacker but invariance of the measurement: SHA pinning, immutable row history, covariate regressions, factorial pairwise terms, and quarterly re-runs collectively make the gaming surface costly and the gamed result legible. We name each attack publicly in this document on launch day rather than discovering it via a hostile reviewer six months later. Three attacks (A1, A2, A4) are fully addressed in v1.0. Two (A5, A6) have v1.1 deferrals named explicitly. One (A3) is reframed as the construct working as intended, not adversarial.

The benchmark survives this audit at v1.0. A1 keyword stuffing is the highest-residual-risk attack and the v1.1 adversarial-description re-run closes it.

## Related

[[FOUNDATION]] [[PRE_REGISTRATION]] [[../RESEARCH_DESIGN]] [[../SYSTEM_DESIGN]] [[REPRODUCIBILITY]] [[SERVER_POOL]] [[CHART_LAYOUT]]
