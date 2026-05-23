---
doc: RAG / long-context distractor scaling landscape
researched: 2026-05-21 (Thu evening)
binding: input to RESEARCH_DESIGN.md novelty paragraph + padded-N=1 control justification
---

# RAG / Long-Context Distractor Scaling: Prior-Art Landscape

## Scope

What does the RAG / long-context / retrieval-pool-scaling literature say about how performance degrades as you add more candidates / distractors / documents to the pool? Specifically: curve shape, where it breaks for frontier LLMs, and whether anyone has isolated the **prompt-length effect** from the **distractor-count effect** with a padded control. This last question is critical for tool-crowding's padded-N=1 control: if the consensus is "it's all prompt-length once you control for it," the N-sweep finds nothing novel.

## Evidence Matrix

| Paper | arxiv / URL | Curve shape | Where it breaks | Isolated prompt-length from distractor-count? | Quote / figure |
|---|---|---|---|---|---|
| **Lost in the Middle** (Liu et al., 2023) | [2307.03172](https://arxiv.org/abs/2307.03172) | U-shape over **position**, not over pool size. Strong at ends, weak in middle. | Mid-context positions: ~20-30 point accuracy drop. At 20 docs, middle position falls to ~55%. | No. Varied position with fixed pool, not pool size. Did not pad. | "Performance is often highest when relevant information occurs at the beginning or end of the input context, and significantly degrades when models must access relevant information in the middle of long contexts." (abstract) |
| **RULER** (Hsieh et al., 2024) | [2404.06654](https://arxiv.org/abs/2404.06654) | Monotonic decline with context length; sharper on multi-key / multi-hop than vanilla NIAH. | Claimed 128K → effective: GPT-4 64K, Llama-3.1-70B 64K, Qwen2-72B 32K, Yi-34B 32K. Llama-3.1-70B drops 96.5% → 66.6% from 4K → 128K; Qwen2 96.9% → 53.7%. | **Partial.** Multi-key NIAH with 3 distractors vs full-haystack "entirely filled with distractor needles" — varies distractor count, but not under length-matched padding. | "Almost all models exhibit large performance drops as the context length increases." (Table 3, abstract) |
| **BABILong** (Kuratov et al., 2024) | [2406.10149](https://arxiv.org/abs/2406.10149) | Sharp decline with reasoning complexity; near-flat for trivial retrieval. | Models effectively use only **10-20% of context.** RAG hits ~60% on single-fact QA "independent of context length." | No. Varies reasoning complexity and length, not distractor count under padded length. | "Performance declines sharply with increased reasoning complexity"; "effectively utilize only 10-20% of the context." (abstract) |
| **NoLiMa** (Modarressi et al., ICML 2025) | [2502.05167](https://arxiv.org/abs/2502.05167) | Smooth, accelerating decline with length when literal lexical match is removed. | GPT-4o: 99.3 base → 69.7 at 32K. Claude 3.5 Sonnet: 87.6 → 29.8 at 32K. Llama 3.3 70B: 97.3 → 42.7. 10 of 12 models below 50% baseline at 32K. | No. Distractors held uniform across lengths; varies length, not N distractors at fixed length with padding. | Table 3 results above; "declines stem from the increased difficulty the attention mechanism faces in longer contexts when literal matches are absent." |
| **Chroma "Context Rot"** (Hong et al., 2025) | [trychroma.com/research/context-rot](https://www.trychroma.com/research/context-rot) | Non-uniform, accelerating degradation. Not linear. | 18 models tested. LongMemEval: significant gap between focused (~300 tokens) and full (~113K tokens) prompts; varies by family. | **Yes — closest prior art.** Three conditions: baseline (needle only), +1 distractor, +4 distractors, with needle and question held constant. Also varies input length independently. Claude shows higher abstention, GPT higher hallucination under distractors. | "Even a single distractor reduces performance relative to the baseline (needle only), and adding four distractors compounds this degradation further." "Impact of distractors and their non-uniformity amplifies as input length grows." Distractor count and length **interact**, not independent. |
| **"Context Length Alone Hurts… Despite Perfect Retrieval"** (2025) | [2510.05381](https://arxiv.org/abs/2510.05381) | Degradation persists even with perfect retrieval and zero distraction. | Llama-3.1-8B: 59-85% drop on Variable Summation depending on length; 20-24.2% on MMLU; 20-47.6% on HumanEval. Mistral-v0.3-7B: 27-34.2% on GSM8K. | **Yes — most rigorous isolation in literature.** Three controls: (a) natural-language padding, (b) **whitespace padding** (length without semantic distraction), (c) **attention-masked padding** (length without any token to attend to). | "The sheer length of the input alone can hurt LLM performance, independent of retrieval quality and without any distraction." Degradation range "13.9%–85%" across 5 LLMs with perfect retrieval. |
| **HELMET** (Yen et al., ICLR 2025) | [2410.02694](https://arxiv.org/abs/2410.02694) | Holistic; non-uniform across 7 task categories up to 128K. | Designed to add controllable lengths up to 128K; reports category-specific curves. | No explicit padded distractor-count vs length ablation. | "Controllable lengths up to 128K tokens, model-based evaluation for reliable metrics, and few-shot prompting." |
| **RAG-MCP** (Gan & Sun, 2025) | [2505.03275](https://arxiv.org/html/2505.03275v1) | Performance collapses without RAG retrieval as N tools grows; retrieval restores most accuracy. | Stress test sweeps **N=1 to 11,100 in 26 intervals.** With RAG: 43.13% accuracy at 1084 prompt tokens. Without (Actual Match): 18.20% at 1646 tokens. Blank: 13.62% at 2134 tokens. | **No.** N varies, but prompt tokens vary with N. No padded-N=1 control where prompt length is held at the N=large length but only 1 real tool is present. | "One ground-truth MCP and N−1 distractor MCPs drawn from registry of over 4,400 servers." 20 web-search tasks per N. |
| **MCP-Atlas** (2026) | [2602.00933](https://arxiv.org/html/2602.00933) | Distractor count varies per task (4-26 distractors, mean 11.1). No N-sweep curve. | 1000 tasks, 36 production servers, 220 tools. Per-task variation only. | **No.** No ablation holding ground-truth tools constant while varying N distractors. | "The remaining tools (mean 11.1 per task) are distractors drawn from semantically similar categories to test tool discovery under noise" (§3.2). |
| **MCPVerse** (2025) | [2508.16260](https://arxiv.org/html/2508.16260v1) | Divergent: Claude improves with more tools (57.77 → 61.01), GPT-4o drops 24.49 points Oracle → Standard, DeepSeek-V3 drops 11.97, Qwen3 drops 5.64. | 552 tools, 140K-token schemas; top model (Claude-4-Sonnet) only 57.77% Oracle. | **No.** Three fixed modes (Oracle / Standard / Max-Scale), no length-matched padded control. Conflates tool count, total tokens, and selection difficulty. | "The combined schemas of these tools exceed 140,000 tokens"; no whitespace / padded control. |

## Synthesis

### 1. Consensus curve shape for "performance vs distractor count"

There is **no single consensus**. Three patterns coexist in the literature:

- **U-shape over position** (Liu 2023): with fixed pool size, the position of the relevant item dominates; middle positions lose 20-30 points.
- **Monotonic, accelerating decline with length** (RULER, NoLiMa, Chroma): performance degrades smoothly but non-linearly as input grows; effective context for frontier models is roughly half their claimed window (GPT-4 effective 64K of claimed 128K).
- **Divergent across models with tool count** (MCPVerse): some models tolerate large tool pools, others collapse. Claude-4-Sonnet rises slightly Oracle → Standard; GPT-4o drops 24.49 points.

The shape is closer to a **non-uniform, model-dependent decline** than a clean cliff. There is no universal "X tokens / X distractors and it breaks" threshold.

### 2. Has anyone isolated prompt-length from distractor-count with a padded control?

**Yes, two papers, both in 2025.** This is the most consequential finding for tool-crowding.

- **arxiv 2510.05381** is the cleanest isolation in the literature. They run three conditions holding evidence and question constant: natural-language padding, whitespace padding, and attention-masked padding. They prove that length alone hurts even when all distraction is removed.
- **Chroma "Context Rot"** runs needle-only vs +1 distractor vs +4 distractors at varied lengths, allowing them to separate effects.

Neither did this for the **MCP / tool-selection setting.** Both work on text retrieval and reasoning tasks.

### 3. What did they find — length, distractors, or both?

**Both, and they interact.** 2510.05381 shows length alone causes 13.9%–85% degradation across 5 LLMs even with whitespace-only padding and perfect retrieval. Chroma confirms distractor impact is "not independent" of length: "the impact of distractors and their non-uniformity amplifies as input length grows." So padding to control for length is necessary, but it will not zero out the distractor effect; the cleanest experimental design needs **both axes.**

### 4. Implication for tool-crowding

- The padded-N=1 control is **methodologically novel for the MCP / tool-selection domain.** RAG-MCP varied N to 11,100 but never padded; MCPVerse compared 3 fixed modes; MCP-Atlas varied distractors per task but never ablated. None ran a length-matched padded baseline.
- The padded-N=1 control is **not novel as methodology in general.** Two 2025 papers (Chroma + 2510.05381) did the equivalent for text retrieval. Tool-crowding should cite both as the methodological precedent it is adapting, not invent.
- The genuine novelty claim narrows to: **first padded-N control for tool / MCP selection across N-sweep × multi-frontier-model × code-retrieval.** That is defensible, but only if framed as adapting a 2025 method (Chroma / 2510.05381) to a new domain.
- **Risk:** if tool-crowding finds "it's all prompt-length once padded," that result is consistent with 2510.05381 and reduces to a domain-replication paper, not a discovery. The interesting outcome is finding a **distractor-count-specific effect** that exceeds the length-only baseline, similar to Chroma's interaction finding.

### 5. Three findings tool-crowding can build on / cite

1. **Chroma "Context Rot"** — the +0 / +1 / +4 distractor design is the direct template for tool-crowding's N-sweep with padded control. Cite as the source of the experimental design, replicated in the tool-selection setting.
2. **arxiv 2510.05381** — whitespace and attention-masked padding as the gold-standard control for isolating length from distraction. Cite to justify why padded-N=1 specifically (not just N=1 baseline) is needed.
3. **RAG-MCP** — first paper to sweep N for MCP tools (1 to 11,100), demonstrates retrieval restores accuracy. Cite as the closest prior MCP work and explicitly state what it did not do (no padded control), to position tool-crowding as the methodological complement.

## Honest take

**Padded-N=1 as methodology is not novel.** Two 2025 papers already did it for text. **Padded-N=1 applied to multi-frontier MCP / tool-selection is novel,** and combining it with the code-retrieval domain narrows further. The defensible framing is: "tool-crowding ports the Chroma / 2510.05381 padded-control methodology into the MCP / agent-tools setting, where prior work (RAG-MCP, MCPVerse, MCP-Atlas) has varied N but always confounded N with prompt length." Drop any phrasing along the lines of "no one has isolated prompt-length from distractor count." Two papers have. Tool-crowding's contribution is the **domain transfer plus the multi-model code-retrieval scope,** not the control itself.

## Sources

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [BABILong (Kuratov et al., 2024)](https://arxiv.org/abs/2406.10149)
- [NoLiMa (Modarressi et al., ICML 2025)](https://arxiv.org/abs/2502.05167)
- [Chroma Context Rot research note](https://www.trychroma.com/research/context-rot)
- [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval (2510.05381)](https://arxiv.org/abs/2510.05381)
- [HELMET (Yen et al., ICLR 2025)](https://arxiv.org/abs/2410.02694)
- [RAG-MCP (Gan & Sun, 2505.03275)](https://arxiv.org/html/2505.03275v1)
- [MCP-Atlas (2602.00933)](https://arxiv.org/html/2602.00933)
- [MCPVerse (2508.16260)](https://arxiv.org/html/2508.16260v1)
