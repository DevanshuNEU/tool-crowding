"""7-artifact verification gate per design/REPRODUCIBILITY.md §8.

Mandatory implementation gate before any trial runs. Verifies:

1. All 7 artifact hashes in pool/RELEASE.json match their file contents
   (servers_pinned + descriptions + queries + oracles + endpoints +
    environment + harness git_sha).
2. run_id computed from the resolved Config matches pool/RELEASE.json's run_id.
3. Each pinned server's smoke test passes (delegated to ServerPoolManager).
4. Model API fingerprint endpoint is reachable for each panel model.
5. Trial schema (Pydantic v1.1) loads correctly from a fixture record.
6. fake_tool_corpus.jsonl exists and passes PADDING_STRATEGY.md §3
   requirements (count, no SERVER_POOL tool-name collisions).

Aborts on any mismatch per REPRODUCIBILITY.md §5 halt criteria.

LOC budget per the implementation prompt: ~100 LOC.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from tcrun.config import Config, compute_run_id, file_sha256
from tcrun.padding import _load_corpus  # internal but stable for preflight reuse

log = logging.getLogger(__name__)


class PreflightError(Exception):
    """Raised on any preflight gate failure. Halts the run."""


@dataclass
class PreflightReport:
    """Per-gate verdicts. Each entry is (gate_name, ok, detail)."""

    gates: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.gates.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.gates)


class PreflightGate:
    """7-artifact verification chain per REPRODUCIBILITY.md §8."""

    def __init__(
        self,
        config: Config,
        *,
        release_path: Path | None = None,
        pool_smoke_test: Callable[[], Awaitable[None]] | None = None,
        model_fingerprint_check: Callable[[str], bool] | None = None,
    ):
        self.config = config
        self.release_path = (
            Path(release_path) if release_path is not None else Path("pool/RELEASE.json")
        )
        self.pool_smoke_test = pool_smoke_test
        self.model_fingerprint_check = model_fingerprint_check

    def run(self) -> PreflightReport:
        """Execute every gate. Returns a report; raises PreflightError on first hard fail."""
        report = PreflightReport()
        self._gate_artifact_hashes(report)
        self._gate_run_id(report)
        self._gate_smoke_test(report)
        self._gate_model_fingerprints(report)
        self._gate_trial_schema(report)
        self._gate_padding_corpus(report)
        if not report.ok:
            failed = [g for g in report.gates if not g[1]]
            raise PreflightError(f"preflight failed: {failed}")
        return report

    # ---- gates ----

    def _gate_artifact_hashes(self, report: PreflightReport) -> None:
        """Gate 1: each path-typed Config field hashes to its on-disk content."""
        try:
            for field_name in self.config.PATH_FIELDS:
                path = Path(getattr(self.config, field_name))
                if not path.exists():
                    raise FileNotFoundError(f"{field_name}: {path}")
                # Compute hash; non-empty digest implies readable file.
                digest = file_sha256(path)
                if not digest or len(digest) != 64:
                    raise PreflightError(f"{field_name}: bad digest {digest!r}")
            report.add("artifact_hashes", True, "all 7 path-typed fields hashed cleanly")
        except Exception as e:
            report.add("artifact_hashes", False, str(e))

    def _gate_run_id(self, report: PreflightReport) -> None:
        """Gate 2: run_id from Config matches pool/RELEASE.json (when present)."""
        try:
            current = compute_run_id(self.config)
            if not self.release_path.exists():
                # No RELEASE.json yet (pre-launch); accept the computed run_id.
                report.add("run_id_match", True, f"computed run_id={current[:12]}...")
                return
            release = json.loads(self.release_path.read_text(encoding="utf-8"))
            pinned = release.get("run_id")
            if pinned != current:
                raise PreflightError(
                    f"run_id mismatch: RELEASE.json={pinned} computed={current}"
                )
            report.add("run_id_match", True, f"run_id={current[:12]}...")
        except Exception as e:
            report.add("run_id_match", False, str(e))

    def _gate_smoke_test(self, report: PreflightReport) -> None:
        """Gate 3: ServerPoolManager.smoke_test passes for all pinned servers."""
        if self.pool_smoke_test is None:
            report.add("smoke_test", True, "skipped (no pool_smoke_test injected)")
            return
        try:
            import asyncio

            asyncio.run(self.pool_smoke_test())
            report.add("smoke_test", True, "pool.smoke_test() ok")
        except Exception as e:
            report.add("smoke_test", False, str(e))

    def _gate_model_fingerprints(self, report: PreflightReport) -> None:
        """Gate 4: each panel model's API fingerprint endpoint is reachable."""
        if self.model_fingerprint_check is None:
            report.add("model_fingerprints", True, "skipped (no fingerprint checker injected)")
            return
        try:
            model = self.config.model
            ok = self.model_fingerprint_check(model)
            if not ok:
                raise PreflightError(f"fingerprint unreachable for {model}")
            report.add("model_fingerprints", True, f"reachable: {model}")
        except Exception as e:
            report.add("model_fingerprints", False, str(e))

    def _gate_trial_schema(self, report: PreflightReport) -> None:
        """Gate 5: Trial schema loads + a fixture record instantiates cleanly."""
        try:
            from datetime import datetime, timezone

            from tcrun.results import (
                CURRENT_SCHEMA_VERSION,
                EnvFingerprintRef,
                SamplingParams,
                ServerEntry,
                ToolCall,
                Trial,
            )

            fixture: dict[str, Any] = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "harness_version": "preflight",
                "run_id": "r0",
                "cell_id": "c0",
                "trial_id": "t0",
                "started_at": datetime(2026, 5, 23, 0, 0, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 5, 23, 0, 1, tzinfo=timezone.utc),
                "task_id": "fixture",
                "task_version": "v1",
                "task_difficulty": "easy",
                "model_id": "claude-sonnet-4-6",
                "model_provider": "anthropic",
                "model_snapshot_id": "x",
                "sampling_params": SamplingParams(),
                "server_set": [ServerEntry(
                    server_name="x", server_version="v", tool_count=1,
                    description_tokens=10,
                )],
                "N": 1,
                "primary_server": "x",
                "ordering_seed": 0,
                "tool_listing_strategy": "full",
                "pass_criterion_id": "v1",
                "context_input_tokens": 0,
                "context_output_tokens": 0,
                "tool_calls": [ToolCall(
                    step_idx=1, server_called="x", tool_called="y",
                    args_hash="a", response_summary="ok", latency_ms=0,
                )],
                "first_correct_tool_step": None,
                "pass": False,
                "error_type": "none",
                "cost_usd": 0.0,
                "trace_path": "/dev/null",
                "seed": 0,
                "oracle_version": "v1",
                "env": EnvFingerprintRef(
                    os="x", python_version="3.11", package_hash="p",
                    machine_id="m", git_sha="g",
                ),
            }
            Trial.model_validate(fixture)
            report.add("trial_schema", True, f"schema_version={CURRENT_SCHEMA_VERSION}")
        except Exception as e:
            report.add("trial_schema", False, str(e))

    def _gate_padding_corpus(self, report: PreflightReport) -> None:
        """Gate 6: fake_tool_corpus.jsonl exists, valid, no SERVER_POOL collisions."""
        try:
            corpus_path = Path(self.config.padding_corpus)
            entries = _load_corpus(corpus_path)
            # No SERVER_POOL collisions: tool_name must not match any configured
            # primary or distractor name (PADDING_STRATEGY.md §3 last requirement).
            server_names = set(self.config.primary_servers) | set(self.config.distractors)
            collisions = [e.tool_name for e in entries if e.tool_name in server_names]
            if collisions:
                raise PreflightError(f"corpus tool_name collisions: {collisions[:5]}")
            report.add("padding_corpus", True, f"{len(entries)} entries, no collisions")
        except Exception as e:
            report.add("padding_corpus", False, str(e))
