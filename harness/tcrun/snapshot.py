"""Install-time artifact generators: pool/descriptions.json + environment.lock.

Both outputs participate in `run_id` via `Config.PATH_FIELDS` (content-hashed
per `design/REPRODUCIBILITY.md §1`). To keep `run_id` stable across re-runs
of the generators when nothing has drifted, both outputs are deterministically
ordered: no timestamps in the file body, sorted keys, sorted lists, atomic
write via tmp+rename. Re-snapshotting on an unchanged environment produces
byte-identical files.

Operational contract:

* `tcrun snapshot-env` is a one-shot library install step. Re-run when
  Python deps or docker images change. The output is git-tracked.
* `tcrun snapshot-descriptions --server NAME` is incremental: it opens
  one MCP session, calls `list_tools`, merges the entry into the existing
  `pool/descriptions.json` (creating it if missing). Use the `--all`
  variant only when every pinned server is locally runnable; it tolerates
  per-server failures (logged, surfaced in the exit code) so the rest of
  the snapshot still lands.

This module deliberately re-implements its own thin MCP session lifecycle
(via AsyncExitStack) rather than going through ServerPoolManager, because
the manager's `_spawn_one` consumes the `list_tools` result for smoke
verification and doesn't preserve the full tool definitions we need here.
The launch primitives (`stdio_client`, `stdio_params_for`) are shared.

LOC budget: ~220.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import shutil
import subprocess
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import yaml

from tcrun.env import _git_sha, _pip_freeze
from tcrun.servers import (
    ClientSession,
    McpError,
    PinnedServer,
    load_pinned_servers,
    stdio_client,
    stdio_params_for,
)

log = logging.getLogger(__name__)


DESCRIPTIONS_SCHEMA_VERSION = "1.0"
ENV_LOCK_SCHEMA_VERSION = "1.0"


class SnapshotError(RuntimeError):
    """Raised when a single server snapshot fails irrecoverably."""


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------


def _atomic_write_json(out_path: Path, payload: dict[str, Any]) -> None:
    """Write `payload` as sorted-key JSON via tmp+rename. Parent dir auto-created."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, sort_keys=True, indent=2)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    tmp.replace(out_path)


# ---------------------------------------------------------------------------
# environment.lock
# ---------------------------------------------------------------------------


def _inspect_docker_digest(image_ref: str) -> str | None:
    """Return the `sha256:<hex>` RepoDigest for `image_ref`, or None on failure.

    Returns None (graceful) if Docker is absent or the image isn't pulled —
    docker-pinned servers can still be snapshotted later when Docker is up,
    and `tcrun snapshot-env` is not the place to halt a run.
    """
    if shutil.which("docker") is None:
        return None
    try:
        r = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                "--format={{index .RepoDigests 0}}",
                image_ref,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    # `docker inspect --format='{{index .RepoDigests 0}}'` returns
    # `<image>@sha256:<hex>`; take the digest portion for stable hashing.
    if "@sha256:" in out:
        return out.split("@", 1)[1]
    return out or None


