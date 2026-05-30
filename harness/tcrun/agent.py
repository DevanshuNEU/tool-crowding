"""Anthropic API + MCP tool-use loop per trial.

Implements SPEC.md §3 AgentHarness + §4 Trial construction + §5 rule 4
(per-trial nonce) + §7 failure modes F7-F13/F18 + PADDING_STRATEGY.md §6
(filler/MethodNotFound handling).

Per-trial guarantees:
    * A 32-byte hex nonce embedded in the system prompt (cache-cold per M5).
    * F18 halts the entire run if `usage.cache_read_input_tokens > 0` OR
      `usage.cache_creation_input_tokens > 0` on any response.
    * All API errors flow through `retry.run_with_retry` (M8 + F5/F6/F7).
    * `MethodNotFound` from a filler tool sets `fake_tool_invoked=True`
      without halting; the trial continues per PADDING_STRATEGY.md §6.
    * For `is_padded_n1` trials, the tool list is built by calling
      `padding.select_padding(...)` and merging the resulting fillers
      with the single primary tool.

LOC budget per SPEC.md §11: ~380 LOC.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import DEFAULT_TOOL_RESULT_CHAR_CAP
from .embedder import Embedder, make_embedder, rank_tools_by_query
from .env import EnvFingerprint
from .results import (
    CURRENT_SCHEMA_VERSION,
    EnvFingerprintRef,
    SamplingParams,
    ServerEntry,
    ToolCall,
    Trial,
)
from .retry import APIFault, ServerFault

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Halt-the-run exception (F18)
# ---------------------------------------------------------------------------


class CacheLeakHalt(RuntimeError):
    """F18: cache_read or cache_creation > 0 despite per-trial nonce. HALT."""


# ---------------------------------------------------------------------------
# Inputs / context dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FakeTool:
    """A padded-N=1 filler entry per PADDING_STRATEGY.md §3.

    This is the canonical FakeTool. `padding.select_padding` constructs and
    returns instances of this type; the agent advertises them in the tool
    list and short-circuits MethodNotFound on invocation (PADDING_STRATEGY.md
    §6). `description_tokens` is the cl100k_base count from the corpus
    (`design/fake_tool_corpus.jsonl`); per-model retokenization is v2.
    """

    tool_name: str
    description: str
    input_schema: dict[str, Any]
    description_tokens: int = 0
    entry_id: str = ""
    domain_tag: str = ""


@dataclass
class TrialInputs:
    """Everything the agent needs to run a single trial.

    Constructed by the orchestrator; the agent does not parse Config or YAML
    on its own (separation of concerns per SPEC.md §3).
    """

    # Identity
    run_id: str
    cell_id: str
    trial_id: str
    seed: int
    harness_version: str

    # What was tested
    task_id: str
    task_version: str
    task_difficulty: str
    task_query: str
    primary_server: str
    model_snapshot_id: str
    model_id: str = "claude-sonnet-4-6"
    model_provider: str = "anthropic"
    sampling_params: SamplingParams = field(default_factory=SamplingParams)
    ordering_seed: int = 0
    tool_listing_strategy: str = "full"
    pass_criterion_id: str = "symbol-plus-50pct-overlap-v1"

    # Ground truth for the oracle ONLY. CONTAMINATION INVARIANT: these must
    # NEVER reach the model. The agent loop sends only task_query (via
    # _build_system_prompt + messages[0]) and the tools manifest; _invoke_api
    # never serializes TrialInputs. test_ground_truth_never_in_prompt locks this.
    ground_truth_target: str = ""
    ground_truth_code: str = ""

    # Sessions (from ServerPoolManager.start)
    sessions: dict[str, Any] = field(default_factory=dict)

    # Padded-N=1 control
    is_padded_n1: bool = False
    padding_corpus_path: Path | None = None
    primary_tool_desc_tokens: int = 0
    target_padding_tokens: int = 0

    # Oracle + tracing
    oracle_version: str = "pass_v1.py@sha256:unknown"
    trace_path: str = ""

    # Optional: cell_seed for deterministic filler selection (PADDING_STRATEGY §5)
    cell_seed: str = ""

    # Environment fingerprint (per-trial; pre-captured by orchestrator)
    env: EnvFingerprint | None = None

    # Embedder pin (models/embedder.json contents) — populates the 4 Trial
    # embedder_* fields per row AND is the fallback construction spec when
    # AgentHarness was created without a pre-built embedder client. The pin
    # itself is content-hashed into run_id by Config; this dict is the runtime
    # echo of that pin. None on retriever-OFF runs (Trial defaults apply).
    embedder_spec: dict | None = None

    # Retriever-ON top-k. Default 5 matches Config.retriever_top_k and
    # RAG-MCP §3. The orchestrator/agent_factory MUST propagate
    # Config.retriever_top_k into this field per-trial (parallel to embedder_spec)
    # so trial behavior matches what's hashed in run_id.
    retriever_top_k: int = 5


# ---------------------------------------------------------------------------
# Oracle protocol
# ---------------------------------------------------------------------------

OracleFn = Callable[[str, "TrialInputs"], bool]
"""(returned_snippet, trial_inputs) -> pass/fail; see oracles/pass_v1.py."""


# ---------------------------------------------------------------------------
# Cost model (Sonnet 4.6 USD per 1M tokens; rough estimate for cost_usd field)
# ---------------------------------------------------------------------------

_SONNET_INPUT_USD_PER_MTOK = 3.0
_SONNET_OUTPUT_USD_PER_MTOK = 15.0


def _estimate_cost_usd(in_tokens: int, out_tokens: int) -> float:
    return (in_tokens * _SONNET_INPUT_USD_PER_MTOK
            + out_tokens * _SONNET_OUTPUT_USD_PER_MTOK) / 1_000_000.0


# ---------------------------------------------------------------------------
# AgentHarness
# ---------------------------------------------------------------------------


class AgentHarness:
    """Runs ONE trial: Anthropic API + MCP tool-use loop + Trial construction.

    Constructed once per trial (cheap; no connection pool state). The Anthropic
    client is created here so HTTPX session isolation per SPEC.md §5 rule 4 is
    automatic (`AsyncAnthropic()` instantiates a fresh httpx session).
    """

    MAX_TURNS = 16  # SPEC.md §7 F9 cap (agent gives up signal)

    def __init__(
        self,
        anthropic_client: Any | None = None,
        oracle: OracleFn | None = None,
        *,
        max_turns: int | None = None,
        embedder: Embedder | None = None,
        tool_result_char_cap: int | None = None,
    ):
        self._client = anthropic_client  # lazy AsyncAnthropic() if None
        self._oracle = oracle or _default_oracle_falsey
        self.max_turns = max_turns or self.MAX_TURNS
        # Max chars of a single tool result forwarded to the model. Threaded
        # from cfg.tool_result_char_cap by the orchestrator; falls back to the
        # shared default for direct construction (tests). A too-small cap clips
        # answers deep in a file (the github-smoke max_turns bug: answer at
        # char 4,417 behind a 4,096 cap), so this must fit the target file.
        self.tool_result_char_cap = (
            tool_result_char_cap
            if tool_result_char_cap is not None
            else DEFAULT_TOOL_RESULT_CHAR_CAP
        )
        # Optional pre-built embedder client for retriever-ON. If None and a
        # trial needs an embedder, _build_tools_manifest constructs one from
        # inputs.embedder_spec on the fly. Tests inject a stub here to avoid
        # API calls. Orchestrator should pass one in for client reuse.
        self._embedder = embedder

    # ---- Public entry point -------------------------------------------------

    async def run_trial(self, inputs: TrialInputs) -> Trial:
        """Execute one trial end-to-end and return the validated Trial record."""
        started_at = datetime.now(timezone.utc)
        nonce = _per_trial_nonce(inputs.trial_id)
        tools_manifest, fake_tool_names, padding_skipped = await self._build_tools_manifest(inputs)
        client = self._client or _new_async_anthropic()
        messages = [{"role": "user", "content": inputs.task_query}]
        system_prompt = _build_system_prompt(nonce, inputs.task_query)
        # Trial schema field always has a path (for documentation), but the
        # actual file is only written when inputs.trace_path is explicitly set.
        # Empty trace_path = trace-writing disabled; the schema-side fallback
        # keeps row provenance readable but commits to no disk side effect.
        effective_trace_path = _effective_trace_path(inputs)
        trace_file = _open_trace_file(inputs.trace_path, inputs)

        tool_calls: list[ToolCall] = []
        first_correct_step: int | None = None
        in_tokens = 0
        out_tokens = 0
        fake_tool_invoked = False
        error_type = "none"
        error_detail: str | None = None
        final_text = ""

        try:
            try:
                for turn in range(self.max_turns):
                    response = await _invoke_api(
                        client, inputs, system_prompt, messages, tools_manifest
                    )
                    _assert_cache_cold(response, inputs.trial_id)  # F18
                    u = getattr(response, "usage", None)
                    turn_in = int(getattr(u, "input_tokens", 0) or 0) if u is not None else 0
                    turn_out = int(getattr(u, "output_tokens", 0) or 0) if u is not None else 0
                    in_tokens += turn_in
                    out_tokens += turn_out
                    stop_reason = getattr(response, "stop_reason", None)
                    blocks = list(getattr(response, "content", []) or [])
                    assistant_text_blocks: list[Any] = []
                    tool_use_blocks: list[Any] = []
                    turn_text_blocks: list[str] = []
                    for b in blocks:
                        btype = getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else None)
                        if btype == "text":
                            assistant_text_blocks.append(b)
                            text_val = getattr(b, "text", None)
                            if text_val is None and isinstance(b, dict):
                                text_val = b.get("text", "")
                            if text_val:
                                turn_text_blocks.append(text_val)
                            final_text = text_val or final_text
                        elif btype == "tool_use":
                            tool_use_blocks.append(b)
                    turn_tool_names = [
                        (getattr(tu, "name", None) or (tu.get("name") if isinstance(tu, dict) else "")) or ""
                        for tu in tool_use_blocks
                    ]
                    turn_tool_args = [
                        (getattr(tu, "input", None) or (tu.get("input") if isinstance(tu, dict) else {})) or {}
                        for tu in tool_use_blocks
                    ]
                    _write_trace_turn(
                        trace_file,
                        turn_idx=turn,
                        stop_reason=stop_reason,
                        text_blocks=turn_text_blocks,
                        tool_use_names=turn_tool_names,
                        tool_use_args=turn_tool_args,
                        input_tokens=turn_in,
                        output_tokens=turn_out,
                    )
                    if not tool_use_blocks:
                        break
                    # Echo assistant turn back into messages
                    messages.append({"role": "assistant", "content": blocks})
                    tool_results_content: list[dict[str, Any]] = []
                    for tu in tool_use_blocks:
                        step_idx = len(tool_calls) + 1
                        name = getattr(tu, "name", None) or (tu.get("name") if isinstance(tu, dict) else "")
                        raw_args = getattr(tu, "input", None) or (tu.get("input") if isinstance(tu, dict) else {})
                        args = raw_args if isinstance(raw_args, dict) else {}
                        tu_id = getattr(tu, "id", None) or (tu.get("id") if isinstance(tu, dict) else f"call_{step_idx}")
                        call_record, content_for_model, was_fake = await self._dispatch_tool_call(
                            step_idx=step_idx,
                            tool_name=name,
                            args=args,
                            inputs=inputs,
                            fake_tool_names=fake_tool_names,
                        )
                        tool_calls.append(call_record)
                        if was_fake:
                            fake_tool_invoked = True
                        if (first_correct_step is None and call_record.was_valid
                                and not call_record.was_hallucinated and call_record.error is None):
                            first_correct_step = call_record.step_idx
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tu_id,
                            "content": content_for_model,
                            "is_error": call_record.error is not None,
                        })
                    messages.append({"role": "user", "content": tool_results_content})
                    if stop_reason == "end_turn":
                        break
                else:
                    error_type = "agent_gave_up"
                    error_detail = f"max_turns={self.max_turns} exhausted"
            except CacheLeakHalt:
                raise  # halt the orchestrator per F18
            except APIFault as e:
                error_type = "api_fault"
                error_detail = str(e)
            except ServerFault as e:
                error_type = "server_fault"
                error_detail = str(e)
            except (asyncio.TimeoutError, TimeoutError) as e:
                error_type = "latency_timeout"
                error_detail = str(e) or "timeout"
            except Exception:  # F13: re-raise so orchestrator halts (SPEC.md §7).
                # Anything not in (CacheLeakHalt, APIFault, ServerFault, TimeoutError)
                # is a persistent failure: retry/categorize returns "persistent_failure"
                # for unknown classes, and the orchestrator's _run_trial_with_sem raises
                # OrchestratorHalt on that category. Swallowing into error_type="harness_bug"
                # and returning a Trial would let the run continue marking false-completions
                # for every cell — see 2026-05-26 smoke (5/5 trials "completed" with
                # cost_usd=0 after anthropic.AuthenticationError on the first API call).
                logger.exception("uncaught exception in agent loop")
                raise

            passed = False
            # Bug A fix: score the oracle on final_text even when the loop hit
            # max_turns (error_type == "agent_gave_up"). A trial that emitted the
            # correct answer before exhausting its turns must count as a pass, not
            # be silently failed by skipping the oracle. Transport/harness failures
            # (api_fault/server_fault/latency_timeout) still skip scoring because
            # final_text is not a trustworthy answer there.
            # Oracle failures are F13-class (the oracle is part of the harness, not
            # the SUT); an oracle *exception* re-raises to halt the orchestrator.
            if error_type in ("none", "agent_gave_up"):
                passed = bool(self._oracle(final_text, inputs))
                if passed:
                    error_type = "none"
                elif error_type == "none":
                    # Classify wrong_tool vs wrong_answer vs agent_gave_up.
                    if first_correct_step is None and not tool_calls:
                        error_type = "agent_gave_up"
                    elif first_correct_step is None:
                        error_type = "wrong_tool"
                    else:
                        error_type = "wrong_answer"
        finally:
            _write_trace_end(
                trace_file,
                final_text=final_text,
                error_type=error_type,
                error_detail=error_detail,
                passed=locals().get("passed", False),
                total_input_tokens=in_tokens,
                total_output_tokens=out_tokens,
                tool_call_count=len(tool_calls),
                first_correct_tool_step=first_correct_step,
            )
            _close_trace_file(trace_file)

        finished_at = datetime.now(timezone.utc)
        env_ref = _to_env_ref(inputs.env)
        trial_dict: dict[str, Any] = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "harness_version": inputs.harness_version,
            "run_id": inputs.run_id,
            "cell_id": inputs.cell_id,
            "trial_id": inputs.trial_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "task_id": inputs.task_id,
            "task_version": inputs.task_version,
            "task_difficulty": inputs.task_difficulty,
            "model_id": inputs.model_id,
            "model_provider": inputs.model_provider,
            "model_snapshot_id": inputs.model_snapshot_id,
            "sampling_params": inputs.sampling_params,
            "server_set": _server_entries_from(inputs.sessions),
            "N": len(inputs.sessions),
            "primary_server": inputs.primary_server,
            "ordering_seed": inputs.ordering_seed,
            "tool_listing_strategy": inputs.tool_listing_strategy,
            "pass_criterion_id": inputs.pass_criterion_id,
            "context_input_tokens": in_tokens,
            "context_output_tokens": out_tokens,
            "tool_calls": tool_calls,
            "first_correct_tool_step": first_correct_step,
            "pass": passed,
            "error_type": error_type,
            "error_detail": error_detail,
            "cost_usd": _estimate_cost_usd(in_tokens, out_tokens),
            "is_padded_n1": inputs.is_padded_n1,
            "fake_tool_invoked": fake_tool_invoked,
            "padding_skipped": padding_skipped,
            "trace_path": effective_trace_path,
            "seed": inputs.seed,
            "oracle_version": inputs.oracle_version,
            "env": env_ref,
        }
        # Override the v1.2 embedder defaults with the configured pin when
        # known. Reflecting the *configured* embedder (not "was it invoked")
        # keeps the row consistent with run_id's h_embedder pin.
        if inputs.embedder_spec is not None:
            spec = inputs.embedder_spec
            trial_dict["embedder_provider"] = spec.get("provider", "openai")
            trial_dict["embedder_model"] = spec.get("model", "text-embedding-3-large")
            trial_dict["embedder_snapshot"] = spec.get(
                "snapshot", spec.get("model", "text-embedding-3-large")
            )
            trial_dict["embedder_dimension"] = spec.get("dimension", 3072)
        return Trial.model_validate(trial_dict)

    # ---- Tool-list assembly + dispatch -------------------------------------

    async def _build_tools_manifest(
        self, inputs: TrialInputs
    ) -> tuple[list[dict[str, Any]], set[str], str | None]:
        """Return (tools, fake_tool_names, padding_skipped).

        For padded-N=1, primary tool + fillers from `padding.select_padding`.
        For retriever-ON (RESEARCH_DESIGN.md §3.5), embed query + all tool
        descriptions and keep the top-k=5 by cosine similarity.
        For unpadded retriever-OFF trials, all tools across `inputs.sessions`.
        """
        tools: list[dict[str, Any]] = []
        fake_names: set[str] = set()
        padding_skipped: str | None = None
        for server_name, session in inputs.sessions.items():
            tool_list = getattr(session, "tool_names", None) or []
            full = await _get_full_tool_defs(session)
            for tdef in full:
                tools.append(_to_anthropic_tool(tdef))
            if not full and tool_list:
                for n in tool_list:
                    tools.append({"name": n, "description": "", "input_schema": {"type": "object"}})
        if inputs.tool_listing_strategy == "retriever-on":
            # retriever-ON is mutually exclusive with padded-N=1 by design
            # (padded-N=1 IS the no-distractor floor; retriever-ON is the
            # distractor-aware filtering). Hard-fail if both somehow set.
            if inputs.is_padded_n1:
                raise ValueError(
                    "retriever-on + is_padded_n1 are mutually exclusive "
                    "(see RESEARCH_DESIGN.md §3.5)"
                )
            # Empty tool list with retriever-on means the orchestrator handed
            # us a cell with no sessions, or every session reported zero tools.
            # Silently passing through would skip the retrieval step and write
            # a trial row claiming retriever-on with zero filtering happening.
            if not tools:
                raise RuntimeError(
                    "retriever-on requires at least one tool to rank; "
                    "got empty manifest (no sessions or sessions had no tools)"
                )
            embedder = self._embedder
            if embedder is None:
                if inputs.embedder_spec is None:
                    raise RuntimeError(
                        "retriever-on trial requires an embedder; pass one via "
                        "AgentHarness(embedder=...) or set inputs.embedder_spec"
                    )
                embedder = make_embedder(inputs.embedder_spec)
            descriptions = [t.get("description", "") for t in tools]
            top_idxs = await rank_tools_by_query(
                embedder, inputs.task_query, descriptions,
                top_k=inputs.retriever_top_k,
            )
            tools = [tools[i] for i in top_idxs]
        if inputs.is_padded_n1:
            from . import padding as _padding  # local import: sibling module
            fakes, padding_skipped = _padding.select_padding(
                cell_seed=inputs.cell_seed,
                target_tokens=inputs.target_padding_tokens,
                primary_tool_desc_tokens=inputs.primary_tool_desc_tokens,
                corpus_path=inputs.padding_corpus_path or Path("design/fake_tool_corpus.jsonl"),
            )
            for fake in fakes:
                fake_names.add(fake.tool_name)
                tools.append({
                    "name": fake.tool_name,
                    "description": fake.description,
                    "input_schema": fake.input_schema,
                })
        return tools, fake_names, padding_skipped

    async def _dispatch_tool_call(
        self,
        *,
        step_idx: int,
        tool_name: str,
        args: dict[str, Any],
        inputs: TrialInputs,
        fake_tool_names: set[str],
    ) -> tuple[ToolCall, str, bool]:
        """Route a tool_use block to the right session (or MethodNotFound for fillers)."""
        args_hash = hashlib.sha256(
            json.dumps(args, sort_keys=True, default=str).encode()
        ).hexdigest()
        # F11 (hallucinated): tool_name not in any installed server AND not a filler
        installed = {n for sess in inputs.sessions.values() for n in (getattr(sess, "tool_names", []) or [])}
        if tool_name in fake_tool_names:
            # PADDING_STRATEGY §6: respond with MethodNotFound, log fake_tool_invoked
            call = ToolCall(
                step_idx=step_idx, server_called="<fake>", tool_called=tool_name,
                args_hash=args_hash, response_summary="MethodNotFound",
                latency_ms=0, error="fake-tool-invoked",
                was_valid=True, was_hallucinated=False,
            )
            return call, "MethodNotFound: fake tool", True
        if tool_name not in installed:
            call = ToolCall(
                step_idx=step_idx, server_called="<unknown>", tool_called=tool_name,
                args_hash=args_hash, response_summary="not in installed tool set",
                latency_ms=0, error="hallucinated_tool_name",
                was_valid=False, was_hallucinated=True,
            )
            return call, f"Error: tool {tool_name!r} not available", False
        # Locate which session owns this tool name
        owner_name = None
        owner_session = None
        for sname, sess in inputs.sessions.items():
            if tool_name in (getattr(sess, "tool_names", []) or []):
                owner_name = sname
                owner_session = sess
                break
        assert owner_session is not None and owner_name is not None
        target = getattr(owner_session, "session", owner_session)  # ServerSession.session or raw
        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(target.call_tool(tool_name, args), timeout=30.0)
        except (asyncio.TimeoutError, TimeoutError):
            elapsed = int((time.perf_counter() - t0) * 1000)
            call = ToolCall(
                step_idx=step_idx, server_called=owner_name, tool_called=tool_name,
                args_hash=args_hash, response_summary="timeout",
                latency_ms=elapsed, error="latency_timeout",
                was_valid=True, was_hallucinated=False,
            )
            return call, "Error: tool call timeout", False
        except Exception as e:
            elapsed = int((time.perf_counter() - t0) * 1000)
            call = ToolCall(
                step_idx=step_idx, server_called=owner_name, tool_called=tool_name,
                args_hash=args_hash, response_summary=str(e)[:256],
                latency_ms=elapsed, error=f"server_fault: {type(e).__name__}",
                was_valid=True, was_hallucinated=False,
            )
            return call, f"Error: {e}", False
        elapsed = int((time.perf_counter() - t0) * 1000)
        payload = _flatten_tool_result(result)
        truncated = payload[: self.tool_result_char_cap]
        call = ToolCall(
            step_idx=step_idx, server_called=owner_name, tool_called=tool_name,
            args_hash=args_hash, response_summary=truncated[:1024],
            latency_ms=elapsed,
            error=None if not getattr(result, "isError", False) else "tool returned isError",
            was_valid=True, was_hallucinated=False,
            output_tokens=max(1, len(truncated) // 4),  # rough token estimate
            result_chars=len(payload),  # full pre-cap length; > cap ⇒ result was clipped
        )
        return call, truncated, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effective_trace_path(inputs: TrialInputs) -> str:
    """Resolve where to write the per-trial trace. Empty inputs.trace_path
    falls back to a relative path matching the Trial.trace_path schema field
    so debugging-after-the-fact still has a stable default location.
    """
    return inputs.trace_path or f"results/{inputs.run_id}/traces/{inputs.trial_id}.jsonl"


def _open_trace_file(trace_path: str, inputs: TrialInputs) -> Any:
    """Open the per-trial JSONL trace and write the trial_meta header.

    Returns the file handle, or None on any I/O error (tracing is best-effort
    diagnostic output; never halt a trial because the trace can't be written).
    """
    if not trace_path:
        return None
    try:
        p = Path(trace_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        f = p.open("w", encoding="utf-8")
        meta = {
            "record_type": "trial_meta",
            "trial_id": inputs.trial_id,
            "cell_id": inputs.cell_id,
            "run_id": inputs.run_id,
            "task_id": inputs.task_id,
            "task_query": inputs.task_query,
            "primary_server": inputs.primary_server,
            "model_snapshot_id": inputs.model_snapshot_id,
            "harness_version": inputs.harness_version,
            "is_padded_n1": inputs.is_padded_n1,
            "tool_listing_strategy": inputs.tool_listing_strategy,
        }
        f.write(json.dumps(meta) + "\n")
        f.flush()
        return f
    except OSError as e:
        logger.warning("could not open trace file %r: %s", trace_path, e)
        return None


def _write_trace_turn(
    trace_file: Any,
    *,
    turn_idx: int,
    stop_reason: str | None,
    text_blocks: list[str],
    tool_use_names: list[str],
    input_tokens: int,
    output_tokens: int,
    tool_use_args: list[Any] | None = None,
) -> None:
    """Append a per-turn record. No-op when trace_file is None."""
    if trace_file is None:
        return
    try:
        rec = {
            "record_type": "turn",
            "turn_idx": turn_idx,
            "stop_reason": stop_reason,
            "text_blocks": text_blocks,
            "tool_use_names": tool_use_names,
            "tool_use_args": tool_use_args if tool_use_args is not None else [],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        trace_file.write(json.dumps(rec) + "\n")
        trace_file.flush()
    except OSError as e:
        logger.warning("could not write trace turn %d: %s", turn_idx, e)


def _write_trace_end(
    trace_file: Any,
    *,
    final_text: str,
    error_type: str,
    error_detail: str | None,
    passed: bool,
    total_input_tokens: int,
    total_output_tokens: int,
    tool_call_count: int,
    first_correct_tool_step: int | None,
) -> None:
    """Append the trial_end record summarising the trial outcome."""
    if trace_file is None:
        return
    try:
        rec = {
            "record_type": "trial_end",
            "final_text": final_text,
            "error_type": error_type,
            "error_detail": error_detail,
            "passed": passed,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "tool_call_count": tool_call_count,
            "first_correct_tool_step": first_correct_tool_step,
        }
        trace_file.write(json.dumps(rec) + "\n")
        trace_file.flush()
    except OSError as e:
        logger.warning("could not write trace_end: %s", e)


def _close_trace_file(trace_file: Any) -> None:
    if trace_file is None:
        return
    try:
        trace_file.close()
    except OSError as e:
        logger.warning("could not close trace file: %s", e)


def _per_trial_nonce(trial_id: str) -> str:
    """32-byte hex per SPEC.md §5 rule 4 + F18.

    `secrets.token_hex` is collision-free; trial_id is salted in for determinism
    under tests (tests can monkeypatch this if they need determinism, but the
    production policy is unique-per-call).
    """
    return hashlib.sha256((trial_id + secrets.token_hex(16)).encode()).hexdigest()


def _build_system_prompt(nonce: str, query: str) -> str:
    # The "stop calling tools once you have the answer" clause is load-bearing.
    # Without it, Sonnet 4.6 in agent mode emits >=1 tool_use per turn for all
    # MAX_TURNS turns even after retrieving the correct file (verified
    # 2026-05-27 against github-smoke-001; agent_gave_up rate = 4/4 with
    # first_correct_tool_step=1 and ~22 redundant tool calls per trial).
    return (
        f"<nonce>{nonce}</nonce>\n"
        "You are a code-retrieval assistant. Use the available tools to find "
        "the code snippet that answers the user's query.\n"
        "\n"
        "When you have located the snippet, reply with the snippet as plain "
        "text and stop calling tools. Do not call additional tools to "
        "double-check or explore further once you have an answer.\n"
        "\n"
        "Do not invent tool names."
    )


def _assert_cache_cold(response: Any, trial_id: str) -> None:
    """F18: any cache_read/cache_creation > 0 halts the run."""
    u = getattr(response, "usage", None)
    if u is None:
        return
    cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    cc = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    if cr > 0 or cc > 0:
        raise CacheLeakHalt(
            f"F18 cache leak on trial {trial_id}: cache_read={cr} cache_creation={cc}"
        )


def _new_async_anthropic() -> Any:
    """Lazy import + instantiate; lets tests monkeypatch when SDK not installed."""
    from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
    return AsyncAnthropic()


def _to_anthropic_tool(tool_obj: Any) -> dict[str, Any]:
    """Convert an `mcp.types.Tool` (or dict) into the Anthropic `tools` shape."""
    name = getattr(tool_obj, "name", None) or tool_obj.get("name", "")
    desc = getattr(tool_obj, "description", None) or tool_obj.get("description", "") or ""
    schema = (getattr(tool_obj, "inputSchema", None)
              or tool_obj.get("inputSchema") or tool_obj.get("input_schema")
              or {"type": "object"})
    return {"name": name, "description": desc, "input_schema": schema}


async def _get_full_tool_defs(session: Any) -> list[Any]:
    """Pull full Tool definitions from a session (or return [] if unavailable)."""
    sess = getattr(session, "session", session)
    list_tools_fn = getattr(sess, "list_tools", None)
    if list_tools_fn is None:
        return []
    try:
        result = await list_tools_fn()
    except Exception:
        return []
    return list(getattr(result, "tools", []) or [])


def _flatten_tool_result(result: Any) -> str:
    """Stringify an MCP CallToolResult to plain text for the model + audit.

    Handles both block shapes the pinned servers emit: plain ``TextContent``
    (text at ``block.text``) and ``EmbeddedResource`` (file/blob payload under
    ``block.resource``). github_mcp's ``get_file_contents`` returns the file
    body as an EmbeddedResource whose content lives at ``resource.text`` (or a
    base64 ``resource.blob``), while ``block.text`` carries only a
    "successfully downloaded ... (SHA: ...)" metadata line. Reading
    ``block.text`` alone therefore discarded the actual file content and the
    agent never received the answer (all 5 github-smoke trials looped to
    max_turns retrying retrieval). Both blocks are now emitted.
    """
    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(str(text))
            continue
        resource = getattr(block, "resource", None)
        if resource is None and isinstance(block, dict):
            resource = block.get("resource")
        if resource is not None:
            rtext = getattr(resource, "text", None)
            if rtext is None and isinstance(resource, dict):
                rtext = resource.get("text")
            if rtext:
                parts.append(str(rtext))
                continue
            blob = getattr(resource, "blob", None)
            if blob is None and isinstance(resource, dict):
                blob = resource.get("blob")
            if blob:
                try:
                    parts.append(base64.b64decode(blob).decode("utf-8", errors="replace"))
                except Exception:
                    parts.append(f"<undecodable blob, {len(str(blob))} base64 chars>")
                continue
    return "\n".join(parts) or json.dumps(getattr(result, "structuredContent", None) or {})


def _server_entries_from(sessions: dict[str, Any]) -> list[ServerEntry]:
    out: list[ServerEntry] = []
    for name, sess in sessions.items():
        pin = getattr(sess, "pin", None)
        version = (getattr(pin, "git_sha", None) or getattr(pin, "npm_lock_hash", None)
                   or getattr(pin, "npm_version", None) or "unpinned")
        tool_count = len(getattr(sess, "tool_names", []) or [])
        out.append(ServerEntry(
            server_name=name, server_version=version,
            tool_count=tool_count, description_tokens=0,  # filled by orchestrator if known
        ))
    return out


def _to_env_ref(env: EnvFingerprint | None) -> EnvFingerprintRef:
    if env is None:
        return EnvFingerprintRef(os="unknown", python_version="unknown",
                                 package_hash="unknown", machine_id="unknown",
                                 git_sha="unknown")
    return EnvFingerprintRef(
        os=env.os, python_version=env.python_version,
        package_hash=env.package_hash, machine_id=env.machine_id, git_sha=env.git_sha,
    )


def _default_oracle_falsey(text: str, inputs: TrialInputs) -> bool:
    """Fallback oracle (always false) so tests that omit one still produce a Trial."""
    return False


# ---------------------------------------------------------------------------
# API invocation (retry-wrapped; mirrors retry_policy semantics in retry.py)
# ---------------------------------------------------------------------------


async def _invoke_api(
    client: Any,
    inputs: TrialInputs,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> Any:
    """Wrap `client.messages.create` in the standard retry policy (M8 + F5/F6/F7)."""
    attempts = 5
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await client.messages.create(
                model=inputs.model_snapshot_id,
                max_tokens=inputs.sampling_params.max_tokens,
                temperature=inputs.sampling_params.temperature,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )
        except (APIFault, ServerFault) as e:
            last_exc = e
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(min(delay, 60.0))
            delay *= 2.0
        except Exception as e:  # noqa: BLE001
            # Translate provider-specific transient errors into APIFault if possible
            name = type(e).__name__.lower()
            if any(k in name for k in ("ratelimit", "timeout", "apistatus", "apiconnection",
                                       "apitimeout", "internalserver", "overloaded")):
                last_exc = APIFault(str(e))
                if attempt == attempts - 1:
                    raise last_exc from e
                await asyncio.sleep(min(delay, 60.0))
                delay *= 2.0
                continue
            raise
    if last_exc:  # pragma: no cover
        raise last_exc
