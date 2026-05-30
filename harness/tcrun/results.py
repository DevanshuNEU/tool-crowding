"""Trial Pydantic schema + JSONL writer + schema validation.

Implements SPEC.md §4 (Data Schema) + §3 ResultWriter responsibility.

Schema v1.2 (locked 2026-05-25, embedder swappability work) adds four
embedder fields (mandatory with v1-primary defaults) and aligns the
`tool_listing_strategy` literal to Config (drops legacy `rag-mcp` and
`mcp-zero` values, neither of which any trial ever wrote):

    - embedder_provider: Literal["openai","voyageai","bge"] = "openai"
    - embedder_model: str = "text-embedding-3-large"
    - embedder_snapshot: str = "text-embedding-3-large"
    - embedder_dimension: int = 3072

Schema v1.1 (post-PADDING_STRATEGY.md v1.2 amendment) added three optional
padding-control fields with sensible defaults.

Schema evolution rules per SPEC.md §4: MINOR bump adds optional fields with
defaults; old analyzers ignore unknown fields. The reader chains migrations
v1.0 → v1.1 → v1.2 so any supported source version hydrates to the current
schema. Pre-v1.2 records with legacy `tool_listing_strategy` values are
normalized in the v1.1→v1.2 migration step.

LOC budget per SPEC.md §11: ~220 LOC (extended ~+30 for v1.2).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

from pydantic import BaseModel, Field, ValidationError


# Schema-version constants per SPEC.md §4 evolution rules.
SCHEMA_VERSION_V1_0 = "1.0"
SCHEMA_VERSION_V1_1 = "1.1"
SCHEMA_VERSION_V1_2 = "1.2"
CURRENT_SCHEMA_VERSION = SCHEMA_VERSION_V1_2
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = (
    SCHEMA_VERSION_V1_0,
    SCHEMA_VERSION_V1_1,
    SCHEMA_VERSION_V1_2,
)


# Per-tool-call audit sub-schema. SPEC.md §4 Trial.tool_calls field.
# Step record fields are dictated by the prompt: step_idx, server_called,
# tool_called, args_hash, response_summary, latency_ms, error_or_null.
class ToolCall(BaseModel):
    """Per-step tool-call audit record (SPEC.md §4 + §6 observability)."""

    step_idx: int = Field(..., ge=1, description="1-indexed step within the trial")
    server_called: str
    tool_called: str
    args_hash: str = Field(..., description="SHA-256 of canonicalized tool args")
    response_summary: str = Field(..., description="Truncated response (<=4k chars per SPEC §6)")
    latency_ms: int = Field(..., ge=0)
    error: str | None = Field(default=None, description="Null on success; server error message otherwise")
    # SPEC.md §4 enrichments (kept optional for backwards-compat with the prompt-spec subset).
    was_valid: bool = True
    was_hallucinated: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    # Full flattened tool-result length BEFORE the model-facing cap
    # (tool_result_char_cap). result_chars > the cap ⇒ the model saw a clipped
    # result — the signal that surfaced the github-smoke answer-truncation bug.
    result_chars: int = 0


class ServerEntry(BaseModel):
    """One installed server in the cell's server_set (SPEC.md §4)."""

    server_name: str
    server_version: str
    tool_count: int = Field(..., ge=0)
    description_tokens: int = Field(..., ge=0)


class SamplingParams(BaseModel):
    """Model sampling parameters (SPEC.md §4).

    `top_p` was removed 2026-05-26: Sonnet 4.6+ rejects requests that specify
    both `temperature` and `top_p` (400 invalid_request_error). With
    `temperature=0.0` (our deterministic default), `top_p` has no observable
    effect anyway. Recording a `top_p` value in the Trial row that we never
    actually sent to the API would mislead downstream reproductions.
    """

    temperature: float = 0.0
    max_tokens: int = 4096


class EnvFingerprintRef(BaseModel):
    """Embedded env fingerprint reference inside Trial (full model in env.py)."""

    os: str
    python_version: str
    package_hash: str
    machine_id: str
    git_sha: str


