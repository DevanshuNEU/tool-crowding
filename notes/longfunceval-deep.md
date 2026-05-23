---
paper: LongFuncEval (Kate et al., IBM)
arxiv: 2505.10570
arxiv_url: https://arxiv.org/abs/2505.10570
read_date: 2026-05-21
read_depth: deep (target methodology + tables, not just abstract)
purpose: pre-DM defensibility check
---

# LongFuncEval deep read

Sibling agent flagged this as a thesis threat after skimming the abstract. Deep read says: **closest peer, not a kill-shot**. They conflate tool-count with prompt-length, which is exactly what our padded-N=1 control isolates. They are also non-MCP (BFCL + Booking.com REST), open-weight-heavy (only GPT-4o is frontier-tier), and have no per-server MPD or retriever-on/off arm.

Related: [[livemcpbench]], [[mcp-universe]], [[ragmcp-100]], [[silent-judge]]

---

## Q1. The per-position alpha control

**Mechanism.** Alpha is an **insertion-position fraction**, not a padded-context control. The correct function is placed at position `p` in the distractor list, where `p = round(alpha * len(distractors))`. Values tested: alpha in {0.1, 0.3, 0.5, 0.7, 0.9}. Quote from Section 4.1:

> "The original function is then inserted at a specified position p of the distractor list, which is determined by a fraction alpha of the length of the distractor list"

**What it controls for.** Position bias inside the catalog — "lost-in-the-middle" and recency/primacy effects when the correct tool is buried among distractors.

**What it does NOT control for.** Prompt-length growth. The distractor list itself is what grows the context (~162 tokens/tool, reverse-engineered from Table 3: 49 tools at 8,192 tok vs 741 tools at 120,000 tok). So when N grows, both `num_competing_tools` AND `raw_token_count` grow together. There is no padded-length isolation arm.

**Same as padded-N=1?** No. Padded-N=1 holds tool-count = 1 and inflates prompt length with filler. Alpha holds tool-count fixed at the N-level and varies WHERE inside the catalog the answer sits. Orthogonal controls. We can cite alpha as prior art for position control but our padded-N=1 is genuinely novel for length-isolation.

---

## Q2. Query construction

- **Challenge 1 (function calling):** Queries are not synthetic. Pulled from **BFCL (Berkeley Function Calling Leaderboard)** subsets `simple`, `live_simple`, `multiple`. Total **858 samples** across the three subsets. Distractor pool also from BFCL.
- **Challenge 2 (Booking.com long-context QA):** Queries are **synthesized** from the ComplexFuncBench dataset (Zhong et al., 2025) over 5 Booking.com REST endpoints. **566 QA samples**, three question categories: extraction / filtering / aggregation. See Table 4.
- **Contamination policy:** Not explicitly stated. BFCL is a public benchmark, so contamination is plausible for any model trained on it. They do not run a held-out leakage check.

**Implication for our project:** Their two challenges are not the same thing. Challenge 1 is "select the right function from a long catalog" (tool retrieval). Challenge 2 is "answer questions about a long JSON response" (long-context QA). Our discrimination-interference construct overlaps Challenge 1 only.

---

## Q3. The 9-model panel and degradation numbers

From Table 1 (overall % drop, max-to-min across all conditions):

| Model | Overall degradation |
|---|---|
| GPT-4o-2024-11-20 | **12.88%** (best) |
| QwQ-32B | 40.89% |
| ToolACE-8B | 62.17% |
| Granite-3.1-8b-instruct | 69.94% |
| Llama-3.1-70B-instruct | 72.11% |
| Llama-3.1-8B-Instruct | 76.11% |
| BitAgent-8B | 82.37% |
| DeepSeek-R1-Distill-Qwen-32B | 89.30% |
| Mistral-large | **94%** (worst) |

**Per-N curves (extracted from Table 1 + heatmaps Figure 3 / Figures 6-7 / Figure 5). Numbers below the dividing line are reverse-engineered from heatmap shading and should be marked "approx" in any DM.**

