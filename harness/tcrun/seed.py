"""Deterministic seed derivation per REPRODUCIBILITY.md §2.

cell_seed     = sha256(run_id || model || N || query_id || ordering_id)
trial_seed    = sha256(cell_seed || repetition_id)
padding_seed  = sha256(cell_seed || "padded_filler")

All RNG in the harness derives from one of these seeds. Domain separators
(e.g., "padded_filler") prevent RNG collision within a cell that uses RNG
for multiple purposes.
"""

from __future__ import annotations
import hashlib


_SEP = "||"


def cell_seed(run_id: str, model: str, N: int, query_id: str, ordering_id: int) -> str:
    """Deterministic seed for a single experimental cell.

    Per REPRODUCIBILITY.md §2. Used to derive distractor selection, filler
    selection, and any other per-cell randomness.
    """
    payload = _SEP.join([run_id, model, str(N), query_id, str(ordering_id)])
    return hashlib.sha256(payload.encode()).hexdigest()


def trial_seed(cell_seed_hex: str, repetition_id: int) -> str:
    """Per-trial seed for any defensive per-trial randomness."""
    payload = _SEP.join([cell_seed_hex, str(repetition_id)])
    return hashlib.sha256(payload.encode()).hexdigest()


def padding_seed(cell_seed_hex: str) -> str:
    """Seed for padded-N=1 filler selection per PADDING_STRATEGY.md §4."""
    payload = _SEP.join([cell_seed_hex, "padded_filler"])
    return hashlib.sha256(payload.encode()).hexdigest()
