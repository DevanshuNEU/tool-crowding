"""Tests for tcrun.servers — yaml loader, pin verification, async pool lifecycle.

Mocks subprocess + ClientSession to verify install path, smoke test, teardown,
and hermetic isolation without spawning real MCP servers.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tcrun.servers import (
    PinnedServer,
    ServerInstallError,
    ServerPinMismatch,
    ServerPoolManager,
    install_server,
    load_pinned_servers,
    stdio_params_for,
    verify_pins,
)


# ---------------------------------------------------------------------------
# yaml loader + pin verification
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "servers_pinned.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_pinned_servers_groups_primary_and_distractors(tmp_path: Path):
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: oci
    description: primary
    install: self-hosted
    repo: a/b
    git_sha: deadbeef
    auth: none
distractors:
  - name: time_mcp
    description: distractor
    install: npx
    package: "@modelcontextprotocol/server-time"
    npm_version: 0.1.0
    npm_lock_hash: sha256-abc
    auth: none
""")
    pins = load_pinned_servers(p)
    assert set(pins) == {"oci", "time_mcp"}
    assert pins["oci"].git_sha == "deadbeef"
    assert pins["time_mcp"].npm_lock_hash == "sha256-abc"


def test_load_pinned_servers_treats_TBD_as_unpinned(tmp_path: Path):
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: x
    description: x
    install: self-hosted
    git_sha: TBD
    auth: none
""")
    pins = load_pinned_servers(p)
    assert pins["x"].git_sha is None


def test_verify_pins_halts_on_missing_git_sha():
    pins = {"x": PinnedServer(name="x", description="", install="self-hosted", auth="none")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_halts_on_missing_npm_lock_or_version():
    pins = {"x": PinnedServer(name="x", description="", install="npx", auth="none",
                              package="@scope/p")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_accepts_npm_version_only():
    pins = {"x": PinnedServer(name="x", description="", install="npx", auth="none",
                              package="@scope/p", npm_version="1.0.0")}
    verify_pins(pins)  # no raise


def test_verify_pins_allow_unpinned_skips_check():
    pins = {"x": PinnedServer(name="x", description="", install="self-hosted", auth="none")}
    verify_pins(pins, allow_unpinned=True)  # no raise


def test_verify_pins_halts_on_missing_docker_image():
    pins = {"x": PinnedServer(name="x", description="", install="docker", auth="none",
                              image_digest="sha256:abc")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_halts_on_missing_image_digest():
    pins = {"x": PinnedServer(name="x", description="", install="docker", auth="none",
                              docker_image="mcp/git")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_accepts_docker_with_both_image_and_digest():
    pins = {"x": PinnedServer(name="x", description="", install="docker", auth="none",
                              docker_image="mcp/git", image_digest="sha256:abc")}
    verify_pins(pins)  # no raise


def test_load_pinned_servers_reads_docker_fields(tmp_path: Path):
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: github_mcp
    description: x
    install: docker
    docker_image: ghcr.io/github/github-mcp-server
    docker_tag: latest
    image_digest: sha256:deadbeef
    auth: PAT
""")
    pins = load_pinned_servers(p)
    assert pins["github_mcp"].docker_image == "ghcr.io/github/github-mcp-server"
    assert pins["github_mcp"].image_digest == "sha256:deadbeef"


# ---------------------------------------------------------------------------
# stdio params builder
# ---------------------------------------------------------------------------


def test_stdio_params_for_npx_includes_version_suffix():
    pin = PinnedServer(name="time_mcp", description="", install="npx", auth="none",
                       package="@modelcontextprotocol/server-time", npm_version="0.1.2")
    params = stdio_params_for(pin)
    assert params.command == "npx"
    assert params.args == ["-y", "@modelcontextprotocol/server-time@0.1.2"]


def test_stdio_params_for_self_hosted_uses_name_as_command():
    pin = PinnedServer(name="oci", description="", install="self-hosted", auth="none",
                       git_sha="deadbeef")
    params = stdio_params_for(pin)
    assert params.command == "oci"


def test_stdio_params_for_unsupported_install_raises():
    pin = PinnedServer(name="x", description="", install="curl", auth="none")
    with pytest.raises(ServerInstallError):
        stdio_params_for(pin)


def test_stdio_params_for_docker_builds_digest_pinned_ref():
    pin = PinnedServer(name="git_mcp", description="", install="docker", auth="none",
                       docker_image="mcp/git",
                       image_digest="sha256:abc123")
    params = stdio_params_for(pin)
    assert params.command == "docker"
    assert params.args == ["run", "--rm", "-i", "mcp/git@sha256:abc123"]


def test_stdio_params_for_docker_raises_on_missing_fields():
    pin = PinnedServer(name="x", description="", install="docker", auth="none",
                       docker_image="mcp/git")  # no image_digest
    with pytest.raises(ServerInstallError):
        stdio_params_for(pin)


# ---------------------------------------------------------------------------
# ServerPoolManager async lifecycle (mocked subprocess + ClientSession)
# ---------------------------------------------------------------------------


