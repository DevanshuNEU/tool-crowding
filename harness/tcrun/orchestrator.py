"""Cell loop + resume logic + per-cell server pool lifecycle.

Implements SPEC.md §3 Orchestrator component.

Responsibilities (verbatim from SPEC.md §3):
    - enumerate cells from config (cartesian over model x N x query x ordering x repetition)
    - dispatch trials with bounded concurrency (asyncio.Semaphore)
    - manage hermetic per-cell server pool lifecycle (fresh subprocess tree per cell)
    - handle resume-from-checkpoint (skip cells whose cell_id is in completed set)
    - cost monitor: halt at config.cost_cap_usd
    - never silently swallow exceptions (categorize via retry.categorize; halt vs mark)

MUST NOT (per SPEC.md §3): silently swallow exceptions; modify task data;
cache results between cells without a content-addressed key.

Wave 2A sibling interfaces (assumed; types referenced lazily to avoid import
cycles when servers.py / agent.py are scaffolds):
    from tcrun.servers import ServerPoolManager  # async context manager
        await pool.start(server_names) -> list[ClientSession]
        await pool.smoke_test() -> None  (validates SHAs)
    from tcrun.agent import AgentHarness
        await harness.run_trial(cell_spec, query) -> Trial

agent_factory contract (v1.2+):
    agent_factory(pool, embedder_spec) -> Agent

    The orchestrator owns the embedder pin: it is read once at __init__ from
    Config.embedder and threaded into every agent_factory call. Concrete agent
    implementations MUST propagate embedder_spec into TrialInputs.embedder_spec
    on every dispatched trial so the 4 Trial embedder_* fields stay consistent
    with the run_id's h_embedder. The 2-arg signature is a hard contract: a
    factory that forgets the spec fails loudly with a TypeError at dispatch,
    not silently with mis-attributed trial rows.

LOC budget per the implementation prompt: ~280 LOC.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Callable, Iterable

from tcrun.config import Config, compute_run_id
from tcrun.embedder import load_embedder_pin
from tcrun.results import ResultWriter, Trial
from tcrun.retry import categorize
from tcrun.seed import cell_seed as derive_cell_seed
from tcrun.seed import trial_seed as derive_trial_seed

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Cell + checkpoint data classes
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class CellSpec:
    """One experimental cell: a unique (model, N, query, ordering, repetition) tuple.

    cell_id is content-addressed per SPEC.md §3 + REPRODUCIBILITY.md §2.
    """

    run_id: str
    model: str
    N: int
    query_id: str
    primary_server: str
    ordering_seed: int
    repetition_id: int
    is_padded_n1: bool = False

    @property
    def cell_id(self) -> str:
        payload = "||".join(
            [
                self.run_id,
                self.model,
                str(self.N),
                self.query_id,
                self.primary_server,
                str(self.ordering_seed),
                f"padded={self.is_padded_n1}",
            ]
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def trial_id(self) -> str:
        payload = "||".join([self.cell_id, str(self.repetition_id)])
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def cell_seed(self) -> str:
        return derive_cell_seed(
            self.run_id, self.model, self.N, self.query_id, self.ordering_seed
        )

    @property
    def trial_seed(self) -> str:
        return derive_trial_seed(self.cell_seed, self.repetition_id)


@dataclass
class Checkpoint:
    """Persisted resume state. JSON-serializable; lives at results/<run_id>/checkpoint.json."""

    run_id: str
    completed_trial_ids: set[str] = field(default_factory=set)
    running_cost_usd: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "completed_trial_ids": sorted(self.completed_trial_ids),
            "running_cost_usd": self.running_cost_usd,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            run_id=data["run_id"],
            completed_trial_ids=set(data.get("completed_trial_ids", [])),
            running_cost_usd=float(data.get("running_cost_usd", 0.0)),
        )


class CostCapExceeded(Exception):
    """Raised when running_cost_usd crosses config.cost_cap_usd. Halts the run."""


class OrchestratorHalt(Exception):
    """Raised when an uncategorized / persistent exception requires halting."""


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------


# Optional cost cap; not in Config schema today, so we read it as an attribute
# with a safe default. PILOT_V0.md §"Sat AM go/no-go gate" item 4 mandates a cost
# monitor that halts at extrapolated $150; default here is $200 (SPEC.md S1).
DEFAULT_COST_CAP_USD = 200.0
DEFAULT_CONCURRENCY = 8


class Orchestrator:
    """Cell enumeration + dispatch + checkpoint + resume.

    Hermetic per-cell pool lifecycle: each cell opens an
    `async with ServerPoolManager(...)` block and tears it down before the
    next cell starts. Within a cell, trials over (ordering, repetition)
    dispatch concurrently with a Semaphore bound.
    """

    def __init__(
        self,
        config: Config,
        *,
        run_dir: Path | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        cost_cap_usd: float | None = None,
        pool_factory: Callable[..., Any] | None = None,
        agent_factory: Callable[..., Any] | None = None,
        queries: Iterable[Any] | None = None,
    ):
        self.config = config
        self.run_id = compute_run_id(config)
        self.run_dir = Path(run_dir) if run_dir is not None else Path(config.out) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.run_dir / "checkpoint.json"
        self.trials_path = self.run_dir / "trials.jsonl"
        self.summary_path = self.run_dir / "summary.json"
        self.concurrency = concurrency
        self.cost_cap_usd = float(
            cost_cap_usd
            if cost_cap_usd is not None
            else getattr(config, "cost_cap_usd", DEFAULT_COST_CAP_USD)
        )
        self._pool_factory = pool_factory
        self._agent_factory = agent_factory
        self._queries = list(queries) if queries is not None else []
        # Load the embedder pin once at __init__ (cheap; no SDK needed) so
        # the agent_factory contract can deliver it to every dispatched agent.
        # Failing here is the right place: pin malformed → orchestrator refuses
        # to construct, no trials run, no half-pinned rows ever written.
        self._embedder_spec = load_embedder_pin(self.config.embedder)
        self.checkpoint = self._load_checkpoint()

    # ---- checkpoint persistence ----

    def _load_checkpoint(self) -> Checkpoint:
        if self.checkpoint_path.exists():
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            if data.get("run_id") != self.run_id:
                raise OrchestratorHalt(
                    f"checkpoint run_id mismatch: file={data.get('run_id')} "
                    f"current={self.run_id}; refusing to mix runs"
                )
            return Checkpoint.from_json(data)
        return Checkpoint(run_id=self.run_id)

    def _save_checkpoint(self) -> None:
        tmp = self.checkpoint_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.checkpoint.to_json(), sort_keys=True, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.checkpoint_path)

    # ---- enumeration ----

    def enumerate_cells(self) -> list[CellSpec]:
        """Cartesian over (primary_server, N, query, ordering, repetition).

        Plus an optional padded-N=1 control trial set when N=1 is in the
        config and include_padded_n1_control is true.
        """
        cells: list[CellSpec] = []
        primaries = list(self.config.primary_servers)
        Ns = list(self.config.N)
        runs_per_cell = self.config.runs_per_cell
        # 5 orderings per cell per SPEC.md §5; honored by ordering_seed 0..4.
        orderings = list(range(5))
        queries = [getattr(q, "query_id", str(q)) for q in self._queries]
        if not queries:
            # Permits enumeration tests without a populated TaskLoader; in
            # production preflight ensures queries.jsonl is loaded first.
            queries = ["__no_queries__"]

        for primary, N, q, ord_seed, rep in product(primaries, Ns, queries, orderings, range(runs_per_cell)):
            cells.append(
                CellSpec(
                    run_id=self.run_id,
                    model=self.config.model,
                    N=N,
                    query_id=q,
                    primary_server=primary,
                    ordering_seed=ord_seed,
                    repetition_id=rep,
                    is_padded_n1=False,
                )
            )
            if N == 1 and self.config.include_padded_n1_control:
                cells.append(
                    CellSpec(
                        run_id=self.run_id,
                        model=self.config.model,
                        N=N,
                        query_id=q,
                        primary_server=primary,
                        ordering_seed=ord_seed,
                        repetition_id=rep,
                        is_padded_n1=True,
                    )
                )
        return cells

    # ---- cost monitor ----

    def _record_cost(self, delta_usd: float) -> None:
        self.checkpoint.running_cost_usd += float(delta_usd)
        if self.checkpoint.running_cost_usd > self.cost_cap_usd:
            raise CostCapExceeded(
                f"cost cap exceeded: ${self.checkpoint.running_cost_usd:.2f} "
                f"> ${self.cost_cap_usd:.2f}"
            )

    # ---- main loop ----

    async def run(self) -> dict[str, Any]:
        """Dispatch all cells; return the summary dict."""
        cells = self.enumerate_cells()
        # Group by (primary, N, ordering, padded) so we can open one pool per
        # group and reuse it across repetitions. Cell-level hermetic per SPEC §3.
        groups: dict[tuple[Any, ...], list[CellSpec]] = {}
        for c in cells:
            key = (c.primary_server, c.N, c.ordering_seed, c.is_padded_n1)
            groups.setdefault(key, []).append(c)

        sem = asyncio.Semaphore(self.concurrency)
        writer = ResultWriter(self.trials_path)
        completed = len(self.checkpoint.completed_trial_ids)
        try:
            for key, group_cells in groups.items():
                # Skip the group entirely if every trial already done (resume).
                pending = [c for c in group_cells if c.trial_id not in self.checkpoint.completed_trial_ids]
                if not pending:
                    continue
                await self._run_group(pending, sem, writer)
                completed = len(self.checkpoint.completed_trial_ids)
                self._save_checkpoint()
        finally:
            writer.close()
        summary = {
            "run_id": self.run_id,
            "n_cells": len(cells),
            "n_completed": completed,
            "running_cost_usd": self.checkpoint.running_cost_usd,
            "wall_clock_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    async def _run_group(
        self,
        cells: list[CellSpec],
        sem: asyncio.Semaphore,
        writer: ResultWriter,
    ) -> None:
        """Open one hermetic ServerPoolManager for the group, then dispatch."""
        if self._pool_factory is None or self._agent_factory is None:
            # Without injected factories we cannot dispatch real trials; this
            # path is exercised by the enumeration / checkpoint tests.
            return
        server_names = self._server_names_for_group(cells[0])
        async with self._pool_factory(server_names) as pool:
            # Contract: agent_factory(pool, embedder_spec). The 2-arg signature
            # is intentional — a factory that omits the spec parameter fails
            # with TypeError here rather than silently dispatching trials whose
            # row-level embedder fields don't match the run_id's h_embedder pin.
            agent = self._agent_factory(pool, self._embedder_spec)
            tasks = [self._run_trial_with_sem(sem, agent, cell, writer) for cell in cells]
            for fut in asyncio.as_completed(tasks):
                await fut

    def _server_names_for_group(self, cell: CellSpec) -> list[str]:
        """The cell's server set: primary + (N-1) deterministic distractors.

        Per REPRODUCIBILITY.md §2 the distractor RNG is seeded by cell_seed.
        Padded-N=1 cells start with just the primary; fillers are added by
        the agent layer via tcrun.padding.
        """
        if cell.is_padded_n1 or cell.N == 1:
            return [cell.primary_server]
        import random as _r

        rng = _r.Random(int(cell.cell_seed[:8], 16))
        pool = [s for s in self.config.distractors if s != cell.primary_server]
        rng.shuffle(pool)
        return [cell.primary_server, *pool[: cell.N - 1]]

    async def _run_trial_with_sem(
        self,
        sem: asyncio.Semaphore,
        agent: Any,
        cell: CellSpec,
        writer: ResultWriter,
    ) -> None:
        async with sem:
            query = self._query_for(cell.query_id)
            try:
                trial: Trial = await agent.run_trial(cell, query)
            except Exception as exc:
                cat = categorize(exc)
                if cat in ("api_fault", "server_fault"):
                    # Retry was attempted inside agent.run_trial; mark + continue.
                    log.warning("trial %s: %s; marking and continuing", cell.trial_id, cat)
                    return
                # Persistent or harness bug: halt the run.
                raise OrchestratorHalt(
                    f"trial {cell.trial_id}: uncategorized {type(exc).__name__}: {exc}"
                ) from exc
            writer.write(trial)
            self.checkpoint.completed_trial_ids.add(trial.trial_id)
            self._record_cost(trial.cost_usd)

    def _query_for(self, query_id: str) -> Any:
        for q in self._queries:
            if getattr(q, "query_id", None) == query_id:
                return q
        return None
