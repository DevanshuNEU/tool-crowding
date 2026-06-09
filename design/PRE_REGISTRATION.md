---
doc: tool-crowding pilot pre-registration
locked: 2026-05-21 Thu PM (before Saturday pilot)
binding: yes — predictions cannot be changed after pilot data lands
pilot_date: 2026-05-23 (Saturday)
construct: discrimination interference (per FOUNDATION.md §1.0)
phase_f_locked: 2026-06-08 (Stage 1 confirmatory 2x2; binding before any Phase F data)
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

### Composition-sensitivity prediction (P5) — added 2026-05-25 PM, BEFORE pilot data

- **Predicted**: |MPD(orthogonal-domain pool primary) − MPD(same-domain query-primary)| ≥ 5pp at N=10 on the 30-query public-tier code-retrieval cell, with paired-bootstrap 99% CI not crossing zero.
- **Orthogonal-domain pool primaries**: Context7 (library-API surface) and Sentry (observability surface).
- **Same-domain query-primaries**: GitHub MCP, DeepWiki, Git MCP.
- **Direction**: not pre-registered as directional. Prior art does not pin a direction; we report descriptive sign and magnitude.
- **If the threshold is not met (CI crosses zero or |Δ| < 5pp)**: F4 fires (`FOUNDATION.md §1.0`). The composition-sensitivity arm is reported as null; chart-primaries collapse to "Pool primaries" without the composition split; query-primaries (GitHub MCP, DeepWiki, Git MCP) carry the headline alone.
- **Why this matters**: distinguishes raw-N crowding (any added server hurts equally) from composition-sensitive crowding (only same-domain servers hurt). Prior art (RAG-MCP, LongFuncEval, MCPVerse) treats N as a uniform scalar; nobody has measured this.

**Pre-registration integrity note.** P5 was added 2026-05-25 PM after the strategic shortlist reframe (`research/server_pool_shortlist_2026-05-25.md` and the install-research reports) revealed that two of the 5 pool primaries (Context7, Sentry) are tool-domain-orthogonal to code-retrieval. P5 was locked BEFORE any pilot data was collected (the Saturday 2026-05-23 pilot did not actually run; harness commissioning is track-3 work). Treating P5 as pre-registered is therefore legitimate.

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
- IF F4 fires (composition Δ <5pp or CI crosses zero): drop the composition-sensitivity arm from the headline figure; report Context7 + Sentry as named-vendor distractors in the leaderboard; the 5-server chart-primaries reading collapses to 3 query-primaries carrying the headline.
- IF Sonnet 4.6 shows monotonic improvement at all N: kill criterion fires; ship as Scenario 3 with detailed MCPVerse comparison.
- IF Sonnet 4.6 N=20 unpadded is within 2pp of N=1: pilot was underpowered (n=3 across 3 queries is the floor); decide Sat PM whether to expand n=3 to n=5 before full study or ship pilot-as-final.

## What we will NOT change after pilot data lands

- The 5pp thresholds above (P1, P2, P5).
- The 0.3 / 0.5 rho thresholds (P3).
- The 0.2 r threshold (P4).
- The scenario assignments above.
- The harness as the lasting contribution regardless of scenario.

## Phase F: factorial framing × ambiguity (LOCKED 2026-06-08)

> **STATUS: LOCKED 2026-06-08 — binding.** Drafted 2026-06-01; thresholds reviewed
> and locked by Devanshu 2026-06-08 BEFORE any Phase F confirmatory data (integrity
> basis identical to P5). Predictions, thresholds, n, kill gates, and scenario
> assignments below cannot be changed after Phase F data lands. The lock fingerprint
> is the git commit that flips this status; any later change is tamper-evident in the
> repo history. Two changes were folded in at lock: (1) the deepwiki index-recording
> clause now describes the shipped Option-C recorder (a hashed read_wiki_structure
> response, not a literal commit); (2) wger is added as a named positive control
> (separate reference arm, not a 2×2 cell). No Phase F trial ran before this flip.

### Why Phase F exists (what the exploratory probes did to P1)