def _capture_docker_digests(servers_yaml_path: Path | str) -> dict[str, str]:
    """Capture {docker_image: sha256:<hex>} for every docker-pinned server.

    Output is sorted by image name for deterministic hashing into the
    env.lock file. Servers without a `docker_image` field, and servers whose
    digest can't be retrieved, are omitted (logged at WARNING).
    """
    p = Path(servers_yaml_path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    pairs: list[tuple[str, str]] = []
    for section in ("primary_servers", "distractors"):
        for row in raw.get(section) or []:
            if row.get("install") != "docker":
                continue
            image = row.get("docker_image")
            tag = row.get("docker_tag", "latest")
            if not image:
                continue
            digest = _inspect_docker_digest(f"{image}:{tag}")
            if digest:
                pairs.append((image, digest))
            else:
                log.warning("docker digest unavailable for %s:%s", image, tag)
    return dict(sorted(pairs))


def write_env_lock(
    out_path: Path | str,
    *,
    servers_yaml_path: Path | str | None = None,
    repo_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate environment.lock as a deterministic JSON file.

    Captures the audit-relevant runtime state: OS, Python version, sorted
    `pip freeze` output, the harness git SHA, and (when `servers_yaml_path`
    is provided) the docker image digests for any docker-pinned servers.

    No `captured_at` field on purpose — re-running on the same environment
    must produce byte-identical output so `run_id` remains stable. State
    drift (new deps, new docker pull) → different bytes → new `run_id`,
    which IS the intended reproducibility signal.
    """
    freeze = _pip_freeze()
    payload: dict[str, Any] = {
        "schema_version": ENV_LOCK_SCHEMA_VERSION,
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "harness_git_sha": _git_sha(repo_dir),
        "pip_freeze": freeze.splitlines() if freeze else [],
    }
    if servers_yaml_path is not None:
        payload["docker_images"] = _capture_docker_digests(servers_yaml_path)
    out = Path(out_path)
    _atomic_write_json(out, payload)
    return payload


# ---------------------------------------------------------------------------
# pool/descriptions.json
# ---------------------------------------------------------------------------


def _serialize_tool(tool: Any) -> dict[str, Any]:
    """Extract `{name, description, inputSchema}` from an mcp.types.Tool.

    Tolerates both attribute access (real `mcp` SDK types) and dict access
    (test stubs). Schema falls back to `{"type": "object"}` so a missing
    inputSchema still produces a structurally valid Anthropic tool def
    downstream.
    """
    name = (
        getattr(tool, "name", None)
        or (tool.get("name", "") if isinstance(tool, dict) else "")
        or ""
    )
    desc = (
        getattr(tool, "description", None)
        or (tool.get("description", "") if isinstance(tool, dict) else "")
        or ""
    )
    schema = (
        getattr(tool, "inputSchema", None)
        or (tool.get("inputSchema") if isinstance(tool, dict) else None)
        or (tool.get("input_schema") if isinstance(tool, dict) else None)
        or {"type": "object"}
    )
    return {"name": name, "description": desc, "inputSchema": schema}


def _pin_identity(pin: PinnedServer) -> str:
    """The strongest available content-pin for `pin`. 'unpinned' as last resort.

    Preference order matches `verify_pins` (servers.py) — source-built repos
    get their git_sha first, npm-installs get the lock hash or version, etc.
    """
    return (
        pin.git_sha
        or pin.npm_lock_hash
        or pin.docker_digest
        or pin.npm_version
        or pin.tarball_sha256
        or "unpinned"
    )


def _first_leaf_exception(eg: BaseExceptionGroup) -> BaseException:
    """Walk a (possibly nested) ExceptionGroup; return a representative leaf.

    Prefers non-cancellation leaves because anyio cancels sibling tasks when
    one of them raises the actual failure — without this preference the
    SnapshotError message would name CancelledError rather than the real cause
    (e.g. the McpError that triggered the cancellation).
    """
    leaves: list[BaseException] = []

    def _walk(group: BaseExceptionGroup) -> None:
        for exc in group.exceptions:
            if isinstance(exc, BaseExceptionGroup):
                _walk(exc)
            else:
                leaves.append(exc)

    _walk(eg)
    for leaf in leaves:
        if not isinstance(leaf, asyncio.CancelledError):
            return leaf
    return leaves[0] if leaves else eg


async def _await_classified(
    coro: Any,
    *,
    pin_name: str,
    stage: str,
    timeout_s: float | None = None,
) -> Any:
    """Await `coro` (optionally with timeout); classify failures as `SnapshotError`.

    Every non-cancellation failure becomes `SnapshotError(f"{pin}: {stage}: ...")`
    with `raise from` preserving the original cause. ExceptionGroups raised by
    the MCP client's anyio task group are unwrapped to their leaf cause so the
    reason field that `snapshot_all_descriptions` logs is human-readable.
    Cancellations propagate unchanged.
    """
    try:
        if timeout_s is None:
            return await coro
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.CancelledError:
        raise
    except (asyncio.TimeoutError, TimeoutError) as e:
        raise SnapshotError(
            f"{pin_name}: {stage} (timed out after {timeout_s}s)"
        ) from e
    except McpError as e:
        raise SnapshotError(f"{pin_name}: {stage}: McpError: {e}") from e
    except OSError as e:
        raise SnapshotError(f"{pin_name}: {stage}: {e}") from e
    except BaseExceptionGroup as eg:
        inner = _first_leaf_exception(eg)
        if isinstance(inner, asyncio.CancelledError):
            raise
        raise SnapshotError(
            f"{pin_name}: {stage}: {type(inner).__name__}: {inner}"
        ) from inner
    except Exception as e:
        raise SnapshotError(
            f"{pin_name}: {stage}: {type(e).__name__}: {e}"
        ) from e


async def snapshot_server_descriptions(
    pin: PinnedServer,
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Open a fresh MCP session, list_tools, return a descriptions entry.

    Every failure is classified into `SnapshotError` with a stage-prefixed
    message (`failed to spawn subprocess` / `MCP session open` / `MCP initialize`
    / `MCP list_tools`). The MCP client wraps subprocess-died-during-handshake
    failures as `McpError` inside an `ExceptionGroup` from its anyio task group;
    `_await_classified` unwraps to the leaf cause and chains it via `raise from`
    so the cause survives in tracebacks while `snapshot_all_descriptions` gets
    a human-readable reason string. Cancellations propagate unchanged.
    """
    if stdio_client is None or ClientSession is None:
        raise SnapshotError(
            "mcp package not installed; cannot snapshot server descriptions"
        )
    params = stdio_params_for(pin)
    async with AsyncExitStack() as stack:
        read_w, write_w = await _await_classified(
            stack.enter_async_context(stdio_client(params)),
            pin_name=pin.name,
            stage="failed to spawn subprocess",
        )
        session = await _await_classified(
            stack.enter_async_context(ClientSession(read_w, write_w)),
            pin_name=pin.name,
            stage="MCP session open",
        )
        await _await_classified(
            session.initialize(),
            pin_name=pin.name,
            stage="MCP initialize",
            timeout_s=timeout_s,
        )
        result = await _await_classified(
            session.list_tools(),
            pin_name=pin.name,
            stage="MCP list_tools",
            timeout_s=timeout_s,
        )
        tools = [_serialize_tool(t) for t in (getattr(result, "tools", None) or [])]
        tools.sort(key=lambda t: t["name"])
        return {
            "server_name": pin.name,
            "install": pin.install,
            "pin": _pin_identity(pin),
            "tools": tools,
        }


def _load_existing_descriptions(out_path: Path) -> dict[str, Any]:
    """Read descriptions.json or return a fresh skeleton.

    A corrupt existing file is logged and replaced; this is install-time
    bootstrap work and an unparseable file is more likely to be a half-written
    artifact than a load-bearing manifest.
    """
    if out_path.exists():
        try:
            return json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("existing %s is corrupt; starting fresh", out_path)
    return {"schema_version": DESCRIPTIONS_SCHEMA_VERSION, "servers": {}}


def update_descriptions_file(
    out_path: Path | str,
    server_name: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Merge one server's entry into descriptions.json. Atomic write.

    Sorts servers alphabetically before serializing so the file's bytes are
    deterministic given the same set of entries — re-snapshotting one server
    when the others haven't drifted produces a stable run_id chain.
    """
    out = Path(out_path)
    data = _load_existing_descriptions(out)
    data.setdefault("servers", {})[server_name] = entry
    data["servers"] = dict(sorted(data["servers"].items()))
    _atomic_write_json(out, data)
    return data


async def snapshot_all_descriptions(
    servers_yaml_path: Path | str,
    out_path: Path | str,
    *,
    timeout_s: float = 30.0,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Snapshot every server in `servers_pinned.yaml`; merge into descriptions.json.

    Per-server graceful failure: a server that fails to launch / handshake /
    list_tools is logged + added to the failures list, but the snapshot
    proceeds for the others. Returns `(final_descriptions, [(server, reason)])`.
    """
    pins = load_pinned_servers(servers_yaml_path)
    failures: list[tuple[str, str]] = []
    final: dict[str, Any] = _load_existing_descriptions(Path(out_path))
    for name in sorted(pins):
        pin = pins[name]
        try:
            entry = await snapshot_server_descriptions(pin, timeout_s=timeout_s)
            final = update_descriptions_file(out_path, name, entry)
            log.info("snapshotted %s (%d tools)", name, len(entry["tools"]))
        except Exception as e:  # noqa: BLE001 — log + continue is the contract
            log.warning("snapshot failed for %s: %s", name, e)
            failures.append((name, str(e)))
    return final, failures
