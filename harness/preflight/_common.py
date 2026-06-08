"""Shared constants + helpers for the query-hygiene preflight gates.

Sources of truth (in priority order):
    1. design/QUERY_SET_HYGIENE.md — the binding spec
    2. design/MODEL_VERSIONS.md — cutoff dates
    3. tcrun.tasks.Query — schema

These values are duplicated here as Python constants rather than re-parsed at
runtime so the preflight is self-contained (no live doc parsing). Any change to
the binding values in the markdown must be mirrored here AND vice versa; a
mismatch is a release-blocker by construction (the spec docs are normative).
"""

from __future__ import annotations

from datetime import date

# QUERY_SET_HYGIENE.md §2 — tier date thresholds
# Queries must be STRICTLY AFTER the threshold (i.e., publication_date > threshold).
TIER_DATE_THRESHOLDS: dict[str, date | None] = {
    "public": date(2026, 1, 31),
    "held_back": date(2026, 4, 30),
    "sealed": None,  # N/A for proprietary tier
}

# QUERY_SET_HYGIENE.md §7 — tier sample sizes (hard counts, no fuzz)
TIER_COUNTS: dict[str, int] = {
    "public": 30,
    "held_back": 10,
    "sealed": 10,
}

# QUERY_SET_HYGIENE.md §6 — per-repo caps
TIER_REPO_CAPS: dict[str, int | None] = {
    "public": 10,
    "held_back": 7,
    "sealed": None,  # sealed tier comes from a single proprietary repo by design
}

# QUERY_SET_HYGIENE.md §3 — banned source repos (presumed in training corpora).
# Matched on the repo *name* component (case-insensitive) so owner-prefix variants
# (e.g., numpy/numpy, scipy/scipy) all get caught.
BANNED_REPO_NAMES: set[str] = {
    "numpy",
    "scipy",
    "pytorch",
    "pandas",
    "celery",
    "aiohttp",
    "jupyter",
    "jupyterlab",
    "requests",
    "flask",
    "django",
    "tensorflow",
    "scikit-learn",
    "matplotlib",
    "seaborn",
}

# QUERY_SET_HYGIENE.md §3 — star ceiling for repo eligibility
STAR_CEILING: int = 10_000

# QUERY_SET_HYGIENE.md §3 — PyPI download ceiling (per month). Best-effort:
# only applies when the repo is published to PyPI.
PYPI_DL_CEILING_PER_MONTH: int = 1_000_000

# QUERY_SET_HYGIENE.md §5 — accepted GPL-family licenses for public + held-back
GPL_FAMILY: set[str] = {"GPL-2.0", "GPL-3.0", "LGPL", "AGPL"}

# QUERY_SET_HYGIENE.md §4 — 5-gram public-hit rejection threshold
# A query is rejected if 2 or more high-entropy 5-grams hit ≥1 public source.
FIVEGRAM_REJECT_THRESHOLD: int = 2

# QUERY_SET_HYGIENE.md §4 — tokenizer choice
# o200k_base is the strictest (longest-output-tokenization) panel encoding.
TOKENIZER_NAME: str = "o200k_base"

# Low-entropy token stoplist per QUERY_SET_HYGIENE.md §4 step 3.
# Combined Python keywords + common builtins so the 5-gram extractor can
# strip these before windowing. Tokenized as plain strings (lowercased).
LOW_ENTROPY_TOKENS: frozenset[str] = frozenset(
    {
        # Python keywords called out in the spec
        "def",
        "return",
        "import",
        "class",
        "for",
        "if",
        "else",
        "try",
        "except",
        "with",
        # Other common keywords (conservative additions; same family of low-entropy)
        "from",
        "as",
        "in",
        "is",
        "not",
        "and",
        "or",
        "elif",
        "while",
        "pass",
        "break",
        "continue",
        "raise",
        "yield",
        "lambda",
        "async",
        "await",
        "self",
        "cls",
        "none",
        "true",
        "false",
        # Common builtins
        "print",
        "len",
        "range",
        "int",
        "str",
        "list",
        "dict",
        "set",
        "tuple",
        "bool",
        "type",
        "isinstance",
        "getattr",
        "setattr",
        "hasattr",
        "open",
    }
)


def is_banned_repo(source_repo: str) -> bool:
    """Match `<owner>/<name>` form against the banned repo-name set."""
    if "/" not in source_repo:
        # Bare name; match directly
        return source_repo.lower() in BANNED_REPO_NAMES
    _owner, name = source_repo.split("/", 1)
    return name.lower() in BANNED_REPO_NAMES
