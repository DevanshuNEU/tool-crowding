"""Tests for tcrun.cli — Typer dispatch + subcommand wiring.

Uses Typer's CliRunner for invocation. Heavy paths (run/resume) are exercised
with --skip-preflight + mocked orchestrator state to avoid network/API.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from typer.testing import CliRunner

from tcrun.cli import app
from tcrun.config import compute_run_id, load_config
from tcrun.results import (
    CURRENT_SCHEMA_VERSION,
    EnvFingerprintRef,
    SamplingParams,
    ServerEntry,
    Trial,
    write_trial,
)


runner = CliRunner()


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_corpus(path: Path, count: int = 60) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(
                json.dumps(
                    {
                        "entry_id": f"ftc_{i:03d}",
                        "tool_name": f"FakeTool{i:03d}",
                        "description": f"placeholder {i}",
                        "input_schema": {"type": "object", "properties": {}, "required": []},
                        "domain_tag": "scheduling",
                        "description_tokens": {"claude-sonnet-4-6-20260131": 50},
                    }
                )
                + "\n"
            )
    return path


def _write_config(tmp_path: Path) -> Path:
    """Write a YAML config + all referenced artifacts. Returns path to config."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    _write(cfg_dir / "queries.jsonl", "{}")
    _write(cfg_dir / "pass_v1.py", "def pass_criterion(*a): return True")
    _write(cfg_dir / "servers.yaml", "{}")
    _write(cfg_dir / "descriptions.json", "{}")
    _write(cfg_dir / "endpoints.json", "{}")
    _write(cfg_dir / "environment.lock", "py=3.11")
    _write(cfg_dir / "embedder.json",
           '{"provider":"openai","model":"text-embedding-3-large","dimension":3072}')
    _make_corpus(cfg_dir / "corpus.jsonl")
    cfg_path = cfg_dir / "mve.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "task_set": str(cfg_dir / "queries.jsonl"),
                "oracle": str(cfg_dir / "pass_v1.py"),
                "servers_pinned": str(cfg_dir / "servers.yaml"),
                "descriptions": str(cfg_dir / "descriptions.json"),
                "endpoints": str(cfg_dir / "endpoints.json"),
                "environment": str(cfg_dir / "environment.lock"),
                "padding_corpus": str(cfg_dir / "corpus.jsonl"),
                "embedder": str(cfg_dir / "embedder.json"),
                "primary_servers": ["oci"],
                "distractors": ["fs", "mem"],
                "N": [1],
                "runs_per_cell": 1,
                "model": "claude-sonnet-4-6-20260131",
                "host": "claude-desktop",
                "seed": 42,
                "out": str(tmp_path / "out"),
                "include_padded_n1_control": False,
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def test_runid_subcommand(tmp_path: Path):
    cfg_path = _write_config(tmp_path)
    result = runner.invoke(app, ["runid", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.stdout
    cfg = load_config(cfg_path)
    assert compute_run_id(cfg) in result.stdout


def test_validate_subcommand(tmp_path: Path):
    cfg_path = _write_config(tmp_path)
    result = runner.invoke(app, ["validate", "--config", str(cfg_path)])
    assert result.exit_code == 0, result.stdout
    out = json.loads(result.stdout)
    assert "run_id" in out
    assert "artifact_hashes" in out["gates"]


def _patch_run_internals(monkeypatch):
    """Stub the heavy run() collaborators so we can assert CLI wiring only."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("tcrun.cli.load_tasks", lambda *a, **k: [])
    monkeypatch.setattr("tcrun.cli.make_default_pool_factory", lambda *a, **k: MagicMock())
    monkeypatch.setattr("tcrun.cli.make_default_agent_factory", lambda *a, **k: MagicMock())
    monkeypatch.setattr("tcrun.cli.asyncio.run", lambda *a, **k: {"run_id": "stub"})
    orch = MagicMock()
    monkeypatch.setattr("tcrun.cli.Orchestrator", orch)
    return orch


def test_run_cost_cap_flag_reaches_orchestrator(tmp_path: Path, monkeypatch):
    cfg_path = _write_config(tmp_path)
    orch = _patch_run_internals(monkeypatch)
    result = runner.invoke(
        app, ["run", "--config", str(cfg_path), "--skip-preflight", "--cost-cap", "0.5"]
    )
    assert result.exit_code == 0, result.stdout
    assert orch.call_args.kwargs["cost_cap_usd"] == 0.5


def test_run_cost_cap_defaults_to_none_when_omitted(tmp_path: Path, monkeypatch):
    cfg_path = _write_config(tmp_path)
    orch = _patch_run_internals(monkeypatch)
    result = runner.invoke(app, ["run", "--config", str(cfg_path), "--skip-preflight"])
    assert result.exit_code == 0, result.stdout
    assert orch.call_args.kwargs["cost_cap_usd"] is None


def test_status_subcommand_reads_checkpoint(tmp_path: Path):
    """status walks results/<exp>/<run_id>/checkpoint.json layout."""
    run_id = "abc123"
    with runner.isolated_filesystem():
        run_dir = Path("results") / "exp" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "checkpoint.json").write_text(
            json.dumps(
                {"run_id": run_id, "completed_trial_ids": ["t1", "t2"], "running_cost_usd": 0.5}
            ),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["status", run_id])
        assert result.exit_code == 0, result.stdout
        out = json.loads(result.stdout)
        assert out["n_completed"] == 2


def test_status_subcommand_missing_run_errors(tmp_path: Path):
    with runner.isolated_filesystem():
        Path("results").mkdir()
        result = runner.invoke(app, ["status", "no-such-run"])
        assert result.exit_code != 0


def test_verify_subcommand_validates_trials(tmp_path: Path):
    """`tcrun verify` re-validates a sample of trials' schema."""
    run_id = "abc123"
    with runner.isolated_filesystem() as fs:
        run_dir = Path(fs) / "results" / "exp" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        # Write 2 valid Trial records.
        for i in range(2):
            trial = Trial.model_validate({
                "schema_version": CURRENT_SCHEMA_VERSION,
                "harness_version": "test",
                "run_id": run_id,
                "cell_id": f"c{i}",
                "trial_id": f"t{i}",
                "started_at": datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 5, 23, 12, 1, tzinfo=timezone.utc),
                "task_id": "q1",
                "task_version": "v1",
                "task_difficulty": "easy",
                "model_id": "claude-sonnet-4-6",
                "model_provider": "anthropic",
                "model_snapshot_id": "x",
                "sampling_params": SamplingParams(),
                "server_set": [ServerEntry(
                    server_name="oci", server_version="v",
                    tool_count=1, description_tokens=10,
                )],
                "N": 1,
                "primary_server": "oci",
                "ordering_seed": 0,
                "tool_listing_strategy": "full",
                "pass_criterion_id": "v1",
                "context_input_tokens": 100,
                "context_output_tokens": 10,
                "tool_calls": [],
                "first_correct_tool_step": None,
                "pass": True,
                "error_type": "none",
                "cost_usd": 0.01,
                "trace_path": "/dev/null",
                "seed": 42,
                "oracle_version": "v1",
                "env": EnvFingerprintRef(
                    os="x", python_version="3.11", package_hash="p",
                    machine_id="m", git_sha="g",
                ),
            })
            write_trial(run_dir / "trials.jsonl", trial)
        result = runner.invoke(app, ["verify", run_id])
        assert result.exit_code == 0, result.stdout
        out = json.loads(result.stdout)
        assert out["verified"] == 2


def test_reproduce_subcommand_finds_trial(tmp_path: Path):
    run_id = "abc"
    trial_id = "trial_xyz"
    with runner.isolated_filesystem() as fs:
        run_dir = Path(fs) / "results" / run_id
        run_dir.mkdir(parents=True)
        trial = Trial.model_validate({
            "schema_version": CURRENT_SCHEMA_VERSION,
            "harness_version": "test",
            "run_id": run_id,
            "cell_id": "c",
            "trial_id": trial_id,
            "started_at": datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc),
            "finished_at": datetime(2026, 5, 23, 12, 1, tzinfo=timezone.utc),
            "task_id": "q",
            "task_version": "v1",
            "task_difficulty": "easy",
            "model_id": "claude-sonnet-4-6",
            "model_provider": "anthropic",
            "model_snapshot_id": "x",
            "sampling_params": SamplingParams(),
            "server_set": [ServerEntry(
                server_name="oci", server_version="v",
                tool_count=1, description_tokens=10,
            )],
            "N": 1,
            "primary_server": "oci",
            "ordering_seed": 0,
            "tool_listing_strategy": "full",
            "pass_criterion_id": "v1",
            "context_input_tokens": 100,
            "context_output_tokens": 10,
            "tool_calls": [],
            "first_correct_tool_step": None,
            "pass": True,
            "error_type": "none",
            "cost_usd": 0.01,
            "trace_path": "/dev/null",
            "seed": 42,
            "oracle_version": "v1",
            "env": EnvFingerprintRef(
                os="x", python_version="3.11", package_hash="p",
                machine_id="m", git_sha="g",
            ),
        })
        write_trial(run_dir / "trials.jsonl", trial)
        result = runner.invoke(app, ["reproduce", trial_id])
        assert result.exit_code == 0, result.stdout
        out = json.loads(result.stdout)
        assert out["trial_id"] == trial_id