GPT-4o curve (only 3 N levels tested due to budget; positions 0.1/0.5/0.9 only):
- 8,192 tok: ~0.79 avg accuracy
- 32,768 tok: ~0.75
- 120,000 tok: ~0.69
- (16,384 and 65,536 not run)

Llama-3.1-70B-instruct:
- 8,192: 0.93
- 65,536: ~0.40 (heatmap inferred)
- 120,000: 0.22

Mistral-large:
- 8,192: 0.94
- 32,768: ~0.30 (heatmap inferred)
- 120,000: 0.00

Endpoints at 120,000 tokens for the rest:
- QwQ-32B: 0.45
- ToolACE-8B: 0.28
- BitAgent-8B: 0.12
- Llama-3.1-8B: 0.09
- Granite-3.1-8b: 0.09
- DeepSeek-R1-Distill-Qwen-32B: 0.02

**Panel composition flag.** Only one frontier closed model (GPT-4o). No Claude, no Gemini, no GPT-5-class. Eight of nine are open-weight, mostly 8B-32B with one 70B and one Mistral-large. **Our panel (Claude 4.7 / Sonnet 4.6 / GPT-5-class / Gemini 2.5-class) is non-overlapping with theirs except via GPT-4o-as-distant-ancestor.**

---

## Q4. Did they isolate prompt-length from tool-count?

**No.** This is the most important methodological gap. Distractors are full functional tool descriptions, and they are the only mechanism for growing context length:

> "Distractors are functions that are not relevant to the user query u but are randomly added to the context to simulate a large tool catalog."

The procedure adds distractors "until the token limit is reached." There is no filler-text padding arm. There is no constant-length-vary-tool-count arm. There is no constant-tool-count-vary-length arm.

Consequence: when Mistral-large drops from 0.94 to 0.00 between 8K and 120K, the paper cannot tell you whether the cause is (a) 740 extra competing tool descriptions or (b) 112K extra tokens of context. Our padded-N=1 control resolves exactly this ambiguity.

---

## Q5. Why is GPT-4o robust?

**Paper provides no mechanistic explanation.** Section 5.1 just states:

> "GPT-4o generalizes well even for longer context lengths exhibiting a minimal drop in performance"

**Methodology artifact warning (the GPT-4o number is partially confounded).** From Section 4.1, footnote:

> "Owing to budget constraints, we ran GPT-4o-2024-11-20 for context lengths 8,192, 32,768 and 120,000 for positions 0.1, 0.5, and 0.9"

So GPT-4o was tested on **3 of 5 N levels and 3 of 5 alpha positions** = 9 cells, while all other models were tested on 5x5 = 25 cells. The 12.88% degradation number is computed over a sparser grid that **skipped the two middle N levels (16K and 65K) where lost-in-the-middle would bite hardest**. It also skipped positions 0.3 and 0.7. This does not invalidate the headline (8K vs 120K is still a real comparison) but it means we should NOT cite "GPT-4o only loses 13%" in DMs without flagging the undersampling.

Defensible interview answer: "Their GPT-4o number is on a sparser sampling grid than the open-weights, so it's a directional finding, not a like-for-like."

---

## Q6. Methodology choices we should ADOPT

1. **Alpha-style position control.** Vary where inside the tool list the relevant tool sits. Even at fixed N, position matters (their Table 6 shows BitAgent loses 83% just from position). We should include at least 3 positions per N to disentangle position bias from raw discrimination.
2. **Category-split queries (extraction / filtering / aggregation).** Their Challenge 2 splits queries by reasoning type and finds different degradation curves per category. Code retrieval has its own analog (lookup / cross-file synthesis / refactor-scope). Worth a one-axis split.
3. **Token-budget-anchored N levels.** They define N levels by token budget (8K, 16K, 32K, 65K, 120K) rather than raw tool count. This is honest because it pins what the model actually sees. We should report both `num_tools` AND `total_prompt_tokens` per condition.

## Q7. Methodology choices we should AVOID

