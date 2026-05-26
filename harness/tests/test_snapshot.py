"""Tests for tcrun.snapshot — env.lock + descriptions.json generators.

Mocks `tcrun.snapshot.stdio_client` + `ClientSession` so no real MCP
subprocesses launch. Mocks `_inspect_docker_digest` so docker isn't required.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mcp import McpError
from mcp.types import ErrorData

from tcrun.servers import PinnedServer
from tcrun.snapshot import (
    DESCRIPTIONS_SCHEMA_VERSION,
    ENV_LOCK_SCHEMA_VERSION,
    SnapshotError,
    _capture_docker_digests,
    _first_leaf_exception,
    _pin_identity,
    _serialize_tool,
    snapshot_all_descriptions,
    snapshot_server_descriptions,
    update_descriptions_file,
    write_env_lock,
)


def _mcp_err(message: str = "Connection closed", code: int = -32000) -> McpError:
    return McpError(ErrorData(code=code, message=message))


# ---------------------------------------------------------------------------
# Test doubles for stdio_client + ClientSession
# ---------------------------------------------------------------------------


class _FakeStdioCtx:
    """Async ctx mgr matching `stdio_client(params)` shape."""

    def __init__(self, *_a, **_kw):
        pass

    async def __aenter__(self):
        return (MagicMock(), MagicMock())

    async def __aexit__(self, *a):
        return False


def _make_client_session(session_obj):
    class _FakeClientSession:
        def __init__(self, *_a, **_kw):
            pass

        async def __aenter__(self):
            return session_obj

        async def __aexit__(self, *a):
            return False

    return _FakeClientSession


def _fake_pin(
    name: str = "git_mcp",
    install: str = "npx",
    *,
    git_sha: str | None = None,
    npm_lock_hash: str | None = "lock-hash-abc",
    npm_version: str | None = "1.0.0",
    docker_digest: str | None = None,
) -> PinnedServer:
    return PinnedServer(
        name=name,
        description="d",
        install=install,
        auth="none",
        package="pkg",
        repo=None,
        git_sha=git_sha,
        npm_version=npm_version,
        npm_lock_hash=npm_lock_hash,
        docker_digest=docker_digest,
        tarball_sha256=None,
    )


# ---------------------------------------------------------------------------
# environment.lock
# ---------------------------------------------------------------------------


def test_env_lock_writes_required_fields(tmp_path: Path):
    out = tmp_path / "environment.lock"
    payload = write_env_lock(out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["schema_version"] == ENV_LOCK_SCHEMA_VERSION
    assert isinstance(data["os"], str) and data["os"]
    assert isinstance(data["python_version"], str) and data["python_version"]
    assert isinstance(data["pip_freeze"], list)
    assert "harness_git_sha" in data


def test_env_lock_is_deterministic_for_same_env(tmp_path: Path):
    """Re-running on an unchanged environment must produce byte-identical output."""
    out1 = tmp_path / "a.lock"
    out2 = tmp_path / "b.lock"
    write_env_lock(out1)
    write_env_lock(out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_env_lock_omits_docker_section_when_no_yaml(tmp_path: Path):
    payload = write_env_lock(tmp_path / "env.lock")
    assert "docker_images" not in payload


def test_env_lock_captures_docker_digests(tmp_path: Path):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "primary_servers:\n"
        "  - name: docker_srv\n"
        "    description: x\n"
        "    install: docker\n"
        "    auth: none\n"
        "    docker_image: ghcr.io/example/img\n"
        "    docker_tag: latest\n",
        encoding="utf-8",
    )
    with patch("tcrun.snapshot._inspect_docker_digest", return_value="sha256:abc"):
        payload = write_env_lock(tmp_path / "env.lock", servers_yaml_path=yaml_path)
    assert payload["docker_images"] == {"ghcr.io/example/img": "sha256:abc"}


def test_env_lock_handles_docker_absent_gracefully(tmp_path: Path):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "primary_servers:\n"
        "  - name: docker_srv\n"
        "    description: x\n"
        "    install: docker\n"
        "    auth: none\n"
        "    docker_image: ghcr.io/example/img\n",
        encoding="utf-8",
    )
    with patch("tcrun.snapshot._inspect_docker_digest", return_value=None):
        payload = write_env_lock(tmp_path / "env.lock", servers_yaml_path=yaml_path)
    assert payload["docker_images"] == {}


def test_capture_docker_digests_sorted_for_stable_hashing(tmp_path: Path):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "primary_servers:\n"
        "  - name: a\n"
        "    description: x\n"
        "    install: docker\n"
        "    auth: none\n"
        "    docker_image: z.example/img\n"
        "  - name: b\n"
        "    description: x\n"
        "    install: docker\n"
        "    auth: none\n"
        "    docker_image: a.example/img\n",
        encoding="utf-8",
    )
    with patch(
        "tcrun.snapshot._inspect_docker_digest",
        side_effect=lambda ref: f"sha256:{ref}",
    ):
        digests = _capture_docker_digests(yaml_path)
    assert list(digests.keys()) == ["a.example/img", "z.example/img"]


def test_env_lock_atomic_write_no_partial_file(tmp_path: Path):
    """A `.tmp` file should never linger after a successful write."""
    out = tmp_path / "env.lock"
    write_env_lock(out)
    assert out.exists()
    assert not (tmp_path / "env.lock.tmp").exists()


# ---------------------------------------------------------------------------
# Tool serialization + pin identity helpers
# ---------------------------------------------------------------------------


def test_serialize_tool_handles_dict_shape():
    t = {"name": "X", "description": "Y", "inputSchema": {"type": "object"}}
    assert _serialize_tool(t) == {
        "name": "X",
        "description": "Y",
        "inputSchema": {"type": "object"},
    }


def test_serialize_tool_handles_attribute_shape():
    t = SimpleNamespace(name="X", description="Y", inputSchema={"type": "object"})
    s = _serialize_tool(t)
    assert s["name"] == "X"
    assert s["inputSchema"] == {"type": "object"}


def test_serialize_tool_defaults_missing_schema():
    t = SimpleNamespace(name="X", description="Y")
    # No inputSchema attribute → fallback object schema
    s = _serialize_tool(t)
    assert s["inputSchema"] == {"type": "object"}


def test_pin_identity_prefers_git_sha():
    pin = _fake_pin(git_sha="abc123", npm_lock_hash="lock", npm_version="1.0")
    assert _pin_identity(pin) == "abc123"


def test_pin_identity_falls_back_to_unpinned():
    pin = _fake_pin(npm_lock_hash=None, npm_version=None)
    assert _pin_identity(pin) == "unpinned"


# ---------------------------------------------------------------------------
# snapshot_server_descriptions
# ---------------------------------------------------------------------------


def test_snapshot_server_descriptions_collects_and_sorts_tools(tmp_path: Path):
    fake_tools = [
        SimpleNamespace(name="b_tool", description="B", inputSchema={"type": "object"}),
        SimpleNamespace(name="a_tool", description="A", inputSchema={"type": "object"}),
    ]
    fake_result = SimpleNamespace(tools=fake_tools)

    class _FakeSession:
        async def initialize(self):
            return None

        async def list_tools(self):
            return fake_result

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        entry = asyncio.run(snapshot_server_descriptions(_fake_pin()))

    assert entry["server_name"] == "git_mcp"
    assert entry["install"] == "npx"
    assert entry["pin"] == "lock-hash-abc"  # npm_lock_hash from _fake_pin
    assert [t["name"] for t in entry["tools"]] == ["a_tool", "b_tool"]


def test_snapshot_server_descriptions_handles_empty_tool_list():
    class _FakeSession:
        async def initialize(self):
            return None

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        entry = asyncio.run(snapshot_server_descriptions(_fake_pin()))
    assert entry["tools"] == []


def test_snapshot_server_descriptions_raises_on_timeout():
    class _FakeSession:
        async def initialize(self):
            raise asyncio.TimeoutError("nope")

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(SnapshotError, match="timed out"):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


def test_snapshot_server_descriptions_raises_on_spawn_oserror():
    class _RaisingStdio:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise OSError("no such binary")

        async def __aexit__(self, *a):
            return False

    with patch("tcrun.snapshot.stdio_client", _RaisingStdio):
        with pytest.raises(SnapshotError, match="failed to spawn subprocess"):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


# ---------------------------------------------------------------------------
# Hardened error classification (McpError, ExceptionGroup, generic, cancel)
# ---------------------------------------------------------------------------


def test_first_leaf_exception_walks_nested_groups():
    inner_err = RuntimeError("real cause")
    nested = ExceptionGroup("outer", [ExceptionGroup("inner", [inner_err])])
    assert _first_leaf_exception(nested) is inner_err


def test_first_leaf_exception_prefers_real_over_cancellation():
    cancel = asyncio.CancelledError()
    real = _mcp_err("the actual failure")
    # asyncio.CancelledError is a BaseException, so any group containing it
    # must be a BaseExceptionGroup. This mirrors what anyio actually raises
    # when a task group cancels siblings after a real error fires.
    grp = BaseExceptionGroup("mixed", [cancel, real])
    assert _first_leaf_exception(grp) is real


def test_first_leaf_exception_returns_cancel_when_only_cancellations():
    grp = BaseExceptionGroup("cancels", [asyncio.CancelledError(), asyncio.CancelledError()])
    assert isinstance(_first_leaf_exception(grp), asyncio.CancelledError)


def test_snapshot_classifies_mcp_error_during_initialize():
    err = _mcp_err("server closed during initialize")

    class _FakeSession:
        async def initialize(self):
            raise err

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(SnapshotError, match="MCP initialize.*server closed") as exc_info:
            asyncio.run(snapshot_server_descriptions(_fake_pin()))
    # raise-from chain preserves the real cause for debugging
    assert exc_info.value.__cause__ is err


def test_snapshot_classifies_mcp_error_during_list_tools():
    err = _mcp_err("tools handler crashed")

    class _FakeSession:
        async def initialize(self):
            return None

        async def list_tools(self):
            raise err

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(SnapshotError, match="MCP list_tools.*tools handler crashed"):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


def test_snapshot_unwraps_exception_group_around_mcp_error():
    # Today's real-world failure mode (git_mcp 404): subprocess spawns OK,
    # MCP client's anyio TaskGroup sees the subprocess die during initialize
    # and surfaces ExceptionGroup containing McpError("Connection closed").
    inner = _mcp_err("Connection closed")

    class _FakeSession:
        async def initialize(self):
            raise ExceptionGroup("unhandled errors in a TaskGroup", [inner])

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(SnapshotError, match="MCP initialize.*Connection closed") as exc_info:
            asyncio.run(snapshot_server_descriptions(_fake_pin()))
    # The cause chain points at the unwrapped leaf, not the wrapping group.
    assert exc_info.value.__cause__ is inner


def test_snapshot_wraps_generic_exception_in_list_tools():
    class _FakeSession:
        async def initialize(self):
            return None

        async def list_tools(self):
            raise ValueError("malformed tool definition")

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(SnapshotError, match="MCP list_tools.*ValueError.*malformed"):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


def test_snapshot_does_not_swallow_cancellation():
    class _FakeSession:
        async def initialize(self):
            raise asyncio.CancelledError()

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


def test_snapshot_does_not_swallow_cancel_only_group():
    class _FakeSession:
        async def initialize(self):
            raise BaseExceptionGroup(
                "cancel storm",
                [asyncio.CancelledError(), asyncio.CancelledError()],
            )

        async def list_tools(self):
            return SimpleNamespace(tools=[])

    with patch("tcrun.snapshot.stdio_client", _FakeStdioCtx), patch(
        "tcrun.snapshot.ClientSession", _make_client_session(_FakeSession())
    ):
        with pytest.raises((asyncio.CancelledError, BaseExceptionGroup)):
            asyncio.run(snapshot_server_descriptions(_fake_pin()))


# ---------------------------------------------------------------------------
# update_descriptions_file (incremental merge)
# ---------------------------------------------------------------------------


def test_update_descriptions_creates_when_missing(tmp_path: Path):
    out = tmp_path / "descriptions.json"
    entry = {"server_name": "git_mcp", "install": "npx", "pin": "p", "tools": []}
    data = update_descriptions_file(out, "git_mcp", entry)
    assert out.exists()
    assert data["servers"]["git_mcp"] == entry
    assert data["schema_version"] == DESCRIPTIONS_SCHEMA_VERSION


def test_update_descriptions_merges_existing(tmp_path: Path):
    out = tmp_path / "descriptions.json"
    update_descriptions_file(
        out,
        "z_srv",
        {"server_name": "z_srv", "install": "npx", "pin": "p", "tools": []},
    )
    update_descriptions_file(
        out,
        "a_srv",
        {"server_name": "a_srv", "install": "npx", "pin": "p", "tools": []},
    )
    data = json.loads(out.read_text())
    assert list(data["servers"]) == ["a_srv", "z_srv"]  # sorted


def test_update_descriptions_overwrites_same_server(tmp_path: Path):
    out = tmp_path / "descriptions.json"
    update_descriptions_file(
        out, "git_mcp", {"server_name": "git_mcp", "install": "npx", "pin": "p", "tools": []}
    )
    new_entry = {
        "server_name": "git_mcp",
        "install": "npx",
        "pin": "p2",
        "tools": [{"name": "t", "description": "d", "inputSchema": {}}],
    }
    update_descriptions_file(out, "git_mcp", new_entry)
    data = json.loads(out.read_text())
    assert data["servers"]["git_mcp"]["pin"] == "p2"
    assert len(data["servers"]["git_mcp"]["tools"]) == 1


def test_update_descriptions_atomic_write(tmp_path: Path):
    out = tmp_path / "descriptions.json"
    update_descriptions_file(
        out, "git_mcp", {"server_name": "git_mcp", "install": "npx", "pin": "p", "tools": []}
    )
    assert not (tmp_path / "descriptions.json.tmp").exists()


def test_update_descriptions_recovers_from_corrupt_existing(tmp_path: Path):
    out = tmp_path / "descriptions.json"
    out.write_text("{not json", encoding="utf-8")
    data = update_descriptions_file(
        out, "git_mcp", {"server_name": "git_mcp", "install": "npx", "pin": "p", "tools": []}
    )
    assert data["servers"]["git_mcp"]["server_name"] == "git_mcp"


# ---------------------------------------------------------------------------
# snapshot_all_descriptions (per-server graceful failure)
# ---------------------------------------------------------------------------


def test_snapshot_all_handles_per_server_failure(tmp_path: Path):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "primary_servers:\n"
        "  - name: ok_srv\n"
        "    description: d\n"
        "    install: npx\n"
        "    auth: none\n"
        "    package: ok-pkg\n"
        "    npm_version: 1.0.0\n"
        "  - name: bad_srv\n"
        "    description: d\n"
        "    install: npx\n"
        "    auth: none\n"
        "    package: bad-pkg\n"
        "    npm_version: 1.0.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "descriptions.json"

    async def fake_snap(pin, *, timeout_s=30.0):
        if pin.name == "bad_srv":
            raise SnapshotError(f"{pin.name}: simulated failure")
        return {
            "server_name": pin.name,
            "install": pin.install,
            "pin": "p",
            "tools": [],
        }

    with patch("tcrun.snapshot.snapshot_server_descriptions", side_effect=fake_snap):
        data, failures = asyncio.run(snapshot_all_descriptions(yaml_path, out))

    assert "ok_srv" in data["servers"]
    assert "bad_srv" not in data["servers"]
    assert failures == [("bad_srv", "bad_srv: simulated failure")]


def test_snapshot_all_with_all_ok(tmp_path: Path):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "primary_servers:\n"
        "  - name: srv_a\n"
        "    description: d\n"
        "    install: npx\n"
        "    auth: none\n"
        "    package: a\n"
        "    npm_version: 1.0.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "descriptions.json"

    async def fake_snap(pin, *, timeout_s=30.0):
        return {
            "server_name": pin.name,
            "install": pin.install,
            "pin": "p",
            "tools": [],
        }

    with patch("tcrun.snapshot.snapshot_server_descriptions", side_effect=fake_snap):
        data, failures = asyncio.run(snapshot_all_descriptions(yaml_path, out))
    assert failures == []
    assert "srv_a" in data["servers"]


# ---------------------------------------------------------------------------
# CLI subcommand smoke tests (no real MCP)
# ---------------------------------------------------------------------------


def test_cli_snapshot_env_subcommand(tmp_path: Path):
    from typer.testing import CliRunner

    from tcrun.cli import app

    out = tmp_path / "env.lock"
    runner = CliRunner()
    result = runner.invoke(app, ["snapshot-env", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data = json.loads(out.read_text())
    assert "python_version" in data


def test_cli_snapshot_descriptions_requires_choice(tmp_path: Path):
    from typer.testing import CliRunner

    from tcrun.cli import app

    runner = CliRunner()
    # Build a minimal config so cfg.servers_pinned resolves.
    cfg_path = _write_minimal_config(tmp_path)
    result = runner.invoke(
        app, ["snapshot-descriptions", "--config", str(cfg_path)]
    )
    assert result.exit_code != 0


def test_cli_snapshot_descriptions_mutually_exclusive_args(tmp_path: Path):
    from typer.testing import CliRunner

    from tcrun.cli import app

    runner = CliRunner()
    cfg_path = _write_minimal_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "snapshot-descriptions",
            "--config",
            str(cfg_path),
            "--server",
            "git_mcp",
            "--all",
        ],
    )
    assert result.exit_code != 0


def test_cli_snapshot_descriptions_single_server_dispatches(tmp_path: Path):
    from typer.testing import CliRunner

    from tcrun.cli import app

    runner = CliRunner()
    cfg_path = _write_minimal_config(
        tmp_path,
        servers_yaml_content=(
            "primary_servers:\n"
            "  - name: git_mcp\n"
            "    description: d\n"
            "    install: npx\n"
            "    auth: none\n"
            "    package: git-mcp-server\n"
            "    npm_version: 1.0.0\n"
        ),
    )
    out = tmp_path / "descriptions.json"

    async def fake_snap(pin, *, timeout_s=30.0):
        return {
            "server_name": pin.name,
            "install": pin.install,
            "pin": "p",
            "tools": [{"name": "x", "description": "y", "inputSchema": {}}],
        }

    with patch("tcrun.cli.snapshot_server_descriptions", side_effect=fake_snap):
        result = runner.invoke(
            app,
            [
                "snapshot-descriptions",
                "--config",
                str(cfg_path),
                "--server",
                "git_mcp",
                "--out",
                str(out),
            ],
        )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["servers"]["git_mcp"]["server_name"] == "git_mcp"


def _write_minimal_config(
    tmp_path: Path,
    *,
    servers_yaml_content: str = "primary_servers: []\n",
) -> Path:
    """Write a minimal mve.yaml-shaped config so cfg.servers_pinned resolves."""
    import yaml

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "queries.jsonl",
        "pass_v1.py",
        "descriptions.json",
        "endpoints.json",
        "environment.lock",
        "corpus.jsonl",
        "embedder.json",
    ):
        (cfg_dir / name).write_text("{}", encoding="utf-8")
    (cfg_dir / "embedder.json").write_text(
        '{"provider":"openai","model":"text-embedding-3-large","dimension":3072}',
        encoding="utf-8",
    )
    (cfg_dir / "servers.yaml").write_text(servers_yaml_content, encoding="utf-8")
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
                "primary_servers": ["git_mcp"],
                "distractors": [],
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
