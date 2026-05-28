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
    HOSTED_HTTP_BUNDLE_FILES,
    HostedHttpParameters,
    PinnedServer,
    ServerInstallError,
    ServerPinMismatch,
    ServerPoolManager,
    compute_snapshot_sha256,
    hosted_http_params_for,
    install_server,
    load_pinned_servers,
    stdio_params_for,
    verify_pins,
    verify_snapshot_integrity,
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


def test_load_pinned_servers_reads_env_passthrough(tmp_path: Path):
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: github_mcp
    description: x
    install: docker
    docker_image: ghcr.io/github/github-mcp-server
    image_digest: sha256:deadbeef
    auth: PAT
    env_passthrough: [GITHUB_PERSONAL_ACCESS_TOKEN]
  - name: git_mcp
    description: x
    install: docker
    docker_image: mcp/git
    image_digest: sha256:cafe
    auth: none
""")
    pins = load_pinned_servers(p)
    assert pins["github_mcp"].env_passthrough == ("GITHUB_PERSONAL_ACCESS_TOKEN",)
    assert pins["git_mcp"].env_passthrough == ()


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


def test_stdio_params_for_docker_threads_env_passthrough(monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_fixture")
    pin = PinnedServer(name="github_mcp", description="", install="docker", auth="PAT",
                       docker_image="ghcr.io/github/github-mcp-server",
                       image_digest="sha256:abc123",
                       env_passthrough=("GITHUB_PERSONAL_ACCESS_TOKEN",))
    params = stdio_params_for(pin)
    assert params.command == "docker"
    assert params.args == [
        "run", "--rm", "-i",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server@sha256:abc123",
    ]


def test_stdio_params_for_docker_env_passthrough_populates_env_dict(monkeypatch):
    # The mcp SDK's stdio_client merges params.env with a curated whitelist
    # (PATH/HOME/USER/...). If params.env is None, declared env_passthrough
    # vars are missing from docker's own process env and `-e <NAME>` forwards
    # nothing. The fix populates params.env with each declared name's value
    # from os.environ; this test pins that contract.
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_fixture_value")
    pin = PinnedServer(name="github_mcp", description="", install="docker", auth="PAT",
                       docker_image="ghcr.io/github/github-mcp-server",
                       image_digest="sha256:abc123",
                       env_passthrough=("GITHUB_PERSONAL_ACCESS_TOKEN",))
    params = stdio_params_for(pin)
    assert params.env == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_fixture_value"}


def test_stdio_params_for_docker_env_passthrough_raises_on_missing_env(monkeypatch):
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    pin = PinnedServer(name="github_mcp", description="", install="docker", auth="PAT",
                       docker_image="ghcr.io/github/github-mcp-server",
                       image_digest="sha256:abc123",
                       env_passthrough=("GITHUB_PERSONAL_ACCESS_TOKEN",))
    with pytest.raises(ServerInstallError, match="env_passthrough requires"):
        stdio_params_for(pin)


def test_stdio_params_for_docker_empty_env_passthrough_omits_e_flags():
    pin = PinnedServer(name="git_mcp", description="", install="docker", auth="none",
                       docker_image="mcp/git",
                       image_digest="sha256:abc123")
    params = stdio_params_for(pin)
    assert "-e" not in params.args
    assert params.env is None


# ---------------------------------------------------------------------------
# server_args (per-server launch flags for tool-surface scoping)
# ---------------------------------------------------------------------------


def test_load_pinned_servers_reads_server_args(tmp_path: Path):
    # The github-mcp-server image's default CMD is `stdio` (it's a Cobra
    # subcommand, not the entrypoint). `docker run image <args>` replaces the
    # CMD, so the yaml's server_args must include `stdio` first when the image
    # uses a subcommand entrypoint. The yaml stores the full container argv.
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: github_mcp
    description: x
    install: docker
    docker_image: ghcr.io/github/github-mcp-server
    image_digest: sha256:deadbeef
    auth: PAT
    server_args: ["stdio", "--toolsets=repos", "--read-only"]
  - name: git_mcp
    description: x
    install: docker
    docker_image: mcp/git
    image_digest: sha256:cafe
    auth: none
""")
    pins = load_pinned_servers(p)
    assert pins["github_mcp"].server_args == ("stdio", "--toolsets=repos", "--read-only")
    assert pins["git_mcp"].server_args == ()