class Trial(BaseModel):
    """Per-trial record appended to results.jsonl. SPEC.md §4."""

    # Identity
    schema_version: str = CURRENT_SCHEMA_VERSION
    harness_version: str
    run_id: str
    cell_id: str
    trial_id: str
    started_at: datetime
    finished_at: datetime

    # What was tested
    task_id: str
    task_version: str
    task_difficulty: Literal["easy", "medium", "hard"]
    model_id: str
    model_provider: Literal["anthropic", "openai", "google"]
    model_snapshot_id: str
    sampling_params: SamplingParams
    server_set: list[ServerEntry]
    N: int = Field(..., ge=0)
    primary_server: str
    ordering_seed: int = Field(..., ge=0)
    tool_listing_strategy: Literal["full", "retriever-on", "oracle-filter"]
    pass_criterion_id: str

    # Embedder identity (v1.2 addition; load-bearing for retriever-ON arm + A1/A5
    # detection per REPRODUCIBILITY.md §1 h_embedder row). Defaults match the v1
    # primary pinned in models/embedder.json so v1.0/v1.1 migrations are clean.
    embedder_provider: Literal["openai", "voyageai", "bge"] = "openai"
    embedder_model: str = "text-embedding-3-large"
    embedder_snapshot: str = "text-embedding-3-large"
    embedder_dimension: int = Field(default=3072, ge=1)

    # What happened (Pareto x-axis definition per SPEC.md §4 inline comment)
    context_input_tokens: int = Field(..., ge=0)
    context_output_tokens: int = Field(..., ge=0)
    tool_calls: list[ToolCall]
    first_correct_tool_step: int | None = None
    pass_: bool = Field(..., alias="pass")
    error_type: Literal[
        "none",
        "wrong_answer",
        "wrong_tool",
        "context_overflow",
        "hallucinated_tool_name",
        "latency_timeout",
        "server_fault",
        "api_fault",
        "agent_gave_up",
        "harness_bug",
        "fake_tool_invoked",
    ]
    error_detail: str | None = None
    cost_usd: float = Field(..., ge=0.0)

    # Padded-N=1 control flags (v1.1 addition per PADDING_STRATEGY.md §6).
    is_padded_n1: bool = False
    fake_tool_invoked: bool = False
    padding_skipped: str | None = None

    # Provenance
    trace_path: str
    seed: int
    oracle_version: str
    env: EnvFingerprintRef

    model_config = {"populate_by_name": True}


class ResultWriter:
    """Append-only JSONL writer with fsync per write (SPEC.md §3 + M3).

    Schema validation on construct + on write. Halts on validation error
    (F15) per SPEC.md §7 failure-mode catalog.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open in append-binary so we can fsync the file descriptor.
        self._fh = open(self.path, "ab")

    def write(self, trial: Trial) -> None:
        """Validate + append + fsync. SPEC.md M3 (append-only + schema_version)."""
        # Re-validate to catch any post-construction mutation.
        validated = Trial.model_validate(trial.model_dump(by_alias=True))
        line = validated.model_dump_json(by_alias=True) + "\n"
        self._fh.write(line.encode("utf-8"))
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()

    def __enter__(self) -> "ResultWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def write_trial(path: Path | str, trial: Trial) -> None:
    """One-shot append helper. Opens, writes, fsyncs, closes."""
    with ResultWriter(path) as w:
        w.write(trial)


def _migrate_v1_0_to_v1_1(record: dict) -> dict:
    """Hydrate a v1.0 record with v1.1 defaults (SPEC.md §4 rule 2)."""
    record.setdefault("is_padded_n1", False)
    record.setdefault("fake_tool_invoked", False)
    record.setdefault("padding_skipped", None)
    record["schema_version"] = SCHEMA_VERSION_V1_1
    return record


# Legacy tool_listing_strategy values that were never written to a real trial
# but lived as dead literals on Trial pre-v1.2. Map forward so any historical
# record with these values still validates.
_LEGACY_STRATEGY_NORMALIZE: dict[str, str] = {
    "rag-mcp": "retriever-on",
    "mcp-zero": "retriever-on",
}


def _migrate_v1_1_to_v1_2(record: dict) -> dict:
    """Hydrate a v1.1 record with v1.2 defaults + normalize legacy strategy.

    Defaults match the v1 primary embedder pinned in models/embedder.json
    (OpenAI text-embedding-3-large, dim 3072). Pre-v1.2 trials that used a
    different embedder configuration (none exist; the embedder layer is
    greenfield in v1.2) would need a manual override at read time.
    """
    legacy = record.get("tool_listing_strategy")
    if legacy in _LEGACY_STRATEGY_NORMALIZE:
        record["tool_listing_strategy"] = _LEGACY_STRATEGY_NORMALIZE[legacy]
    record.setdefault("embedder_provider", "openai")
    record.setdefault("embedder_model", "text-embedding-3-large")
    record.setdefault("embedder_snapshot", "text-embedding-3-large")
    record.setdefault("embedder_dimension", 3072)
    record["schema_version"] = SCHEMA_VERSION_V1_2
    return record


def read_jsonl(path: Path | str) -> Iterator[Trial]:
    """Stream Trial records from a results.jsonl, dispatching on schema_version.

    Per SPEC.md §4 rule 6: "the analyzer dispatches on schema_version". Older
    records are upgraded in memory through the migration chain
    v1.0 → v1.1 → v1.2. Unknown schema_version raises ValueError.
    """
    p = Path(path)
    with open(p, "r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            record = json.loads(raw)
            version = record.get("schema_version")
            if version not in SUPPORTED_SCHEMA_VERSIONS:
                raise ValueError(
                    f"{p}:{line_num}: unsupported schema_version {version!r}; "
                    f"expected one of {SUPPORTED_SCHEMA_VERSIONS}"
                )
            if version == SCHEMA_VERSION_V1_0:
                record = _migrate_v1_0_to_v1_1(record)
                version = SCHEMA_VERSION_V1_1
            if version == SCHEMA_VERSION_V1_1:
                record = _migrate_v1_1_to_v1_2(record)
            try:
                yield Trial.model_validate(record)
            except ValidationError as e:
                raise ValueError(f"{p}:{line_num}: schema validation failed: {e}") from e
