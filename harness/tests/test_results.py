"""Tests for tcrun.results — Trial schema, JSONL writer, schema dispatch.

Coverage targets per the prompt: schema validation, JSONL roundtrip,
schema_version dispatch (v1.0 + v1.1 read correctly).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from tcrun.results import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_VERSION_V1_0,
    SCHEMA_VERSION_V1_1,
    SCHEMA_VERSION_V1_2,
    SCHEMA_VERSION_V1_3,
    EnvFingerprintRef,
    ResultWriter,
    SamplingParams,
    ServerEntry,
    ToolCall,
    Trial,
    read_jsonl,
    write_trial,
)


def _make_trial(**overrides) -> Trial:
    base = dict(
        harness_version="abc123",
        run_id="r0",
        cell_id="c0",
        trial_id="t0",
        started_at=datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 23, 12, 1, tzinfo=timezone.utc),
        task_id="v1-pub-001",
        task_version="coir-v1",
        task_difficulty="medium",
        model_id="claude-sonnet-4-6",
        model_provider="anthropic",
        model_snapshot_id="claude-sonnet-4-6-20260315",
        sampling_params=SamplingParams(),
        server_set=[ServerEntry(server_name="oci", server_version="sha:abc",
                                tool_count=3, description_tokens=120)],
        N=1,
        primary_server="oci",
        ordering_seed=0,
        tool_listing_strategy="full",
        pass_criterion_id="symbol-plus-50pct-overlap-v1",
        context_input_tokens=2500,
        context_output_tokens=300,
        tool_calls=[ToolCall(step_idx=1, server_called="oci", tool_called="search",
                             args_hash="d3a", response_summary="ok", latency_ms=120)],
        first_correct_tool_step=1,
        error_type="none",
        cost_usd=0.05,
        trace_path="results/r0/traces/t0.jsonl",
        seed=42,
        oracle_version="pass_v1.py@sha256:abc",
        env=EnvFingerprintRef(os="Darwin", python_version="3.11.7",
                              package_hash="ph", machine_id="mid", git_sha="gs"),
    )
    base["pass"] = True
    base.update(overrides)
    return Trial.model_validate(base)


def test_current_schema_version_is_v1_3():
    assert CURRENT_SCHEMA_VERSION == SCHEMA_VERSION_V1_3


def test_trial_validates_happy_path():
    t = _make_trial()
    assert t.schema_version == SCHEMA_VERSION_V1_3
    # v1.3 lure-attribution defaults.
    assert t.solving_server is None
    assert t.tool_calls[0].result_contained_target is False
    assert t.is_padded_n1 is False
    assert t.fake_tool_invoked is False
    assert t.padding_skipped is None
    # v1.2 embedder fields default to the v1 primary (OpenAI text-embedding-3-large).
    assert t.embedder_provider == "openai"
    assert t.embedder_model == "text-embedding-3-large"
    assert t.embedder_dimension == 3072
    # `pass` is exposed via alias.
    assert t.model_dump(by_alias=True)["pass"] is True


def test_trial_rejects_missing_required_field():
    with pytest.raises(ValidationError):
        Trial.model_validate({"schema_version": "1.2"})  # everything else missing


def test_trial_rejects_bad_error_type():
    with pytest.raises(ValidationError):
        _make_trial(error_type="not_a_valid_enum_member")


def test_writer_roundtrips_single_record(tmp_path: Path):
    out = tmp_path / "results.jsonl"
    trial = _make_trial()
    write_trial(out, trial)
    loaded = list(read_jsonl(out))
    assert len(loaded) == 1
    assert loaded[0].trial_id == "t0"
    assert loaded[0].model_dump(by_alias=True)["pass"] is True


def test_writer_appends_multiple_records_with_fsync(tmp_path: Path):
    out = tmp_path / "results.jsonl"
    with ResultWriter(out) as w:
        w.write(_make_trial(trial_id="t0"))
        w.write(_make_trial(trial_id="t1", is_padded_n1=True))
    rows = list(read_jsonl(out))
    assert [r.trial_id for r in rows] == ["t0", "t1"]
    assert rows[1].is_padded_n1 is True


def test_reader_dispatches_v1_0_to_current_chain(tmp_path: Path):
    """v1.0 records ride the full migration chain to v1.2 with all defaults applied."""
    record = _make_trial().model_dump(by_alias=True, mode="json")
    record["schema_version"] = SCHEMA_VERSION_V1_0
    record.pop("is_padded_n1", None)
    record.pop("fake_tool_invoked", None)
    record.pop("padding_skipped", None)
    record.pop("embedder_provider", None)
    record.pop("embedder_model", None)
    record.pop("embedder_snapshot", None)
    record.pop("embedder_dimension", None)
    out = tmp_path / "results.jsonl"
    out.write_text(json.dumps(record) + "\n", encoding="utf-8")

    rows = list(read_jsonl(out))
    assert len(rows) == 1
    # Migrated forward through the full chain v1.0 → v1.1 → v1.2 → v1.3.
    assert rows[0].schema_version == SCHEMA_VERSION_V1_3
    assert rows[0].is_padded_n1 is False
    assert rows[0].fake_tool_invoked is False
    assert rows[0].padding_skipped is None
    assert rows[0].embedder_provider == "openai"
    assert rows[0].embedder_dimension == 3072
    assert rows[0].solving_server is None


def test_reader_dispatches_v1_1_to_v1_2_migration(tmp_path: Path):
    """v1.1 records hydrate with v1 primary embedder defaults."""
    record = _make_trial().model_dump(by_alias=True, mode="json")
    record["schema_version"] = SCHEMA_VERSION_V1_1
    record.pop("embedder_provider", None)
    record.pop("embedder_model", None)
    record.pop("embedder_snapshot", None)
    record.pop("embedder_dimension", None)
    out = tmp_path / "results.jsonl"
    out.write_text(json.dumps(record) + "\n", encoding="utf-8")

    rows = list(read_jsonl(out))
    assert rows[0].schema_version == SCHEMA_VERSION_V1_3
    assert rows[0].embedder_provider == "openai"
    assert rows[0].embedder_model == "text-embedding-3-large"
    assert rows[0].embedder_snapshot == "text-embedding-3-large"
    assert rows[0].embedder_dimension == 3072


def test_v1_3_attribution_fields_roundtrip(tmp_path: Path):
    """solving_server + per-call result_contained_target survive write/read."""
    calls = [
        ToolCall(step_idx=1, server_called="deepwiki", tool_called="ask_question",
                 args_hash="h1", response_summary="prose", latency_ms=80,
                 result_contained_target=False),
        ToolCall(step_idx=2, server_called="github_mcp", tool_called="get_file_contents",
                 args_hash="h2", response_summary="code", latency_ms=120,
                 result_contained_target=True),
    ]
    t = _make_trial(tool_calls=calls, solving_server="github_mcp")
    out = tmp_path / "results.jsonl"
    with ResultWriter(out) as w:
        w.write(t)
    rows = list(read_jsonl(out))
    assert rows[0].solving_server == "github_mcp"
    assert [c.result_contained_target for c in rows[0].tool_calls] == [False, True]


def test_reader_dispatches_v1_2_to_v1_3_migration(tmp_path: Path):
    """v1.2 records hydrate with solving_server=None and per-call default False."""
    record = _make_trial().model_dump(by_alias=True, mode="json")
    record["schema_version"] = SCHEMA_VERSION_V1_2
    record.pop("solving_server", None)
    for c in record["tool_calls"]:
        c.pop("result_contained_target", None)
    out = tmp_path / "results.jsonl"
    out.write_text(json.dumps(record) + "\n", encoding="utf-8")
    rows = list(read_jsonl(out))
    assert rows[0].schema_version == SCHEMA_VERSION_V1_3
    assert rows[0].solving_server is None
    assert all(c.result_contained_target is False for c in rows[0].tool_calls)


@pytest.mark.parametrize("legacy_value", ["rag-mcp", "mcp-zero"])
def test_reader_normalizes_legacy_tool_listing_strategy(legacy_value: str, tmp_path: Path):
    """Both legacy `rag-mcp` and `mcp-zero` map forward to `retriever-on`."""
    record = _make_trial().model_dump(by_alias=True, mode="json")
    record["schema_version"] = SCHEMA_VERSION_V1_1
    record["tool_listing_strategy"] = legacy_value
    record.pop("embedder_provider", None)
    out = tmp_path / "results.jsonl"
    out.write_text(json.dumps(record) + "\n", encoding="utf-8")

    rows = list(read_jsonl(out))
    assert rows[0].tool_listing_strategy == "retriever-on"


def test_reader_rejects_unsupported_schema_version(tmp_path: Path):
    record = _make_trial().model_dump(by_alias=True, mode="json")
    record["schema_version"] = "9.9"
    out = tmp_path / "results.jsonl"
    out.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema_version"):
        list(read_jsonl(out))


def test_reader_skips_blank_lines(tmp_path: Path):
    out = tmp_path / "results.jsonl"
    record = _make_trial().model_dump_json(by_alias=True)
    out.write_text(f"{record}\n\n{record}\n", encoding="utf-8")
    rows = list(read_jsonl(out))
    assert len(rows) == 2


def test_padding_flags_persist_through_roundtrip(tmp_path: Path):
    out = tmp_path / "results.jsonl"
    t = _make_trial(is_padded_n1=True, fake_tool_invoked=True, padding_skipped="budget_negative")
    write_trial(out, t)
    rows = list(read_jsonl(out))
    assert rows[0].is_padded_n1 is True
    assert rows[0].fake_tool_invoked is True
    assert rows[0].padding_skipped == "budget_negative"
