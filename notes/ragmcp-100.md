---
paper: "RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation"
arxiv: 2505.03275
arxiv_url: https://arxiv.org/abs/2505.03275
read_date: 2026-05-21
read_depth: skim (abstract + HTML v1 extraction via WebFetch; PDF binary not parsed)
authors: Tiantian Gan, Qiyao Sun
artifact: no public code link surfaced in abstract; registry referenced is mcp.so (April 2025 snapshot, 4,400+ servers)
verdict: THESIS_THREAT (partial) — they DID vary N as an IV
relevance_to_tool_crowding: HIGH (closest prior art on N-as-IV; we must position carefully)
---

# RAG-MCP (Gan & Sun, May 2025)

## What they measured

A retrieval-augmented framework for MCP tool selection: instead of dumping all installed tool schemas into the prompt, semantically retrieve the top-k MCPs from an external index of 4,400+ servers (mcp.so) and only pass those descriptions to the LLM. They evaluate on the web-search subset of MCPBench with **qwen-max-0125** as the base LLM, 20 trials per baseline. Headline: 43.13% selection accuracy vs 13.62% blank-conditioning baseline, with prompt tokens cut from 2,133.84 → 1,084.

They also run a separate "MCP stress test" that varies N (the number of MCP schemas in the prompt) systematically and plots a heatmap (Figure 3) of which positions get retrieved correctly as N grows. **This is the experiment that directly overlaps tool-crowding's design.**

## Did they vary N as an IV? YES.

This is the part that matters.

