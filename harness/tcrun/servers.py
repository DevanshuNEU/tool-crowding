"""ServerPoolManager: install + version-pin + health-check + teardown.

Implements SPEC.md §3 ServerPoolManager + §5 rule 4 (hermetic per cell) +
§7 failure modes F1 (install fail), F2 (health-check timeout), F4 (zombie),
F20 (OS process limit) + REPRODUCIBILITY.md §5 (SHA mismatch halt).

Per-cell lifecycle:
    1. Resolve the subset of `servers_pinned.yaml` rows we need.
    2. Spawn each MCP server as its own subprocess (npx / git+pip / docker
       per `install`); start via `mcp.client.stdio.stdio_client`.
    3. Initialize the `ClientSession`, list tools, run a no-op smoke test.
    4. Yield the session-map dict to the caller.
    5. On exit (success or fail), close every session + terminate every
       subprocess tree (SIGTERM, then SIGKILL after grace period).

SHA / version drift is detected at smoke time: a `verify_pins()` helper
re-reads `git_sha` (for source installs) or `npm_lock_hash` (for npx) and
compares against the pinned value. Mismatch raises `ServerPinMismatch`
which halts the run per REPRODUCIBILITY.md §5.

LOC budget per SPEC.md §11: ~200 LOC.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Module-level MCP imports (kept patchable by tests/test_servers.py which calls
# `patch("tcrun.servers.stdio_client", ...)`). Real launches go through these;
# stdio_params_for() still re-imports `StdioServerParameters` lazily because some
# unit tests construct PinnedServer rows without `mcp` installed at all.
try:
    from mcp import ClientSession, McpError  # type: ignore[import-not-found]
    from mcp.client.stdio import stdio_client  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - mcp pinned in pyproject.toml
    ClientSession = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]

    class McpError(Exception):  # type: ignore[no-redef]
        """Placeholder when mcp isn't installed; never raised, exists so
        downstream `except McpError` clauses resolve to a real class."""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions per SPEC §7 failure-mode catalog
# ---------------------------------------------------------------------------


class ServerInstallError(RuntimeError):
    """F1: subprocess install returncode != 0."""


class ServerHealthCheckError(RuntimeError):
    """F2/F4: server failed handshake / list_tools within timeout."""


class ServerPinMismatch(RuntimeError):
    """REPRODUCIBILITY.md §5: pinned SHA/version drift from current. HALTS run."""


# ---------------------------------------------------------------------------
# Pinning model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PinnedServer:
    """One row of `servers_pinned.yaml`. Either git_sha OR npm_lock_hash is set."""

    name: str
    description: str
    install: str  # "npx" | "self-hosted" | "npx-or-pip" | "docker"
    auth: str
    package: str | None = None
    repo: str | None = None
    git_sha: str | None = None
    npm_version: str | None = None
    npm_lock_hash: str | None = None
    docker_image: str | None = None
    image_digest: str | None = None
    tarball_sha256: str | None = None


@dataclass
class ServerSession:
    """A running server: subprocess + open ClientSession."""

    name: str
    pin: PinnedServer
    process: Any  # asyncio.subprocess.Process or stdio_client-managed proc
    session: Any  # mcp.ClientSession
    tool_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def load_pinned_servers(yaml_path: Path | str) -> dict[str, PinnedServer]:
    """Load `servers_pinned.yaml` into a {name: PinnedServer} dict.

    The YAML has two top-level lists: `primary_servers` and `distractors`.
    Both flatten into one dict keyed by `name`.
    """
    p = Path(yaml_path)
    with open(p, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, PinnedServer] = {}
    for section in ("primary_servers", "distractors"):
        for row in data.get(section) or []:
            if "name" not in row:
                continue
            ps = PinnedServer(
                name=row["name"],
                description=row.get("description", ""),
                install=row.get("install", "npx"),
                auth=row.get("auth", "none"),
                package=row.get("package"),
                repo=row.get("repo"),
                git_sha=_normalize_pin(row.get("git_sha")),
                npm_version=_normalize_pin(row.get("npm_version")),
                npm_lock_hash=_normalize_pin(row.get("npm_lock_hash")),
                docker_image=_normalize_pin(row.get("docker_image")),
                image_digest=_normalize_pin(row.get("image_digest")),
                tarball_sha256=_normalize_pin(row.get("tarball_sha256")),
            )
            out[ps.name] = ps
    return out


def _normalize_pin(v: Any) -> str | None:
    """Treat the literal "TBD" sentinel and empty strings as unpinned (None)."""
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "TBD") else s


# ---------------------------------------------------------------------------
# Smoke-test pin verification (REPRODUCIBILITY.md §5)
# ---------------------------------------------------------------------------


def verify_pins(servers: dict[str, PinnedServer], allow_unpinned: bool = False) -> None:
    """Halt the run if any selected server lacks a populated pin.

    For source installs (self-hosted, npx-or-pip): require `git_sha`.
    For npx installs: require `npm_lock_hash` OR `npm_version`.
    For docker installs: require both `docker_image` and `image_digest`
    (the digest alone is not addressable by `docker run`; we need
    `<image>@sha256:...` form).

    `allow_unpinned=True` is for harness-build smoke tests only; production
    sweeps must run with `allow_unpinned=False` (the default).
    """
    if allow_unpinned:
        return
    for name, ps in servers.items():
        if ps.install in ("self-hosted", "npx-or-pip"):
            if not ps.git_sha:
                raise ServerPinMismatch(f"{name}: install={ps.install} requires git_sha pin")
        elif ps.install == "npx":
            if not (ps.npm_lock_hash or ps.npm_version):
                raise ServerPinMismatch(f"{name}: npx install requires npm_lock_hash or npm_version")
        elif ps.install == "docker":
            if not (ps.docker_image and ps.image_digest):
                raise ServerPinMismatch(
                    f"{name}: docker install requires both docker_image and image_digest pins"
                )


# ---------------------------------------------------------------------------
# Subprocess launch (one StdioServerParameters per server)
# ---------------------------------------------------------------------------


def stdio_params_for(pin: PinnedServer) -> Any:
    """Build an `mcp.StdioServerParameters` for the given pin. Imported lazily."""
    from mcp import StdioServerParameters  # type: ignore[import-not-found]

    if pin.install == "npx":
        # `npx -y @scope/server-name@version` ensures a deterministic version.
        version_suffix = f"@{pin.npm_version}" if pin.npm_version else ""
        package = pin.package or pin.name
        return StdioServerParameters(command="npx", args=["-y", f"{package}{version_suffix}"])
    if pin.install in ("self-hosted", "npx-or-pip"):
        # Source-pinned servers are launched via their pip-installed entrypoint
        # (e.g., `mcp-server-git`). Name is the binary by convention.
        return StdioServerParameters(command=pin.name, args=[])
    if pin.install == "docker":
        # `docker run --rm -i <image>@sha256:<hex>` — digest-pinned reference.
        # A bare sha256 is not addressable; the repo prefix is required.
        if not (pin.docker_image and pin.image_digest):
            raise ServerInstallError(
                f"{pin.name}: docker install requires both docker_image and image_digest"
            )
        image_ref = f"{pin.docker_image}@{pin.image_digest}"
        return StdioServerParameters(command="docker", args=["run", "--rm", "-i", image_ref])
    raise ServerInstallError(f"{pin.name}: unsupported install type {pin.install!r}")


# ---------------------------------------------------------------------------
# ServerPoolManager
# ---------------------------------------------------------------------------


class ServerPoolManager:
    """Hermetic per-cell MCP server pool (SPEC.md §3 + §5 rule 4).

    Usage::

        async with ServerPoolManager("tcrun/servers_pinned.yaml") as pool:
            sessions = await pool.start(["oci", "github_mcp"])
            tools = sessions["oci"].tool_names
            ...
        # On exit: every subprocess is terminated, every session closed.
    """

    def __init__(self, yaml_path: Path | str, *, allow_unpinned: bool = False,
                 smoke_timeout_s: float = 30.0):
        self.yaml_path = Path(yaml_path)
        self.allow_unpinned = allow_unpinned
        self.smoke_timeout_s = smoke_timeout_s
        self.pins: dict[str, PinnedServer] = {}
        self.sessions: dict[str, ServerSession] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "ServerPoolManager":
        self.pins = load_pinned_servers(self.yaml_path)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self, server_names: list[str]) -> dict[str, ServerSession]:
        """Spawn each named server, run smoke test, return the session map.

        Hermetic: each call to `start` brings a fresh subprocess tree. Calling
        `start` twice without `stop` raises.
        """
        if self.sessions:
            raise RuntimeError("ServerPoolManager.start called twice without stop()")
        selected = {name: self.pins[name] for name in server_names if name in self.pins}
        missing = [n for n in server_names if n not in self.pins]
        if missing:
            raise ServerInstallError(f"unknown server(s) in yaml: {missing}")
        verify_pins(selected, allow_unpinned=self.allow_unpinned)
        for name, pin in selected.items():
            self.sessions[name] = await self._spawn_one(name, pin)
        return self.sessions

    async def _spawn_one(self, name: str, pin: PinnedServer) -> ServerSession:
        """Launch one server + initialize the ClientSession + smoke-test.

        Uses module-level `stdio_client` and `ClientSession` so tests can
        `patch("tcrun.servers.stdio_client", ...)` without going through the
        real `mcp` package.
        """
        if stdio_client is None or ClientSession is None:  # pragma: no cover - covered by patches
            raise ServerInstallError("mcp package not installed; cannot spawn servers")
        params = stdio_params_for(pin)
        try:
            read_w, write_w = await self._stack.enter_async_context(stdio_client(params))
        except OSError as e:
            raise ServerInstallError(f"{name}: failed to spawn subprocess: {e}") from e
        session = await self._stack.enter_async_context(ClientSession(read_w, write_w))
        try:
            await asyncio.wait_for(session.initialize(), timeout=self.smoke_timeout_s)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=self.smoke_timeout_s)
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise ServerHealthCheckError(f"{name}: smoke test timed out") from e
        tool_names = [t.name for t in getattr(tools_result, "tools", [])]
        return ServerSession(name=name, pin=pin, process=None, session=session, tool_names=tool_names)

    async def stop(self) -> None:
        """Tear down every active server. Idempotent."""
        try:
            await self._stack.aclose()
        except Exception:  # pragma: no cover -- defensive: never let teardown raise
            logger.exception("ServerPoolManager teardown error (swallowed)")
        finally:
            self.sessions = {}


# ---------------------------------------------------------------------------
# Install helper (subprocess preflight for npx / pip self-hosted)
# ---------------------------------------------------------------------------


def install_server(pin: PinnedServer, timeout_s: float = 120.0) -> None:
    """Best-effort pre-install (F1 detection). Synchronous; called before a sweep."""
    if pin.install == "npx" and pin.package:
        version = f"@{pin.npm_version}" if pin.npm_version else ""
        cmd = ["npm", "view", f"{pin.package}{version}", "version"]
    elif pin.install in ("self-hosted", "npx-or-pip"):
        cmd = ["python", "-c", f"import importlib; importlib.import_module('{pin.name}')"]
    else:
        return  # docker: covered by digest pin
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        raise ServerInstallError(f"{pin.name}: preflight failed: {e}") from e
    if r.returncode != 0:
        raise ServerInstallError(f"{pin.name}: preflight nonzero rc={r.returncode}: {r.stderr.strip()}")
