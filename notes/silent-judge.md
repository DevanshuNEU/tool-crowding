---
paper: "The Silent Judge: Unacknowledged Shortcut Bias in LLM-as-a-Judge"
arxiv: 2509.26072
arxiv_url: https://arxiv.org/abs/2509.26072
read_date: 2026-05-21
read_depth: skim
verdict: neutral
---

# The Silent Judge (Marioriyad, Rohban, Soleymani Baghshah; Sep 2025)

Authors: Arash Marioriyad, Mohammad Hossein Rohban, Mahdieh Soleymani Baghshah. Posted arXiv 2509.26072 (Sep 2025). Also at NeurIPS 2025 (San Diego virtual) and OpenReview (id=6j8jAaDyUG).

## What they measured

Whether LLM-as-a-judge systems (GPT-4o, Gemini-2.5-Flash) base verdicts on response quality alone, and whether their written justifications faithfully acknowledge the cues actually driving their decisions. Two pairwise-judgment datasets: ELI5 (long-form QA) and LitBench (creative writing), 100 pairwise tasks per dataset. They inject two kinds of superficial cues into the prompt:

- **Provenance cues** (4 levels): HUMAN, LLM, UNKNOWN, EXPERT
- **Recency cues** (2 levels): OLD (1950) vs NEW (2025)

Outcomes: verdict-shift rate (does the cue flip the winner?) and cue-acknowledgment rate (does the written justification mention the cue?).

Headline findings:
- Strong recency bias: both judges systematically prefer NEW over OLD.
- Provenance hierarchy: Expert > Human > LLM > Unknown.
- Cue acknowledgment is rare; justifications rationalize via content qualities instead of citing the injected cue. "Silent" in the title = silent about the actual cause of the verdict.

## Did they vary N as an IV?

**No.** N (number of concurrent tools / retrieval sources / MCP servers) is not in scope. The paper is about LLM-as-judge faithfulness, not about tool-using agents. The closest analogous variable they sweep is the cue category (4 provenance × 2 recency), not source count.

## Methodology choices that stood out

- **100 pairwise items per dataset.** Small but adequate for proportion-shift tests; they would not detect single-digit pp effects without trial repetition (not clear from abstract whether they repeated).
- **Controlled cue injection in the prompt itself**, with the response content held constant. This is a clean A/B: only the metadata label changes. Strong internal validity.
- **Two outcome axes (verdict shift + acknowledgment) reported separately.** The acknowledgment axis is the novel piece; most prior LLM-judge bias work stops at verdict shifts.
- Only 2 judge models tested. Generalization claim is narrow.

## What to steal

- **Two-axis reporting**: outcome change (did the verdict flip?) plus introspection faithfulness (did the model self-report the cause?). Tool-crowding can borrow the structure: report not just pass@1 degradation as N grows, but also whether the agent's own trace mentions tool-selection conflict / context pressure / wrong-server-picked. A "silent failure" rate.
- **Cue-acknowledgment as a metric** is a usable construct. If our agent fails at N=20 and the trace says "I couldn't find the right tool," that is acknowledged failure. If it says "the task was unclear," that is silent failure caused by tool crowding. Worth a small ablation.
- The clean cue-injection design (hold content constant, vary one label) is a template for our padded-N=1 control: hold the active server set constant, vary only the distractor descriptions.

## What they didn't measure

- No tool-using agents, no retrieval, no MCP, no multi-source setup. This is text-judgment only.
- No N-variance, no scaling curve.
- Only 2 judge models; no open-weight models tested.
- Single-trial reporting implied (the abstract does not mention CIs or n-trials per cell).
- No human inter-annotator agreement baseline for the same pairs.

## One open question

Does the silent-failure pattern (model rationalizes a cue-driven verdict in content terms) transfer to tool-using agents? When a Claude-4 agent at N=20 servers fails to select the right tool, does its trace honestly say "too many tools" or does it rationalize as "the user query was ambiguous"? If the latter, tool-crowding's qualitative analysis layer becomes much more important; we cannot trust agent self-reports about why they failed.

## Compatibility with our gap claim: neutral

This paper is not about tool crowding, retrieval interference, or N-as-IV. It does not support or contradict the "nobody varies N" claim directly. It lives in an adjacent slot (LLM-as-judge eval methodology) and is useful only as:

1. A methodology template (two-axis reporting, controlled injection).
2. A caution about agent self-report: traces are unreliable evidence about failure causes. Relevant if our oracle includes any LLM-judge step.
3. A weak prior that frontier LLMs do not introspect causally about prompt-level interventions, which we should expect to extend to multi-tool prompt interventions.

Not a must-cite. Optional citation in the methodology section if we use any LLM-as-judge in our evaluator stack, or in a "limitations of agent self-report traces" footnote.

## Related

[[mcp-universe]] [[../RESEARCH_DESIGN]]
