---
doc: tool-crowding pilot pre-registration
locked: 2026-05-21 Thu PM (before Saturday pilot)
binding: yes — predictions cannot be changed after pilot data lands
pilot_date: 2026-05-23 (Saturday)
construct: discrimination interference (per FOUNDATION.md §1.0)
---

# Pre-registration

This document locks predictions BEFORE the pilot runs. Per FOUNDATION.md §1.0 falsification conditions and §3 kill criteria. The point of pre-registration: if we cannot write the abstract for any of the 4 scenarios, we don't know what the null means and shouldn't run the pilot.

## Pilot design (locked, full details in design/PILOT_V0.md)

- 2 models: Claude Sonnet 4.6 (primary), GPT-5-class (robustness)
- 4 N levels: 1, 5, 10, 20
- 2 conditions: unpadded (real distractors), padded-N=1 (length-matched neutral filler)
- n=3 trial repeats per (model, N, condition, query) cell
- 3 queries from design/QUERY_SET_HYGIENE.md pilot subset
- Code-retrieval task; passes per programmatic oracle
- 2 × 4 × 2 × 3 × 3 = **144 trials** total (main matrix)
- Plus retriever-ON robustness probe at N=20 only (~30 trials)
- Plus RAG-MCP replication cell at N=10/100/1000 on Sonnet 4.6 (~50 trials)

## Pre-locked predictions (DO NOT MODIFY AFTER PILOT DATA)

### Primary effect prediction (P1)

- Sonnet 4.6 unpadded pass@1 at N=20 will be at least 5pp lower than at N=1.
- GPT-5-class unpadded pass@1 at N=20 will be at least 5pp lower than at N=1.
- Intermediate N=5 and N=10 may show non-monotonic behavior (MCPVerse v1 showed inverted-U with peak at Standard mode); we do not pre-lock monotonicity.

### Mechanism prediction (P2) — load-bearing test of the construct

- Padded-N=1 pass@1 will be AT LEAST 5pp HIGHER than unpadded-N=20 pass@1 on Sonnet 4.6.
- This isolates discrimination from capacity per FOUNDATION §1.0.
- If the gap is <5pp, falsification condition F1 fires.

### Stability prediction (P3)

- Per-server Marginal Performance Delta across the 3 trial repeats will have Spearman rho > 0.5 on Sonnet 4.6.
- If rho < 0.3, falsification condition F2 fires.

### Description-similarity prediction (P4)

- Description-similarity (cosine of embedding centroids between target server and pool average) will correlate with MPD with Pearson r > 0.2.
- If r < 0.2 across models, F3 fires.

## Four scenario abstracts (locked before data lands)

### Scenario 1: Clean win (prior ~15%)

> Tool-crowding measures discrimination interference in multi-MCP tool selection. Across 144 trials, both Claude Sonnet 4.6 and GPT-5-class showed 5+pp pass@1 degradation at N=20 versus N=1 on a contamination-resistant code-retrieval query set. Padded-N=1 controls left a residual gap of 5+pp, isolating the effect from prompt-length confounds. Per-server MPD Spearman rho was above 0.5, indicating stable per-server discriminability, and description-similarity correlated with MPD at r above 0.2. Implications: production MCP deployments above N=10 require per-server quality filtering or active retrieval. The harness ships with both as configurable conditions, plus full server SHA pinning, padded-context controls adapted from Chroma, and the RAG-MCP replication cell as external validity probe.

### Scenario 2: Methodology contribution (prior ~35%)

> Tool-crowding ports Chroma's padded-context methodology to multi-MCP tool selection. Across 144 trials, both Claude Sonnet 4.6 and GPT-5-class showed 5+pp pass@1 degradation at N=20 versus N=1. However, padded-N=1 controls accounted for the majority of the gap (within 5pp of the unpadded effect), indicating that prompt-length capacity is the dominant mechanism, not semantic discrimination. The contribution is methodological: the first multi-MCP benchmark with proper length-isolation, paired with per-server MPD as a diagnostic tool. Production implications: capacity dominates; deploy code-execution-with-MCP (Anthropic Nov 2025) or aggressive retrieval. The construct of "discrimination interference" is shown not to apply to current frontier models; capacity is the right frame.

### Scenario 3: Frontier robust (prior ~25%)

> Tool-crowding probes whether multi-MCP interference is a frontier-model phenomenon. Across 144 trials, both Claude Sonnet 4.6 and GPT-5-class showed less than 5pp pass@1 degradation at N=20 versus N=1, contradicting per-N-level degradation reported by LongFuncEval on smaller open-weight models (7.59-85.58% range). The headline finding: frontier-class models in 2026 absorb 1-20 concurrent MCPs without measurable selection degradation. The harness ships as a diagnostic tool: per-server MPD identifies rare server-pair conflicts that frontier robustness does not erase, and is the project's lasting contribution. Production implications: stop avoiding multi-MCP at frontier-class deployments; do continue avoiding it at smaller-model deployments per LongFuncEval.

### Scenario 4: Mixed by model class (prior ~25%)

> Tool-crowding measures multi-MCP discrimination interference across frontier-class regimes and finds model-class is the dominant moderator. Sonnet 4.6 shows inverted-U behavior at the pilot N levels, partially replicating MCPVerse's Standard-mode result with multi-trial confidence intervals. GPT-5-class shows monotonic degradation. Per-server MPD is stable for Sonnet 4.6 but unstable for GPT-5-class. Implications: tool-crowding is real for some frontier models and absent for others; deployment recommendations must be model-conditional. The harness becomes the artifact production teams use to evaluate their specific deployment.

## Pre-locked decision rules

- IF F1 fires (padded gap <5pp on either Sonnet 4.6 OR GPT-5-class): ship Scenario 2 paper, downgrade harness from "headline finding" to "methodology contribution," drop discrimination-as-mechanism externally.
- IF F2 fires (per-server MPD rho <0.3 on both models): drop per-server MPD from the paper; ship as global N-effect only.
- IF F3 fires (similarity-MPD r <0.2): drop the description-similarity correlation analysis; ship per-server MPD as observed-but-unexplained variance.
- IF Sonnet 4.6 shows monotonic improvement at all N: kill criterion fires; ship as Scenario 3 with detailed MCPVerse comparison.
- IF Sonnet 4.6 N=20 unpadded is within 2pp of N=1: pilot was underpowered (n=3 across 3 queries is the floor); decide Sat PM whether to expand n=3 to n=5 before full study or ship pilot-as-final.

## What we will NOT change after pilot data lands

- The 5pp thresholds above (P1, P2).
- The 0.3 / 0.5 rho thresholds (P3).
- The 0.2 r threshold (P4).
- The scenario assignments above.
- The harness as the lasting contribution regardless of scenario.

## Authorship and audit trail

- Predictions locked 2026-05-21 Thu PM by Devanshu, written by Claude in collaboration.
- File hash will be committed before pilot run Sat AM (after git init if not done).
- Any post-hoc modification will be marked as exploratory analysis, not pre-registered.

## Related

[[FOUNDATION]] [[PILOT_V0]] [[../RESEARCH_DESIGN]] [[../notes/longfunceval-deep]] [[../notes/mcpverse-deep]] [[../notes/ragmcp-100]]
