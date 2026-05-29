"""Default Orchestrator factories: pool wiring + agent bridge.

This module is the wiring layer between `Orchestrator` and `AgentHarness`.
It implements two factory builders that the CLI assembles into the
Orchestrator at run time:

    pool_factory   : (server_names) -> async ctx mgr yielding dict[str, ServerSession]
    agent_factory  : (pool_sessions, embedder_spec) -> AgentRunner

`AgentRunner` is a thin bridge that converts the orchestrator's call shape
`(cell, query) -> Trial` into the harness call shape `(TrialInputs) -> Trial`.

Design (DDIA-aligned):

* Single source of truth. `endpoints.json` drives `model_snapshot_id` and
  `model_provider`. The oracle file's SHA drives `oracle_version`. The
  `EnvFingerprint`, the `Embedder` client, and the resolved harness
  version are computed once per run; never re-resolved per trial.
* Loud failures. If endpoints.json lacks the configured model, or
  `tool_listing_strategy="retriever-on"` is set but no embedder client can
  be constructed (missing API key, missing SDK extra), the factory raises
  at orchestrator-wire-up time, not at first trial dispatch. There are no
  silent fall-throughs that would let `tcrun run` no-op or write
  mis-attributed rows.
* Separation of concerns. `AgentHarness` stays focused on the API tool-use
  loop. `AgentRunner` owns per-trial `TrialInputs` assembly. Orchestrator
  remains factory-agnostic so tests can keep substituting fakes.
* Evolvability. Every external dependency (`anthropic_client`, `embedder`,
  `env`, `harness_version`) is keyword-injectable.

LOC budget: ~180.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from tcrun.agent import AgentHarness, TrialInputs
from tcrun.config import Config, file_sha256
from tcrun.embedder import Embedder, load_embedder_pin, make_embedder
from tcrun.env import EnvFingerprint, capture_fingerprint
from tcrun.orchestrator import CellSpec
from tcrun.results import SamplingParams, Trial
from tcrun.servers import ServerPoolManager, ServerSession
from tcrun.tasks import Query

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Endpoint resolution
# ---------------------------------------------------------------------------


class EndpointResolutionError(RuntimeError):
    """Raised when models/endpoints.json does not pin the configured model."""


def _load_endpoint_pin(endpoints_path: Path | str, model_id: str) -> dict[str, Any]:
    """Find the endpoints.json row matching `model_id`. Raises if missing.

    Required fields per row: `model_id`, `provider`, `checkpoint_identifier`.
    The pin file is already content-hashed into run_id via Config.PATH_FIELDS,
    so this loader only validates semantic completeness — file existence and
    hash integrity are gated upstream by preflight.
    """
    p = Path(endpoints_path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise EndpointResolutionError(f"{p}: invalid JSON: {e}") from e
    models = data.get("models") or []
    for row in models:
        if row.get("model_id") == model_id:
            for key in ("provider", "checkpoint_identifier"):
                if not row.get(key):
                    raise EndpointResolutionError(
                        f"{p}: model {model_id!r} missing required key {key!r}"
                    )
            return row
    raise EndpointResolutionError(
        f"{p}: model_id {model_id!r} not pinned; known model_ids: "
        f"{[r.get('model_id') for r in models]}"
    )


# ---------------------------------------------------------------------------
# Difficulty mapping
# ---------------------------------------------------------------------------

# Query.difficulty_quartile (q1..q4) → Trial.task_difficulty (easy|medium|hard).
# Conservative split: q1 is easy, q2/q3 share medium, q4 is hard. This is the
# single source of truth for the mapping; refine here (not at call sites) if
# FOUNDATION.md ever locks a different binning.
_DIFFICULTY_FROM_QUARTILE: dict[str, str] = {
    "q1": "easy",
    "q2": "medium",
    "q3": "medium",
    "q4": "hard",
}


def _difficulty_for(quartile: str) -> str:
    if quartile not in _DIFFICULTY_FROM_QUARTILE:
        raise ValueError(
            f"unknown difficulty_quartile {quartile!r}; "
            f"expected one of {sorted(_DIFFICULTY_FROM_QUARTILE)}"
        )
    return _DIFFICULTY_FROM_QUARTILE[quartile]


# ---------------------------------------------------------------------------
# Oracle versioning
# ---------------------------------------------------------------------------


def _oracle_version_for(oracle_path: Path | str) -> str:
    """Render the Trial.oracle_version string from the pinned oracle file."""
    p = Path(oracle_path)
    return f"{p.name}@sha256:{file_sha256(p)}"


# ---------------------------------------------------------------------------
# Default pool factory
# ---------------------------------------------------------------------------


def make_default_pool_factory(
    config: Config,
    *,
    allow_unpinned: bool = False,
) -> Callable[[list[str]], Any]:
    """Build the orchestrator's pool_factory.

    Returns a callable `(server_names) -> AsyncContextManager[dict[str, ServerSession]]`
    so the orchestrator's existing `async with self._pool_factory(names) as pool`
    binds `pool` to the live sessions dict. One ServerPoolManager is opened per
    group (hermetic per SPEC.md §5 rule 4); teardown is owned by the context.
    """
    yaml_path = config.servers_pinned

    @asynccontextmanager
    async def pool_factory(
        server_names: list[str],
    ) -> AsyncIterator[dict[str, ServerSession]]:
        async with ServerPoolManager(yaml_path, allow_unpinned=allow_unpinned) as pool:
            sessions = await pool.start(server_names)
            yield sessions

    return pool_factory


# ---------------------------------------------------------------------------
# AgentRunner — the bridge object
# ---------------------------------------------------------------------------


class AgentRunner:
    """Bridges `Orchestrator.(cell, query)` to `AgentHarness.(TrialInputs)`.

    Stateless beyond construction. The per-cell-group sessions and the
    run-scoped resources (env, model snapshot, oracle version, embedder)
    are bound here; per-trial inputs are assembled on each `run_trial`
    call from cell + query + bound config.
    """

    def __init__(
        self,
        harness: AgentHarness,
        pool_sessions: dict[str, ServerSession],
        embedder_spec: dict | None,
        *,
        config: Config,
        env: EnvFingerprint,
        model_snapshot_id: str,
        model_provider: str,
        oracle_version: str,
        harness_version: str,
        run_dir: Path | None = None,
    ):
        self._harness = harness
        self._sessions = pool_sessions
        self._embedder_spec = embedder_spec
        self._config = config
        self._env = env
        self._model_snapshot_id = model_snapshot_id
        self._model_provider = model_provider
        self._oracle_version = oracle_version
        self._harness_version = harness_version
        self._run_dir = Path(run_dir) if run_dir is not None else None

    async def run_trial(self, cell: CellSpec, query: Query) -> Trial:
        inputs = self._build_inputs(cell, query)
        return await self._harness.run_trial(inputs)

    def _build_inputs(self, cell: CellSpec, query: Query) -> TrialInputs:
        cfg = self._config
        # trial_seed is hex (sha256). Reduce to a 32-bit unsigned int so any
        # downstream RNG that takes an int seed gets a deterministic value
        # derived from the same chain. Same cell+rep → same int.
        seed_int = int(cell.trial_seed[:8], 16)
        trace_path = (
            str(self._run_dir / "traces" / f"{cell.trial_id}.jsonl")
            if self._run_dir is not None
            else ""
        )
        return TrialInputs(
            run_id=cell.run_id,
            cell_id=cell.cell_id,
            trial_id=cell.trial_id,
            seed=seed_int,
            harness_version=self._harness_version,
            task_id=query.query_id,
            task_version="v1",
            task_difficulty=_difficulty_for(query.difficulty_quartile),
            task_query=query.text,
            primary_server=cell.primary_server,
            model_id=cfg.model,
            model_provider=self._model_provider,
            model_snapshot_id=self._model_snapshot_id,
            sampling_params=SamplingParams(),
            ordering_seed=cell.ordering_seed,
            tool_listing_strategy=cfg.tool_listing_strategy,
            sessions=self._sessions,
            is_padded_n1=cell.is_padded_n1,
            padding_corpus_path=cfg.padding_corpus,
            oracle_version=self._oracle_version,
            cell_seed=cell.cell_seed,
            env=self._env,
            embedder_spec=self._embedder_spec,
            retriever_top_k=cfg.retriever_top_k,
            trace_path=trace_path,
        )


# ---------------------------------------------------------------------------
# Default agent factory
# ---------------------------------------------------------------------------


def make_default_agent_factory(
    config: Config,
    *,
    env: EnvFingerprint | None = None,
    anthropic_client: Any | None = None,
    embedder: Embedder | None = None,
    harness_version: str | None = None,
    run_dir: Path | None = None,
) -> Callable[[dict[str, ServerSession], dict | None], AgentRunner]:
    """Build the orchestrator's agent_factory.

    Run-scoped resources are resolved here, once:

        * endpoints.json   → model_snapshot_id + provider
        * oracle file SHA  → oracle_version
        * EnvFingerprint   → per-run env identity (every trial shares it)
        * Embedder client  → built iff cfg.tool_listing_strategy == "retriever-on"
        * harness_version  → cfg.harness_version unless TBD, else env.git_sha

    The returned closure satisfies the contract:
        agent_factory(pool_sessions, embedder_spec) -> AgentRunner

    A fresh AgentHarness is constructed per group (so the bound sessions
    match the group's hermetic server set), but it reuses the same
    anthropic_client and embedder across groups for connection-pool sanity.

    Loud-failure guarantees:
        * endpoints.json missing the cfg.model row → raises here.
        * cfg.tool_listing_strategy == "retriever-on" with no buildable
          embedder (missing API key, missing SDK extra) → raises here.
    """
    endpoint = _load_endpoint_pin(config.endpoints, config.model)
    model_snapshot_id = endpoint["checkpoint_identifier"]
    model_provider = endpoint["provider"]
    oracle_version = _oracle_version_for(config.oracle)
    fp = env if env is not None else capture_fingerprint()
    h_version = harness_version or (
        config.harness_version
        if config.harness_version != "TBD"
        else fp.git_sha
    )

    # Pre-build the embedder iff retriever-on is configured. retriever-OFF
    # runs never import openai/voyage/torch through this path, so a config
    # with `tool_listing_strategy: full` and no embedder SDK installed still
    # runs cleanly. Failures here halt the whole run, by design.
    if embedder is None and config.tool_listing_strategy == "retriever-on":
        embedder = make_embedder(load_embedder_pin(config.embedder))

    def agent_factory(
        pool_sessions: dict[str, ServerSession],
        embedder_spec: dict | None,
    ) -> AgentRunner:
        harness = AgentHarness(
            anthropic_client=anthropic_client,
            embedder=embedder,
        )
        return AgentRunner(
            harness=harness,
            pool_sessions=pool_sessions,
            embedder_spec=embedder_spec,
            config=config,
            env=fp,
            model_snapshot_id=model_snapshot_id,
            model_provider=model_provider,
            oracle_version=oracle_version,
            harness_version=h_version,
            run_dir=run_dir,
        )

    return agent_factory