The N=1/4/6 exploratory probes (two clean nulls + the ambiguity/confound pair,
2026-05-30 → 05-31) returned pass@1 flat at 100% across N under an
**unambiguous, target-named** task. The naive N-main-effect of P1 ("more servers
→ lower pass@1") did not appear and kill criterion #1 was approaching. What
survived is sharper: in the neutral-prompt confound run (`c6d2dae`), the deepwiki
LURE bit (2/4 trials explored a distractor, 1 solved via the lure), whereas the
code-retrieval framing suppressed it (0 lured) and target-named tasks suppressed
it (both nulls, 0 lured). The surviving hypothesis is therefore an **interaction**,
not a main effect: interference appears only when the task is ambiguous AND the
agent is under-framed. n=4 is signal, not result. Phase F is the confirmatory test.

Spine decision (Devanshu, 2026-06-01): **staged synthesis that rescues N.**
Confirm the interaction first (Stage 1); then, conditional on a positive, sweep N
inside the hot cell (Stage 2) to test whether crowding is a real dose-response in
that regime. The project keeps its name only if Stage 2 is positive; otherwise
"crowding" is dropped from the spine and the paper reframes as
ambiguity-driven discrimination interference.

### Harm metric (Devanshu, 2026-06-01; refined 2026-06-04): DCR_trial is THE primary

In the wger instrument the lure (deepwiki) returns a CORRECT answer, so pass@1 is
at ceiling and is NOT the harm signal. The registered harm is **efficiency**, and
the single gating metric is **DCR_trial**.

**Callability vs solve (the 2026-06-04 reframe).** The lure plays two separable
roles. (1) CALLABILITY — does the agent route to the lure? Decided at
tool-selection time, BEFORE any result, from the PINNED tool description + task +
framing + model + temperature. (2) SOLVE — does the lure return the target?
Depends on deepwiki's live, drifting index. The deepwiki coverage probe
(2026-06-04) found all current anchor symbols postdate their repo's deepwiki index,
so deepwiki cannot SOLVE them — but it remains live and CALLABLE. DCR_trial is a
callability measure and is therefore **robust to deepwiki staleness**; SSA-miss is
a solve measure and is freshness-conditional. We make DCR_trial the gating metric.
See `~/DevVault/tool-crowding/lure-design-rethink-2026-06-04.md`.

- **DCR_trial (PRIMARY, gating)** — fraction of trials with ≥1 call to a
  non-grounded (distractor) server. "How often crowding causes a wrong-tool
  excursion." Confound probe hot corner ≈ 0.50; both nulls ≈ 0. Reproducible: the
  first distractor call depends only on pinned inputs + model sampling.
- **DCR_call (secondary)** — distractor calls / total tool calls, aggregate.
- **SSA-miss (secondary, freshness-conditional)** — fraction of PASSING trials whose
  `solving_server` is not the grounded primary (solved via the lure). SSA =
  Solving-Server Attribution; generalizes MetaTool's CSR. Reported ONLY for
  (repo, run) pairs where the recorded deepwiki index commit postdates the anchor's
  introducing commit (i.e. the lure could actually solve). NOT gating: a stale-index
  run still measures DCR_trial.
- **Cost/latency (secondary)** — mean tool calls/trial, input+output tokens/trial.
- **pass@1 (secondary, expected ceiling)** — reported, but not the harm signal here.
- **Correctness harm (exploratory, opportunistic)** — trials where the lure route
  yields a wrong/stale answer the agent trusts. Captured only if a task naturally
  produces it; NOT engineered. The pinned-synthetic-lure upgrade path (lure-design
  rethink, direction B) is what would make this a first-class arm later.

**Lure strategy (Devanshu, 2026-06-04): hybrid (direction C).** Stage 1 uses the
real deepwiki lure with DCR_trial primary, and RECORDS each repo's deepwiki index
commit at run time (partially closes ADVERSARIAL_AUDIT A7-A9). A pinned synthetic
lure is deferred as the upgrade path if correctness harm becomes a headline.

Prior art (MetaTool, MCP-Atlas) partially scoops the bare lure effect; Phase F's
novelty is the **factorial decomposition** (framing × ambiguity) with two
pre-existing nulls bounding it, plus the conditional N dose-response. Cite and
distinguish MetaTool in the paper.

### Factors and held-constant topology (Stage 1)

- **Factor A — agent framing** (`system_prompt_variant`): {code-retrieval, neutral}.
  Runtime-swappable via `TC_SYSTEM_PROMPT_VARIANT`, value-hashed into run_id.
- **Factor B — task specification**: {target-named, ambiguous}. Two query variants
  per underlying task sharing identical ground_truth: target-named names the route
  ("…in the GitHub repository ansible/ansible"); ambiguous states only the
  conceptual question. The ONLY text difference is the repo-name prefix.
- **Topology held constant**: N=4, identical to the composition null and the
  ambiguity probe (github_mcp grounded primary + deepwiki LURE + git_mcp +
  filesystem_mcp), retriever OFF. Isolates framing × ambiguity with topology fixed.
- **Task set**: `tasks/stage1-factorial.jsonl` — 5 verified post-cutoff anchors
  (ansible, paperless-ngx, synapse, calibre, weblate) × {ambiguous, target-named} =
  10 records. wger EXCLUDED (it generated the hypothesis → non-independent). All
  copyleft. Provenance: `~/DevVault/tool-crowding/stage1-task-set-provenance-2026-06-03.md`.
- **deepwiki index recording (REQUIRED at run time)**: for each repo, record
  deepwiki's `read_wiki_structure` response (hashed + timestamped) alongside the run
  via `tcrun/deepwiki_index.py` (writes `run_dir/deepwiki_index.json`). deepwiki's API
  exposes no literal index commit, so the recorded response IS the index-state
  evidence. SSA-miss is interpreted only for (repo, run) pairs where that recorded
  response shows the target could have been surfaced. DCR_trial needs no such gate.
- **Sampling**: temp = 1.0 (the effect needs stochastic trajectories; temp=0 gave
  the deterministic 0-lure result), n ≥ 15 trials/cell, Q = 5 queries across 5
  repos. Paired-bootstrap CIs, B = 10,000, 99% (matching P5).
- **Positive control (wger, separate reference arm — added at lock 2026-06-08)**: a
  small (neutral, ambiguous) wger arm runs alongside Stage 1, NOT as a 2×2 cell (wger
  stays excluded from the confirmatory factorial to preserve independence). wger is the
  one anchor whose deepwiki index postdates its symbol, so the lure genuinely SOLVES
  it; the arm confirms SSA-solve > 0, demonstrating the lure CAN bite. This makes a
  null DCR_trial interpretable (instrument sensitivity — earning the null) and
  validates the SSA-miss secondary. Reported as a control; never pooled into
  H-F1/H-F2/H-F3.

### Stage 0 — exploratory replication gate (NON-binding, ~$12)

n=15 at a single query, Sonnet 4.6, the 2×2, N=4. Proceed to Stage 1 only if the
(neutral, ambiguous) corner shows DCR_trial > 0 and descriptively exceeds the
other three corners. Cheapest falsification first (staged-spend doctrine). If the
corner is flat here, stop before the Stage 1 spend.

### Stage 1 — CONFIRMATORY 2×2 (registered; ~$60, cost-cap $80)

- **H-F1 (interaction, primary; gated on DCR_trial ALONE):** DCR_trial is elevated
  ONLY in the (neutral × ambiguous) cell. Predicted: (neutral, ambiguous)
  DCR_trial ≥ 0.40 AND each of the other three cells ≤ 0.15; the difference
  [(neutral,ambiguous) − max(other three)] has a 99% paired-bootstrap CI not
  crossing zero. SSA-miss is reported as a freshness-conditional secondary (hot
  corner ≥ 0.20 where the deepwiki index could solve), but does NOT gate H-F1.
- **H-F2 (framing main effect, secondary):** holding task ambiguous, neutral
  framing yields higher DCR_trial than code-retrieval framing, CI clear of zero.
- **H-F3 (ambiguity main effect, secondary):** holding framing neutral, ambiguous
  task yields higher DCR_trial than target-named, CI clear of zero.
- **Kill gate (FF1):** if H-F1 fails (hot corner does not separate from the other
  three at threshold with CI clear of zero), the n=4 interaction was noise. STOP.
  Document as null; do not run Stage 2. Paper becomes an honest negative or shelve.

### Stage 1b — model robustness (CONDITIONAL on Stage 1 positive; ~$60)

Repeat Stage 1 on a second frontier model (GPT-5-class or Opus). H-F1 expected to
replicate in direction; report per-model. Non-replication → effect is
model-specific, reported as such (does not retroactively kill Stage 1).

### Stage 2 — N dose-response / the crowding rescue (CONDITIONAL on Stage 1 positive; ~$60, cost-cap $80)

Within the hot cell (neutral framing, ambiguous task), sweep N ∈ {4, 8, 12} by
adding pool distractors; grounded primary + deepwiki lure held fixed.

- **H-F4 (dose-response; gated on DCR_trial):** DCR_trial increases with N.
  Predicted: DCR_trial(N=12) − DCR_trial(N=4) ≥ 0.15, 99% paired-bootstrap CI not
  crossing zero. SSA-miss reported as freshness-conditional secondary, not gating.
- **Kill gate (FF2 — the spine fork):** if flat across N (difference < 0.15 or CI
  crosses zero), the interference is ambiguity×framing-driven, NOT crowding-driven.
  "Crowding" is dropped from the paper's spine; reframe as N-independent
  discrimination interference under ambiguity. This is the honest fork the staged
  design forces.

### Staged budget + cost discipline

Total across all stages if every gate fires: ~$170-190, inside the ~$200 top-up.
Hard cost-cap enforced per stage via `tcrun run --cost-cap` (orchestrator
CostCapExceeded). No-MCP baseline arm (`include_no_mcp_baseline`, now wired) runs
once per query as the uncontaminated floor; manual probe was 0/5.

### Phase F scenario abstracts (LOCKED 2026-06-08)

- **F-A — Clean interaction:** the 2×2 confirms H-F1; Stage 2 confirms H-F4. Story:
  "tool crowding is real but conditional — it costs you wasted tool calls (and
  lure commitment) only when the task is under-specified and the agent is
  under-framed, and that cost grows with the number of installed servers." Keeps
  the project name; reconciles the nulls with the thesis.