def test_stdio_params_for_docker_appends_server_args_after_image_ref():
    # server_args MUST land after image_ref in docker argv so they reach the
    # container's entrypoint (the MCP binary), not docker itself. Pinning the
    # ordering: [run, --rm, -i, image_ref, *server_args].
    pin = PinnedServer(name="github_mcp", description="", install="docker", auth="none",
                       docker_image="ghcr.io/github/github-mcp-server",
                       image_digest="sha256:abc123",
                       server_args=("--toolsets=repos", "--read-only"))
    params = stdio_params_for(pin)
    assert params.args == [
        "run", "--rm", "-i",
        "ghcr.io/github/github-mcp-server@sha256:abc123",
        "--toolsets=repos", "--read-only",
    ]


def test_stdio_params_for_docker_server_args_after_env_passthrough(monkeypatch):
    # When both env_passthrough and server_args are set, env -e flags precede
    # the image_ref and server_args follow it. Ordering contract:
    # [run, --rm, -i, -e ENV1, -e ENV2, image_ref, *server_args].
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_fixture")
    pin = PinnedServer(name="github_mcp", description="", install="docker", auth="PAT",
                       docker_image="ghcr.io/github/github-mcp-server",
                       image_digest="sha256:abc123",
                       env_passthrough=("GITHUB_PERSONAL_ACCESS_TOKEN",),
                       server_args=("--toolsets=repos", "--read-only"))
    params = stdio_params_for(pin)
    assert params.args == [
        "run", "--rm", "-i",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server@sha256:abc123",
        "--toolsets=repos", "--read-only",
    ]


def test_stdio_params_for_npx_appends_server_args_after_package():
    pin = PinnedServer(name="some_npx_mcp", description="", install="npx", auth="none",
                       package="@scope/server-x", npm_version="1.2.3",
                       server_args=("--some-flag", "value"))
    params = stdio_params_for(pin)
    assert params.args == ["-y", "@scope/server-x@1.2.3", "--some-flag", "value"]


def test_stdio_params_for_self_hosted_appends_server_args():
    pin = PinnedServer(name="oci", description="", install="self-hosted", auth="none",
                       git_sha="deadbeef",
                       server_args=("--config", "/etc/oci.yml"))
    params = stdio_params_for(pin)
    assert params.command == "oci"
    assert params.args == ["--config", "/etc/oci.yml"]


def test_stdio_params_for_empty_server_args_unchanged():
    # When server_args is the default empty tuple, behavior matches the
    # pre-server_args contract exactly. Regression guard.
    npx_pin = PinnedServer(name="time_mcp", description="", install="npx", auth="none",
                           package="@mcp/time", npm_version="0.1.0")
    assert stdio_params_for(npx_pin).args == ["-y", "@mcp/time@0.1.0"]

    docker_pin = PinnedServer(name="git_mcp", description="", install="docker", auth="none",
                              docker_image="mcp/git",
                              image_digest="sha256:abc")
    assert stdio_params_for(docker_pin).args == ["run", "--rm", "-i", "mcp/git@sha256:abc"]

    sh_pin = PinnedServer(name="oci", description="", install="self-hosted", auth="none",
                          git_sha="deadbeef")
    assert stdio_params_for(sh_pin).args == []


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


def test_install_server_hosted_http_is_noop():
    """hosted-http has no local install step; install_server returns silently."""
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="snap",
                       snapshot_sha256="sha256:abc")
    install_server(pin)  # must not raise, must not call subprocess


# ---------------------------------------------------------------------------
# hosted-http: PinnedServer fields + yaml load + verify_pins
# ---------------------------------------------------------------------------


def test_load_pinned_servers_reads_hosted_http_fields(tmp_path: Path):
    p = _write_yaml(tmp_path, """
primary_servers:
  - name: deepwiki
    description: x
    install: hosted-http
    url: https://mcp.deepwiki.com/mcp
    snapshot_path: server-pool/deepwiki-snapshot-2026-05-26
    snapshot_sha256: sha256:abc123
    auth: none
""")
    pins = load_pinned_servers(p)
    assert pins["deepwiki"].install == "hosted-http"
    assert pins["deepwiki"].url == "https://mcp.deepwiki.com/mcp"
    assert pins["deepwiki"].snapshot_path == "server-pool/deepwiki-snapshot-2026-05-26"
    assert pins["deepwiki"].snapshot_sha256 == "sha256:abc123"