Section 3.1: *"we vary N from 1 to 11100 in 26 intervals"* (the "11100" is likely an OCR rendering of "1,100" or similar — couldn't verify in the PDF binary; the qualitative claim "we sweep N over many orders of magnitude" survives either reading).

Each trial: present model with N MCP schemas (1 ground-truth + N-1 distractors drawn from the 4,400 mcp.so registry), ask it to select and invoke the correct WebSearch MCP. Metrics: selection accuracy, task success, prompt tokens, latency.

Section 5: *"Beyond position ~100, purple dominates, signifying that retrieval precision diminishes when handling very large tool registries."* This is the only place "100" appears in the paper text I could verify — it is a **per-position retrieval degradation threshold in the Figure 3 heatmap**, not a separate "RAG-MCP-100" experiment. The "100" in the project's `[VERIFY-RAGMCP-100]` shorthand is third-party framing, not the paper's own.

**They did the N-sweep. The "nobody varies N as an IV" framing of tool-crowding's thesis is wrong as currently written.**

## Methodology choices that stood out

- **Single model only** (qwen-max-0125). No cross-model comparison. Their N-sweep findings are not known to generalize to Claude, GPT-5, Gemini, etc.
- **Single task domain** (web search, single ground-truth tool per task). Their "task success" oracle is "did you call the right tool" — closer to tool selection than end-to-end task completion. They do not run a multi-step code-retrieval workflow.
- **Distractor pool is the 4,400 mcp.so registry**, sampled at random per trial. No control for semantic similarity between distractors and ground-truth tool (which is the actual interference mechanism we suspect).
- **Trial count is 20 per baseline method**, NOT 20 per N value. The stress-test plot in Figure 3 appears to be a single-trial-per-cell heatmap with no error bars or confidence intervals. ABC R.10 violation again.
- **No per-N accuracy table.** Figure 3 is a heatmap; numeric accuracy at specific N is not tabulated. To cite "performance drops above N=100" we have to point at a figure, not a number.
- **Retriever is a lightweight Qwen-based encoder.** Solution they propose (RAG-MCP) tests their own retriever; no comparison to off-the-shelf BM25, OpenAI text-embedding, or other encoders. Solution-side ablation is thin.

## What to steal for tool-crowding harness design

- **The padded-N stress-test pattern** (1 ground-truth + N-1 distractors, vary N) is exactly the control we need for the padded-N=1 condition. They've validated the design pattern. We can cite them and inherit credibility.
- **mcp.so as the distractor pool** (4,400+ servers, public registry). Tool-crowding's `SERVER_POOL.md` currently lists curated servers; consider drawing distractors from mcp.so to match prior art and increase external validity.
- **The retrieval-as-mitigation framing** is a natural section 7 ("Implications") for our paper: if our N-curve degradation is real, RAG-MCP is the obvious fix and we should benchmark *with vs without* retrieval as a treatment arm. This makes our paper constructive, not just diagnostic.
- **Heatmap visualization of which tool positions get retrieved at each N** (Figure 3 shape) is a strong figure idea. Adapt for code-retrieval.

## What they DIDN'T measure (where the gap survives)

This is the load-bearing list. Each item is a piece of the tool-crowding thesis that RAG-MCP did NOT touch.

1. **Cross-model N-degradation curves.** Only qwen-max. Sonnet 4.6 vs GPT-5 vs Claude Haiku 4.5 vs Gemini at the same N is open territory. Our N-sweep × model heatmap is novel.
2. **Code-retrieval as the task.** Their task is "select the WebSearch tool from a pile." Code-retrieval (multi-step, multi-tool, requires actual code understanding to grade) is untouched. Our case study domain is uncontested.
3. **Per-server Marginal Performance Delta (MPD).** They treat distractors as a homogeneous bag drawn from 4,400 servers at random. Which *specific* added servers degrade performance most is the MPD question. They never ask it.
4. **End-to-end task pass@1 at fixed N.** Their oracle is binary tool-selection. The compositional failure mode (right tool selected, wrong args; right tool, hit context overflow before completing; etc.) is invisible to their metric.
5. **Padded-N=1 control.** They never isolate "long prompt with one tool" vs "long prompt with N tools." Their 1-ground-truth-N-1-distractor design conflates prompt length with tool count. **This is the exact methodological gap our padded-N=1 control closes.**
6. **Server version pinning.** mcp.so listings drift. No SHA pinning, no description-hash. Their experiment cannot be re-run on the same registry state as April 2025.
7. **Distractor semantic-similarity control.** Random draws from 4,400 servers means distractor similarity to ground-truth is uncontrolled. Whether crowding is driven by N alone, or by N × semantic-similarity, is undisturbed.
8. **Token cost decomposition.** They report prompt-token reduction (2133 → 1084) but not how it scales with N, not output-token cost, not retries.

## One open question this raises for tool-crowding

**Does our padded-N=1 control replicate RAG-MCP's stress-test pattern, or does it pick up something they missed?**

If we run their setup (qwen-max, web-search task, 1 ground-truth + N-1 random distractors) and reproduce their Figure 3 degradation curve, that's a strong external-validity hit for our harness — same shape as the published prior art. If our padded-N=1 condition (1 ground-truth + N-1 *copies* or *padded-token-equivalents* with no other tools) is FLAT while their N-distractor condition degrades, we've cleanly decomposed "long prompt" from "many tools competing for selection" in a way they could not.

**Action:** Add a "replicate RAG-MCP web-search stress test" cell to the harness as a sanity check / external-validity probe. Cost: low (single model, simple oracle). Payoff: high (cites prior art, validates harness on a known-degrading curve, then shows our code-retrieval curve is qualitatively different or similar).

## Compatibility with our gap claim

**THESIS THREAT (partial). The "nobody varies N" framing is FALSE as written. Rewrite required.**

What survives of the tool-crowding gap claim after this paper:

- **Nobody varies N for code-retrieval.** Survives. RAG-MCP is web-search-only, single-tool oracle.
- **Nobody varies N across multiple frontier models.** Survives. RAG-MCP is qwen-max-only.
- **Nobody computes per-server MPD.** Survives. They treat distractors as a uniform bag.
- **Nobody runs a padded-N=1 prompt-length control.** Survives. Their design conflates prompt length with tool count.
- **Nobody pins server versions / hashes descriptions.** Survives. mcp.so snapshot is unpinned.
- **Nobody publishes per-trial logs with CIs at each N.** Survives. They publish a heatmap, not a table with error bars.

What does NOT survive:

- **"Nobody sweeps N as an IV."** Dead. They did, from N=1 to N=~1,100 (or 11,100) across 26 intervals. We have to acknowledge this in the related work and in the launch post. Rewriting required in RESEARCH_DESIGN.md Section 1 (the novelty paragraph) and in any public framing that says "no one has varied N."

The thesis is not dead. The framing is. Pivot the pitch to: *"RAG-MCP varied N as an IV for **tool selection accuracy** on a **single-tool web-search oracle** with **a single model**. We vary N for **end-to-end code-retrieval pass@1** across **multiple frontier models**, with **padded-N=1 prompt-length controls** and **per-server MPD decomposition** that their random-distractor design cannot produce."*

This is a stronger pitch than "nobody varies N" because it's defensible against the obvious reviewer pushback ("but RAG-MCP did?") and forces us to articulate the actual measurement contribution. RAG-MCP becomes a citation and a sanity-check replication, not a competitor.

## Actions pulled out of this read

1. **Rewrite the novelty paragraph in RESEARCH_DESIGN.md Section 1** (Wed evening) to acknowledge RAG-MCP. Replace "nobody varies N" with the precise scoped claim above.
2. **Update [VERIFY-RAGMCP-100] in CLAUDE.md status:** the "fails above 100" claim is in the paper (Section 5, Figure 3 caption-adjacent text), referring to position-in-heatmap, not a separate experiment.
3. **Add a "RAG-MCP replication" cell to the harness pre-registration** as an external-validity probe. Single model (qwen-max or substitute), web-search task, 1 + N-1 random distractors from mcp.so, N ∈ our standard grid.
4. **Cite RAG-MCP prominently in Related Work** as the closest prior art. Frame as complementary (their solution + our diagnostic), not adversarial.
5. **Re-read the strategy-level pitch in `strategy/week-1/2026-05-21.md`** and the BIP launch draft for any "no one has varied N" framing. Fix it before Sun launch.
6. **Pull PDF locally and verify "11100" number** before any public statement quotes the range. Web fetch on the HTML produced OCR-suspect output. Honest framing for now: "varied N over many orders of magnitude (1 to ~10^3 or ~10^4 depending on PDF interpretation)."

## Verdict for tool-crowding

**Partial thesis threat. The blunt "nobody varies N as an IV" claim is dead — RAG-MCP did exactly that for web-search tool selection.** The gap survives in a tighter, more defensible form: nobody varies N for end-to-end code-retrieval pass@1 across multiple frontier models, with per-server MPD decomposition and padded-N=1 controls. The harness still has a clean contribution; the framing needs surgery before Sunday's launch post. RAG-MCP becomes prior art to cite and a replication target for external validity, not a scoop. Material reframing required in RESEARCH_DESIGN.md Section 1 and the launch narrative — but no kill-criterion fires.

## Deep verification (2026-05-21 Thu PM)

Resolved the 1,100 vs 11,100 OCR ambiguity flagged in tonight's earlier read. Pulled the paper from two independent HTML renderings — `arxiv.org/html/2505.03275` and `ar5iv.labs.arxiv.org/html/2505.03275`. Both agree verbatim. PDF binary was not parsed; HTML is the canonical machine-readable source for arXiv and is generated from the same LaTeX source as the PDF, so the number is authoritative.

### Q1. Exact N range

**N = 1 to 11,100.** Confirmed verbatim from both HTML sources: *"we vary N from 1 to 11100 in 26 intervals."* The earlier skim's hedge ("1,100 or 11,100") resolves to **11,100**. The framing in section 5 about "beyond position ~100" is a different statement — it refers to the per-position retrieval degradation threshold *within* the heatmap rows, not the global N bound.

### Q2. Number of intervals

**26 intervals.** Confirmed verbatim from both HTML sources, exactly as previously reported.

### Q3. MCPBench subset

**Web-search subset only.** The main evaluation uses MCPBench's "web search subset." No other MCPBench domains (e.g., DB, file ops, mixed-tool tasks) were tested. Single-domain evaluation is one of the strongest external-validity limitations.

### Q4. Model panel

**Single base model: qwen-max-0125.** Confirmed across both HTML sources. Supporting models in the pipeline (not under test):
- Retriever encoder: lightweight Qwen-based embedder (k value never stated numerically — paper only says "top-k candidate MCPs")
- Evaluator: Deepseek-v3
- Judge: Llama-based verifier

No cross-model comparison. Claude, GPT, Gemini, and even open-weights alternatives like Llama-3-base are absent from the base-model panel.

### Q5. MCPBench server pool details

**Distractor pool: "over 4,400 publicly listed servers" from mcp.so**, sampled randomly per trial. Each stress-test trial = 1 ground-truth MCP + (N-1) randomly-drawn distractors from the 4,400 pool. No control for semantic similarity between distractor and ground-truth. No version pinning, no SHA, no description-hash. The pool is unreproducible as of any future date because mcp.so drifts.

The fact that the upper bound is **11,100 while the registry has only ~4,400 unique servers** implies they sample WITH REPLACEMENT at high N — i.e., the same distractor MCP appears multiple times in a single prompt. This is a methodological choice the paper does not flag. It means N > 4,400 is not "11,100 distinct tools" but "a prompt padded with 11,100 schema-slots, many duplicates." This is a defect we should call out: their high-N regime is closer to a padded-prompt-length condition than a true tool-count condition. Borderline-relevant to our padded-N=1 framing.

### Q6. Retriever methodology

- **Top-k value:** Not stated numerically. Paper only says "top-k candidate MCPs."
- **Embedding model:** Qwen-based lightweight encoder. No specific HF model card cited.
- **Pre/post filtering:** Neither described. Single-stage semantic retrieval; no rerank, no BM25 prefilter, no keyword overlap gate.
- **No retriever ablation.** No comparison to BM25, OpenAI text-embedding-3-large, Cohere rerank, or any other off-the-shelf encoder. The retriever-side ablation is empty.

### Q7. Per-server / per-tool diagnostics

**None.** They treat distractors as a homogeneous bag drawn at random from 4,400. They never ask "which specific added MCPs degrade performance most," never compute a per-server MPD-equivalent, never rank servers by their interference contribution. The closest thing in the paper is the Figure 3 heatmap which shows accuracy as a function of *position* (where the ground-truth tool sits in the prompt), not as a function of *which servers are present*. This is the exact diagnostic gap our MPD framework fills.

### Q8. Padded-length control

**No.** Confirmed across both HTML renderings: no condition holds prompt length constant while varying N, and no condition holds N constant while varying prompt length. Their stress-test design fundamentally conflates "long prompt" with "many tools." This is the methodological gap our **padded-N=1 control** closes — and the fact that their high-N regime samples with replacement (Q5) makes this gap even sharper than the skim noted.

### Q9. Headline numbers

**43.13% accuracy:** RAG-MCP on the MCPBench web-search subset, qwen-max-0125 as base model. Baselines:
- **Actual Match (keyword-based selection):** 18.20%
- **Blank Conditioning (no retrieval, raw N tools in prompt):** 13.62%

**"Tool-selection accuracy"** is defined operationally as: *"percentage of trials in which the model selected the ground-truth MCP."* It is a single-step binary oracle. They do not measure:
- Whether the selected tool was invoked with correct arguments
- Whether the end-to-end task succeeded after correct tool selection
- Latency or token cost decomposition at the per-N level (only aggregate prompt-token reduction 2,133.84 → 1,084)

**20 trials per baseline method**, not per N value. Figure 3's stress-test heatmap appears to be effectively single-trial-per-cell with no error bars, no CIs, no variance reporting. Major ABC R.10 violation.

### Q10. Top 3 methodology weaknesses we can defensibly cite

**(1) Single base model (qwen-max-0125 only).** Headline N-degradation curve has never been replicated on Claude, GPT, Gemini, or even Llama. "Does tool-crowding generalize across frontier models" is an open question their design cannot answer. *We answer it with a model × N matrix.* Evidence: HTML section on experimental setup, both renderings.

**(2) Distractor pool sampling with replacement at high N + no semantic-similarity control.** Registry has ~4,400 servers, sweep tops at 11,100, so >2.5x oversample. Beyond N=4,400 their "more tools" condition is really "more padding with duplicate schemas," collapsing the IV they claim to be measuring. Compounding this: distractors are drawn uniformly at random from the full registry with no control for embedding similarity to the ground-truth tool. Whether crowding is driven by N alone, by N × semantic-similarity, or by padded-length is undisturbed. *We control padded-N=1 and stratify distractors by similarity.* Evidence: pool size 4,400 + N upper bound 11,100, both verbatim from HTML.

**(3) No padded-length control, no per-server MPD, no statistical rigor in the stress test.** The stress-test Figure 3 reports a heatmap with no error bars, no CIs, ~1 trial per (N, position) cell. The 20-trial figure applies only to the main RAG-vs-baseline table, not the N-sweep. Their oracle is single-step tool selection, not end-to-end pass@1. They publish no per-N accuracy table. *We pre-register trial counts per N, report 95% CIs, decompose per-server MPD, and grade end-to-end code-retrieval pass@1.* Evidence: absence of CIs verified in both HTML renderings; "20 trials" appears only in the main results section, not the stress test.

### Source accessed

Two independent HTML renderings of the arXiv source, both giving identical text:
- `https://arxiv.org/html/2505.03275`
- `https://ar5iv.labs.arxiv.org/html/2505.03275`

Both render directly from arXiv's LaTeX source (not OCR of the PDF), which is why "11100" appears unambiguously without thousands-separator ambiguity. The PDF binary itself was not parsed, but HTML rendering of arXiv-hosted LaTeX is the canonical machine-readable representation and matches the PDF by construction. No GitHub repo for RAG-MCP appears in the abstract or HTML.

### What changes in the parent note above this section

Section "Did they vary N as an IV? YES" hedges "(the '11100' is likely an OCR rendering of '1,100' or similar — couldn't verify in the PDF binary)." That hedge is now **resolved: the upper bound is 11,100, not 1,100.** The qualitative claim survives unchanged; the precise number is now safe to cite in Friday DMs and the Sunday launch post.

Action item 6 in the original note ("Pull PDF locally and verify '11100' number before any public statement quotes the range") is **complete via HTML verification.** Honest framing for public statements: *"They swept N from 1 to 11,100 across 26 intervals on a 4,400-server registry — meaning above N=4,400 they were sampling with replacement, padding the prompt with duplicate schemas rather than adding new tools."*

## Related

[[abc-best-practices]] [[mcp-universe]] [[swe-bench-illusion]] [[coderag-bench]] [[swe-bench-pro]] [[../RESEARCH_DESIGN]] [[../CLAUDE]] [[../../strategy/week-1/2026-05-21]]