1. **Conflating tool-count and prompt-length.** Their core flaw. Our padded-N=1 arm exists precisely to fix this. Do not let reviewers conflate us with them.
2. **Sparse sampling for the headline model.** GPT-4o on 9 cells vs others on 25 cells = the most-cited number is also the least-comparable. We should run the same grid on every model in our panel, even if it costs more.
3. **No contamination check on BFCL.** BFCL is widely trained on. Code retrieval has the same risk (HumanEval, MBPP, etc). We should either pick a less-trained-on corpus or run a contamination probe.

---

## Q8. 6-condition intersection verdict

After this read, our defensible novelty:

| Condition | Verdict | Justification |
|---|---|---|
| **Code-retrieval domain** | OPEN | LongFuncEval is Booking.com REST APIs + BFCL function calling. No code-retrieval. |
| **Frontier-tier panel (Claude 4.7 / Sonnet 4.6 / GPT-5 / Gemini 2.5)** | OPEN | They tested GPT-4o on a sparse grid; everything else is open-weight ~8B-70B. Zero overlap with our panel. |
| **Padded-N=1 length-isolation in MCP regime** | OPEN | Their alpha control is position-only. No length-isolation arm anywhere in the paper. This is our hardest novelty. |
| **Per-server MPD (mean pairwise description distance)** | OPEN | They have no description-similarity metric. Distractors are sampled at random, not by lexical proximity. |
| **Pinned model versions across replication runs** | OPEN | They use one GPT-4o snapshot (2024-11-20) but do not formalize pinning across the panel. We can claim methodological tightening. |
| **Retriever ON / OFF arm** | OPEN | They do not test any retrieval-augmented baseline. Pure "all tools in context" regime. We can claim novelty on the ON/OFF contrast. |

**All six conditions are open or partially-covered. None are closed.** The closest competitor closes zero of our six.

---

## Honest DM-ready summary line

> "LongFuncEval is the closest peer methodologically. They proved tool-count harms function calling (7-94% degradation on 9 models) but they couldn't separate 'more competing tools' from 'longer prompt' because distractors are their only padding. Our padded-N=1 arm isolates that. They also only ran one frontier-tier model (GPT-4o, on a sparser grid) and never touched code-retrieval or MCP. The thesis stands."

---

## Tables and figures referenced

- **Table 1:** 9-model overall degradation percentages (Challenge 1).
- **Table 3 (App A.1.1):** Token-budget to tool-count mapping (49 / 102 / 207 / 417 / 741 tools).
- **Table 4 (App A.2):** Challenge 2 query distribution across 5 Booking.com endpoints (566 total).
- **Table 5:** Performance drop across context lengths at fixed position.
- **Table 6:** Performance drop across positions at fixed context length.
- **Table 7:** Challenge 2 per-model degradation (GPT-4o 7.04%, Mistral-large 91.30%, Llama-3.1-70B 52.25%, Granite-3.1-8b 30.47%).
- **Figure 2:** Challenge 2 question categories (extraction / filtering / aggregation).
- **Figure 3:** AST-accuracy heatmaps for `live_simple` subset, all 9 models, 5x5 grid.
- **Figure 5 (App B.1):** Average AST accuracy across the 3 datasets, 9 models.
- **Figures 6-7 (App B.1):** Heatmaps for `simple` and `multiple` subsets.

---

## Loose ends to verify before Friday DMs

1. The exact text of the alpha equation — current quote is paraphrased from "fraction alpha of the length of the distractor list". Pull the verbatim sentence before quoting in a DM.
2. Per-N decimals for Llama-3.1-70B at 16K, 32K (currently heatmap-inferred, marked "approx" above).
3. Whether Challenge 2's "p = ordinal position of records in JSON response array" is the same construct or a different one from Challenge 1's alpha — looks different (one is tool-list position, the other is JSON-array position) but worth confirming.
4. Footnote 4 mention of "120,000 to account for the maximum number of additional tokens introduced by tokenization and the prompts introduced by all the models" — read in full, it might already be a partial acknowledgment of the prompt-length confound. If so, we should cite that acknowledgment when claiming our novelty over them.
