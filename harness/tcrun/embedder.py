"""Pluggable embedder layer for the retriever-ON arm and adversarial audits.

Implements:
    - RESEARCH_DESIGN.md §3.5 (retriever-ON tool-listing strategy)
    - REPRODUCIBILITY.md §1 h_embedder row (8th artifact in the run_id chain)
    - ADVERSARIAL_AUDIT.md §A1 + §A5 (downstream consumers, not in this module)

The embedder is the only Config knob users swap day-to-day, so:
    - The Embedder Protocol is provider-agnostic (no inheritance).
    - Provider classes lazy-import their heavy deps (FlagEmbedding/torch for
      BGE, openai-sdk for OpenAI, voyageai for Voyage) so a `pip install -e .`
      with the openai extra alone doesn't pull 2GB of PyTorch wheels.
    - Identity is pinned via `models/embedder.json` (content-hashed into
      run_id by Config.compute_run_id); the EmbedderSpec dict is the runtime
      counterpart of that pin file.
    - Providers are deterministic at temperature=0 (all three named here),
      so a future per-content-hash cache is sound (Phase 2 TODO).

Provider set (v1, locked 2026-05-25 — Cohere dropped):
    openai      text-embedding-3-large   dim 3072   primary
    voyageai    voyage-3-large           dim 1024   robustness rotation
    bge         BAAI/bge-m3              dim 1024   robustness rotation (local)

Runtime override:
    TC_EMBEDDER=voyage|bge|openai  swaps the active pin without editing
    mve.yaml. See tcrun/config.py EMBEDDER_ALIASES + load_config().
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Pin-file loader
# ---------------------------------------------------------------------------


REQUIRED_PIN_KEYS = frozenset({"provider", "model", "dimension"})


class EmbedderConfigError(ValueError):
    """Raised when models/embedder.json is malformed or missing keys."""


def load_embedder_pin(path: Path | str) -> dict:
    """Read and validate an embedder pin file (models/embedder.json shape)."""
    p = Path(path)
    if not p.exists():
        raise EmbedderConfigError(f"embedder pin file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise EmbedderConfigError(f"{p}: invalid JSON: {e}") from e
    missing = REQUIRED_PIN_KEYS - data.keys()
    if missing:
        raise EmbedderConfigError(f"{p}: missing required keys {sorted(missing)}")
    return data


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Embedder(Protocol):
    """Provider-agnostic embedder interface.

    Identity attributes (name/provider/snapshot/dimension) are read into the
    Trial schema's embedder_* fields per result row; they must match the
    pin file at `models/embedder.json` for the run_id chain to be honest.
    """

    name: str
    provider: str
    snapshot: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _assert_pin_dim(provider: str, returned_dim: int, pin_dim: int) -> None:
    """Fail-loud if the provider returned a vector dim that disagrees with the pin.

    The pin file's `dimension` field is hashed into run_id; if the runtime
    produces a different dim, the audit artifact would lie about what was
    actually computed. Raise so the trial halts before writing a misleading row.
    """
    if returned_dim != pin_dim:
        raise EmbedderConfigError(
            f"{provider} returned {returned_dim}-dim vectors; pin claims {pin_dim}. "
            f"Either the pin is wrong or the SDK returned an unexpected shape."
        )


class OpenAIEmbedder:
    """OpenAI embedding provider (v1 primary: text-embedding-3-large).

    Pin-driven: `model` and `dimension` come from models/embedder.json so a
    custom pin (e.g. text-embedding-3-small at dim 1536, or text-embedding-3-large
    truncated to 1024) works without code changes. OpenAI's SDK applies internal
    retry + exponential backoff for 429/5xx (no extra tenacity wrapper needed).
    """

    provider = "openai"

    def __init__(
        self,
        *,
        model: str = "text-embedding-3-large",
        dimension: int = 3072,
        api_key: str | None = None,
        snapshot: str | None = None,
    ):
        try:
            from openai import AsyncOpenAI  # lazy import
        except ImportError as e:
            raise EmbedderConfigError(
                "openai SDK not installed; run `pip install -e .[embedders-openai]`"
            ) from e
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EmbedderConfigError(
                "OPENAI_API_KEY not set; add it to harness/.env or export it"
            )
        self._client = AsyncOpenAI(api_key=key)
        self.name = model
        self.dimension = dimension
        # OpenAI does not yet expose a per-snapshot version for embedding-3-*.
        # When they do, pin it via the snapshot kwarg from models/embedder.json.
        self.snapshot = snapshot or model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict = {"model": self.name, "input": texts}
        # text-embedding-3-* models natively support per-call dim truncation
        # via the `dimensions` API parameter; older models (e.g. ada-002) do not.
        if self.name.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.dimension
        resp = await self._client.embeddings.create(**kwargs)
        vecs = [d.embedding for d in resp.data]
        if vecs:
            _assert_pin_dim(self.provider, len(vecs[0]), self.dimension)
        return vecs


class VoyageEmbedder:
    """Voyage AI embedding provider (robustness rotation: voyage-3-large default).

    Pin-driven. Voyage models have fixed dims per model (no truncation API),
    so the pin's dimension is treated as an assertion target post-encode.
    """

    provider = "voyageai"

    def __init__(
        self,
        *,
        model: str = "voyage-3-large",
        dimension: int = 1024,
        api_key: str | None = None,
        snapshot: str | None = None,
    ):
        try:
            import voyageai  # lazy import
        except ImportError as e:
            raise EmbedderConfigError(
                "voyageai SDK not installed; run `pip install -e .[embedders-voyage]`"
            ) from e
        key = api_key or os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise EmbedderConfigError(
                "VOYAGE_API_KEY not set; add it to harness/.env or export it"
            )
        self._client = voyageai.AsyncClient(api_key=key)
        self.name = model
        self.dimension = dimension
        self.snapshot = snapshot or model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embed(
            texts=texts, model=self.name, input_type="document"
        )
        vecs = resp.embeddings
        if vecs:
            _assert_pin_dim(self.provider, len(vecs[0]), self.dimension)
        return vecs


class BGEM3Embedder:
    """BAAI/bge-m3 (open-weights, local; robustness rotation).

    Pin-driven. The local model architecture fixes the dim per checkpoint
    (1024 for bge-m3); the pin's dimension is asserted post-encode.
    """

    provider = "bge"

    def __init__(
        self,
        *,
        model: str = "BAAI/bge-m3",
        dimension: int = 1024,
        weights_dir: str | None = None,
        snapshot: str | None = None,
        use_fp16: bool = False,
    ):
        try:
            from FlagEmbedding import BGEM3FlagModel  # lazy import (pulls torch)
        except ImportError as e:
            raise EmbedderConfigError(
                "FlagEmbedding not installed; run `pip install -e .[embedders-bge]`"
            ) from e
        self.name = model
        self.dimension = dimension
        weights = weights_dir or model
        self._model = BGEM3FlagModel(weights, use_fp16=use_fp16)
        # snapshot SHOULD be the safetensors SHA-256 (pinned in
        # models/embedder.bge-m3.json). The placeholder string keeps the
        # interface honest; real hashing lands when BGE goes live in the
        # robustness rotation. Until then, leaving the placeholder makes the
        # provenance pin visible in trial rows.
        self.snapshot = snapshot or "TBD-safetensors-sha256"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out = await asyncio.to_thread(
            self._model.encode, texts, return_dense=True
        )
        vecs = out["dense_vecs"].tolist()
        if vecs:
            _assert_pin_dim(self.provider, len(vecs[0]), self.dimension)
        return vecs


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


# Canonical provider names. Pin files' `provider` field MUST use one of these
# three values; they are also the literal accepted by Trial.embedder_provider.
# For env-var ergonomic aliases (e.g. `TC_EMBEDDER=voyage|bge-m3`), see
# EMBEDDER_ALIASES in tcrun/config.py — those map env values to pin-file paths
# at load_config time, NOT to provider names at the runtime layer.
_PROVIDER_BUILDERS = {
    "openai": OpenAIEmbedder,
    "voyageai": VoyageEmbedder,
    "bge": BGEM3Embedder,
}


def make_embedder(spec: dict | Path | str) -> Embedder:
    """Construct an Embedder from a pin dict, pin file path, or alias.

    Accepts either:
        - a dict with provider/model/dimension (and optional snapshot/weights_dir)
        - a path to models/embedder.json (or sibling pin file)

    The pin's `model`, `dimension`, and `snapshot` flow into the constructor,
    so the pin file is the single source of truth for runtime behavior (not
    just for run_id metadata). Different pins → different embedding behavior.
    """
    if isinstance(spec, (Path, str)) and not isinstance(spec, dict):
        spec = load_embedder_pin(spec)
    provider = spec["provider"]
    builder = _PROVIDER_BUILDERS.get(provider)
    if builder is None:
        raise EmbedderConfigError(
            f"unknown embedder provider {provider!r}; "
            f"known: {sorted(_PROVIDER_BUILDERS)}"
        )
    kwargs: dict = {
        "model": spec["model"],
        "dimension": spec["dimension"],
        "snapshot": spec.get("snapshot"),
    }
    if builder is BGEM3Embedder:
        kwargs["weights_dir"] = spec.get("weights_dir")
    return builder(**kwargs)


# ---------------------------------------------------------------------------
# Retrieval helpers (used by agent._build_tools_manifest under retriever-ON)
# ---------------------------------------------------------------------------


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity; small + dependency-free (no numpy import here)."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def rank_tools_by_query(
    embedder: Embedder,
    query: str,
    tool_descriptions: list[str],
    *,
    top_k: int = 5,
) -> list[int]:
    """Return indices of the top-k tool descriptions by cosine similarity to query.

    One batched embed call covers query + descriptions to minimize round-trips.
    Indices are in descending-score order. RAG-MCP top-k=5 by default
    (RESEARCH_DESIGN.md §3.5 + RAG-MCP §3 replication).
    """
    if not tool_descriptions:
        return []
    vecs = await embedder.embed([query] + tool_descriptions)
    qv, *dvs = vecs
    scored = [(i, cosine(qv, dv)) for i, dv in enumerate(dvs)]
    scored.sort(key=lambda t: -t[1])
    return [i for i, _ in scored[:top_k]]
