"""Tests for the configurable `orderings` knob (added 2026-06-08).

Orderings was hardcoded to 5 in the orchestrator; it is now `Config.orderings`
(default 5), value-hashed into run_id, so an MVE can cut trial count by lowering it
(SPEC.md §5 sanctions 3 for an MVE) without touching code.
"""

from __future__ import annotations

from pathlib import Path

from tcrun.config import Config, compute_run_id
from tcrun.orchestrator import Orchestrator


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        task_set=_write(tmp_path / "queries.jsonl", "{}"),
        oracle=_write(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True"),
        servers_pinned=_write(tmp_path / "servers.yaml", "{}"),
        descriptions=_write(tmp_path / "descriptions.json", "{}"),
        endpoints=_write(tmp_path / "endpoints.json", "{}"),
        environment=_write(tmp_path / "environment.lock", "py=3.11"),
        padding_corpus=_write(tmp_path / "corpus.jsonl", "{}"),
        embedder=_write(tmp_path / "embedder.json", '{"provider":"openai","model":"x","dimension":3072}'),
        primary_servers=["oci"],
        distractors=["fs", "mem", "time", "seq", "sqlite"],
        N=[1, 5],
        runs_per_cell=1,
        model="claude-sonnet-4-6",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
        include_padded_n1_control=True,
    )
    base.update(overrides)
    return Config(**base)


def test_orderings_defaults_to_five(tmp_path: Path):
    """Omitting `orderings` preserves the pilot's 5-ordering structure."""
    cfg = _config(tmp_path)
    assert cfg.orderings == 5
    from types import SimpleNamespace
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    cells = orch.enumerate_cells()
    # 1 primary x 2 N x 5 orderings x 1 rep = 10 base + 5 padded (N=1) = 15.
    assert len([c for c in cells if not c.is_padded_n1]) == 10
    assert len([c for c in cells if c.is_padded_n1]) == 5


def test_lowering_orderings_cuts_cell_count(tmp_path: Path):
    """orderings=2 scales the base + padded cell counts linearly."""
    from types import SimpleNamespace
    cfg = _config(tmp_path, orderings=2)
    orch = Orchestrator(cfg, queries=[SimpleNamespace(query_id="q1")])
    cells = orch.enumerate_cells()
    # 1 primary x 2 N x 2 orderings x 1 rep = 4 base + 2 padded (N=1) = 6.
    assert len([c for c in cells if not c.is_padded_n1]) == 4
    assert len([c for c in cells if c.is_padded_n1]) == 2
    assert sorted({c.ordering_seed for c in cells}) == [0, 1]


def test_orderings_hashes_into_run_id(tmp_path: Path):
    """A different ordering count yields a distinct run_id (reproducibility-honest)."""
    cfg5 = _config(tmp_path, orderings=5)
    cfg2 = _config(tmp_path, orderings=2)
    assert compute_run_id(cfg5) != compute_run_id(cfg2)


def test_orderings_rejects_zero(tmp_path: Path):
    """orderings must be >= 1 (Field ge=1)."""
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _config(tmp_path, orderings=0)
