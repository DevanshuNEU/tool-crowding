---
title: PADDING_STRATEGY.md — padded-N=1 control padding strategy (binding)
status: v1 (locked 2026-05-22 Fri AM)
binds: v1.2 SPEC item (b) — "specify padded-N=1 control padding strategy" per FOUNDATION.md §6 item 2
supersedes: inline 5-bullet draft in PILOT_V0.md (Thu PM 2026-05-21). PILOT_V0.md now references this doc.
related_docs: FOUNDATION.md §1.0 F1 (falsification), REPRODUCIBILITY.md (cell_seed mechanism), PILOT_V0.md (Sat pilot gate), harness/SPEC.md (integration), notes/ragmcp-100.md (the failure mode this avoids)
---

# Padded-N=1 control: padding strategy

## 1. Purpose and what this isolates

The padded-N=1 control answers a falsification question pre-registered in FOUNDATION.md §1.0 F1: *Does discrimination interference exist independent of prompt length?* If a padded-N=1 prompt — long like the unpadded-N=20 prompt, but with only one real, selectable, task-relevant tool — degrades pass@1 to the same level as unpadded-N=20, the construct collapses to capacity (the long-prompt confound). If padded-N=1 stays at the unpadded-N=1 baseline while unpadded-N=20 drops, discrimination interference is the real mechanism.

This spec defines what "padded" means concretely: which filler goes in, how it's generated, how token length is matched, how the harness handles it.

The spec is binding for the Saturday 2026-05-23 pilot, the v1 full sweep, and the Monday 2026-05-25 public launch. Changes after lock require a v1.x bump in FOUNDATION.md §6.

## 2. Padding mechanism: neutral-tool-shaped descriptions

The padded-N=1 prompt contains:

1. **One real primary tool** for the query (e.g., for a code-retrieval query, OCI / GitHub MCP / Git MCP / Aider MCP / Fetch MCP per SERVER_POOL.md, whichever is being tested).
2. **K filler entries** drawn from a fake-tool corpus (defined below), where K is chosen by the matching protocol in §4.
3. **No other real distractors.** This is what makes the control "N=1" semantically.

The filler entries are not whitespace, not attention-masked tokens, and not Lorem ipsum. They are **JSON tool definitions that match the structural shape of real MCP tool definitions**: a `name` string, a `description` string, and a JSON-Schema-valid `input_schema` object. They are presented to the model in the same tool-list manifest position as real tools.

### Why not whitespace or attention-mask padding (Chroma / Liu et al. approach)

