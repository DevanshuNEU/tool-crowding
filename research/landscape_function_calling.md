---
doc: Function-calling/tool-use benchmark landscape audit
researched: 2026-05-21 (Thu evening)
binding: input to RESEARCH_DESIGN.md §1 novelty rewrite
---

# Function-calling / tool-use benchmark landscape

Investigation question: which existing benchmarks vary "number of available tools" or "tool pool size" or "distractor function count" as an independent variable (≥3 sweep levels with per-N results)?

## Truthfulness note

- I read abstracts for all rows; HTML/PDF body where reachable. Several PDFs returned compressed/binary blobs and are marked "abstract only" or "HTML body" honestly.
- "Sweep" = ≥3 levels of tool count varied with per-N accuracy reported. Single 10-vs-100 toggles do NOT count.
- arxiv IDs cited verbatim from search results; I did not invent any.

## Matrix

| Benchmark | arxiv/URL | Year | Varies N (≥3 levels)? | What they vary | Single- or multi-model | Code-task or general | Notes |
|---|---|---|---|---|---|---|---|
| **LongFuncEval** | arxiv 2505.10570 | 2025-04 | **YES** | Tool-catalog token length: 8K, 16K, 32K, 65K, 120K tokens (~49, 102, 207, 417, 741 tools). 5 sweep levels. Also varies correct-tool insertion position α ∈ {0.1, 0.3, 0.5, 0.7, 0.9}. | Multi-model: Llama-3.1-70B/8B, Mistral-Large, Granite, ToolACE-8B, BitAgent-8B, DeepSeek-R1-Distill-Qwen-32B, QwQ-32B, GPT-4o-2024-11-20 | General (BFCL Simple/Multiple + ComplexFuncBench Booking.com REST APIs — flight, hotel, car, attractions). **NO code-retrieval.** | **HIGH OVERLAP WITH OUR THESIS.** Reports 7.59%–85.58% drop in tool-call accuracy as N grows. Distractors = random irrelevant functions ("not relevant to user query but randomly added to context to simulate a large tool catalog"). Includes position-of-correct-tool control. Does NOT include padded-context control disentangling context length from tool count (the very confound we're worried about). |
| **BFCL v1 / v2 / v3** | gorilla.cs.berkeley.edu; OpenReview 2GmDdhBdDk (ICML 2025) | 2024–25 | **NO** (categorical, not swept) | "Simple" (1 fn), "Multiple" (2–4 fns), "Parallel", "Parallel Multiple", "Irrelevance" (240), "Live Irrelevance" (882), "Missing Functions" (v3). | Multi-model (50+ on leaderboard) | General | Has irrelevant-function and missing-function categories but uses 2–4 distractors typically; **no systematic N-sweep**. The "average function choices per test is 3" per critique. Search hits referenced "1–8% accuracy loss from semantic distractors" but I could not extract this number from the OpenReview PDF (binary). Treat as unconfirmed until PDF read manually. |
| **RoTBench** | arxiv 2401.08326 (EMNLP 2024) | 2024 | NO (5 noise levels, but noise = name/param corruption, not tool count) | Noise applied to tool names + parameters: Clean → Slight (insert/omit/substitute chars) → Medium (reverse/nonsense) → Heavy (shuffle names + add params) → Union | Multi-model | General | Multi-level structure looks N-sweep-like but is orthogonal to tool count. Useful as method-precedent for "graduated difficulty" framing, NOT prior art on N. |
| **ToolMATH** | arxiv 2602.21265 | 2026-02 (v2 May 2026) | Likely YES per search hits, but I could NOT extract exact sweep levels from PDF (binary blob). Confirmed it tests "robustness against distractors" + "logical-hop measure" + "tool-catalog conditions." | Multi-model (Llama 3, Qwen 2.5, Yi, Phi-3, Mistral 7B per search; not verified) | Math (MATH dataset converted to Python tools) | Tool catalog ~12K tools total (ToolMATH-Hard: 626 tools). Authors: Choi, Lee, Lee, Lee (Jay-Yoon). arxiv only, no venue stated. **Needs full-text read before claiming as pre-empt.** |
| **τ-bench / τ²-bench** | arxiv 2406.12045 (Sierra) | 2024 | NO | Domain (retail vs airline); consistency across runs; policy compliance. Fixed tool set per domain. | Multi-model | General customer-service | Not N-sweep — measures consistency of completion at fixed tool count. |
| **ToolBench / ToolLLM** | arxiv 2307.16789 | 2023 | NO (abstract only — PDF binary) | Uses neural API retriever to recommend APIs; total pool 16K+ APIs but per-task retrieved subset is the unit, not the manipulated variable. | Multi-model | General (RapidAPI) | Predecessor to StableToolBench. |
| **StableToolBench** | arxiv 2403.07714 | 2024 | NO | Stability of API evaluation (caching, simulators). | Multi-model | General | Solves ToolBench's API-flakiness, not an N-sweep paper. |
| **ToolHop** | arxiv 2501.02506 (ACL 2025) | 2025-01 | NO (multi-hop depth, not tool count) | Hop depth (sequence length of nested calls); 995 queries, 3,912 tools fixed. Avg hop length 4.36. | Multi-model: 14 LLMs across 5 families (LLaMA3.1, Qwen2.5, Gemini1.5, Claude3.5, GPT). | General math/composition | The IV is multi-hop depth, not pool size. |
| **GTA** | arxiv 2407.08713 (NeurIPS 2024) | 2024 | NO (fixed 14-tool inventory) | Number of tools *required per task*: 1 (17), 2 (147), 3 (50), 4 (15). Pool is fixed at 14. | Multi-model | General multimodal | Variation is in task complexity, not available-tool count. |
| **Gorilla / APIBench** | arxiv 2305.15334 | 2023 | NO (abstract only) | HuggingFace + TorchHub + TensorHub API selection accuracy. | Single-fine-tune focus (Gorilla-7B); evaluated against GPT-4, Claude. | Code/API (closest to our domain — but no N-sweep) | The original "retrieve from API catalog" paper. |
| **AgentBench** | arxiv 2308.03688 | 2023 | NO (abstract only) | 8 distinct environments. | Multi-model | General | Environment-axis, not tool-count axis. |
| **MetaTool** | arxiv 2310.03128 | 2023 | NO (abstract only — could not confirm sweep) | Tool-use-awareness + tool-selection across 4 subtasks. | Multi-model | General | Search returned no evidence of N-sweep. |
| **API-Bank** | arxiv 2304.08244 | 2023 | NO (73 APIs eval set, 2,138 training) | Test cases evaluate single-API selection from full set. | Multi-model | General | No reported sweep. |
| **T-Eval** | arxiv 2312.14033 | 2023 | NO (abstract only) | 6 capability sub-dimensions of tool use. | Multi-model | General | Capability decomposition, not pool-size sweep. |
| **ToolEyes** | arxiv 2401.00741 (COLING 2025) | 2024 | NO | 7 scenarios × 5 capability dimensions × 568-tool library (fixed). | 10 LLMs (open + tool-tuned + closed) | General | No N-sweep. |
| **ToolACE** | arxiv 2409.00920 | 2024 | NO (abstract only) | Pool of 26,507 APIs — but the contribution is *synthesis*, not pool-size effect. | Self-instruction-tuned focus | General | Training-data paper, not evaluation-design paper. |
| **NESTFUL** | arxiv 2409.03797 (EMNLP 2025) | 2024 | NO (sequence-length axis) | Nested-API-call sequence length (avg 4.36). | Multi-model | General (MathQA-based) | Variation is nesting depth, not pool size. |
| **ComplexFuncBench** | arxiv 2501.10132 | 2025-01 | NO (5 challenge axes, not N) | Multi-step / constrained / param-reasoning / long-param / 128K long-context. | Multi-model | General (Booking.com) | Becomes a *building block* of LongFuncEval. |
| **MCP-RADAR** | arxiv 2505.16700 | 2025-05 | NO | 5 dimensions: answer accuracy, tool selection efficiency, compute efficiency, param accuracy, exec speed. Fixed 507 tasks × 6 domains. | Multi-model | General (incl. SWE, math) | First MCP-named benchmark but NOT a tool-count sweep. |
| **MCPToolBench++** | arxiv 2508.07575 | 2025-08 | NO | Built on 4K+ MCP servers across 40+ categories as a *corpus*; not as a swept IV. | Multi-model: Claude 4, Qwen 3, K2-Instruct, Gemini 2.5, O3/O4-mini, GPT-4 | General | Largest-scale MCP benchmark but the 4K servers are scope, not sweep. |
| **ToolEmu** | arxiv 2309.15817 (ICLR 2024 spotlight) | 2023 | NO | 36 toolkits × 144 test cases × 9 risk categories. | LM-simulated execution | General safety | Safety/risk evaluation, not capacity. |
| **ToolRet** (Retrieval Models Aren't Tool-Savvy) | arxiv 2503.01763 | 2025-03 | NO | Tool-retrieval IR benchmark on fixed 43K-tool corpus; 7.6K retrieval tasks. | Multi-model retrievers | General | Tests retriever quality on fixed N; motivates retrieval but doesn't sweep pool size. |
| **ToolHaystack** | arxiv 2505.23662 | 2025-05 | NO (haystack-session sweep, but tool count is collateral) | Number of haystack (distractor) sessions 1→20; needle position; scenario type CR/IS/MC. | Multi-model | General long-term interaction | "Number of haystack sessions" sweep is the closest cousin to N-sweep among everything not-LongFuncEval; the sessions contain tools but the IV is sessions, not tool count per se. Figure 5 shows monotone degradation with session count. |
| **AgentTuning** | (training paper, not eval) | 2023 | n/a | — | — | — | Not a benchmark. |

## Synthesis (≤400 words)

### 1. Of ~22 benchmarks checked, how many actually sweep N?

**Exactly one with confidence: LongFuncEval (arxiv 2505.10570).** It sweeps 5 levels of tool-catalog size (8K→120K tokens, ≈49→741 tools) across 9 models on BFCL + ComplexFuncBench, and reports per-N degradation of 7.59%–85.58%.

**One probable, unconfirmed: ToolMATH (arxiv 2602.21265).** Search hits describe "controllable tool-catalog conditions" + distractor robustness — but the PDF was unreadable, so I cannot verify ≥3 levels with per-N results. Needs manual read.

**One adjacent cousin: ToolHaystack (arxiv 2505.23662)** sweeps "haystack sessions" 1→20; the tool count grows incidentally as sessions accumulate, but sessions are the IV, not tool count.

**BFCL's irrelevance + missing-function categories** are binary/categorical, not sweeps.

### 2. Closest in methodology to tool-crowding?

**LongFuncEval, by a wide margin.** Same dependent variable (tool-call accuracy), same kind of IV (count of available tools scaled monotonically), same multi-frontier model panel. Differences: (a) they vary by *token budget* not literal N, (b) no code-retrieval domain, (c) no padded-context-only control to disentangle context-length vs tool-count effects, (d) no MCP-server framing.

### 3. Citeable prior-art findings

- LongFuncEval: 7%–85% accuracy drop as tools grow from ~49 to ~741.
- LongFuncEval: GPT-4o is the most resilient (12.88% degradation on simple); open-weight degrades much harder (Llama-3.1-70B: 69.61%).
- BFCL: distinct "irrelevance" (240) and "live_irrelevance" (882) splits — useful baseline for refusal behavior, but the "1–8% accuracy loss" claim from one search hit I could not source-verify from the OpenReview PDF.
- ToolHaystack Figure 5: monotone degradation from 1→20 haystack sessions across all models.

### 4. Honest take on the gap

**The "N-sweep" pillar is no longer novel after LongFuncEval.** The remaining defensible novelty pillars for tool-crowding:

1. **Code-retrieval domain specifically** — LongFuncEval uses Booking.com REST APIs; no code-retrieval benchmark has done this sweep. Real.
2. **MCP-server framing** (concurrent install semantics, not just "long catalog") — no one has done this. Real but partly cosmetic; the underlying mechanism is the same context-pollution.
3. **Padded-context control** disentangling tool-description tokens from raw context-length effects — LongFuncEval explicitly does NOT do this. **This is the strongest remaining methodological wedge.**
4. **Frontier-model panel including Claude 4 / GPT-5-class models** — LongFuncEval's only closed model was GPT-4o-2024-11-20; the frontier has moved.

Pillar #3 (padded-context control) is the cleanest "they didn't do this and it matters" pitch.

### 5. Top 3 must-read before novelty paragraph

1. **LongFuncEval (arxiv 2505.10570)** — full paper, especially Table 1 (per-model degradation %), Section on insertion fraction α, and any discussion of context-length confounds. **Read first.**
2. **ToolMATH (arxiv 2602.21265)** — verify whether their "controllable tool-catalog conditions" constitutes a real N-sweep or just a few configurations. If sweep, becomes pre-empt #2.
3. **RAG-MCP (arxiv 2505.03275)** — already known but re-anchor: their 1→11,100 sweep (registry ~4,400 servers, so above N=4,400 they sample with replacement) is the precedent for N-as-IV in MCP-flavored work, even though only qwen-max.

If LongFuncEval + RAG-MCP + ToolMATH together cover (a) multi-model N-sweep, (b) MCP framing, and (c) controllable distractor conditions, the only clean tool-crowding contribution left is **code-retrieval domain + padded-context control + 2026-era frontier models**. That is a "third paper in this thread," not a "first."

Related: [[RESEARCH_DESIGN]] [[../notes/]] [[../CLAUDE]]
