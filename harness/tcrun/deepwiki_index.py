"""Run-time deepwiki index-state recording (Phase F pre-registration requirement).

The Phase F pre-registration requires logging each repo's deepwiki index state
alongside the run, so the SSA-miss secondary metric is interpreted only where the
lure's index could actually have solved the task (see PRE_REGISTRATION.md Phase F
and lure-design-rethink-2026-06-04: callability vs solve).

deepwiki's MCP API exposes no index commit or date (verified against the captured
snapshot bundle: read_wiki_structure returns the page tree, no version metadata),
and the literal commit lives only on deepwiki's web frontend. Rather than scrape a
third-party page (fragile, untestable), we record the `read_wiki_structure`
RESPONSE per repo, hashed + persisted + timestamped, as the index-state evidence
(Option C, locked 2026-06-08). The stored response is what the lure "knew" at run
time: whether it carried the target symbol is checkable against it after the fact.

$0: read_wiki_structure is a documentation lookup, not an LLM call. `fetched_at` is
the probe timestamp (when we read the index), not deepwiki's internal index date.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

# Server + tool names (shared with the orchestrator hook).
DEEPWIKI_SERVER = "deepwiki"
STRUCTURE_TOOL = "read_wiki_structure"


def _to_jsonable(obj: Any) -> Any:
    """Serialize an MCP result (pydantic model) or a plain object to JSON-able form."""
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump(mode="json", exclude_none=True)
    return obj


async def record_deepwiki_index(
    repos: list[str],
    call_structure: Callable[[str], Awaitable[Any]],
    out_dir: Path,
) -> dict[str, dict[str, Any]]:
    """Record deepwiki's index state for each repo at run time.

    Args:
        repos: task source repos (``owner/name``); deduplicated and sorted here.
        call_structure: awaits deepwiki ``read_wiki_structure`` for one repo and
            returns the raw result (raises on transport/tool failure).
        out_dir: the run directory; per-repo responses land under ``out_dir/deepwiki/``
            and the manifest at ``out_dir/deepwiki_index.json``.

    Returns the manifest ``{repo: {response_sha256, response_path, fetched_at}}`` on
    success per repo, or ``{repo: {error, fetched_at}}`` on a per-repo failure.
    Best-effort by design: a single repo's failure is recorded, never raised, so an
    index-probe hiccup cannot abort (and waste) the trial spend.
    """
    resp_dir = out_dir / "deepwiki"
    resp_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, Any]] = {}

    for repo in sorted(set(repos)):
        fetched_at = datetime.now(timezone.utc).isoformat()
        slug = repo.replace("/", "__")
        try:
            result = await call_structure(repo)
            payload = json.dumps(
                _to_jsonable(result), sort_keys=True, separators=(",", ":")
            )
            sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            rel_path = f"deepwiki/{slug}.json"
            (resp_dir / f"{slug}.json").write_text(payload + "\n", encoding="utf-8")
            manifest[repo] = {
                "response_sha256": sha,
                "response_path": rel_path,
                "fetched_at": fetched_at,
            }
        except Exception as e:  # noqa: BLE001 - best-effort; record, don't halt the run
            manifest[repo] = {"error": f"{type(e).__name__}: {e}", "fetched_at": fetched_at}

    (out_dir / "deepwiki_index.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
