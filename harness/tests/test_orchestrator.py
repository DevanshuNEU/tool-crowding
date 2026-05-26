"""Tests for tcrun.orchestrator — cell enumeration, checkpoint, cost monitor.

Mocks ServerPoolManager + AgentHarness with thin async test doubles so we can
verify dispatch + checkpoint behavior without booting real MCP subprocesses.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from tcrun.config import Config
from tcrun.orchestrator import (
    CellSpec,
    CostCapExceeded,
    Orchestrator,
    OrchestratorHalt,
)
from tcrun.results import (
    CURRENT_SCHEMA_VERSION,
    EnvFingerprintRef,
    SamplingParams,
    ServerEntry,
    Trial,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _write_artifact(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _build_config(tmp_path: Path) -> Config:
    return Config(
        task_set=_write_artifact(tmp_path / "queries.jsonl", "{}"),
        oracle=_write_artifact(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True"),
        servers_pinned=_write_artifact(tmp_path / "servers.yaml", "{}"),
        descriptions=_write_artifact(tmp_path / "descriptions.json", "{}"),
        endpoints=_write_artifact(tmp_path / "endpoints.json", "{}"),
        environment=_write_artifact(tmp_path / "environment.lock", "py=3.11"),
        padding_corpus=_write_artifact(tmp_path / "corpus.jsonl", "{}"),
        embedder=_write_artifact(tmp_path / "embedder.json", '{"provider":"openai","model":"text-embedding-3-large","dimension":3072}'),
        primary_servers=["oci"],
        distractors=["fs", "mem", "time", "seq", "sqlite"],
        N=[1, 5],
        runs_per_cell=1,
        model="claude-sonnet-4-6-20260131",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
        include_padded_n1_control=True,
    )


def _make_trial(cell: CellSpec, *, cost_usd: float = 0.01) -> Trial:
    return Trial.model_validate({
        "schema_version": CURRENT_SCHEMA_VERSION,
        "harness_version": "test",
        "run_id": cell.run_id,
        "cell_id": cell.cell_id,
        "trial_id": cell.trial_id,
        "started_at": datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 5, 23, 12, 1, tzinfo=timezone.utc),
        "task_id": cell.query_id,
        "task_version": "v1",
        "task_difficulty": "easy",
        "model_id": "claude-sonnet-4-6",
        "model_provider": "anthropic",
        "model_snapshot_id": cell.model,
        "sampling_params": SamplingParams(),
        "server_set": [ServerEntry(
            server_name=cell.primary_server, server_version="v",
            tool_count=1, description_tokens=10,
        )],
        "N": cell.N,
        "primary_server": cell.primary_server,
        "ordering_seed": cell.ordering_seed,
        "tool_listing_strategy": "full",
        "pass_criterion_id": "v1",
        "context_input_tokens": 100,
        "context_output_tokens": 10,
        "tool_calls": [],
        "first_correct_tool_step": None,
        "pass": True,
        "error_type": "none",
        "cost_usd": cost_usd,
        "trace_path": "/dev/null",
        "seed": 42,
        "oracle_version": "v1",
        "env": EnvFingerprintRef(
            os="x", python_version="3.11", package_hash="p", machine_id="m", git_sha="g",
        ),
        "is_padded_n1": cell.is_padded_n1,
    })


class _FakePool:
    """Async context manager that mimics ServerPoolManager(server_names)."""

    def __init__(self, server_names):
        self.server_names = server_names

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def smoke_test(self):
        return None


class _FakeAgent:
    """AgentHarness double; run_trial returns a synthesized Trial."""

    def __init__(self, pool, *, cost_usd: float = 0.01, fail: bool = False):
        self.pool = pool
        self.cost_usd = cost_usd
        self.fail = fail
        self.calls = 0

    async def run_trial(self, cell: CellSpec, query):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic harness bug")
        return _make_trial(cell, cost_usd=self.cost_usd)


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_enumerate_cells_includes_padded_control(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    cells = orch.enumerate_cells()
    # 1 primary x 2 N x 1 query x 5 orderings x 1 rep + padded control at N=1
    # = 10 base + 5 padded = 15.
    padded = [c for c in cells if c.is_padded_n1]
    assert len(padded) == 5
    base = [c for c in cells if not c.is_padded_n1]
    assert len(base) == 10


def test_cell_id_is_deterministic(tmp_path: Path):
    c = CellSpec(run_id="r", model="m", N=1, query_id="q", primary_server="p",
                 ordering_seed=0, repetition_id=0)
    assert c.cell_id == CellSpec(run_id="r", model="m", N=1, query_id="q",
                                 primary_server="p", ordering_seed=0,
                                 repetition_id=0).cell_id


def test_checkpoint_roundtrip(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    orch.checkpoint.completed_trial_ids.add("t-abc")
    orch.checkpoint.running_cost_usd = 1.23
    orch._save_checkpoint()
    # Re-instantiate and verify resume state.
    orch2 = Orchestrator(cfg, run_dir=orch.run_dir, queries=[SimpleNamespace(query_id="q1")])
    assert "t-abc" in orch2.checkpoint.completed_trial_ids
    assert orch2.checkpoint.running_cost_usd == pytest.approx(1.23)


def test_checkpoint_run_id_mismatch_halts(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    orch.checkpoint_path.write_text(
        json.dumps({"run_id": "wrong", "completed_trial_ids": []}), encoding="utf-8"
    )
    with pytest.raises(OrchestratorHalt, match="run_id mismatch"):
        Orchestrator(cfg, run_dir=orch.run_dir, queries=[SimpleNamespace(query_id="q1")])


def test_run_dispatches_via_injected_factories(tmp_path: Path):
    cfg = _build_config(tmp_path)
    agents: list[_FakeAgent] = []

    def agent_factory(pool, embedder_spec):
        # Real agent_factories must propagate embedder_spec into
        # TrialInputs.embedder_spec; this fake just records that the
        # orchestrator delivered it (asserted below).
        a = _FakeAgent(pool, cost_usd=0.001)
        a.received_embedder_spec = embedder_spec
        agents.append(a)
        return a

    orch = Orchestrator(
        cfg,
        queries=[SimpleNamespace(query_id="q1")],
        pool_factory=lambda names: _FakePool(names),
        agent_factory=agent_factory,
        concurrency=4,
    )
    summary = asyncio.run(orch.run())
    cells = orch.enumerate_cells()
    assert summary["n_completed"] == len(cells)
    # Each cell counted once; checkpoint persisted.
    assert orch.checkpoint_path.exists()
    assert len(orch.checkpoint.completed_trial_ids) == len(cells)
    # Orchestrator must have threaded embedder_spec into every agent.
    assert agents, "factory was never called"
    for a in agents:
        assert a.received_embedder_spec["provider"] == "openai"
        assert a.received_embedder_spec["dimension"] == 3072


def test_resume_skips_completed_trials(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(
        cfg,
        queries=[SimpleNamespace(query_id="q1")],
        pool_factory=lambda names: _FakePool(names),
        agent_factory=lambda pool, _spec: _FakeAgent(pool, cost_usd=0.001),
    )
    asyncio.run(orch.run())
    n_first = orch.checkpoint.running_cost_usd

    # Second invocation: same run_dir, factories see zero new calls.
    agents: list[_FakeAgent] = []

    def factory(pool, _embedder_spec):
        a = _FakeAgent(pool, cost_usd=0.001)
        agents.append(a)
        return a

    orch2 = Orchestrator(
        cfg,
        run_dir=orch.run_dir,
        queries=[SimpleNamespace(query_id="q1")],
        pool_factory=lambda names: _FakePool(names),
        agent_factory=factory,
    )
    asyncio.run(orch2.run())
    # No new trials should have run.
    assert sum(a.calls for a in agents) == 0
    assert orch2.checkpoint.running_cost_usd == pytest.approx(n_first)


def test_cost_cap_halts_run(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(
        cfg,
        queries=[SimpleNamespace(query_id="q1")],
        pool_factory=lambda names: _FakePool(names),
        agent_factory=lambda pool, _spec: _FakeAgent(pool, cost_usd=1.0),
        concurrency=1,
        cost_cap_usd=2.5,
    )
    with pytest.raises(CostCapExceeded):
        asyncio.run(orch.run())
    # Cost recorded above cap; some trials completed before the halt.
    assert orch.checkpoint.running_cost_usd > 2.5


def test_uncategorized_exception_halts(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(
        cfg,
        queries=[SimpleNamespace(query_id="q1")],
        pool_factory=lambda names: _FakePool(names),
        agent_factory=lambda pool, _spec: _FakeAgent(pool, fail=True),
        concurrency=1,
    )
    with pytest.raises(OrchestratorHalt):
        asyncio.run(orch.run())


def test_server_names_for_group_n1(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    cell = CellSpec(run_id=orch.run_id, model=cfg.model, N=1, query_id="q1",
                    primary_server="oci", ordering_seed=0, repetition_id=0)
    assert orch._server_names_for_group(cell) == ["oci"]


def test_server_names_for_group_n5_deterministic(tmp_path: Path):
    cfg = _build_config(tmp_path)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    cell = CellSpec(run_id=orch.run_id, model=cfg.model, N=5, query_id="q1",
                    primary_server="oci", ordering_seed=0, repetition_id=0)
    first = orch._server_names_for_group(cell)
    second = orch._server_names_for_group(cell)
    assert first == second
    assert first[0] == "oci"
    assert len(first) == 5