def test_verify_pins_halts_on_missing_url_for_hosted_http():
    pins = {"dw": PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                               snapshot_path="snap", snapshot_sha256="sha256:abc")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_halts_on_missing_snapshot_sha256_for_hosted_http():
    pins = {"dw": PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                               url="https://example.test/mcp", snapshot_path="snap")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_halts_on_missing_snapshot_path_for_hosted_http():
    pins = {"dw": PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                               url="https://example.test/mcp", snapshot_sha256="sha256:abc")}
    with pytest.raises(ServerPinMismatch):
        verify_pins(pins)


def test_verify_pins_accepts_hosted_http_with_url_path_and_sha():
    pins = {"dw": PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                               url="https://example.test/mcp", snapshot_path="snap",
                               snapshot_sha256="sha256:abc")}
    verify_pins(pins)  # no raise


# ---------------------------------------------------------------------------
# hosted_http_params_for
# ---------------------------------------------------------------------------


def test_hosted_http_params_for_returns_url_container():
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="snap",
                       snapshot_sha256="sha256:abc")
    params = hosted_http_params_for(pin)
    assert isinstance(params, HostedHttpParameters)
    assert params.url == "https://example.test/mcp"


def test_hosted_http_params_for_rejects_non_hosted_http_pin():
    pin = PinnedServer(name="x", description="", install="docker", auth="none",
                       docker_image="mcp/git", image_digest="sha256:abc")
    with pytest.raises(ServerInstallError):
        hosted_http_params_for(pin)


def test_hosted_http_params_for_raises_on_missing_url():
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       snapshot_path="snap", snapshot_sha256="sha256:abc")
    with pytest.raises(ServerInstallError):
        hosted_http_params_for(pin)


def test_stdio_params_for_rejects_hosted_http():
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp")
    with pytest.raises(ServerInstallError):
        stdio_params_for(pin)


# ---------------------------------------------------------------------------
# Snapshot integrity (REPRODUCIBILITY.md §5)
# ---------------------------------------------------------------------------


def _write_valid_snapshot(snapshot_dir: Path, payloads: dict[str, str] | None = None) -> str:
    """Write the full HOSTED_HTTP_BUNDLE_FILES set into snapshot_dir and return
    its expected sha256 (matches compute_snapshot_sha256's algorithm)."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    defaults = {name: "{}\n" for name in HOSTED_HTTP_BUNDLE_FILES}
    if payloads:
        defaults.update(payloads)
    for name, body in defaults.items():
        (snapshot_dir / name).write_text(body, encoding="utf-8")
    return compute_snapshot_sha256(snapshot_dir)


def test_compute_snapshot_sha256_is_deterministic(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    sha_a = _write_valid_snapshot(a)
    sha_b = _write_valid_snapshot(b)
    assert sha_a == sha_b  # same byte content → same hash


def test_compute_snapshot_sha256_changes_when_content_changes(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    sha_a = _write_valid_snapshot(a)
    sha_b = _write_valid_snapshot(b, payloads={"initialize.json": '{"changed": true}\n'})
    assert sha_a != sha_b


def test_compute_snapshot_sha256_raises_on_missing_file(tmp_path: Path):
    snap = tmp_path / "snap"
    snap.mkdir()
    # only write 2 of the 4 required files
    (snap / "initialize.json").write_text("{}\n", encoding="utf-8")
    (snap / "meta.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        compute_snapshot_sha256(snap)


def test_verify_snapshot_integrity_passes_with_correct_sha(tmp_path: Path):
    snap = tmp_path / "snap"
    sha = _write_valid_snapshot(snap)
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="snap",
                       snapshot_sha256=sha)
    verify_snapshot_integrity(pin, tmp_path)  # no raise


def test_verify_snapshot_integrity_raises_on_sha_drift(tmp_path: Path):
    snap = tmp_path / "snap"
    _write_valid_snapshot(snap)
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="snap",
                       snapshot_sha256="sha256:wrong")
    with pytest.raises(ServerPinMismatch, match="snapshot drift"):
        verify_snapshot_integrity(pin, tmp_path)


def test_verify_snapshot_integrity_raises_on_missing_dir(tmp_path: Path):
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="does-not-exist",
                       snapshot_sha256="sha256:abc")
    with pytest.raises(ServerPinMismatch, match="does not exist"):
        verify_snapshot_integrity(pin, tmp_path)


def test_verify_snapshot_integrity_raises_on_missing_bundle_files(tmp_path: Path):
    snap = tmp_path / "snap"
    snap.mkdir()
    # write only 1 of 4 required files
    (snap / "initialize.json").write_text("{}\n", encoding="utf-8")
    pin = PinnedServer(name="dw", description="", install="hosted-http", auth="none",
                       url="https://example.test/mcp", snapshot_path="snap",
                       snapshot_sha256="sha256:abc")
    with pytest.raises(ServerPinMismatch):
        verify_snapshot_integrity(pin, tmp_path)


def test_verify_snapshot_integrity_skips_non_hosted_http():
    pin = PinnedServer(name="x", description="", install="docker", auth="none",
                       docker_image="mcp/git", image_digest="sha256:abc")
    verify_snapshot_integrity(pin, Path("/nonexistent"))  # no raise, returns None


# ---------------------------------------------------------------------------
# ServerPoolManager: hosted-http spawn path (mocked streamablehttp_client)
# ---------------------------------------------------------------------------


def _fake_streamablehttp_client_factory(read_w, write_w, session_id="sess-1"):
    @asynccontextmanager
    async def fake_streamablehttp_client(url, **kwargs):
        def _get_id():
            return session_id
        yield (read_w, write_w, _get_id)
    return fake_streamablehttp_client


@pytest.mark.asyncio
async def test_pool_start_uses_streamablehttp_for_hosted_http(tmp_path: Path):
    """End-to-end mock: yaml → pool.start → streamablehttp_client called with the URL."""
    snap = tmp_path / "snap"
    sha = _write_valid_snapshot(snap)
    yaml_path = _write_yaml(tmp_path, f"""
