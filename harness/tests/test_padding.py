"""Tests for tcrun.padding — length-matched filler selection.

Coverage targets per the implementation prompt:
- synthetic corpus
- verify ±10% match
- edge cases: budget_negative, undersized corpus, malformed JSON
- determinism on same padding_seed
- retries on greedy stuck condition
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tcrun.padding import (
    MIN_CORPUS_ENTRIES,
    FakeTool,
    PaddingCorpusError,
    PaddingPackError,
    select_padding,
)
from tcrun.seed import cell_seed


MODEL_ID = "claude-sonnet-4-6-20260131"


def _make_entry(i: int, tokens: int) -> dict:
    return {
        "entry_id": f"ftc_{i:03d}",
        "tool_name": f"FakeTool{i:03d}",
        "description": f"placeholder description {i}",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "domain_tag": "scheduling",
        "description_tokens": tokens,
    }


def _write_corpus(path: Path, count: int = MIN_CORPUS_ENTRIES, token_size: int = 50) -> None:
    """Write a JSONL corpus with `count` entries, each `token_size` tokens under MODEL_ID."""
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(json.dumps(_make_entry(i, token_size)) + "\n")


def _seed() -> str:
    return cell_seed("run0", MODEL_ID, 1, "v1-pub-001", 0)


def test_returns_fillers_within_pm10_pct(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    _write_corpus(corpus, count=60, token_size=50)
    # Target 1000 tokens, primary 100 → filler budget 900 → ~18 fillers @ 50 each.
    selected, skip = select_padding(
        cell_seed_hex=_seed(),
        target_tokens=1000,
        primary_tool_desc_tokens=100,
        corpus_path=corpus,
        model=MODEL_ID,
    )
    assert skip is None
    total = 100 + sum(e.description_tokens for e in selected)
    assert 900 <= total <= 1100, f"out of band: {total}"


def test_budget_negative_skips(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    _write_corpus(corpus)
    selected, skip = select_padding(
        cell_seed_hex=_seed(),
        target_tokens=100,
        primary_tool_desc_tokens=500,  # primary already > target
        corpus_path=corpus,
        model=MODEL_ID,
    )
    assert skip == "budget_negative"
    assert selected == []


def test_undersized_corpus_raises(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    _write_corpus(corpus, count=10)  # below MIN_CORPUS_ENTRIES
    with pytest.raises(PaddingCorpusError, match="requires >= 50"):
        select_padding(
            cell_seed_hex=_seed(),
            target_tokens=1000,
            primary_tool_desc_tokens=100,
            corpus_path=corpus,
            model=MODEL_ID,
        )


def test_missing_corpus_raises(tmp_path: Path):
    with pytest.raises(PaddingCorpusError, match="not found"):
        select_padding(
            cell_seed_hex=_seed(),
            target_tokens=1000,
            primary_tool_desc_tokens=100,
            corpus_path=tmp_path / "nope.jsonl",
            model=MODEL_ID,
        )


def test_malformed_corpus_raises(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    with open(corpus, "w", encoding="utf-8") as fh:
        for i in range(60):
            fh.write(json.dumps(_make_entry(i, 50)) + "\n")
        fh.write("{not json\n")
    with pytest.raises(PaddingCorpusError, match="invalid JSON"):
        select_padding(
            cell_seed_hex=_seed(),
            target_tokens=1000,
            primary_tool_desc_tokens=100,
            corpus_path=corpus,
            model=MODEL_ID,
        )


def test_determinism_on_same_seed(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    # Mixed token sizes so shuffle order matters.
    with open(corpus, "w", encoding="utf-8") as fh:
        for i in range(60):
            fh.write(json.dumps(_make_entry(i, 30 + (i % 5) * 10)) + "\n")
    seed = _seed()
    s1, _ = select_padding(seed, 1000, 100, corpus, model=MODEL_ID)
    s2, _ = select_padding(seed, 1000, 100, corpus, model=MODEL_ID)
    assert [e.entry_id for e in s1] == [e.entry_id for e in s2]


def test_different_seeds_yield_different_selections(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    with open(corpus, "w", encoding="utf-8") as fh:
        for i in range(60):
            fh.write(json.dumps(_make_entry(i, 30 + (i % 7) * 10)) + "\n")
    s1, _ = select_padding(_seed(), 1000, 100, corpus, model=MODEL_ID)
    s2, _ = select_padding(
        cell_seed("run0", MODEL_ID, 1, "v1-pub-002", 0), 1000, 100, corpus, model=MODEL_ID
    )
    assert [e.entry_id for e in s1] != [e.entry_id for e in s2]


def test_no_duplicates_within_trial(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    _write_corpus(corpus, count=60, token_size=50)
    selected, skip = select_padding(_seed(), 2000, 100, corpus, model=MODEL_ID)
    assert skip is None
    ids = [e.entry_id for e in selected]
    assert len(ids) == len(set(ids)), "duplicate entries selected"


def test_pack_failure_raises_when_unachievable(tmp_path: Path):
    """Token sizes that cannot pack to ±10% of a tiny budget → PaddingPackError."""
    corpus = tmp_path / "corpus.jsonl"
    # All entries are 500 tokens but budget is only 50: single entry overshoots.
    with open(corpus, "w", encoding="utf-8") as fh:
        for i in range(60):
            fh.write(json.dumps(_make_entry(i, 500)) + "\n")
    with pytest.raises(PaddingPackError):
        select_padding(
            cell_seed_hex=_seed(),
            target_tokens=150,
            primary_tool_desc_tokens=100,  # budget = 50, target band 135..165
            corpus_path=corpus,
            model=MODEL_ID,
        )


def test_fake_tool_dataclass_construction():
    """Canonical FakeTool (dataclass in tcrun.agent) accepts the documented shape."""
    raw = _make_entry(0, 50)
    t = FakeTool(**raw)
    assert t.entry_id == "ftc_000"
    assert t.input_schema["type"] == "object"
    assert t.description_tokens == 50
    assert t.tool_name == "FakeTool000"


def test_fake_tool_is_canonical_across_modules():
    """padding.FakeTool and agent.FakeTool must be the same class (post-2026-05-23 fix)."""
    from tcrun import agent, padding
    assert padding.FakeTool is agent.FakeTool
