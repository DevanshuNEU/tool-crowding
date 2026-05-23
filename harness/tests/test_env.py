"""Tests for tcrun.env — EnvFingerprint determinism + run summary capture."""

from __future__ import annotations

from unittest.mock import patch

from tcrun.env import (
    EnvFingerprint,
    RunEnvSummary,
    _ping_latency_ms,
    capture_fingerprint,
    capture_run_summary,
)


def test_fingerprint_fields_populated():
    fp = capture_fingerprint()
    assert isinstance(fp, EnvFingerprint)
    assert fp.os
    assert fp.python_version
    assert len(fp.package_hash) == 64  # SHA-256 hex
    assert len(fp.machine_id) == 64


def test_fingerprint_deterministic_on_same_env():
    # Same process, same env → identical fingerprints. Patched pip_freeze
    # ensures stability even if the test machine's pip cache mutates.
    with patch("tcrun.env._pip_freeze", return_value="anthropic==0.40\npydantic==2.10"):
        a = capture_fingerprint()
        b = capture_fingerprint()
    assert a.package_hash == b.package_hash
    assert a.machine_id == b.machine_id


def test_fingerprint_package_hash_depends_on_pip_freeze():
    with patch("tcrun.env._pip_freeze", return_value="a==1.0"):
        a = capture_fingerprint()
    with patch("tcrun.env._pip_freeze", return_value="a==2.0"):
        b = capture_fingerprint()
    assert a.package_hash != b.package_hash


def test_ping_latency_returns_none_when_unreachable():
    # Patch socket.create_connection to always raise → no samples → None.
    with patch("tcrun.env.socket.create_connection", side_effect=OSError("no net")):
        result = _ping_latency_ms(host="example.invalid", attempts=2)
    assert result is None


def test_ping_latency_returns_median_on_success():
    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with patch("tcrun.env.socket.create_connection", return_value=_Ctx()):
        result = _ping_latency_ms(attempts=3)
    assert result is not None
    assert result >= 0.0


def test_run_summary_includes_fingerprint():
    with patch("tcrun.env._ping_latency_ms", return_value=12.5):
        summary = capture_run_summary()
    assert isinstance(summary, RunEnvSummary)
    assert isinstance(summary.fingerprint, EnvFingerprint)
    assert summary.network_latency_p50_ms == 12.5
    assert summary.wall_clock_utc.tzinfo is not None  # UTC-aware


def test_run_summary_handles_unreachable_network():
    with patch("tcrun.env._ping_latency_ms", return_value=None):
        summary = capture_run_summary()
    assert summary.network_latency_p50_ms is None
