"""Tests for tcrun.preflight — 6-gate verification chain.

Each gate is exercised in isolation to keep failure isolation tight.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tcrun.config import Config, compute_run_id
from tcrun.preflight import PreflightError, PreflightGate


def _make_corpus(path: Path, count: int = 60, *, collision_with: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(count):
            name = collision_with if (collision_with and i == 0) else f"FakeTool{i:03d}"
            fh.write(
                json.dumps(
                    {
                        "entry_id": f"ftc_{i:03d}",
                        "tool_name": name,
                        "description": f"placeholder {i}",
                        "input_schema": {"type": "object", "properties": {}, "required": []},
                        "domain_tag": "scheduling",
                        "description_tokens": {"claude-sonnet-4-6-20260131": 50},
                    }
                )
                + "\n"
            )
    return path


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _build_config(tmp_path: Path, *, corpus: Path | None = None) -> Config:
    return Config(
        task_set=_write(tmp_path / "queries.jsonl", "{}"),
        oracle=_write(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True"),
        servers_pinned=_write(tmp_path / "servers.yaml", "{}"),
        descriptions=_write(tmp_path / "descriptions.json", "{}"),
        endpoints=_write(tmp_path / "endpoints.json", "{}"),
        environment=_write(tmp_path / "environment.lock", "py=3.11"),
        padding_corpus=corpus or _make_corpus(tmp_path / "corpus.jsonl"),
        embedder=_write(tmp_path / "embedder.json", '{"provider":"openai","model":"text-embedding-3-large","dimension":3072}'),
        primary_servers=["oci"],
        distractors=["fs", "mem"],
        N=[1],
        runs_per_cell=1,
        model="claude-sonnet-4-6-20260131",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
    )


def test_all_gates_pass(tmp_path: Path):
    cfg = _build_config(tmp_path)
    report = PreflightGate(cfg).run()
    assert report.ok
    names = {g[0] for g in report.gates}
    assert names == {
        "artifact_hashes", "run_id_match", "smoke_test",
        "model_fingerprints", "trial_schema", "padding_corpus",
        "embedder",
    }


def test_artifact_hash_gate_fails_on_missing_path(tmp_path: Path):
    cfg = _build_config(tmp_path)
    Path(cfg.task_set).unlink()  # remove the queries file
    with pytest.raises(PreflightError):
        PreflightGate(cfg).run()


def test_run_id_gate_matches_release_json(tmp_path: Path):
    cfg = _build_config(tmp_path)
    release = tmp_path / "RELEASE.json"
    release.write_text(json.dumps({"run_id": compute_run_id(cfg)}), encoding="utf-8")
    report = PreflightGate(cfg, release_path=release).run()
    assert report.ok


def test_run_id_gate_halts_on_mismatch(tmp_path: Path):
    cfg = _build_config(tmp_path)
    release = tmp_path / "RELEASE.json"
    release.write_text(json.dumps({"run_id": "wrong-id"}), encoding="utf-8")
    with pytest.raises(PreflightError, match="run_id mismatch"):
        PreflightGate(cfg, release_path=release).run()


def test_smoke_test_gate_invokes_injected_callable(tmp_path: Path):
    cfg = _build_config(tmp_path)
    calls = {"n": 0}

    async def smoke():
        calls["n"] += 1

    report = PreflightGate(cfg, pool_smoke_test=smoke).run()
    assert report.ok
    assert calls["n"] == 1


def test_smoke_test_gate_halts_on_failure(tmp_path: Path):
    cfg = _build_config(tmp_path)

    async def smoke():
        raise RuntimeError("SHA drift")

    with pytest.raises(PreflightError):
        PreflightGate(cfg, pool_smoke_test=smoke).run()


def test_model_fingerprint_gate_invokes_callable(tmp_path: Path):
    cfg = _build_config(tmp_path)
    seen: list[str] = []

    def check(model_id: str) -> bool:
        seen.append(model_id)
        return True

    report = PreflightGate(cfg, model_fingerprint_check=check).run()
    assert report.ok
    assert seen == [cfg.model]


# ----------------------------------------------------------------------
# Embedder gate (gate 7; added 2026-05-25 v1.2 schema bump)
# ----------------------------------------------------------------------


def test_embedder_gate_passes_for_valid_pin(tmp_path: Path):
    cfg = _build_config(tmp_path)
    report = PreflightGate(cfg).run()
    assert report.ok
    embedder_gate = [g for g in report.gates if g[0] == "embedder"][0]
    assert embedder_gate[1] is True
    assert "provider=openai" in embedder_gate[2]


def test_embedder_gate_fails_on_unknown_provider(tmp_path: Path):
    cfg = _build_config(tmp_path)
    Path(cfg.embedder).write_text(
        '{"provider":"cohere","model":"x","dimension":1024}', encoding="utf-8",
    )
    with pytest.raises(PreflightError):
        PreflightGate(cfg).run()


def test_embedder_gate_fails_on_bad_dimension(tmp_path: Path):
    cfg = _build_config(tmp_path)
    Path(cfg.embedder).write_text(
        '{"provider":"openai","model":"x","dimension":0}', encoding="utf-8",
    )
    with pytest.raises(PreflightError):
        PreflightGate(cfg).run()


def test_embedder_gate_fails_when_require_api_key_and_env_unset(tmp_path: Path, monkeypatch):
    cfg = _build_config(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PreflightError, match="OPENAI_API_KEY"):
        PreflightGate(cfg, embedder_require_api_key=True).run()


def test_embedder_gate_passes_when_require_api_key_and_env_set(tmp_path: Path, monkeypatch):
    cfg = _build_config(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-for-test")
    report = PreflightGate(cfg, embedder_require_api_key=True).run()
    assert report.ok
    embedder_gate = [g for g in report.gates if g[0] == "embedder"][0]
    assert "api_key ok" in embedder_gate[2]


def test_embedder_gate_skips_key_check_for_bge_local(tmp_path: Path, monkeypatch):
    """BGE provider is local — no API key required even with require_api_key=True."""
    cfg = _build_config(tmp_path)
    Path(cfg.embedder).write_text(
        '{"provider":"bge","model":"BAAI/bge-m3","dimension":1024}', encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = PreflightGate(cfg, embedder_require_api_key=True).run()
    assert report.ok
    embedder_gate = [g for g in report.gates if g[0] == "embedder"][0]
    assert "local" in embedder_gate[2]


def test_embedder_gate_rejects_placeholder_snapshot(tmp_path: Path):
    """A TBD-prefixed snapshot would lie in trial rows about what was actually computed."""
    cfg = _build_config(tmp_path)
    Path(cfg.embedder).write_text(
        '{"provider":"bge","model":"BAAI/bge-m3","dimension":1024,'
        '"snapshot":"TBD-safetensors-sha256"}',
        encoding="utf-8",
    )
    with pytest.raises(PreflightError, match="placeholder snapshot"):
        PreflightGate(cfg).run()


def test_model_fingerprint_gate_halts_when_unreachable(tmp_path: Path):
    cfg = _build_config(tmp_path)

    def check(model_id: str) -> bool:
        return False

    with pytest.raises(PreflightError, match="fingerprint unreachable"):
        PreflightGate(cfg, model_fingerprint_check=check).run()


def test_padding_corpus_gate_halts_on_collision(tmp_path: Path):
    """Corpus must not contain a tool_name that collides with SERVER_POOL names."""
    cfg = _build_config(
        tmp_path,
        corpus=_make_corpus(tmp_path / "corpus.jsonl", count=60, collision_with="oci"),
    )
    with pytest.raises(PreflightError):
        PreflightGate(cfg).run()


def test_padding_corpus_gate_halts_on_undersized_corpus(tmp_path: Path):
    cfg = _build_config(
        tmp_path,
        corpus=_make_corpus(tmp_path / "corpus.jsonl", count=10),
    )
    with pytest.raises(PreflightError):
        PreflightGate(cfg).run()
