"""Tests for tcrun.runner — default pool/agent factories + AgentRunner bridge.

Verifies:
    * `_load_endpoint_pin` raises loudly when cfg.model isn't pinned
    * `_load_endpoint_pin` returns the matched row, requires provider + checkpoint
    * `_difficulty_for` maps q1..q4 and rejects unknown values
    * `_oracle_version_for` formats `<name>@sha256:<hex>`
    * `make_default_pool_factory` yields a `dict[str, ServerSession]` via the
      orchestrator's `async with ... as pool` pattern
    * `make_default_agent_factory` resolves endpoints + oracle + env once,
      returns a closure satisfying the orchestrator's (pool, spec) contract
    * `AgentRunner.run_trial` constructs `TrialInputs` from a (cell, query)
      pair and threads embedder_spec + retriever_top_k + env through
    * retriever-OFF runs don't try to build an embedder
    * retriever-ON runs pre-build the embedder once (and fail loud if not buildable)
    * Orchestrator with default factories dispatches real trials end-to-end
      (with mocked AgentHarness so no API calls happen)
    * Orchestrator without factories raises OrchestratorHalt at .run() time
      (no silent no-op for misconfigured production callers)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from tcrun.config import Config
from tcrun.env import EnvFingerprint
from tcrun.orchestrator import CellSpec, Orchestrator, OrchestratorHalt
from tcrun.runner import (
    AgentRunner,
    EndpointResolutionError,
    _difficulty_for,
    _load_endpoint_pin,
    _oracle_version_for,
    make_default_agent_factory,
    make_default_pool_factory,
)
from tcrun.tasks import Query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_endpoints(path: Path, model_id: str = "claude-sonnet-4-6-20260131") -> Path:
    payload = {
        "schema_version": "1.0",
        "models": [
            {
                "model_id": model_id,
                "provider": "anthropic",
                "api_url": "https://example.test/v1/messages",
                "checkpoint_identifier": f"{model_id}-snapshot",
                "default_temperature": 0.0,
                "default_max_tokens": 4096,
            }
        ],
    }
    return _write(path, json.dumps(payload))


def _build_config(
    tmp_path: Path,
    *,
    model_id: str = "claude-sonnet-4-6-20260131",
    strategy: str = "full",
) -> Config:
    return Config(
        task_set=_write(tmp_path / "queries.jsonl", "{}"),
        oracle=_write(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True"),
        servers_pinned=_write(tmp_path / "servers.yaml", "{}"),
        descriptions=_write(tmp_path / "descriptions.json", "{}"),
        endpoints=_write_endpoints(tmp_path / "endpoints.json", model_id=model_id),
        environment=_write(tmp_path / "environment.lock", "py=3.11"),
        padding_corpus=_write(tmp_path / "corpus.jsonl", "{}"),
        embedder=_write(
            tmp_path / "embedder.json",
            '{"provider":"openai","model":"text-embedding-3-large","dimension":3072}',
        ),
        primary_servers=["oci"],
        distractors=["fs", "mem"],
        N=[1],
        runs_per_cell=1,
        model=model_id,
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
        tool_listing_strategy=strategy,
        include_padded_n1_control=False,
    )


def _fingerprint() -> EnvFingerprint:
    return EnvFingerprint(
        os="Darwin-test",
        python_version="3.11.7",
        package_hash="ph" * 32,
        machine_id="mid" * 21 + "x",
        git_sha="abc1234",
    )


def _query(query_id: str = "q1", quartile: str = "q2") -> Query:
    return Query(
        query_id=query_id,
        tier="public",
        text="find function that parses yaml",
        ground_truth_target="parse_yaml",
        ground_truth_code="def parse_yaml(): ...",
        source_repo="example/repo",
        source_publication_date="2026-05-22",
        source_license="GPL-2.0",
        difficulty_quartile=quartile,
        primary_server="oci",
    )


def _cell(model: str, *, run_id: str = "r0") -> CellSpec:
    return CellSpec(
        run_id=run_id,
        model=model,
        N=1,
        query_id="q1",
        primary_server="oci",
        ordering_seed=0,
        repetition_id=0,
        is_padded_n1=False,
    )


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_load_endpoint_pin_returns_row(tmp_path: Path):
    p = _write_endpoints(tmp_path / "endpoints.json", model_id="claude-test-001")
    row = _load_endpoint_pin(p, "claude-test-001")
    assert row["provider"] == "anthropic"
    assert row["checkpoint_identifier"] == "claude-test-001-snapshot"


def test_load_endpoint_pin_missing_model_raises(tmp_path: Path):
    p = _write_endpoints(tmp_path / "endpoints.json", model_id="claude-A")
    with pytest.raises(EndpointResolutionError, match="not pinned"):
        _load_endpoint_pin(p, "claude-B")


def test_load_endpoint_pin_missing_required_key_raises(tmp_path: Path):
    p = _write(
        tmp_path / "endpoints.json",
        json.dumps(
            {
                "schema_version": "1.0",
                "models": [{"model_id": "m", "provider": "anthropic"}],
            }
        ),
    )
    with pytest.raises(EndpointResolutionError, match="checkpoint_identifier"):
        _load_endpoint_pin(p, "m")


def test_load_endpoint_pin_invalid_json_raises(tmp_path: Path):
    p = _write(tmp_path / "endpoints.json", "{not json")
    with pytest.raises(EndpointResolutionError, match="invalid JSON"):
        _load_endpoint_pin(p, "anything")


def test_difficulty_for_known_quartiles():
    assert _difficulty_for("q1") == "easy"
    assert _difficulty_for("q2") == "medium"
    assert _difficulty_for("q3") == "medium"
    assert _difficulty_for("q4") == "hard"


def test_difficulty_for_unknown_raises():
    with pytest.raises(ValueError, match="unknown difficulty_quartile"):
        _difficulty_for("q5")


def test_oracle_version_for_includes_sha256(tmp_path: Path):
    p = _write(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True")
    v = _oracle_version_for(p)
    assert v.startswith("pass_v1.py@sha256:")
    assert len(v.split(":")[1]) == 64  # full sha256 hex


# ---------------------------------------------------------------------------
# AgentRunner — TrialInputs construction
# ---------------------------------------------------------------------------


class _RecordingHarness:
    """AgentHarness double that records the TrialInputs it would have run."""

    def __init__(self):
        self.inputs: list[Any] = []

    async def run_trial(self, inputs):
        self.inputs.append(inputs)
        return SimpleNamespace(trial_id=inputs.trial_id, cost_usd=0.0)


def test_agent_runner_builds_trial_inputs(tmp_path: Path):
    cfg = _build_config(tmp_path)
    fp = _fingerprint()
    harness = _RecordingHarness()
    sessions: dict[str, Any] = {"oci": SimpleNamespace(tool_names=[])}
    spec = {"provider": "openai", "model": "text-embedding-3-large", "dimension": 3072}

    runner = AgentRunner(
        harness=harness,
        pool_sessions=sessions,
        embedder_spec=spec,
        config=cfg,
        env=fp,
        model_snapshot_id="snap-X",
        model_provider="anthropic",
        oracle_version="pass_v1.py@sha256:deadbeef",
        harness_version="harness-Y",
    )

    cell = _cell(cfg.model, run_id="run-A")
    q = _query(query_id="q42", quartile="q3")
    asyncio.run(runner.run_trial(cell, q))

    assert len(harness.inputs) == 1
    inputs = harness.inputs[0]
    assert inputs.run_id == "run-A"
    assert inputs.trial_id == cell.trial_id
    assert inputs.cell_id == cell.cell_id
    assert inputs.task_id == "q42"
    assert inputs.task_difficulty == "medium"  # q3 → medium
    assert inputs.task_query == q.text
    assert inputs.primary_server == "oci"
    assert inputs.model_snapshot_id == "snap-X"
    assert inputs.model_provider == "anthropic"
    assert inputs.harness_version == "harness-Y"
    assert inputs.oracle_version == "pass_v1.py@sha256:deadbeef"
    assert inputs.env is fp
    assert inputs.sessions is sessions
    assert inputs.embedder_spec == spec
    assert inputs.retriever_top_k == cfg.retriever_top_k
    assert inputs.padding_corpus_path == cfg.padding_corpus
    assert inputs.cell_seed == cell.cell_seed
    # seed is the int prefix of the trial seed
    assert inputs.seed == int(cell.trial_seed[:8], 16)


def test_agent_runner_propagates_retriever_top_k(tmp_path: Path):
    cfg = _build_config(tmp_path)
    cfg = cfg.model_copy(update={"retriever_top_k": 11, "tool_listing_strategy": "retriever-on"})
    runner = AgentRunner(
        harness=_RecordingHarness(),
        pool_sessions={},
        embedder_spec={"provider": "openai", "model": "m", "dimension": 1},
        config=cfg,
        env=_fingerprint(),
        model_snapshot_id="snap",
        model_provider="anthropic",
        oracle_version="v",
        harness_version="h",
    )
    inputs = runner._build_inputs(_cell(cfg.model), _query())
    assert inputs.retriever_top_k == 11
    assert inputs.tool_listing_strategy == "retriever-on"


# ---------------------------------------------------------------------------
# Default factories
# ---------------------------------------------------------------------------


def test_default_agent_factory_resolves_endpoint_once(tmp_path: Path):
    cfg = _build_config(tmp_path)
    factory = make_default_agent_factory(cfg, env=_fingerprint())
    a = factory({"oci": SimpleNamespace(tool_names=[])}, {"provider": "openai"})
    b = factory({"oci": SimpleNamespace(tool_names=[])}, {"provider": "openai"})
    assert isinstance(a, AgentRunner)
    assert isinstance(b, AgentRunner)
    # Both runners agree on the resolved model snapshot.
    assert a._model_snapshot_id == b._model_snapshot_id
    assert a._model_provider == "anthropic"


def test_default_agent_factory_fails_loud_on_missing_model(tmp_path: Path):
    cfg = _build_config(tmp_path, model_id="claude-A")
    cfg = cfg.model_copy(update={"model": "claude-missing"})
    with pytest.raises(EndpointResolutionError, match="not pinned"):
        make_default_agent_factory(cfg, env=_fingerprint())


def test_default_agent_factory_retriever_off_skips_embedder_build(tmp_path: Path):
    cfg = _build_config(tmp_path, strategy="full")
    with patch("tcrun.runner.make_embedder") as mk:
        make_default_agent_factory(cfg, env=_fingerprint())
        mk.assert_not_called()


def test_default_agent_factory_retriever_on_prebuilds_embedder(tmp_path: Path):
    cfg = _build_config(tmp_path, strategy="retriever-on")
    with patch("tcrun.runner.make_embedder") as mk:
        mk.return_value = SimpleNamespace(provider="openai")
        make_default_agent_factory(cfg, env=_fingerprint())
        mk.assert_called_once()


def test_default_agent_factory_retriever_on_propagates_build_failure(tmp_path: Path):
    cfg = _build_config(tmp_path, strategy="retriever-on")
    def _boom(spec):
        raise RuntimeError("no OPENAI_API_KEY")
    with patch("tcrun.runner.make_embedder", side_effect=_boom):
        with pytest.raises(RuntimeError, match="no OPENAI_API_KEY"):
            make_default_agent_factory(cfg, env=_fingerprint())


def test_default_pool_factory_yields_sessions(tmp_path: Path):
    cfg = _build_config(tmp_path)
    pool_factory = make_default_pool_factory(cfg)

    # Patch ServerPoolManager so we don't try to launch real MCP subprocesses.
    class _FakeManager:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def start(self, names):
            return {n: SimpleNamespace(name=n, tool_names=[]) for n in names}

    with patch("tcrun.runner.ServerPoolManager", _FakeManager):
        async def _drive():
            async with pool_factory(["oci", "fs"]) as sessions:
                return sessions
        sessions = asyncio.run(_drive())

    assert set(sessions) == {"oci", "fs"}
    assert sessions["oci"].name == "oci"


# ---------------------------------------------------------------------------
# Orchestrator + default factories end-to-end (mocked harness)
# ---------------------------------------------------------------------------


def test_orchestrator_with_defaults_dispatches(tmp_path: Path):
    cfg = _build_config(tmp_path)
    queries = [_query()]
    env = _fingerprint()
    harness = _RecordingHarness()

    # We want the orchestrator to use the default factories, but the harness
    # they construct must be our recording double so no API calls fire.
    real_factory = make_default_agent_factory(cfg, env=env)
    captured_runners: list[AgentRunner] = []

    def wrapping_factory(pool, spec):
        runner = real_factory(pool, spec)
        runner._harness = harness  # swap in the recorder
        captured_runners.append(runner)
        return runner

    # Pool factory yields a fixed session dict; no subprocess work.
    async def _drive():
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _pool(names):
            yield {n: SimpleNamespace(tool_names=[]) for n in names}

        orch = Orchestrator(
            cfg,
            queries=queries,
            pool_factory=_pool,
            agent_factory=wrapping_factory,
        )
        # Manually drive the harness output through the trial pipeline; the
        # recorder returns a SimpleNamespace that the orchestrator reads
        # `.cost_usd` and `.trial_id` from. Patch the writer + checkpoint
        # path so we don't need to validate Trial rows in this seam.
        with patch("tcrun.orchestrator.ResultWriter") as RW:
            RW.return_value.write = lambda t: None
            RW.return_value.close = lambda: None
            return await orch.run()

    summary = asyncio.run(_drive())
    assert summary["n_cells"] > 0
    # Every cell should have driven the recorder once.
    assert len(harness.inputs) == summary["n_cells"]
    # Every input should carry the run-scoped embedder_spec from the orchestrator.
    for inputs in harness.inputs:
        assert inputs.embedder_spec is not None
        assert inputs.embedder_spec["provider"] == "openai"
        assert inputs.env is env


def test_orchestrator_run_without_factories_halts(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[_query()])
    with pytest.raises(OrchestratorHalt, match="must inject both"):
        asyncio.run(orch.run())