Two reasons. First, tool definitions reach the model through the structured tool-use channel (Anthropic's `tools` parameter, OpenAI's `tools`, Gemini's `function_declarations`), not through the text prompt. Whitespace padding inside a tool description is structurally different from text-prompt whitespace; it might be elided by the model's tool-listing parser before attention sees it. Second, the construct (FOUNDATION.md §1.0) is *discrimination interference*: degradation attributable to other concurrently-installed tools whose descriptions compete with the correct tool. The natural null condition is "tool-shaped content that does not compete," not "no content at all." Whitespace tests a different and weaker null.

Chroma Context Rot and Liu et al. (arXiv 2510.05381) ran their padded controls on text-retrieval tasks (FOUNDATION.md §2a). Their methodology is cited as the source of the padded-N=1 concept. We port the concept to the tool-context regime and adapt the filler shape to match.

### Why not Lorem ipsum or random strings

Lorem ipsum and random strings break the JSON-Schema validation that providers (Anthropic, OpenAI, Gemini) apply to the `tools` parameter at request time. The request would be rejected before reaching the model. Even if it were not rejected, the model's tool-selection head is trained on schema-shaped input; introducing non-schema-shaped tokens in the tool slot is out-of-distribution and would confound the measurement with input-distribution effects.

### Why not real-but-orthogonal MCP servers

Real distractors (e.g., Notion MCP, Slack MCP from SERVER_POOL.md) cannot be filler in padded-N=1 because they are themselves selectable: the agent could pick them, and they would count as "other tools competing for selection." That is the unpadded-N=K condition, not padded-N=1. The whole point of padding is to add tool-shaped *content* without adding *selectable competitors*.

The mechanism that makes filler entries non-selectable: filler entries are advertised in the tool list but not backed by any running MCP server process. If the agent tries to call one, the MCP layer returns a `MethodNotFound` error (per JSON-RPC 2.0 §5.1) within milliseconds. The agent treats this as a tool fault and continues. The trial is flagged with `fake_tool_invoked: true` and the failure mode is logged but the trial is not discarded — accidentally selecting a filler IS measurement signal (it means the filler successfully passed as plausible).

## 3. The fake-tool corpus

A versioned, content-hashed corpus of filler entries. Lives at `design/fake_tool_corpus.jsonl`. One row per entry. Schema:

```json
{
  "entry_id": "ftc_001",
  "tool_name": "...",
  "description": "...",
  "input_schema": { "type": "object", "properties": {...}, "required": [...] },
  "domain_tag": "scheduling | finance | health | hr | weather | travel | ..." 
}
```

### Requirements on the corpus

| Requirement | Why |
|---|---|
| **At least 50 entries** | Need enough variety to support length matching across the unpadded-N=20 token-count distribution without exhausting the corpus. The v1 unpadded-N=20 prompts are expected to total ~2-3k tokens of tool definitions (per SERVER_POOL.md TBD measurements); a 50-entry corpus with descriptions ranging from ~40 to ~200 tokens covers this range with margin. |
| **Domain-agnostic, orthogonal to code-retrieval** | Descriptions must not mention code, repositories, files, functions, search, retrieval, indexing, or any term that semantically overlaps with the primary task. The construct measures interference from *competing* tools; filler entries must not compete. |
| **Plausible-sounding names** | Names like "TaskScheduler", "ExpenseTracker", "WeatherLookup". Not "HelperA" or "ToolStub42" — obviously-placeholder names signal "fake" to the model and may bias selection. |
| **Valid JSON Schema** | `input_schema` must validate against JSON Schema draft 2020-12. Providers reject malformed schemas. |
| **No real MCP server backing them** | A filler `tool_name` MUST NOT collide with any tool exposed by any server in SERVER_POOL.md. Pre-flight check in the harness. |
| **Per-entry token count cached** | Each entry stores its token count under each model's tokenizer used in the sweep. Computed once at corpus-build time, frozen in the corpus file. |

### Corpus build provenance

Two acceptable generation methods. The chosen method is documented in the corpus file header.

**A. Hand-curated (preferred for paper).** Devanshu writes 50 entries directly. Time cost: ~2 hours. Most defensible to reviewers (no LLM-generated semantics that might leak code-domain terms). Auditable as a single artifact.

**B. LLM-generated with QA gate (acceptable for pilot).** Generated via a documented prompt (e.g., "Generate 50 MCP tool definitions for orthogonal domains: scheduling, finance, weather, HR, fitness, travel, etc. Each must have a plausible name, a 1-2 sentence description, and a valid JSON Schema. No mention of code, files, repos, search, or retrieval."). Generation uses `temperature=0` and a documented seed. Each entry then passes through a QA gate:

- Code-domain leakage check: regex against `{code, function, file, repo, search, retriev, index, snippet, query, AST, syntax, parse, compile, class, method, variable, debug}` (case-insensitive). Any hit → reject the entry.
- Schema validity check: JSON Schema draft 2020-12 validator passes.
- Name collision check: not present in any server's tool list.

If method B is used, the generation prompt + seed + LLM model + rejection log are committed alongside the corpus.

### Corpus lock and hashing

The corpus file `design/fake_tool_corpus.jsonl` is hashed (SHA-256 of canonicalized JSONL) into the `h_pool` artifact of REPRODUCIBILITY.md §1. Any mutation to the corpus forces a new `run_id`. There is no "corpus drift" allowed mid-collection.

## 4. Token-length matching protocol

For each padded-N=1 trial, the harness must match the unpadded-N=20 condition's token count for the same `(query_id, ordering_seed)` pair within **±10%**. This is the Sat AM gate threshold from PILOT_V0.md §"Sat AM go/no-go gate" item 2.

### Algorithm

```python
def select_padding(query_id, ordering_seed, model, run_id, fake_corpus, server_pool):
    # 1. Compute the target: tokens in the unpadded-N=20 prompt for this cell.
    target_tokens = compute_unpadded_tokens(
        query_id=query_id,
        ordering_seed=ordering_seed,
        model=model,
        N=20,
        server_pool=server_pool,
    )
    # ^ This uses the SAME deterministic distractor selection as the real unpadded-N=20
    # trial would produce (per REPRODUCIBILITY.md §2 cell_seed), then sums tool-definition
    # tokens via the model's tokenizer.

    # 2. Determine the primary tool's tokens (already present in padded-N=1).
    primary_tool = primary_for_query(query_id, server_pool)
    primary_tokens = primary_tool.description_tokens[model]

    # 3. The filler budget is the gap.
    filler_budget = target_tokens - primary_tokens

    # 4. Deterministic filler selection via cell_seed-derived RNG.
    rng = SeededRNG(sha256(run_id || model || query_id || ordering_seed || "padded_filler"))

    # 5. Greedy length-matched selection. No duplicates within a trial.
    #    Match within ±10% of filler_budget. Stop when within band or corpus exhausted.
    selected = greedy_select(
        corpus=fake_corpus,
        target=filler_budget,
        tolerance=0.10,
        rng=rng,
        no_duplicates=True,
    )

    # 6. Verify the final total is within ±10% of target_tokens.
    actual_total = primary_tokens + sum(e.description_tokens[model] for e in selected)
    assert 0.90 * target_tokens <= actual_total <= 1.10 * target_tokens, \
        f"Padding budget out of band: target={target_tokens}, actual={actual_total}"

    return selected
```

### Edge cases

| Case | Detection | Behavior |
|---|---|---|
| Filler budget is negative (primary tool already longer than unpadded-N=20 prompt) | `filler_budget < 0` | Skip padding. Use bare N=1 condition. Flag trial with `padding_skipped: budget_negative`. This is rare and should not occur for v1 primary tools; if it does, the primary tool's description is anomalously long and this is the right behavior. |
| Corpus cannot pack to within ±10% | `actual_total` outside band after corpus exhaustion | Halt the run. The corpus is undersized for this query. Either expand the corpus or document the exclusion. Do NOT proceed with out-of-band padding. |
| Greedy gets stuck above target | Greedy heuristic overshoots even when packing is feasible | Re-try with a different rng-derived ordering of corpus entries (re-seed with `cell_seed || "padded_filler_retry"`). Up to 3 retries. Then halt as in case above. |
| Model tokenizer unavailable | `model.count_tokens()` returns None or errors | Halt the run. Tokenizer-aware matching is mandatory for cross-model comparisons (each model has its own tokenizer per harness/SPEC.md Section 5 rule 2 and FOUNDATION.md §4.1 T.6). |

### Tokenizer policy

Each model in the sweep uses its own tokenizer to compute `description_tokens[model]`:

- **Claude (Opus 4.7, Sonnet 4.6, Haiku 4.5)**: Anthropic's `count_tokens` API or the equivalent in `anthropic` Python SDK.
- **GPT-5-class**: `tiktoken` with the appropriate encoding for the snapshot.
- **Gemini 2.5-class**: Google's tokenizer via `google-generativeai` SDK.

Each `(corpus_entry, model)` pair has a cached token count. The cache is committed to `design/fake_tool_corpus.jsonl` itself, under the `description_tokens` field as a map `{model_id: count}`. Re-computation triggers a corpus version bump.

## 5. Determinism and integration with cell_seed

Per REPRODUCIBILITY.md §2, every random choice in the harness derives from `cell_seed = sha256(run_id || model || N || query_id || ordering_id)`. Padding is no exception. The seed for filler selection is:

```
padding_seed = sha256(cell_seed || "padded_filler")
```

The `"padded_filler"` domain separator ensures padding RNG does not collide with other RNG uses in the same cell (e.g., distractor selection for unpadded conditions). Same `(run_id, model, query_id, ordering_id)` produces the same padded-N=1 filler set, byte-for-byte.

## 6. Schema validity and accidental-call behavior

Each filler entry's `input_schema` MUST pass JSON Schema draft 2020-12 validation. The harness validates at corpus-load time and refuses to start if any entry is malformed.

If the model invokes a filler tool during a trial:

1. The MCP layer returns `{"jsonrpc": "2.0", "error": {"code": -32601, "message": "MethodNotFound"}, "id": ...}` (JSON-RPC 2.0 §5.1, mapping to MCP's standard error envelope).
2. The trial logs the call under `tool_calls` with `was_hallucinated: false` (the tool IS in the tool list) and `error: "fake-tool-invoked"`.
3. The trial sets a top-level flag `fake_tool_invoked: true` (added in Trial schema v1.1 — see harness/SPEC.md amendment).
4. The trial CONTINUES. The agent receives the error and may retry, pivot to the primary tool, or give up. The trial's final outcome is graded by the oracle as usual.
5. If `fake_tool_invoked` is true and the trial passes, the trial is still counted as a pass (the agent recovered). If `fake_tool_invoked` is true and the trial fails, the failure mode is tagged `fake_tool_invoked` in addition to whatever else fired.

The pilot's go/no-go gate (PILOT_V0.md §"Sat AM go/no-go gate") includes a check that the fake-tool-invocation rate in padded-N=1 trials is < 10%. Higher than that means the fillers are not behaving as neutral, and the construct's validity is compromised.

## 7. What this does NOT cover

- **Primary tool selection logic.** The primary tool for each query is fixed per SERVER_POOL.md primary list (OCI, GitHub MCP, Git MCP, Aider MCP, Fetch MCP). Which one is primary for a given query depends on the query; that mapping is part of `tasks/v1/queries.jsonl`.
- **Unpadded-N=K distractor selection.** Covered by REPRODUCIBILITY.md §2.
- **Padded-N=K for K > 1.** Not in scope for v1. Only padded-N=1 is the control.
- **Cross-trial filler reuse.** Within a single padded-N=1 trial, no duplicates. Across trials with different `cell_seed`s, the same filler entry may appear repeatedly; this is expected and not a confound (filler is not selectable competition).

## 8. How this binds the harness

Five implementation gates before any padded-N=1 trial runs:

1. **`design/fake_tool_corpus.jsonl` exists, is at least 50 entries, passes all corpus requirements in §3.** Hashed into `h_pool` per REPRODUCIBILITY.md §1.
2. **`harness/padding.py`** implements the algorithm in §4 deterministically. Test: same inputs produce same outputs across re-runs.
3. **`harness/agent.py`** registers fillers in the tool list passed to the model, ensures they are not backed by real server processes, and handles `MethodNotFound` errors per §6.
4. **Trial schema v1.1** adds the `fake_tool_invoked: bool` field and a new error_type `"fake_tool_invoked"`. Schema bump per harness/SPEC.md Section 4 schema evolution rules.
5. **Sat AM pilot gate** (PILOT_V0.md): the padded-N=1 condition's total token count is within ±10% of the matching unpadded-N=20 token count on at least 95% of the gate-test trials. Below that, fix the corpus or matching algorithm before kicking off the 144-trial main pilot.

## 9. Open methodology questions (resolve during pilot, document in launch post)

1. **Does the model recognize fillers as fake?** Sanity-check on the pilot: compute the rate at which the model selects fillers vs. real tools. If fillers are selected at < 1% the rate of the primary tool, they are functioning as designed. If higher, the fillers are too plausible (paradoxically a problem — they ARE competing, not just padding). Re-tune corpus or rotate to method A (hand-curated).
2. **Does ±10% token matching introduce a confound?** Empirical check on the pilot: regress padded-N=1 pass@1 on the (padded - unpadded) token gap. If the slope is statistically distinguishable from zero, the matching tolerance is too loose; tighten to ±5% and re-pad.
3. **Does the filler's domain tag matter?** Stratify padded-N=1 pass@1 by the dominant domain_tag in the filler set. If pass@1 varies across domains, the "orthogonal" assumption is violated for some domains; document and remove those domains from the corpus.

These three questions become a supplementary subsection in the v1 launch post. Their results are not headline numbers but they are non-optional disclosure.

## 10. Why this scope, not more

The padded-N=1 control is the load-bearing falsification arm for FOUNDATION.md §1.0 F1. It does not have to be elegant; it has to be defensible. The design above is the minimum spec that (a) tests the right null, (b) is reproducible byte-for-byte, (c) survives the obvious reviewer attacks ("how do you know the filler is neutral?" — §9 question 1; "what if the model sees fillers as obviously fake?" — §3 plausibility requirement; "your match is loose" — §9 question 2 + §4 halt-on-out-of-band).

A more elegant design (e.g., learn an embedding-space neutral region, or generate fillers per-trial from a length-matched gaussian) buys precision at the cost of reviewer-defensibility. We are not optimizing for elegance; we are optimizing for survival of peer review and reproducibility audit.

## Related

[[FOUNDATION]] [[REPRODUCIBILITY]] [[PILOT_V0]] [[../harness/SPEC]] [[SERVER_POOL]] [[PRE_REGISTRATION]] [[../notes/ragmcp-100]] [[../notes/abc-best-practices]] [[../research/landscape_rag_distractor]]
