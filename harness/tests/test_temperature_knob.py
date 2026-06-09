"""Tests for the configurable `temperature` knob (added 2026-06-08 for Phase F).

Temperature was hardcoded to 0.0 (the SamplingParams default) in runner.py with no
config path. The Phase F confirmatory factorial requires temp=1.0 ("the effect needs
stochastic trajectories; temp=0 gave the deterministic 0-lure result"). It is now
`Config.temperature` (default 0.0), value-hashed into run_id, runtime-swappable via
TC_TEMPERATURE, and threaded into the per-trial SamplingParams (see test_runner.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from tcrun.config import Config, compute_run_id, load_config


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
        distractors=["fs", "mem"],
        N=[1],
        runs_per_cell=1,
        model="claude-sonnet-4-6",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
    )
    base.update(overrides)
    return Config(**base)


def _yaml_dict() -> dict:
    return dict(
        task_set="queries.jsonl", oracle="pass_v1.py", servers_pinned="servers.yaml",
        descriptions="descriptions.json", endpoints="endpoints.json",
        environment="environment.lock", padding_corpus="corpus.jsonl",
        embedder="embedder.json", primary_servers=["oci"], distractors=["fs"],
        N=[1], runs_per_cell=1, model="claude-sonnet-4-6", host="claude-desktop",
        out="out",
    )


def test_temperature_defaults_to_zero(tmp_path: Path):
    """Omitting temperature preserves the deterministic temp=0.0 default."""
    assert _config(tmp_path).temperature == 0.0


def test_temperature_is_settable(tmp_path: Path):
    assert _config(tmp_path, temperature=1.0).temperature == 1.0


def test_temperature_hashes_into_run_id(tmp_path: Path):
    """A different temperature yields a distinct run_id (reproducibility-honest)."""
    assert compute_run_id(_config(tmp_path, temperature=0.0)) != compute_run_id(
        _config(tmp_path, temperature=1.0)
    )


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_temperature_rejects_out_of_range(tmp_path: Path, bad: float):
    """temperature must be within [0.0, 1.0] (Anthropic rejects > 1.0 for Claude)."""
    with pytest.raises(ValidationError):
        _config(tmp_path, temperature=bad)


def test_tc_temperature_env_overrides_yaml(tmp_path: Path, monkeypatch):
    """TC_TEMPERATURE overrides the YAML value at load time."""
    cfg_yaml = _yaml_dict()
    cfg_yaml["temperature"] = 0.0
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(cfg_yaml), encoding="utf-8")
    monkeypatch.setenv("TC_TEMPERATURE", "1.0")
    assert load_config(p).temperature == 1.0


def test_tc_temperature_invalid_is_ignored(tmp_path: Path, monkeypatch):
    """A non-float TC_TEMPERATURE is ignored, falling back to the YAML value."""
    cfg_yaml = _yaml_dict()
    cfg_yaml["temperature"] = 0.5
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(cfg_yaml), encoding="utf-8")
    monkeypatch.setenv("TC_TEMPERATURE", "not-a-float")
    assert load_config(p).temperature == 0.5
