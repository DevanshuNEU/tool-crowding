"""Tests for tcrun.embedder — pin loader, factory, providers, retrieval helpers.

Providers are tested via lazy-import error path (SDK absent) + factory
dispatch. A live OpenAI/Voyage embed is NOT exercised here; those run under
the optional `tcrun-live-embed` mark which is opt-in for callers with keys.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from tcrun.embedder import (
    BGEM3Embedder,
    Embedder,
    EmbedderConfigError,
    OpenAIEmbedder,
    VoyageEmbedder,
    cosine,
    load_embedder_pin,
    make_embedder,
    rank_tools_by_query,
)


# ---------------------------------------------------------------------------
# load_embedder_pin
# ---------------------------------------------------------------------------


def _write_pin(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_pin_happy_path(tmp_path: Path):
    p = _write_pin(tmp_path / "embedder.json", {
        "provider": "openai", "model": "text-embedding-3-large", "dimension": 3072,
    })
    pin = load_embedder_pin(p)
    assert pin["provider"] == "openai"
    assert pin["dimension"] == 3072


def test_load_pin_missing_file_raises(tmp_path: Path):
    with pytest.raises(EmbedderConfigError, match="not found"):
        load_embedder_pin(tmp_path / "nope.json")


def test_load_pin_invalid_json_raises(tmp_path: Path):
    p = tmp_path / "embedder.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(EmbedderConfigError, match="invalid JSON"):
        load_embedder_pin(p)


def test_load_pin_missing_required_keys_raises(tmp_path: Path):
    p = _write_pin(tmp_path / "embedder.json", {"provider": "openai"})  # no model/dim
    with pytest.raises(EmbedderConfigError, match="missing required keys"):
        load_embedder_pin(p)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_make_embedder_unknown_provider_raises():
    with pytest.raises(EmbedderConfigError, match="unknown embedder provider"):
        make_embedder({"provider": "cohere", "model": "x", "dimension": 1024})


def test_make_embedder_accepts_path(tmp_path: Path, monkeypatch):
    p = _write_pin(tmp_path / "embedder.json", {
        "provider": "openai", "model": "text-embedding-3-large", "dimension": 3072,
    })
    # We can't instantiate OpenAIEmbedder without OPENAI_API_KEY, so monkeypatch.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-for-test")
    # If openai SDK isn't installed, this raises EmbedderConfigError — accept either path.
    try:
        emb = make_embedder(p)
        assert emb.provider == "openai"
        assert emb.name == "text-embedding-3-large"
        assert emb.dimension == 3072
    except EmbedderConfigError as e:
        assert "openai SDK not installed" in str(e)


def test_make_embedder_propagates_custom_model_and_dimension(tmp_path: Path, monkeypatch):
    """Pin's model + dimension must flow into the embedder instance.

    A custom pin (e.g. text-embedding-3-large truncated to 1024) must produce
    an embedder whose .name and .dimension reflect the pin, not class defaults.
    Otherwise the run_id pin disagrees with the runtime — the audit lies.
    """
    p = _write_pin(tmp_path / "custom.json", {
        "provider": "openai",
        "model": "text-embedding-3-small",  # different model
        "dimension": 1536,                  # different dim (smaller default)
    })
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-for-test")
    try:
        emb = make_embedder(p)
        assert emb.name == "text-embedding-3-small"
        assert emb.dimension == 1536
        assert emb.snapshot == "text-embedding-3-small"  # falls back to model
    except EmbedderConfigError as e:
        assert "openai SDK not installed" in str(e)


def test_provider_dispatch_rejects_alias_names(tmp_path: Path):
    """`voyage` and `bge-m3` are env-var aliases, NOT canonical provider names.

    Pin files must use canonical names (openai/voyageai/bge). Aliases in pin
    files should fail loud at construct time, not silently at Trial-write time.
    """
    for alias in ("voyage", "bge-m3"):
        with pytest.raises(EmbedderConfigError, match="unknown embedder provider"):
            make_embedder({"provider": alias, "model": "x", "dimension": 1024})


# ---------------------------------------------------------------------------
# Provider lazy imports + env-var guards
# ---------------------------------------------------------------------------


def test_openai_embedder_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        # Will hit lazy-import first; if SDK absent, that error is fine too.
        with pytest.raises(EmbedderConfigError):
            OpenAIEmbedder()
    except ImportError:
        pytest.skip("openai SDK not present; lazy-import error path takes precedence")


def test_voyage_embedder_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    try:
        with pytest.raises(EmbedderConfigError):
            VoyageEmbedder()
    except ImportError:
        pytest.skip("voyageai SDK not present; lazy-import error path takes precedence")


# ---------------------------------------------------------------------------
# Cosine
# ---------------------------------------------------------------------------


def test_cosine_parallel_is_one():
    assert cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert cosine([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)


def test_cosine_antiparallel_is_negative_one():
    assert cosine([1, 0, 0], [-1, 0, 0]) == pytest.approx(-1.0)


def test_cosine_zero_vector_is_zero():
    assert cosine([0, 0, 0], [1, 0, 0]) == 0.0
    assert cosine([1, 0, 0], [0, 0, 0]) == 0.0


# ---------------------------------------------------------------------------
# rank_tools_by_query
# ---------------------------------------------------------------------------


class _StubEmbedder:
    """Test double implementing the Embedder Protocol.

    Returns a fixed mapping from input string → vector so cosine ranks are
    deterministic. First text is the query; later texts are tool descriptions.
    """

    name = "stub"
    provider = "openai"
    snapshot = "stub"
    dimension = 3

    def __init__(self, mapping: dict[str, list[float]]):
        self._mapping = mapping

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._mapping[t] for t in texts]


def test_rank_tools_returns_top_k_in_descending_score_order():
    """The closest description should land at index 0."""
    embedder = _StubEmbedder({
        "find yaml parser": [1.0, 0.0, 0.0],
        "parses yaml files":  [0.99, 0.01, 0.0],   # closest
        "deletes records":    [0.0, 1.0, 0.0],     # orthogonal
        "renders charts":     [0.0, 0.0, 1.0],     # orthogonal
        "yaml-related stuff": [0.8, 0.6, 0.0],     # middling
    })
    descs = ["parses yaml files", "deletes records", "renders charts", "yaml-related stuff"]
    idxs = asyncio.run(rank_tools_by_query(
        embedder, "find yaml parser", descs, top_k=2
    ))
    assert len(idxs) == 2
    assert idxs[0] == 0  # "parses yaml files" is the best match
    assert idxs[1] == 3  # "yaml-related stuff" is second best


def test_rank_tools_empty_descriptions_returns_empty():
    embedder = _StubEmbedder({})
    idxs = asyncio.run(rank_tools_by_query(embedder, "q", [], top_k=5))
    assert idxs == []


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_stub_embedder_conforms_to_protocol():
    """Sanity: the test double satisfies the runtime-checkable Protocol."""
    stub = _StubEmbedder({})
    assert isinstance(stub, Embedder)
