"""Pydantic Config + run_id derivation.

Implements harness/SPEC.md Section 8 Identity rule (v1.2 amendment).

The run_id is derived from the *resolved canonical Config* — the canonical
Config where every path-typed field is augmented with the SHA-256 of the
file at that path. This catches both:
    (a) mutations to the Config itself (paths, flags, seed)
    (b) mutations to artifact CONTENTS at those paths

See ../design/REPRODUCIBILITY.md §1 for the 8-artifact chain spec
(embedder added as the 8th artifact 2026-05-25).
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel


# Embedder is the one Config knob users swap day-to-day (locked
# 2026-05-25: "embedder runtime-swappable"). The TC_EMBEDDER env var
# overrides the YAML's `embedder:` field at load time so a swap is one
# `export` away — no edit to the committed config. Either a short alias
# (openai / voyage / bge) or a literal path is accepted.
# Reproducibility holds: compute_run_id hashes the *resolved* Config, so
# different TC_EMBEDDER values produce different run_ids automatically.
EMBEDDER_ALIASES: dict[str, str] = {
    "openai": "models/embedder.json",
    "voyage": "models/embedder.voyage.json",
    "voyageai": "models/embedder.voyage.json",
    "bge": "models/embedder.bge-m3.json",
    "bge-m3": "models/embedder.bge-m3.json",
}


# Default cap on the number of characters of a single tool result forwarded to
# the model. Runtime-swappable via the TC_TOOL_RESULT_CHAR_CAP env var (handled
# in load_config) and value-hashed into run_id, so any cap sweep is
# reproducibility-honest. 65536 chars (~16k tokens) fits observed source files
# (the github smoke target is 16,895 chars) with headroom while bounding
# context growth so a large retrieved file cannot silently drive the
# degradation curve via kill criterion #2 (context overflow). See
# ../design/TOOL_RESULT_CAP.md for the rationale + planned sensitivity analysis.
DEFAULT_TOOL_RESULT_CHAR_CAP = 65536


def _resolve_embedder_env(value: str) -> str:
    """Map a TC_EMBEDDER value to a pin-file path. Accepts alias or literal path.

    If the value matches no known alias AND doesn't look like a path (no `/`
    and not ending in `.json`), warn — likely a typo'd alias such as
    `voyage-ai` instead of `voyage`. Preserves the literal-path escape hatch
    while making mistakes loud.
    """
    normalized = value.strip().lower()
    if normalized in EMBEDDER_ALIASES:
        return EMBEDDER_ALIASES[normalized]
    if "/" not in value and not value.endswith(".json"):
        print(
            f"[load_config] WARNING: TC_EMBEDDER={value!r} matches no known alias "
            f"({sorted(EMBEDDER_ALIASES)}) and doesn't look like a path; "
            f"treating as literal path (will likely fail at preflight).",
            file=sys.stderr,
        )
    return value


class Config(BaseModel):
    """The canonical Config object.

    Path-typed fields (registered in PATH_FIELDS) participate in run_id by
    content hash, not just by path string. Non-path fields participate by value.
    The `out` field is dropped from run_id derivation (running the same
    experiment to a different output directory should not change run_id).
    """

    # Path-typed fields (content-hashed into run_id per SPEC.md Section 8 v1.2)
    task_set: Path
    oracle: Path
    servers_pinned: Path
    descriptions: Path
    endpoints: Path
    environment: Path
    padding_corpus: Path
    # Mandatory like the other 7 PATH_FIELDS. mve.yaml supplies the default
    # pin path; TC_EMBEDDER env var (handled by load_config) is the runtime
    # override. No Python-side default — forgetting embedder=... fails loud.
    embedder: Path

    # Non-path fields (value-hashed)
    primary_servers: list[str]
    distractors: list[str]
    N: list[int]
    runs_per_cell: int
    model: str
    host: str
    seed: int = 42

    tool_listing_strategy: Literal["full", "retriever-on", "oracle-filter"] = "full"
    # Top-k for the retriever-ON arm. Default 5 matches RAG-MCP §3 + our
    # pre-registration; varying k produces a new run_id (value-hashed) so any
    # sensitivity sweep is reproducibility-honest.
    retriever_top_k: int = 5
    # Max chars of a single tool result handed to the model. Runtime-swappable
    # via TC_TOOL_RESULT_CHAR_CAP (load_config); value-hashed into run_id so a
    # cap sweep is reproducibility-honest. See ../design/TOOL_RESULT_CAP.md.
    tool_result_char_cap: int = DEFAULT_TOOL_RESULT_CHAR_CAP
    include_padded_n1_control: bool = True
    include_no_mcp_baseline: bool = False
    include_random_tool_call_baseline: bool = False
    ragmcp_replication: bool = False

    # Harness version (resolved at runtime from `git rev-parse HEAD` of harness checkout
    # per SPEC.md Section 8 path-typed fields table; "TBD" until populated)
    harness_version: str = "TBD"

    # Output path is NOT a registered path-typed field; it does not participate in run_id
    out: Path

    # The path-typed fields that participate in run_id by content hash.
    # Match this list to SPEC.md Section 8 Identity rule path-typed table.
    PATH_FIELDS: ClassVar[tuple[str, ...]] = (
        "task_set",
        "oracle",
        "servers_pinned",
        "descriptions",
        "endpoints",
        "environment",
        "padding_corpus",
        "embedder",
    )


def file_sha256(path: Path | str) -> str:
    """SHA-256 of file contents, lowercase hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_run_id(config: Config) -> str:
    """Derive run_id from the resolved canonical Config per SPEC.md Section 8 v1.2.

    Each path-typed field is augmented with {"path": str, "sha256": str} before
    the canonical Config is hashed. Output path is dropped from hash inputs.
    """
    resolved = config.model_dump(mode="json")  # mode="json" serializes Path to str
    for field_name in config.PATH_FIELDS:
        path = resolved[field_name]
        resolved[field_name] = {
            "path": path,
            "sha256": file_sha256(path),
        }
    # Output path does not participate in run_id identity.
    resolved.pop("out", None)
    canonical = json.dumps(resolved, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_config(path: Path | str) -> Config:
    """Load YAML config from disk, apply TC_EMBEDDER override, and validate.

    Env override (runtime-swappable embedder per locked 2026-05-25 decision):
        TC_EMBEDDER=voyage  → models/embedder.voyage.json
        TC_EMBEDDER=bge     → models/embedder.bge-m3.json
        TC_EMBEDDER=models/embedder.custom.json  → that path verbatim
    The resolved Config hashes into run_id, so env overrides produce a new
    run_id and the resolved config (post-override) is the audit artifact.
    """
    import yaml

    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    env_choice = os.getenv("TC_EMBEDDER")
    if env_choice:
        resolved = _resolve_embedder_env(env_choice)
        # Loud notification: a stale shell `export TC_EMBEDDER=voyage` from a
        # prior session would otherwise silently change run_id at load time.
        print(
            f"[load_config] TC_EMBEDDER={env_choice!r} → embedder={resolved!r} "
            f"(overrides YAML; resolved Config will hash into a new run_id)",
            file=sys.stderr,
        )
        raw["embedder"] = resolved
    env_cap = os.getenv("TC_TOOL_RESULT_CHAR_CAP")
    if env_cap:
        try:
            cap_val = int(env_cap)
        except ValueError:
            print(
                f"[load_config] WARNING: TC_TOOL_RESULT_CHAR_CAP={env_cap!r} is not "
                f"an integer; ignoring and using the YAML/default value.",
                file=sys.stderr,
            )
        else:
            print(
                f"[load_config] TC_TOOL_RESULT_CHAR_CAP={env_cap!r} overrides YAML "
                f"tool_result_char_cap (resolved Config hashes into a new run_id)",
                file=sys.stderr,
            )
            raw["tool_result_char_cap"] = cap_val
    return Config(**raw)
