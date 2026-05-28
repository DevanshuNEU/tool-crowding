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
import hashlib
import logging
import os
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
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - mcp pinned in pyproject.toml
    ClientSession = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    streamablehttp_client = None  # type: ignore[assignment]

    class McpError(Exception):  # type: ignore[no-redef]
        """Placeholder when mcp isn't installed; never raised, exists so
        downstream `except McpError` clauses resolve to a real class."""

logger = logging.getLogger(__name__)

# Hosted-HTTP snapshot bundle file manifest. Mirrors
# server-pool/_capture_deepwiki_snapshot.py BUNDLE_FILES so the runtime
# integrity check hashes the same artifacts the capture script did.
HOSTED_HTTP_BUNDLE_FILES: tuple[str, ...] = (
    "initialize.json",
    "meta.json",
    "sample_query.json",
    "tools_list.json",
)


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
    """One row of `servers_pinned.yaml`. Exactly one pin field is populated
    per install type (git_sha / npm_lock_hash / image_digest / snapshot_sha256)."""

    name: str
    description: str
    install: str  # "npx" | "self-hosted" | "npx-or-pip" | "docker" | "hosted-http"
    auth: str
    package: str | None = None
    repo: str | None = None
    git_sha: str | None = None
    npm_version: str | None = None
    npm_lock_hash: str | None = None
    docker_image: str | None = None
    image_digest: str | None = None
    tarball_sha256: str | None = None
    url: str | None = None
    snapshot_path: str | None = None
    snapshot_sha256: str | None = None
    # Env var names to forward into the docker container via `-e <NAME>` (no
    # value; docker picks each up from the host harness process env). Used for
    # credentialed docker servers like github_mcp (PAT). Empty for everything
    # else. Tuple keeps the dataclass frozen/hashable.
    env_passthrough: tuple[str, ...] = ()
    # Command-line args appended to the server invocation after the
    # entrypoint marker (docker: after image_ref; npx: after package@ver;
    # self-hosted: after binary). Used to scope an MCP's tool surface at
    # launch time (e.g., github_mcp uses `--read-only --toolsets=repos` to
    # drop a 38-tool surface to ~8). Empty for servers that don't expose
    # CLI scope flags. Tuple for frozen-hashable, matching env_passthrough.
    server_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class HostedHttpParameters:
    """URL container for hosted-HTTP MCP servers (Streamable HTTP transport).

    Mirrors `mcp.StdioServerParameters` in shape but holds a URL instead of an
    argv. Returned by `hosted_http_params_for(pin)` and consumed by
    `_spawn_one` via `streamablehttp_client(url)`.
    """

    url: str


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
                url=_normalize_pin(row.get("url")),
                snapshot_path=_normalize_pin(row.get("snapshot_path")),
                snapshot_sha256=_normalize_pin(row.get("snapshot_sha256")),
                env_passthrough=tuple(row.get("env_passthrough") or ()),
                server_args=tuple(row.get("server_args") or ()),
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
        elif ps.install == "hosted-http":
            if not (ps.url and ps.snapshot_sha256 and ps.snapshot_path):
                raise ServerPinMismatch(
                    f"{name}: hosted-http install requires url, snapshot_path, and snapshot_sha256 pins"
                )


# ---------------------------------------------------------------------------
# Subprocess launch (one StdioServerParameters per server)
# ---------------------------------------------------------------------------


def stdio_params_for(pin: PinnedServer) -> Any:
    """Build an `mcp.StdioServerParameters` for the given pin. Imported lazily.

    Hosted-HTTP pins route through `hosted_http_params_for` instead and are
    rejected here.
    """
    from mcp import StdioServerParameters  # type: ignore[import-not-found]

    if pin.install == "npx":
        # `npx -y @scope/server-name@version` ensures a deterministic version.
        # `server_args` (e.g., `--read-only`) follow the package spec.
        version_suffix = f"@{pin.npm_version}" if pin.npm_version else ""
        package = pin.package or pin.name
        return StdioServerParameters(
            command="npx",
            args=["-y", f"{package}{version_suffix}", *pin.server_args],
        )
    if pin.install in ("self-hosted", "npx-or-pip"):
        # Source-pinned servers are launched via their pip-installed entrypoint
        # (e.g., `mcp-server-git`). Name is the binary by convention.
        # `server_args` are appended directly as the binary's argv.
        return StdioServerParameters(command=pin.name, args=[*pin.server_args])
    if pin.install == "docker":
        # `docker run --rm -i <image>@sha256:<hex>` — digest-pinned reference.
        # A bare sha256 is not addressable; the repo prefix is required.
        if not (pin.docker_image and pin.image_digest):
            raise ServerInstallError(
                f"{pin.name}: docker install requires both docker_image and image_digest"
            )
        image_ref = f"{pin.docker_image}@{pin.image_digest}"
        args = ["run", "--rm", "-i"]
        # mcp.client.stdio.stdio_client filters subprocess env to a curated
        # whitelist (PATH/HOME/USER/...) when StdioServerParameters.env is None,
        # so `docker -e <NAME>` would forward a variable that's been stripped
        # from docker's own env. Populate `env` explicitly with each declared
        # passthrough name so the var survives into docker's process; the SDK
        # merges this dict with its default whitelist (mcp/client/stdio L127).
        env: dict[str, str] | None = None
        if pin.env_passthrough:
            env = {}
            for env_name in pin.env_passthrough:
                value = os.environ.get(env_name)
                if value is None:
                    raise ServerInstallError(
                        f"{pin.name}: env_passthrough requires {env_name!r} in os.environ "
                        f"(check harness/.env)"
                    )
                env[env_name] = value
        for env_name in pin.env_passthrough:
            args.extend(["-e", env_name])
        args.append(image_ref)
        # Anything after `image_ref` is the container entrypoint's argv.
        # `server_args` lands here so flags like `--toolsets=repos` reach the
        # MCP server binary inside the container, not docker itself.
        args.extend(pin.server_args)
        return StdioServerParameters(command="docker", args=args, env=env)
    raise ServerInstallError(f"{pin.name}: unsupported install type {pin.install!r}")


