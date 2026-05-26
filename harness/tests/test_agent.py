"""Tests for tcrun.agent — Trial construction, F18 cache leak halt, padded-N=1.

Mocks AsyncAnthropic.messages.create and ClientSession.call_tool to avoid real
API/network/MCP. Verifies:
    * Trial returned with the correct schema shape
    * F18 (cache leak) halts the run via CacheLeakHalt
    * Padded-N=1 invokes padding.select_padding and merges fillers
    * MethodNotFound on filler invocation sets fake_tool_invoked=True
    * Hallucinated tool name produces a was_hallucinated=True ToolCall record
    * Per-trial nonce is regenerated per call
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tcrun.agent import (
    AgentHarness,
    CacheLeakHalt,
    FakeTool,
    TrialInputs,
    _build_system_prompt,
    _estimate_cost_usd,
    _per_trial_nonce,
)
from tcrun.env import EnvFingerprint
from tcrun.results import SamplingParams, Trial


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fp() -> EnvFingerprint:
    return EnvFingerprint(os="Darwin", python_version="3.11.7",
                          package_hash="ph" * 32, machine_id="mid" * 21 + "x",
                          git_sha="gs")


def _inputs(**overrides) -> TrialInputs:
    base = dict(
        run_id="r0",
        cell_id="c0",
        trial_id="t0",
        seed=42,
        harness_version="v0",
        task_id="v1-pub-001",
        task_version="coir-v1",
        task_difficulty="medium",
        task_query="find function that parses yaml",
        primary_server="oci",
        model_snapshot_id="claude-sonnet-4-6-20260315",
        sampling_params=SamplingParams(),
        env=_fp(),
        trace_path="results/r0/traces/t0.jsonl",
    )
    base.update(overrides)
    return TrialInputs(**base)


def _session_with(tools: list[str], call_result=None) -> SimpleNamespace:
    """Build a fake ServerSession with the given tool_names + call_tool result."""
    cr = call_result if call_result is not None else MagicMock(
        content=[SimpleNamespace(text="snippet", type="text")],
        structuredContent=None, isError=False,
    )
    inner = SimpleNamespace(
        call_tool=AsyncMock(return_value=cr),
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
    )
    return SimpleNamespace(name="oci", pin=SimpleNamespace(git_sha="abc"),
                           tool_names=tools, session=inner)


def _api_response(text: str, *, stop_reason="end_turn", tool_uses=None,
                  cache_read=0, cache_creation=0,
                  input_tokens=100, output_tokens=20):
    blocks: list = []
    if text:
        blocks.append(SimpleNamespace(type="text", text=text))
    for tu in tool_uses or []:
        blocks.append(SimpleNamespace(type="tool_use", name=tu["name"],
                                      input=tu.get("input", {}), id=tu.get("id", "u1")))
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens,
                            cache_read_input_tokens=cache_read,
                            cache_creation_input_tokens=cache_creation)
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=usage)


def _client_returning(*responses):
    """Build a fake AsyncAnthropic that returns the given responses in order."""
    iterator = iter(responses)
    create = AsyncMock(side_effect=lambda **_kw: next(iterator))
    return SimpleNamespace(messages=SimpleNamespace(create=create))


# ---------------------------------------------------------------------------
# nonce + helpers
# ---------------------------------------------------------------------------


def test_per_trial_nonce_is_hex_and_changes_per_call():
    a = _per_trial_nonce("t0")
    b = _per_trial_nonce("t0")
    assert len(a) == 64  # sha256 hex
    assert a != b  # secrets.token_hex is fresh per call


# ---------------------------------------------------------------------------
# Retriever-ON path (v1.2 embedder layer, locked 2026-05-25)
# ---------------------------------------------------------------------------


class _StubEmbedderForAgent:
    """Embedder Protocol stub — assigns the first tool the best score."""

    name = "stub"
    provider = "openai"
    snapshot = "stub"
    dimension = 3

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # First text is the query; next N are tool descriptions.
        # Map text index → vector: idx 0 query == [1,0,0]; descriptions get
        # decaying weights so index 0 is best, 1 is worst.
        out = [[1.0, 0.0, 0.0]]
        n_desc = len(texts) - 1
        for i in range(n_desc):
            score = 1.0 - (i / max(n_desc, 1))
            out.append([score, 1.0 - score, 0.0])
        return out


def _retriever_session(tool_names: list[str]) -> SimpleNamespace:
    """A fake session that exposes tool_names but no list_tools detail."""
    return SimpleNamespace(
        name="oci",
        pin=SimpleNamespace(git_sha="abc"),
        tool_names=tool_names,
        session=SimpleNamespace(list_tools=AsyncMock(return_value=SimpleNamespace(tools=[]))),
    )


def test_retriever_on_requires_embedder_or_spec():
    """retriever-on without an embedder or pin spec must error loud."""
    harness = AgentHarness(anthropic_client=_client_returning(_api_response("ok")))
    inputs = _inputs(
        tool_listing_strategy="retriever-on",
        sessions={"oci": _retriever_session(["a", "b", "c", "d", "e", "f", "g"])},
    )
    with pytest.raises(RuntimeError, match="requires an embedder"):
        asyncio.run(harness._build_tools_manifest(inputs))


def test_retriever_on_filters_to_top_k_via_injected_embedder():
    """With a stub embedder, retriever-on keeps top-5 tools by cosine in score order."""
    harness = AgentHarness(
        anthropic_client=_client_returning(_api_response("ok")),
        embedder=_StubEmbedderForAgent(),
    )
    # Stub assigns descending scores by index → top-5 are tools a..e in order.
    inputs = _inputs(
        tool_listing_strategy="retriever-on",
        sessions={"oci": _retriever_session(["a", "b", "c", "d", "e", "f", "g"])},
    )
    tools, fakes, skipped = asyncio.run(harness._build_tools_manifest(inputs))
    assert [t["name"] for t in tools] == ["a", "b", "c", "d", "e"]
    assert fakes == set()
    assert skipped is None


def test_retriever_top_k_is_configurable_via_trial_inputs():
    """A non-default retriever_top_k on TrialInputs flows into the filter."""
    harness = AgentHarness(
        anthropic_client=_client_returning(_api_response("ok")),
        embedder=_StubEmbedderForAgent(),
    )
    inputs = _inputs(
        tool_listing_strategy="retriever-on",
        retriever_top_k=3,
        sessions={"oci": _retriever_session(["a", "b", "c", "d", "e", "f", "g"])},
    )
    tools, _, _ = asyncio.run(harness._build_tools_manifest(inputs))
    assert [t["name"] for t in tools] == ["a", "b", "c"]


def test_retriever_on_with_empty_tools_raises():
    """Empty manifest with retriever-on is an upstream config error, not silent skip."""
    harness = AgentHarness(
        anthropic_client=_client_returning(_api_response("ok")),
        embedder=_StubEmbedderForAgent(),
    )
    # session with NO tool_names → manifest stays empty
    inputs = _inputs(
        tool_listing_strategy="retriever-on",
        sessions={"oci": _retriever_session([])},
    )
    with pytest.raises(RuntimeError, match="at least one tool"):
        asyncio.run(harness._build_tools_manifest(inputs))


# ---------------------------------------------------------------------------
# embedder_spec → Trial row attribution (v1.2; uncovered prior to this batch)
# ---------------------------------------------------------------------------


def test_embedder_spec_overrides_trial_row_defaults():
    """inputs.embedder_spec must flow into Trial.embedder_* fields, not v1.2 defaults.

    Without this override, a TC_EMBEDDER=voyage run would write trial rows
    claiming OpenAI — mis-attributing the embedder relative to run_id's pin.
    """
    harness = AgentHarness(anthropic_client=_client_returning(_api_response("ok")))
    spec = {
        "provider": "voyageai",
        "model": "voyage-3-large",
        "snapshot": "voyage-3-large",
        "dimension": 1024,
    }
    inputs = _inputs(
        embedder_spec=spec,
        sessions={"oci": _session_with(["search"])},
    )
    trial = asyncio.run(harness.run_trial(inputs))
    assert trial.embedder_provider == "voyageai"
    assert trial.embedder_model == "voyage-3-large"
    assert trial.embedder_snapshot == "voyage-3-large"
    assert trial.embedder_dimension == 1024


def test_embedder_defaults_apply_when_spec_absent():
    """Without inputs.embedder_spec, Trial uses v1.2 defaults (OpenAI primary)."""
    harness = AgentHarness(anthropic_client=_client_returning(_api_response("ok")))
    inputs = _inputs(sessions={"oci": _session_with(["search"])})
    assert inputs.embedder_spec is None
    trial = asyncio.run(harness.run_trial(inputs))
    assert trial.embedder_provider == "openai"
    assert trial.embedder_model == "text-embedding-3-large"
    assert trial.embedder_dimension == 3072


def test_retriever_on_with_is_padded_n1_raises():
    """retriever-on + padded-N=1 are mutually exclusive design choices."""
    harness = AgentHarness(
        anthropic_client=_client_returning(_api_response("ok")),
        embedder=_StubEmbedderForAgent(),
    )
    inputs = _inputs(
        tool_listing_strategy="retriever-on",
        is_padded_n1=True,
        sessions={"oci": _retriever_session(["a", "b"])},
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        asyncio.run(harness._build_tools_manifest(inputs))


def test_retriever_off_full_strategy_keeps_all_tools():
    """The default `full` strategy returns the full unranked tool list."""
    harness = AgentHarness(anthropic_client=_client_returning(_api_response("ok")))
    inputs = _inputs(
        tool_listing_strategy="full",
        sessions={"oci": _retriever_session(["a", "b", "c", "d", "e", "f", "g"])},
    )
    tools, _, _ = asyncio.run(harness._build_tools_manifest(inputs))
    assert len(tools) == 7


def test_system_prompt_embeds_nonce():
    prompt = _build_system_prompt("abc123", "find foo")
    assert "<nonce>abc123</nonce>" in prompt


def test_estimate_cost_usd_is_positive():
    assert _estimate_cost_usd(1000, 100) > 0.0


# ---------------------------------------------------------------------------
# Trial construction (happy path: agent returns text without tool calls)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_trial_returns_valid_trial_no_tool_use():
    client = _client_returning(_api_response("here is the answer"))
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    trial = await harness.run_trial(_inputs(sessions={"oci": _session_with(["search"])}))
    assert isinstance(trial, Trial)
    assert trial.trial_id == "t0"
    assert trial.tool_calls == []
    assert trial.pass_ is True
    assert trial.error_type == "none"
    assert trial.context_input_tokens > 0
    assert trial.cost_usd > 0


@pytest.mark.asyncio
async def test_run_trial_dispatches_tool_call_and_marks_first_correct_step():
    sess = _session_with(["search"])
    client = _client_returning(
        _api_response("", tool_uses=[{"name": "search", "input": {"q": "foo"}, "id": "u1"}]),
        _api_response("done"),
    )
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    trial = await harness.run_trial(_inputs(sessions={"oci": sess}))
    assert len(trial.tool_calls) == 1
    assert trial.tool_calls[0].tool_called == "search"
    assert trial.tool_calls[0].was_hallucinated is False
    assert trial.first_correct_tool_step == 1
    sess.session.call_tool.assert_awaited_once()


# ---------------------------------------------------------------------------
# F18: cache leak halt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_trial_halts_on_cache_read_input_tokens():
    client = _client_returning(_api_response("hi", cache_read=5))
    harness = AgentHarness(anthropic_client=client)
    with pytest.raises(CacheLeakHalt):
        await harness.run_trial(_inputs(sessions={"oci": _session_with([])}))


@pytest.mark.asyncio
async def test_run_trial_halts_on_cache_creation_input_tokens():
    client = _client_returning(_api_response("hi", cache_creation=3))
    harness = AgentHarness(anthropic_client=client)
    with pytest.raises(CacheLeakHalt):
        await harness.run_trial(_inputs(sessions={"oci": _session_with([])}))


# ---------------------------------------------------------------------------
# F13: uncaught exceptions in the agent loop re-raise (do not swallow into
# error_type="harness_bug"). Surfaced 2026-05-26 when an invalid Anthropic
# API key produced 5 trials reported "completed" with cost_usd=0.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_trial_re_raises_on_unhandled_api_exception():
    class WeirdAPIError(Exception):
        pass

    async def create(**_kw):
        raise WeirdAPIError("auth refused")

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    harness = AgentHarness(anthropic_client=client)
    with pytest.raises(WeirdAPIError, match="auth refused"):
        await harness.run_trial(_inputs(sessions={"oci": _session_with([])}))


@pytest.mark.asyncio
async def test_run_trial_re_raises_on_oracle_exception():
    def oracle_that_raises(text, inputs):
        raise RuntimeError("oracle ate it")

    client = _client_returning(_api_response("any answer"))
    harness = AgentHarness(anthropic_client=client, oracle=oracle_that_raises)
    with pytest.raises(RuntimeError, match="oracle ate it"):
        await harness.run_trial(_inputs(sessions={"oci": _session_with([])}))


# ---------------------------------------------------------------------------
# Hallucinated tool name (F11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_trial_flags_hallucinated_tool_name():
    sess = _session_with(["search"])  # real tool is "search"
    client = _client_returning(
        _api_response("", tool_uses=[{"name": "definitely_not_real", "id": "u1"}]),
        _api_response("giving up"),
    )
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: False)
    trial = await harness.run_trial(_inputs(sessions={"oci": sess}))
    assert trial.tool_calls[0].was_hallucinated is True
    assert trial.tool_calls[0].error == "hallucinated_tool_name"
    # call_tool was NOT invoked on the real session
    sess.session.call_tool.assert_not_called()


# ---------------------------------------------------------------------------
# Padded-N=1: select_padding invoked, fillers advertised, MethodNotFound -> flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_padded_n1_invokes_select_padding_and_advertises_fillers():
    fake = FakeTool(tool_name="WeatherLookup",
                    description="checks weather",
                    input_schema={"type": "object"})
    sess = _session_with(["search"])
    client = _client_returning(_api_response("ok"))
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    with patch("tcrun.padding.select_padding", return_value=([fake], None)) as mock_pad:
        trial = await harness.run_trial(_inputs(
            sessions={"oci": sess},
            is_padded_n1=True,
            padding_corpus_path=Path("design/fake_tool_corpus.jsonl"),
            cell_seed="cs_hex",
            target_padding_tokens=500,
            primary_tool_desc_tokens=100,
        ))
    mock_pad.assert_called_once()
    assert trial.is_padded_n1 is True
    # Padding ran (no skip)
    assert trial.padding_skipped is None


@pytest.mark.asyncio
async def test_fake_tool_invoked_flag_set_on_methodnotfound():
    fake = FakeTool(tool_name="WeatherLookup",
                    description="weather",
                    input_schema={"type": "object"})
    sess = _session_with(["search"])
    # Agent invokes the filler on turn 1, then gives up
    client = _client_returning(
        _api_response("", tool_uses=[{"name": "WeatherLookup", "id": "u1"}]),
        _api_response("done"),
    )
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    with patch("tcrun.padding.select_padding", return_value=([fake], None)):
        trial = await harness.run_trial(_inputs(
            sessions={"oci": sess},
            is_padded_n1=True,
            cell_seed="cs",
            target_padding_tokens=200,
            primary_tool_desc_tokens=50,
        ))
    assert trial.fake_tool_invoked is True
    assert trial.tool_calls[0].error == "fake-tool-invoked"
    # The MCP layer was never asked to call the fake tool on a real session
    sess.session.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_padded_n1_propagates_padding_skipped_reason():
    sess = _session_with(["search"])
    client = _client_returning(_api_response("ok"))
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    with patch("tcrun.padding.select_padding", return_value=([], "budget_negative")):
        trial = await harness.run_trial(_inputs(
            sessions={"oci": sess},
            is_padded_n1=True,
            cell_seed="cs",
            target_padding_tokens=10,
            primary_tool_desc_tokens=1000,
        ))
    assert trial.padding_skipped == "budget_negative"


# ---------------------------------------------------------------------------
# Retry on API fault (translates to APIFault internally via name-based heuristic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_trial_retries_then_succeeds_on_transient_api_error():
    # First call raises a class named like a rate-limit error; second succeeds.
    class APIStatusError(Exception):
        pass

    succeeded = _api_response("ok")
    call_count = {"n": 0}
    async def create(**_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise APIStatusError("429 rate limit")
        return succeeded

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: True)
    # Patch sleep so the test is fast
    with patch("tcrun.agent.asyncio.sleep", new=AsyncMock(return_value=None)):
        trial = await harness.run_trial(_inputs(sessions={"oci": _session_with([])}))
    assert call_count["n"] == 2
    assert trial.error_type == "none"


# ---------------------------------------------------------------------------
# Agent gives up after max_turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_gives_up_after_max_turns():
    sess = _session_with(["search"])
    # Always return a tool_use with stop_reason='tool_use' so the loop never
    # exits via the end_turn break path. After max_turns iterations the for-else
    # branch fires and marks the trial agent_gave_up.
    def make_tool_use_response(*_a, **_kw):
        return _api_response("", stop_reason="tool_use",
                             tool_uses=[{"name": "search", "id": "u1"}])
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=make_tool_use_response)))
    harness = AgentHarness(anthropic_client=client, oracle=lambda t, i: False, max_turns=2)
    trial = await harness.run_trial(_inputs(sessions={"oci": sess}))
    assert trial.error_type == "agent_gave_up"
    assert trial.pass_ is False