- **F-B — Gated but N-flat:** H-F1 confirms, H-F4 fails (FF2 fires). Story: the
  interference is ambiguity×framing, independent of N. Drop "crowding"; reframe.
- **F-C — No interaction (null):** H-F1 fails (FF1 fires). The n=4 signal was
  noise. Honest negative: "across a pre-registered factorial we could not
  reproduce multi-MCP discrimination interference under any framing×ambiguity
  combination at N=4." Ship the harness + the null, or shelve.

### What Phase F will NOT change after Stage 1 data lands

- The DCR_trial 0.40 / 0.15 gating thresholds (H-F1). SSA-miss is a
  freshness-conditional secondary and does not gate.
- The 0.15 dose-response threshold (H-F4).
- The temp=1.0, n=15, Q=5, N=4 Stage 1 design.
- The kill gates FF1 / FF2 and their spine consequences.
- The scenario assignments F-A / F-B / F-C.

## Authorship and audit trail

- Phase F (factorial framing × ambiguity) drafted 2026-06-01 by Claude in
  collaboration; spine + harm-metric forks decided by Devanshu the same day.
  Integrity basis identical to P5: added before any confirmatory data.
- Phase F refined 2026-06-04 (pre-data; still DRAFT at the time): after the deepwiki
  coverage probe found all anchor symbols postdate their repo's deepwiki index,
  the callability-vs-solve distinction was made explicit and **DCR_trial became the
  sole gating metric** (Devanshu's call); SSA-miss demoted to freshness-conditional
  secondary; deepwiki-index recording added as a run-time requirement; lure strategy
  set to hybrid (direction C). All changes are pre-confirmatory-data and logged here.
- Phase F LOCKED 2026-06-08 by Devanshu after threshold review. Thresholds frozen
  as-is (DCR 0.40/0.15, dose 0.15, temp 1.0, n=15, Q=5, N=4; kill gates FF1/FF2;
  scenarios F-A/F-B/F-C). Two changes folded in at lock: (1) the deepwiki
  index-recording clause now matches the shipped Option-C recorder (hashed
  read_wiki_structure response); (2) wger added as a named positive control
  (separate arm, not a 2×2 cell). No Phase F trial ran before this lock; the
  status-flipping git commit is the lock fingerprint.
- Predictions P1-P4 locked 2026-05-21 Thu PM by Devanshu, written by Claude in collaboration.
- Prediction P5 (composition-sensitivity) added 2026-05-25 PM as part of the locked-decision pivot (`research/oci_removal_audit_2026-05-25.md`, `research/server_pool_shortlist_2026-05-25.md`). Added BEFORE pilot data collection (the Sat 2026-05-23 pilot did not actually run; harness commissioning is track-3 work). Pre-registration integrity preserved.
- File hash will be committed before pilot run (after harness commissioning in track-3).
- Any post-hoc modification will be marked as exploratory analysis, not pre-registered.

## Related

[[FOUNDATION]] [[PILOT_V0]] [[../RESEARCH_DESIGN]] [[../notes/longfunceval-deep]] [[../notes/mcpverse-deep]] [[../notes/ragmcp-100]]
