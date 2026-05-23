"""Bounded retry + exponential backoff + jitter for API + MCP calls.

Implements SPEC.md M8 + failure modes F5, F6, F7, F19.

Policy: base 1s, factor 2, max 5 retries, max wait 60s, ±10% jitter.
Categorization: api_fault / server_fault / persistent_failure. Persistent
failures mark the trial and continue; they do NOT halt the run (SPEC.md §7).

LOC budget per SPEC.md §11: ~40 LOC.
"""

from __future__ import annotations

from typing import Callable, Literal, TypeVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

T = TypeVar("T")

FaultCategory = Literal["api_fault", "server_fault", "persistent_failure", "none"]


class APIFault(Exception):
    """Transient Anthropic API error (4xx/5xx, timeout) — F5/F6/F7."""


class ServerFault(Exception):
    """Transient MCP server error (malformed JSON-RPC, zombie, timeout) — F3/F4."""


# Standard policy: 5 retries total, exponential base 1s factor 2 capped at 60s,
# ±10% jitter via tenacity's jitter parameter (initial=1 means up to 1s extra).
retry_policy = retry(
    retry=retry_if_exception_type((APIFault, ServerFault)),
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1.0, max=60.0, exp_base=2.0, jitter=0.1),
    reraise=True,
)


def categorize(exc: BaseException) -> FaultCategory:
    """Classify an exception per SPEC.md §7 failure-mode catalog."""
    if isinstance(exc, RetryError):
        return categorize(exc.last_attempt.exception() or exc)
    if isinstance(exc, APIFault):
        return "api_fault"
    if isinstance(exc, ServerFault):
        return "server_fault"
    return "persistent_failure"


def run_with_retry(fn: Callable[..., T], *args, **kwargs) -> T:
    """Invoke `fn` under the standard retry policy. Re-raises on exhaustion."""
    return retry_policy(fn)(*args, **kwargs)