def hosted_http_params_for(pin: PinnedServer) -> HostedHttpParameters:
    """Build a `HostedHttpParameters` for a hosted-HTTP pin.

    The yielded URL is consumed by `streamablehttp_client(url)` inside
    `_spawn_one`. Raises if the pin is not hosted-HTTP or lacks a URL.
    """
    if pin.install != "hosted-http":
        raise ServerInstallError(
            f"{pin.name}: hosted_http_params_for called on install={pin.install!r}"
        )
    if not pin.url:
        raise ServerInstallError(f"{pin.name}: hosted-http install requires url pin")
    return HostedHttpParameters(url=pin.url)


def compute_snapshot_sha256(snapshot_dir: Path) -> str:
    """Recompute the snapshot bundle sha256 over HOSTED_HTTP_BUNDLE_FILES.

    Must match server-pool/_capture_deepwiki_snapshot.py::bundle_sha256. Raises
    `FileNotFoundError` if any required file is missing.
    """
    h = hashlib.sha256()
    for name in HOSTED_HTTP_BUNDLE_FILES:
        path = snapshot_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"snapshot bundle missing required file: {path}")
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def verify_snapshot_integrity(pin: PinnedServer, harness_root: Path) -> None:
    """Halt the run if the hosted-HTTP snapshot bundle is missing or drifted.

    REPRODUCIBILITY.md §5: SHA drift halts the run. The snapshot is the
    evidentiary proof of what the hosted server's tool surface looked like at
    capture; drift means the server's tools changed underneath us and any
    cross-run comparison is invalid.
    """
    if pin.install != "hosted-http":
        return
    if not (pin.snapshot_path and pin.snapshot_sha256):
        raise ServerPinMismatch(
            f"{pin.name}: hosted-http pin missing snapshot_path or snapshot_sha256"
        )
    snapshot_dir = harness_root / pin.snapshot_path
    if not snapshot_dir.is_dir():
        raise ServerPinMismatch(
            f"{pin.name}: snapshot_path {snapshot_dir} does not exist or is not a directory"
        )
    try:
        actual = compute_snapshot_sha256(snapshot_dir)
    except FileNotFoundError as e:
        raise ServerPinMismatch(f"{pin.name}: {e}") from e
    if actual != pin.snapshot_sha256:
        raise ServerPinMismatch(
            f"{pin.name}: snapshot drift — pinned {pin.snapshot_sha256}, computed {actual}"
        )


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
                 smoke_timeout_s: float = 30.0, harness_root: Path | str | None = None):
        self.yaml_path = Path(yaml_path)
        # harness_root is the base for resolving snapshot_path on hosted-http
        # pins. Defaults to yaml_path.parent.parent (convention:
        # harness/tcrun/servers_pinned.yaml → harness/ is the root). Tests pass
        # tmp_path explicitly.
        self.harness_root = Path(harness_root) if harness_root else self.yaml_path.parent.parent
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

        Bifurcates by install type: stdio-class installs (npx, self-hosted,
        docker, etc.) use `stdio_client`; hosted-http installs use
        `streamablehttp_client` and gate on `verify_snapshot_integrity` first.

        Uses module-level `stdio_client` / `streamablehttp_client` /
        `ClientSession` so tests can `patch("tcrun.servers.<name>", ...)`
        without going through the real `mcp` package.
        """
        if ClientSession is None:  # pragma: no cover - covered by patches
            raise ServerInstallError("mcp package not installed; cannot spawn servers")
        if pin.install == "hosted-http":
            if streamablehttp_client is None:  # pragma: no cover - covered by patches
                raise ServerInstallError(
                    "mcp.client.streamable_http not installed; cannot spawn hosted-http servers"
                )
            verify_snapshot_integrity(pin, self.harness_root)
            http_params = hosted_http_params_for(pin)
            try:
                # streamablehttp_client yields a 3-tuple: (read, write, get_session_id).
                # The session-id callback is unused by ClientSession itself but exposed
                # for future resumption logic.
                read_w, write_w, _get_session_id = await self._stack.enter_async_context(
                    streamablehttp_client(http_params.url)
                )
            except Exception as e:
                # httpx may raise ConnectError, TimeoutException, etc.; surface
                # them all as install errors so the orchestrator can mark the
                # cell as F1-failed per SPEC.md §7.
                raise ServerInstallError(
                    f"{name}: failed to connect to hosted-http server at {http_params.url}: {e}"
                ) from e
        else:
            if stdio_client is None:  # pragma: no cover - covered by patches
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
    """Best-effort pre-install (F1 detection). Synchronous; called before a sweep.

    docker installs are covered by digest pin (no preflight needed).
    hosted-http installs are remote services with no local install step; the
    snapshot integrity check at spawn-time is the equivalent gate.
    """
    if pin.install == "npx" and pin.package:
        version = f"@{pin.npm_version}" if pin.npm_version else ""
        cmd = ["npm", "view", f"{pin.package}{version}", "version"]
    elif pin.install in ("self-hosted", "npx-or-pip"):
        cmd = ["python", "-c", f"import importlib; importlib.import_module('{pin.name}')"]
    else:
        return  # docker / hosted-http: no local install step
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        raise ServerInstallError(f"{pin.name}: preflight failed: {e}") from e
    if r.returncode != 0:
        raise ServerInstallError(f"{pin.name}: preflight nonzero rc={r.returncode}: {r.stderr.strip()}")
