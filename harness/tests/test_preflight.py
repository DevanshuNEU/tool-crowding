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