def test_reproduce_subcommand_missing_trial(tmp_path: Path):
    with runner.isolated_filesystem():
        Path("results").mkdir()
        result = runner.invoke(app, ["reproduce", "nope"])
        assert result.exit_code != 0


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["run", "resume", "status", "verify", "runid", "reproduce", "validate"]:
        assert cmd in result.stdout


# ---------------------------------------------------------------------------
# _load_env: .env beats shell env (override=True).
# Surfaced 2026-05-26: a stale `export ANTHROPIC_API_KEY=...` in ~/.zshrc
# silently shadowed a freshly-rotated .env key for ~30 minutes of debugging.
# ---------------------------------------------------------------------------


def test_load_env_dot_env_overrides_shell_export(tmp_path: Path, monkeypatch, capsys):
    import os
    from unittest.mock import patch
    from tcrun.cli import _load_env

    # Simulate a stale shell export: shell env has the OLD key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-stale-shell-export")

    # And the harness .env has the NEW key.
    fake_env = tmp_path / ".env"
    fake_env.write_text("ANTHROPIC_API_KEY=sk-ant-fresh-from-dotenv\n", encoding="utf-8")

    # _load_env anchors to Path(__file__).parents[1] / ".env" — patch the
    # cli module's __file__ so it resolves to the fixture path's parent.
    fake_cli_file = tmp_path / "tcrun" / "cli.py"
    fake_cli_file.parent.mkdir(parents=True, exist_ok=True)
    fake_cli_file.write_text("", encoding="utf-8")

    with patch("tcrun.cli.__file__", str(fake_cli_file)):
        _load_env()

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fresh-from-dotenv"
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "ANTHROPIC_API_KEY" in captured.err


def test_load_env_no_warning_when_shell_matches_dotenv(tmp_path: Path, monkeypatch, capsys):
    import os
    from unittest.mock import patch
    from tcrun.cli import _load_env

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-same-value")
    fake_env = tmp_path / ".env"
    fake_env.write_text("ANTHROPIC_API_KEY=sk-ant-same-value\n", encoding="utf-8")
    fake_cli_file = tmp_path / "tcrun" / "cli.py"
    fake_cli_file.parent.mkdir(parents=True, exist_ok=True)
    fake_cli_file.write_text("", encoding="utf-8")

    with patch("tcrun.cli.__file__", str(fake_cli_file)):
        _load_env()

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-same-value"
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err
