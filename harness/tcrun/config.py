"""Pydantic Config + run_id derivation.

Implements harness/SPEC.md Section 8 Identity rule (v1.2 amendment).

The run_id is derived from the *resolved canonical Config* — the canonical
Config where every path-typed field is augmented with the SHA-256 of the
file at that path. This catches both:
    (a) mutations to the Config itself (paths, flags, seed)
    (b) mutations to artifact CONTENTS at those paths

See ../design/REPRODUCIBILITY.md §1 for the 7-artifact chain spec.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel


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

    # Non-path fields (value-hashed)
    primary_servers: list[str]
    distractors: list[str]
    N: list[int]
    runs_per_cell: int
    model: str
    host: str
    seed: int = 42

    tool_listing_strategy: Literal["full", "retriever-on", "oracle-filter"] = "full"
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
    """Load YAML config from disk and validate."""
    import yaml

    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
