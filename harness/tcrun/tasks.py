"""TaskLoader: load tasks/v1/queries.jsonl into typed Query objects.

Implements SPEC.md §3 TaskLoader component.

Query schema is the binding source in tasks/v1/README.md §"Format". The
loader halts the run on any of the failure modes listed in SPEC.md §3
TaskLoader.MUST-fail rules:
    - file not found → FileNotFoundError (let caller convert to TaskLoadError)
    - JSONL parse error → TaskLoadError
    - schema validation failure → TaskLoadError

Empty file (no records) is a NON-fatal case at the loader level: returns an
empty list. The pre-flight gate (SPEC.md §12) is the layer that enforces
"at least 50 queries before launch".

LOC budget per SPEC.md §11: ~80 LOC.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class FivegramAuditEntry(BaseModel):
    """One 5-gram audit row per query (tasks/v1/README.md §"Format")."""

    ngram: str
    github_hits: int = Field(..., ge=0)
    web_hits: int = Field(..., ge=0)


class Query(BaseModel):
    """One task query (tasks/v1/README.md §"Format")."""

    query_id: str
    tier: Literal["public", "held_back", "sealed"]
    text: str
    ground_truth_target: str
    ground_truth_code: str
    source_repo: str
    source_publication_date: str
    source_license: Literal["GPL-2.0", "GPL-3.0", "LGPL", "AGPL", "proprietary"]
    difficulty_quartile: Literal["q1", "q2", "q3", "q4"]
    primary_server: str
    fivegram_audit: list[FivegramAuditEntry] = Field(default_factory=list)


class TaskLoadError(Exception):
    """Raised on JSONL parse error or schema validation failure (SPEC.md §3)."""


class TaskLoader:
    """Load + validate `tasks/v1/queries.jsonl`. SPEC.md §3 TaskLoader."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> list[Query]:
        """Return the list of validated `Query` objects.

        File not found → FileNotFoundError. Empty file → []. Any malformed
        record (JSON or schema) → TaskLoadError.
        """
        if not self.path.exists():
            raise FileNotFoundError(f"task set not found: {self.path}")
        queries: list[Query] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line_num, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError as e:
                    raise TaskLoadError(f"{self.path}:{line_num}: invalid JSON: {e}") from e
                try:
                    queries.append(Query.model_validate(record))
                except ValidationError as e:
                    raise TaskLoadError(
                        f"{self.path}:{line_num}: schema validation failed: {e}"
                    ) from e
        return queries


def load_tasks(path: Path | str) -> list[Query]:
    """Convenience wrapper around `TaskLoader(path).load()`."""
    return TaskLoader(path).load()