def _fake_stdio_client_factory(read_w, write_w):
    @asynccontextmanager
    async def fake_stdio_client(params, errlog=None):
        yield (read_w, write_w)
    return fake_stdio_client


def _fake_session_class(tool_names: list[str]):
    """Build a fake ClientSession-shaped async context manager."""
    class FakeSession:
        def __init__(self, *_a, **_kw):
            self.initialize = AsyncMock(return_value=MagicMock())
            tools_result = MagicMock()
            tools_result.tools = [MagicMock(name=n) for n in tool_names]
            # MagicMock(name=...) sets .name as the repr label; override .name explicitly:
            for t, n in zip(tools_result.tools, tool_names):
                t.name = n
            self.list_tools = AsyncMock(return_value=tools_result)
            self.call_tool = AsyncMock()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
    return FakeSession


@pytest.mark.asyncio
async def test_pool_start_returns_session_map(tmp_path: Path):
    yaml_path = _write_yaml(tmp_path, """
primary_servers:
  - name: time_mcp
    description: x
    install: npx
    package: "@scope/time"
    npm_version: 1.0.0
    auth: none
""")
    FakeSession = _fake_session_class(["now", "tz"])
    with patch("tcrun.servers.stdio_client",
               _fake_stdio_client_factory("rs", "ws")), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path) as pool:
            sessions = await pool.start(["time_mcp"])
            assert set(sessions) == {"time_mcp"}
            assert sorted(sessions["time_mcp"].tool_names) == ["now", "tz"]


@pytest.mark.asyncio
async def test_pool_unknown_server_raises(tmp_path: Path):
    yaml_path = _write_yaml(tmp_path, """
primary_servers: []
distractors: []
""")
    async with ServerPoolManager(yaml_path, allow_unpinned=True) as pool:
        with pytest.raises(ServerInstallError):
            await pool.start(["does_not_exist"])


@pytest.mark.asyncio
async def test_pool_start_twice_raises(tmp_path: Path):
    yaml_path = _write_yaml(tmp_path, """
primary_servers:
  - name: t
    description: x
    install: npx
    package: "@scope/t"
    npm_version: 1.0.0
    auth: none
""")
    FakeSession = _fake_session_class(["a"])
    with patch("tcrun.servers.stdio_client", _fake_stdio_client_factory("r", "w")), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path) as pool:
            await pool.start(["t"])
            with pytest.raises(RuntimeError, match="twice"):
                await pool.start(["t"])


@pytest.mark.asyncio
async def test_pool_smoke_timeout_marks_health_check_failure(tmp_path: Path):
    yaml_path = _write_yaml(tmp_path, """
primary_servers:
  - name: t
    description: x
    install: npx
    package: "@scope/t"
    npm_version: 1.0.0
    auth: none
""")
    class HangingSession:
        def __init__(self, *_a, **_kw):
            async def _hang():
                await asyncio.sleep(10)
            self.initialize = _hang
            self.list_tools = AsyncMock()
            self.call_tool = AsyncMock()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    from tcrun.servers import ServerHealthCheckError
    with patch("tcrun.servers.stdio_client", _fake_stdio_client_factory("r", "w")), \
         patch("tcrun.servers.ClientSession", HangingSession):
        async with ServerPoolManager(yaml_path, smoke_timeout_s=0.05) as pool:
            with pytest.raises(ServerHealthCheckError):
                await pool.start(["t"])


@pytest.mark.asyncio
async def test_pool_teardown_via_context_manager_clears_sessions(tmp_path: Path):
    yaml_path = _write_yaml(tmp_path, """
primary_servers:
  - name: t
    description: x
    install: npx
    package: "@scope/t"
    npm_version: 1.0.0
    auth: none
""")
    FakeSession = _fake_session_class(["a"])
    with patch("tcrun.servers.stdio_client", _fake_stdio_client_factory("r", "w")), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path) as pool:
            await pool.start(["t"])
            assert "t" in pool.sessions
        # After __aexit__, sessions cleared (hermetic-per-cell invariant).
        assert pool.sessions == {}


# ---------------------------------------------------------------------------
# install_server (subprocess preflight)
# ---------------------------------------------------------------------------


def test_install_server_npm_view_nonzero_raises():
    pin = PinnedServer(name="x", description="", install="npx", auth="none",
                       package="@scope/p", npm_version="1.0.0")
    fake_completed = MagicMock(returncode=1, stderr="404")
    with patch("tcrun.servers.subprocess.run", return_value=fake_completed):
        with pytest.raises(ServerInstallError):
            install_server(pin)


def test_install_server_npm_view_ok_returns_silently():
    pin = PinnedServer(name="x", description="", install="npx", auth="none",
                       package="@scope/p", npm_version="1.0.0")
    fake_completed = MagicMock(returncode=0, stdout="1.0.0", stderr="")
    with patch("tcrun.servers.subprocess.run", return_value=fake_completed):
        install_server(pin)  # no raise
