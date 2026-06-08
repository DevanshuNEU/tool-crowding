"""Tests for tcrun.tasks — Query schema validation + JSONL loader edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tcrun.tasks import Query, TaskLoader, TaskLoadError, load_tasks


def _valid_record(**overrides) -> dict:
    rec = {
        "query_id": "v1-pub-001",
        "tier": "public",
        "text": "find the function that parses YAML config files",
        "ground_truth_target": "load_config",
        "ground_truth_code": "def load_config(path):\n    return yaml.safe_load(open(path))",
        "source_repo": "octocat/hello-world",
        "source_publication_date": "2026-02-15",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q2",
        "primary_server": "oci",
        "fivegram_audit": [{"ngram": "load yaml safe config file", "github_hits": 0, "web_hits": 1}],
    }
    rec.update(overrides)
    return rec


def test_query_schema_accepts_valid_record():
    q = Query.model_validate(_valid_record())
    assert q.query_id == "v1-pub-001"
    assert q.tier == "public"
    assert q.fivegram_audit[0].github_hits == 0


def test_query_schema_rejects_bad_tier():
    with pytest.raises(Exception):
        Query.model_validate(_valid_record(tier="not_a_real_tier"))


def test_query_schema_rejects_bad_license():
    with pytest.raises(Exception):
        Query.model_validate(_valid_record(source_license="MIT"))


def test_loader_returns_empty_list_on_empty_file(tmp_path: Path):
    p = tmp_path / "queries.jsonl"
    p.write_text("", encoding="utf-8")
    assert load_tasks(p) == []


def test_loader_skips_blank_lines(tmp_path: Path):
    p = tmp_path / "queries.jsonl"
    line = json.dumps(_valid_record())
    p.write_text(f"\n{line}\n\n", encoding="utf-8")
    qs = load_tasks(p)
    assert len(qs) == 1


def test_loader_loads_multiple_valid_records(tmp_path: Path):
    p = tmp_path / "queries.jsonl"
    lines = [
        json.dumps(_valid_record(query_id="v1-pub-001")),
        json.dumps(_valid_record(query_id="v1-pub-002", difficulty_quartile="q3")),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    qs = load_tasks(p)
    assert [q.query_id for q in qs] == ["v1-pub-001", "v1-pub-002"]


def test_loader_raises_on_invalid_json(tmp_path: Path):
    p = tmp_path / "queries.jsonl"
    p.write_text("{not valid json\n", encoding="utf-8")
    with pytest.raises(TaskLoadError, match="invalid JSON"):
        load_tasks(p)


def test_loader_raises_on_schema_violation(tmp_path: Path):
    p = tmp_path / "queries.jsonl"
    bad = _valid_record()
    del bad["ground_truth_target"]
    p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(TaskLoadError, match="schema validation failed"):
        load_tasks(p)


def test_loader_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        TaskLoader(tmp_path / "does_not_exist.jsonl").load()


def test_loader_real_v1_path_smoke():
    """Smoke test: the live `tasks/v1/queries.jsonl` loads cleanly into Query
    objects via the production schema. Row count is intentionally not asserted
    (it grows per batch). Empty-file behavior is covered by
    `test_loader_returns_empty_list_on_empty_file`."""
    real_path = Path(__file__).resolve().parents[1] / "tasks" / "v1" / "queries.jsonl"
    if not real_path.exists():
        pytest.skip("tasks/v1/queries.jsonl not present in this checkout")
    qs = load_tasks(real_path)
    assert isinstance(qs, list)
    assert all(isinstance(q, Query) for q in qs)
    assert all(q.query_id.startswith("v1-") for q in qs)
