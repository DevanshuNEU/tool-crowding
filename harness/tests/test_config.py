"""Tests for tcrun.config — embedder env override + run_id chain integration.

Covers the 2026-05-25 v1.2 schema bump: embedder is the 8th path-typed
field, content-hashed into run_id; TC_EMBEDDER env var overrides the YAML
pin at load time without editing the committed config.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tcrun.config import (
    EMBEDDER_ALIASES,
    Config,
    _resolve_embedder_env,
    compute_run_id,
    load_config,
)


# ---------------------------------------------------------------------------
# Embedder alias resolver
# ---------------------------------------------------------------------------


def test_embedder_alias_voyage_resolves_to_pin_path():
    assert _resolve_embedder_env("voyage") == "models/embedder.voyage.json"
    assert _resolve_embedder_env("voyageai") == "models/embedder.voyage.json"


def test_embedder_alias_bge_resolves_to_pin_path():
    assert _resolve_embedder_env("bge") == "models/embedder.bge-m3.json"
    assert _resolve_embedder_env("bge-m3") == "models/embedder.bge-m3.json"


def test_embedder_alias_openai_resolves_to_default_pin():
    assert _resolve_embedder_env("openai") == "models/embedder.json"


def test_embedder_alias_passes_through_literal_path():
    """Non-alias values are treated as literal paths (escape hatch)."""
    assert _resolve_embedder_env("models/embedder.custom.json") == "models/embedder.custom.json"


def test_embedder_alias_warns_on_suspicious_value(capsys):
    """Typo'd aliases (no path-shape) should warn on stderr."""
    out = _resolve_embedder_env("voyage-ai")  # typo: meant `voyage`
    assert out == "voyage-ai"  # still falls through to literal path
    captured = capsys.readouterr()
    assert "matches no known alias" in captured.err
    assert "voyage-ai" in captured.err


def test_embedder_alias_literal_path_does_not_warn(capsys):
    """A path-shaped value (has `/` or .json) is a legitimate literal — no warning."""
    _resolve_embedder_env("models/embedder.custom.json")
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_embedder_alias_resolution_is_case_insensitive():
    assert _resolve_embedder_env("VOYAGE") == EMBEDDER_ALIASES["voyage"]
    assert _resolve_embedder_env(" Voyage ") == EMBEDDER_ALIASES["voyage"]


# ---------------------------------------------------------------------------
# load_config + TC_EMBEDDER env override
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, embedder_value: str = "models/embedder.json") -> Path:
    """Write a minimal-but-valid mve.yaml-shaped config for load_config tests."""
    body = f"""\
task_set: t.jsonl
oracle: o.py
servers_pinned: s.yaml
descriptions: d.json
endpoints: e.json
environment: env.lock
padding_corpus: c.jsonl
embedder: {embedder_value}
primary_servers: [oci]
distractors: [fs]
N: [1]
runs_per_cell: 1
model: claude-sonnet-4-6-20260131
host: claude-desktop
seed: 42
out: out/
"""
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_default_uses_yaml_embedder(tmp_path: Path, monkeypatch):
    cfg_path = _write_yaml(tmp_path / "mve.yaml")
    monkeypatch.delenv("TC_EMBEDDER", raising=False)
    cfg = load_config(cfg_path)
    assert str(cfg.embedder) == "models/embedder.json"


def test_load_config_env_override_alias_voyage(tmp_path: Path, monkeypatch):
    cfg_path = _write_yaml(tmp_path / "mve.yaml")
    monkeypatch.setenv("TC_EMBEDDER", "voyage")
    cfg = load_config(cfg_path)
    assert str(cfg.embedder) == "models/embedder.voyage.json"


def test_load_config_env_override_alias_bge(tmp_path: Path, monkeypatch):
    cfg_path = _write_yaml(tmp_path / "mve.yaml")
    monkeypatch.setenv("TC_EMBEDDER", "bge")
    cfg = load_config(cfg_path)
    assert str(cfg.embedder) == "models/embedder.bge-m3.json"


def test_load_config_env_override_literal_path(tmp_path: Path, monkeypatch):
    cfg_path = _write_yaml(tmp_path / "mve.yaml")
    monkeypatch.setenv("TC_EMBEDDER", "models/custom-embedder.json")
    cfg = load_config(cfg_path)
    assert str(cfg.embedder) == "models/custom-embedder.json"


# ---------------------------------------------------------------------------
# PATH_FIELDS + run_id chain
# ---------------------------------------------------------------------------


def test_path_fields_includes_embedder():
    """The embedder is the 8th content-hashed artifact per REPRODUCIBILITY.md §1."""
    assert "embedder" in Config.PATH_FIELDS
    assert len(Config.PATH_FIELDS) == 8


def _write_blob(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _build_cfg(tmp_path: Path, *, embedder_blob: str) -> Config:
    return Config(
        task_set=_write_blob(tmp_path / "t.jsonl"),
        oracle=_write_blob(tmp_path / "o.py"),
        servers_pinned=_write_blob(tmp_path / "s.yaml"),
        descriptions=_write_blob(tmp_path / "d.json"),
        endpoints=_write_blob(tmp_path / "e.json"),
        environment=_write_blob(tmp_path / "env.lock"),
        padding_corpus=_write_blob(tmp_path / "c.jsonl"),
        embedder=_write_blob(tmp_path / "embedder.json", embedder_blob),
        primary_servers=["oci"],
        distractors=["fs"],
        N=[1],
        runs_per_cell=1,
        model="claude-sonnet-4-6-20260131",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
    )


def test_run_id_changes_when_embedder_pin_content_changes(tmp_path: Path):
    """Swapping the embedder pin file's content must produce a new run_id.

    This is the load-bearing reproducibility property: a Voyage run and an
    OpenAI run cannot share a run_id, even if every other artifact is identical.
    """
    cfg_a = _build_cfg(tmp_path / "a", embedder_blob='{"provider":"openai","model":"text-embedding-3-large","dimension":3072}')
    cfg_b = _build_cfg(tmp_path / "b", embedder_blob='{"provider":"voyageai","model":"voyage-3-large","dimension":1024}')
    run_id_a = compute_run_id(cfg_a)
    run_id_b = compute_run_id(cfg_b)
    assert run_id_a != run_id_b


def test_run_id_is_deterministic_for_same_config(tmp_path: Path):
    cfg = _build_cfg(tmp_path, embedder_blob='{"provider":"openai","model":"x","dimension":3072}')
    assert compute_run_id(cfg) == compute_run_id(cfg)
