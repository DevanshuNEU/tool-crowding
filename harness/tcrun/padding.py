"""Padded-N=1 filler selection per design/PADDING_STRATEGY.md §4.

Implements the binding length-matching algorithm for the padded-N=1 control.
Given a target token count (the unpadded-N=20 prompt size for the cell), the
primary tool's description token count, and the fake-tool corpus, returns a
deterministic length-matched filler set within ±10% of target.

Determinism per design/PADDING_STRATEGY.md §5:
    padding_seed = sha256(cell_seed || "padded_filler")  (see seed.py)
Same (run_id, model, query_id, ordering_id) → byte-identical filler set.

Edge cases per design/PADDING_STRATEGY.md §4 table:
    - filler_budget < 0 → return ([], "budget_negative") (soft-skip)
    - corpus missing / undersized → PaddingCorpusError (halt run)
    - greedy cannot pack ±10% after 3 retries → PaddingPackError (halt run)
    - tokenizer returns None → PaddingTokenizerError (halt run)

LOC budget per the implementation prompt: ~120 LOC.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from tcrun.agent import FakeTool
from tcrun.seed import padding_seed

# ±10% tolerance band per PADDING_STRATEGY.md §4.
TOLERANCE = 0.10
MAX_PACK_RETRIES = 3
MIN_CORPUS_ENTRIES = 50  # PADDING_STRATEGY.md §3 requirement.


class PaddingError(Exception):
    """Base class for padded-N=1 selection halt-on errors."""


class PaddingCorpusError(PaddingError):
    """Corpus missing, malformed, or undersized."""


class PaddingPackError(PaddingError):
    """Greedy packer could not reach ±10% band after MAX_PACK_RETRIES retries."""


class PaddingTokenizerError(PaddingError):
    """Tokenizer unavailable or returned None for a corpus entry."""


def _normalize_corpus_record(record: dict, line_num: int) -> dict:
    """Map the corpus-side JSONL schema onto the canonical FakeTool fields.

    The corpus file (`design/fake_tool_corpus.jsonl`) ships with
    `{name, description, input_schema, estimated_tokens}` per PADDING_STRATEGY.md §3.
    FakeTool (canonical in `tcrun.agent`) wants
    `{tool_name, description, input_schema, description_tokens, entry_id, domain_tag}`.
    Normalize at load time so the corpus generator and the agent can evolve
    independently without breaking the loader.
    """
    out = dict(record)
    if "tool_name" not in out and "name" in out:
        out["tool_name"] = out.pop("name")
    if "description_tokens" not in out:
        if "estimated_tokens" in out:
            out["description_tokens"] = int(out.pop("estimated_tokens"))
        else:
            out["description_tokens"] = 0
    if "entry_id" not in out:
        out["entry_id"] = f"ft-{line_num:04d}"
    if "domain_tag" not in out:
        out["domain_tag"] = ""
    # Strip any extra keys not on the FakeTool dataclass; pydantic was forgiving,
    # the dataclass is not.
    allowed = {"tool_name", "description", "input_schema",
               "description_tokens", "entry_id", "domain_tag"}
    return {k: v for k, v in out.items() if k in allowed}


def _load_corpus(corpus_path: Path) -> list[FakeTool]:
    """Stream-validate the JSONL corpus. Halts on parse/schema/size violations."""
    if not corpus_path.exists():
        raise PaddingCorpusError(f"fake_tool_corpus not found at {corpus_path}")
    entries: list[FakeTool] = []
    with open(corpus_path, "r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as e:
                raise PaddingCorpusError(
                    f"{corpus_path}:{line_num}: invalid JSON: {e}"
                ) from e
            normalized = _normalize_corpus_record(record, line_num)
            try:
                entries.append(FakeTool(**normalized))
            except (TypeError, ValueError) as e:
                raise PaddingCorpusError(
                    f"{corpus_path}:{line_num}: schema validation failed: {e}"
                ) from e
    if len(entries) < MIN_CORPUS_ENTRIES:
        raise PaddingCorpusError(
            f"corpus has {len(entries)} entries; PADDING_STRATEGY.md §3 "
            f"requires >= {MIN_CORPUS_ENTRIES}"
        )
    return entries


def _tokens_for(entry: FakeTool, model: str | None = None) -> int:
    """Return token count for `entry`. Uses corpus cl100k_base count if set;
    otherwise re-tokenizes via tiktoken cl100k_base over a canonical JSON payload.

    PADDING_STRATEGY.md §4's per-model tokenizer policy is deferred to v2; v1
    uses the corpus's cl100k_base count uniformly across models. `model` is
    kept on the signature for forward-compat with v2 per-model retokenization.
    """
    del model  # v2 hook; intentionally unused in v1
    if entry.description_tokens > 0:
        return entry.description_tokens
    try:
        import tiktoken
    except ImportError as e:  # pragma: no cover - dep pinned in pyproject
        raise PaddingTokenizerError(f"tiktoken not available: {e}") from e
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        raise PaddingTokenizerError(f"tiktoken encoding load failed: {e}") from e
    payload = json.dumps(
        {
            "name": entry.tool_name,
            "description": entry.description,
            "input_schema": entry.input_schema,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    tokens = enc.encode(payload)
    if tokens is None:
        raise PaddingTokenizerError(f"tokenizer returned None for {entry.entry_id}")
    return len(tokens)


def _greedy_pack(
    entries: list[FakeTool],
    budget: int,
    rng: random.Random,
    model: str | None,
) -> tuple[list[FakeTool], int]:
    """Greedy length-matched pack with no duplicates. Returns (selected, total)."""
    pool = list(entries)
    rng.shuffle(pool)
    lo = int(round(budget * (1.0 - TOLERANCE)))
    hi = int(round(budget * (1.0 + TOLERANCE)))
    selected: list[FakeTool] = []
    total = 0
    for entry in pool:
        tk = _tokens_for(entry, model)
        if total + tk > hi:
            continue  # would overshoot upper band; skip
        selected.append(entry)
        total += tk
        if lo <= total <= hi:
            return selected, total
    return selected, total


def select_padding(
    cell_seed_hex: str,
    target_tokens: int,
    primary_tool_desc_tokens: int,
    corpus_path: Path | str,
    model: str | None = None,
) -> tuple[list[FakeTool], str | None]:
    """Pick a deterministic length-matched filler set for a padded-N=1 trial.

    Returns (selected_fillers, skip_reason). skip_reason is None on success,
    or "budget_negative" when the primary tool already exceeds target
    (PADDING_STRATEGY.md §4 edge case 1; trial proceeds with bare N=1).

    Raises PaddingError subclasses (halt the run) on every other failure mode.
    """
    filler_budget = target_tokens - primary_tool_desc_tokens
    if filler_budget < 0:
        return [], "budget_negative"

    entries = _load_corpus(Path(corpus_path))

    base_seed = padding_seed(cell_seed_hex)
    target_lo = int(round(target_tokens * (1.0 - TOLERANCE)))
    target_hi = int(round(target_tokens * (1.0 + TOLERANCE)))

    last_total = -1
    last_selected: list[FakeTool] = []
    for attempt in range(MAX_PACK_RETRIES + 1):
        # Re-seed per attempt deterministically (PADDING_STRATEGY.md §4 retry rule).
        seed_int = int(
            hashlib.sha256(f"{base_seed}||attempt={attempt}".encode()).hexdigest(),
            16,
        ) & 0xFFFFFFFF
        rng = random.Random(seed_int)
        selected, filler_total = _greedy_pack(entries, filler_budget, rng, model)
        actual_total = primary_tool_desc_tokens + filler_total
        if target_lo <= actual_total <= target_hi:
            return selected, None
        last_total = actual_total
        last_selected = selected

    raise PaddingPackError(
        f"greedy packer could not reach +/-{int(TOLERANCE * 100)}% band after "
        f"{MAX_PACK_RETRIES + 1} attempts: target={target_tokens}, "
        f"last_total={last_total}, selected={len(last_selected)} entries"
    )