primary_servers:
  - name: deepwiki
    description: x
    install: hosted-http
    url: https://mcp.deepwiki.com/mcp
    snapshot_path: snap
    snapshot_sha256: {sha}
    auth: none
""")

    FakeSession = _fake_session_class(["read_wiki_structure", "read_wiki_contents", "ask_question"])
    called_urls: list[str] = []

    @asynccontextmanager
    async def recording_streamablehttp_client(url, **kwargs):
        called_urls.append(url)
        def _get_id():
            return "sess-1"
        yield ("r", "w", _get_id)

    with patch("tcrun.servers.streamablehttp_client", recording_streamablehttp_client), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path, harness_root=tmp_path) as pool:
            sessions = await pool.start(["deepwiki"])
            assert set(sessions) == {"deepwiki"}
            assert sorted(sessions["deepwiki"].tool_names) == [
                "ask_question", "read_wiki_contents", "read_wiki_structure"
            ]
    assert called_urls == ["https://mcp.deepwiki.com/mcp"]


@pytest.mark.asyncio
async def test_pool_start_halts_on_snapshot_drift(tmp_path: Path):
    """If snapshot has drifted, _spawn_one must halt before contacting the server."""
    snap = tmp_path / "snap"
    _write_valid_snapshot(snap)
    yaml_path = _write_yaml(tmp_path, """
primary_servers:
  - name: deepwiki
    description: x
    install: hosted-http
    url: https://mcp.deepwiki.com/mcp
    snapshot_path: snap
    snapshot_sha256: sha256:definitely-wrong
    auth: none
""")
    FakeSession = _fake_session_class([])
    called = []

    @asynccontextmanager
    async def recording_streamablehttp_client(url, **kwargs):
        called.append(url)
        def _get_id(): return None
        yield ("r", "w", _get_id)

    with patch("tcrun.servers.streamablehttp_client", recording_streamablehttp_client), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path, harness_root=tmp_path) as pool:
            with pytest.raises(ServerPinMismatch, match="snapshot drift"):
                await pool.start(["deepwiki"])
    assert called == []  # halted before network


@pytest.mark.asyncio
async def test_pool_hosted_http_connect_error_becomes_install_error(tmp_path: Path):
    """httpx-side errors during connect must surface as ServerInstallError."""
    snap = tmp_path / "snap"
    sha = _write_valid_snapshot(snap)
    yaml_path = _write_yaml(tmp_path, f"""
primary_servers:
  - name: deepwiki
    description: x
    install: hosted-http
    url: https://mcp.deepwiki.com/mcp
    snapshot_path: snap
    snapshot_sha256: {sha}
    auth: none
""")

    @asynccontextmanager
    async def failing_streamablehttp_client(url, **kwargs):
        raise ConnectionError("simulated httpx ConnectError")
        yield  # pragma: no cover (unreachable)

    FakeSession = _fake_session_class([])
    with patch("tcrun.servers.streamablehttp_client", failing_streamablehttp_client), \
         patch("tcrun.servers.ClientSession", FakeSession):
        async with ServerPoolManager(yaml_path, harness_root=tmp_path) as pool:
            with pytest.raises(ServerInstallError, match="failed to connect"):
                await pool.start(["deepwiki"])
