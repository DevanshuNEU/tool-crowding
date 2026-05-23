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
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
    ):
        self._client = anthropic_client  # lazy AsyncAnthropic() if None
        self._oracle = oracle or _default_oracle_falsey
        self.max_turns = max_turns or self.MAX_TURNS

    # ---- Public entry point -------------------------------------------------

    async def run_trial(self, inputs: TrialInputs) -> Trial:
        """Execute one trial end-to-end and return the validated Trial record."""
        started_at = datetime.now(timezone.utc)
        nonce = _per_trial_nonce(inputs.trial_id)
        tools_manifest, fake_tool_names, padding_skipped = await self._build_tools_manifest(inputs)
        client = self._client or _new_async_anthropic()
        messages = [{"role": "user", "content": inputs.task_query}]
        system_prompt = _build_system_prompt(nonce, inputs.task_query)

        tool_calls: list[ToolCall] = []
        first_correct_step: int | None = None
        in_tokens = 0
        out_tokens = 0
        fake_tool_invoked = False
        error_type = "none"
        error_detail: str | None = None
        final_text = ""

        try:
            for turn in range(self.max_turns):
                response = await _invoke_api(
                    client, inputs, system_prompt, messages, tools_manifest
                )
                _assert_cache_cold(response, inputs.trial_id)  # F18
                u = getattr(response, "usage", None)
                if u is not None:
                    in_tokens += int(getattr(u, "input_tokens", 0) or 0)
                    out_tokens += int(getattr(u, "output_tokens", 0) or 0)
                stop_reason = getattr(response, "stop_reason", None)
                blocks = list(getattr(response, "content", []) or [])
                assistant_text_blocks: list[Any] = []
                tool_use_blocks: list[Any] = []
                for b in blocks:
                    btype = getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else None)
                    if btype == "text":
                        assistant_text_blocks.append(b)
                        text_val = getattr(b, "text", None)
                        if text_val is None and isinstance(b, dict):
                            text_val = b.get("text", "")
                        final_text = text_val or final_text
                    elif btype == "tool_use":
                        tool_use_blocks.append(b)
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
        except Exception as e:  # F13: any other uncaught -> harness_bug, will halt
            logger.exception("uncaught exception in agent loop")
            error_type = "harness_bug"
            error_detail = f"{type(e).__name__}: {e}"

        passed = False
        if error_type == "none":
            try:
                passed = bool(self._oracle(final_text, inputs))
            except Exception as e:
                error_type = "harness_bug"
                error_detail = f"oracle raised: {e}"
            if not passed and error_type == "none":
                # Classify wrong_tool vs wrong_answer vs agent_gave_up.
                if first_correct_step is None and not tool_calls:
                    error_type = "agent_gave_up"
                elif first_correct_step is None:
                    error_type = "wrong_tool"
                else:
                    error_type = "wrong_answer"

        finished_at = datetime.now(timezone.utc)
        env_ref = _to_env_ref(inputs.env)
        trial = Trial.model_validate({
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
            "trace_path": inputs.trace_path or f"results/{inputs.run_id}/traces/{inputs.trial_id}.jsonl",
            "seed": inputs.seed,
            "oracle_version": inputs.oracle_version,
            "env": env_ref,
        })
        return trial

    # ---- Tool-list assembly + dispatch -------------------------------------

    async def _build_tools_manifest(
        self, inputs: TrialInputs
    ) -> tuple[list[dict[str, Any]], set[str], str | None]:
        """Return (tools, fake_tool_names, padding_skipped).

        For padded-N=1, primary tool + fillers from `padding.select_padding`.
        For unpadded trials, all tools across `inputs.sessions`.
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
        truncated = payload[:4096]
        call = ToolCall(
            step_idx=step_idx, server_called=owner_name, tool_called=tool_name,
            args_hash=args_hash, response_summary=truncated[:1024],
            latency_ms=elapsed,
            error=None if not getattr(result, "isError", False) else "tool returned isError",
            was_valid=True, was_hallucinated=False,
            output_tokens=max(1, len(truncated) // 4),  # rough token estimate
        )
        return call, truncated, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _per_trial_nonce(trial_id: str) -> str:
    """32-byte hex per SPEC.md §5 rule 4 + F18.

    `secrets.token_hex` is collision-free; trial_id is salted in for determinism
    under tests (tests can monkeypatch this if they need determinism, but the
    production policy is unique-per-call).
    """
    return hashlib.sha256((trial_id + secrets.token_hex(16)).encode()).hexdigest()


def _build_system_prompt(nonce: str, query: str) -> str:
    return (
        f"<nonce>{nonce}</nonce>\n"
        "You are a code-retrieval assistant. Use the available tools to find the "
        "code snippet that answers the user's query. Reply with the snippet as plain "
        "text. Do not invent tool names."
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
    """Stringify an MCP CallToolResult to plain text for the model + audit."""
    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text", "")
        if text:
            parts.append(str(text))
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
                top_p=inputs.sampling_params.top_p,
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
