"""Tests for tcrun.retry — backoff policy, retry semantics, categorization."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tcrun.retry import APIFault, ServerFault, categorize, run_with_retry


def test_categorize_api_fault():
    assert categorize(APIFault("429")) == "api_fault"


def test_categorize_server_fault():
    assert categorize(ServerFault("zombie")) == "server_fault"


def test_categorize_unknown_exception_is_persistent():
    assert categorize(RuntimeError("boom")) == "persistent_failure"


def test_run_with_retry_succeeds_first_attempt():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "ok"

    assert run_with_retry(fn) == "ok"
    assert calls["n"] == 1


def test_run_with_retry_retries_then_succeeds():
    """Mock backoff sleep so the test is fast. Tenacity retries up to 5 times."""
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise APIFault("transient")
        return "ok"

    with patch("tenacity.nap.time.sleep", return_value=None):
        assert run_with_retry(fn) == "ok"
    assert calls["n"] == 3


def test_run_with_retry_exhausts_and_reraises_api_fault():
    def fn():
        raise APIFault("persistent 5xx")

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(APIFault):
            run_with_retry(fn)


def test_run_with_retry_does_not_retry_non_categorized_exceptions():
    """ValueError is NOT in retry_if_exception_type → raised immediately."""
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        run_with_retry(fn)
    assert calls["n"] == 1


def test_retry_attempt_count_capped_at_five():
    """SPEC.md M8: max 5 retries total."""
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ServerFault("never recovers")

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(ServerFault):
            run_with_retry(fn)
    assert calls["n"] == 5
