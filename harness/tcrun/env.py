"""EnvFingerprint capture for Trial.env + per-run summary capture.

Implements SPEC.md §4 EnvFingerprint + §5 rule 3 (environment capture).

Per-trial fingerprint:
    os, python_version, package_hash (SHA-256 of sorted `pip freeze`),
    machine_id (anonymized hostname hash), git_sha of harness checkout.

Per-run summary capture (SPEC.md §5 rule 3): RAM, CPU info, network latency
p50 to api.anthropic.com (3 pings before the run starts), wall-clock UTC.

LOC budget per SPEC.md §11: ~50 LOC.
"""

from __future__ import annotations

import hashlib
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


class EnvFingerprint(BaseModel):
    """Per-trial environment fingerprint (SPEC.md §4)."""

    os: str
    python_version: str
    package_hash: str
    machine_id: str
    git_sha: str


class RunEnvSummary(BaseModel):
    """Per-run environment snapshot written into summary.json (SPEC.md §5 rule 3)."""

    ram_bytes: int
    cpu_model: str
    cpu_count: int
    network_latency_p50_ms: float | None
    wall_clock_utc: datetime
    fingerprint: EnvFingerprint


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pip_freeze() -> str:
    """`pip freeze` output, sorted for stable hashing. Empty string on failure.

    Bound to `sys.executable` so the captured deps are the running interpreter's,
    not whichever `pip` happens to be first on `$PATH` (which would yield the
    system or homebrew env and silently poison `package_hash` / env.lock).
    """
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        lines = sorted(line.strip() for line in out.stdout.splitlines() if line.strip())
        return "\n".join(lines)
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def _git_sha(repo_dir: Path | str | None = None) -> str:
    """git rev-parse HEAD of `repo_dir` (or cwd). 'unknown' if not a repo."""
    cwd = Path(repo_dir) if repo_dir is not None else Path.cwd()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return "unknown"


def capture_fingerprint(repo_dir: Path | str | None = None) -> EnvFingerprint:
    """Capture EnvFingerprint per SPEC.md §4 + §5 rule 3.

    Deterministic on the same environment: identical Python/OS/pip-freeze/host
    produce identical `package_hash` and `machine_id`. `git_sha` is stable
    within a checkout.
    """
    return EnvFingerprint(
        os=platform.platform(),
        python_version=platform.python_version(),
        package_hash=_sha256_text(_pip_freeze()),
        machine_id=_sha256_text(socket.gethostname()),
        git_sha=_git_sha(repo_dir),
    )


def _ping_latency_ms(host: str = "api.anthropic.com", attempts: int = 3) -> float | None:
    """Median TCP-connect latency to host:443 over `attempts` tries. None on failure."""
    samples: list[float] = []
    for _ in range(attempts):
        start = time.perf_counter()
        try:
            with socket.create_connection((host, 443), timeout=5):
                pass
            samples.append((time.perf_counter() - start) * 1000.0)
        except OSError:
            continue
    if not samples:
        return None
    samples.sort()
    return samples[len(samples) // 2]


def capture_run_summary(repo_dir: Path | str | None = None) -> RunEnvSummary:
    """Per-run environment snapshot (SPEC.md §5 rule 3 — written into summary.json)."""
    try:
        import psutil  # type: ignore
        ram_bytes = int(psutil.virtual_memory().total)
        cpu_count = int(psutil.cpu_count(logical=True) or 0)
    except ImportError:
        ram_bytes = 0
        cpu_count = 0
    return RunEnvSummary(
        ram_bytes=ram_bytes,
        cpu_model=platform.processor() or platform.machine(),
        cpu_count=cpu_count,
        network_latency_p50_ms=_ping_latency_ms(),
        wall_clock_utc=datetime.now(timezone.utc),
        fingerprint=capture_fingerprint(repo_dir),
    )
