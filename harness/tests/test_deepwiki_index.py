"""Tests for run-time deepwiki index-state recording (Phase F pre-reg, Option C).

Covers the pure helper (record_deepwiki_index) and the orchestrator hook
(_maybe_record_deepwiki_index): gated on deepwiki being in the pool, idempotent on
resume, best-effort on failure.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from tcrun.config import Config
from tcrun.deepwiki_index import STRUCTURE_TOOL, record_deepwiki_index
from tcrun.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


class _Result:
    """Stand-in for an MCP CallToolResult (has model_dump)."""

    def __init__(self, payload):
        self._p = payload

    def model_dump(self, mode="python", exclude_none=False):
        return self._p


async def _ok(repo: str):
    return _Result({"repo": repo, "pages": ["1 Overview", "2 Core"]})


def test_helper_records_each_repo(tmp_path: Path):
    manifest = asyncio.run(record_deepwiki_index(["a/b", "c/d"], _ok, tmp_path))
    assert set(manifest) == {"a/b", "c/d"}
    for repo, entry in manifest.items():
        assert entry["response_sha256"] and entry["fetched_at"]
        assert (tmp_path / entry["response_path"]).exists()
    on_disk = json.loads((tmp_path / "deepwiki_index.json").read_text())
    assert on_disk == manifest


def test_helper_dedups_and_sorts(tmp_path: Path):
    manifest = asyncio.run(record_deepwiki_index(["b/b", "a/a", "b/b"], _ok, tmp_path))
    assert list(manifest) == ["a/a", "b/b"]


def test_helper_records_error_without_raising(tmp_path: Path):
    async def maybe_boom(repo: str):
        if repo == "bad/repo":
            raise RuntimeError("no index")
        return _Result({"ok": True})

    manifest = asyncio.run(record_deepwiki_index(["bad/repo", "good/repo"], maybe_boom, tmp_path))
    assert "RuntimeError" in manifest["bad/repo"]["error"]
    assert "response_sha256" in manifest["good/repo"]


def test_helper_handles_plain_dict_result(tmp_path: Path):
    async def plain(repo: str):
        return {"pages": ["x"]}

    manifest = asyncio.run(record_deepwiki_index(["a/b"], plain, tmp_path))
    assert "response_sha256" in manifest["a/b"]


def test_helper_hash_is_deterministic(tmp_path_factory):
    d1 = tmp_path_factory.mktemp("d1")
    d2 = tmp_path_factory.mktemp("d2")
    m1 = asyncio.run(record_deepwiki_index(["a/b"], _ok, d1))
    m2 = asyncio.run(record_deepwiki_index(["a/b"], _ok, d2))
    assert m1["a/b"]["response_sha256"] == m2["a/b"]["response_sha256"]


# ---------------------------------------------------------------------------
# Orchestrator hook
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _cfg(tmp_path: Path, **overrides) -> Config:
    base = dict(
        task_set=_write(tmp_path / "queries.jsonl", "{}"),
        oracle=_write(tmp_path / "pass_v1.py", "def pass_criterion(*a): return True"),
        servers_pinned=_write(tmp_path / "servers.yaml", "{}"),
        descriptions=_write(tmp_path / "descriptions.json", "{}"),
        endpoints=_write(tmp_path / "endpoints.json", "{}"),
        environment=_write(tmp_path / "environment.lock", "py=3.11"),
        padding_corpus=_write(tmp_path / "corpus.jsonl", "{}"),
        embedder=_write(tmp_path / "embedder.json", '{"provider":"openai","model":"x","dimension":3072}'),
        primary_servers=["github_mcp"],
        distractors=["deepwiki", "git_mcp", "filesystem_mcp"],
        N=[4],
        runs_per_cell=1,
        model="claude-sonnet-4-6",
        host="claude-desktop",
        seed=42,
        out=tmp_path / "out",
    )
    base.update(overrides)
    return Config(**base)


class _FakeDeepwiki:
    def __init__(self):
        self.session = self
        self.calls: list = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"name": name, "args": args, "pages": ["1 Overview"]}


def _pool_factory_with(sessions: dict):
    @asynccontextmanager
    async def _factory(server_names):
        yield sessions

    return _factory


def _q(query_id: str, repo: str):
    return SimpleNamespace(query_id=query_id, source_repo=repo)


def test_hook_records_when_deepwiki_present(tmp_path: Path):
    sess = _FakeDeepwiki()
    orch = Orchestrator(
        _cfg(tmp_path),
        queries=[_q("q1", "ansible/ansible"), _q("q2", "ansible/ansible"), _q("q3", "kovidgoyal/calibre")],
        pool_factory=_pool_factory_with({"deepwiki": sess}),
        run_dir=tmp_path / "run",
    )
    asyncio.run(orch._maybe_record_deepwiki_index())
    manifest = json.loads((tmp_path / "run" / "deepwiki_index.json").read_text())
    assert list(manifest) == ["ansible/ansible", "kovidgoyal/calibre"]  # deduped + sorted
    assert (STRUCTURE_TOOL, {"repoName": "ansible/ansible"}) in sess.calls
    assert len(sess.calls) == 2


def test_hook_noop_when_deepwiki_absent(tmp_path: Path):
    sess = _FakeDeepwiki()
    orch = Orchestrator(
        _cfg(tmp_path, distractors=["git_mcp", "filesystem_mcp"]),
        queries=[_q("q1", "ansible/ansible")],
        pool_factory=_pool_factory_with({"deepwiki": sess}),
        run_dir=tmp_path / "run",
    )
    asyncio.run(orch._maybe_record_deepwiki_index())
    assert not (tmp_path / "run" / "deepwiki_index.json").exists()
    assert sess.calls == []


def test_hook_idempotent_on_resume(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "deepwiki_index.json").write_text("{}", encoding="utf-8")
    sess = _FakeDeepwiki()
    orch = Orchestrator(
        _cfg(tmp_path),
        queries=[_q("q1", "ansible/ansible")],
        pool_factory=_pool_factory_with({"deepwiki": sess}),
        run_dir=run_dir,
    )
    asyncio.run(orch._maybe_record_deepwiki_index())
    assert sess.calls == []  # skipped; manifest already present


def test_hook_best_effort_on_pool_failure(tmp_path: Path):
    def _broken_factory(server_names):
        @asynccontextmanager
        async def _factory(names):
            raise RuntimeError("pool down")
            yield {}  # pragma: no cover

        return _factory(server_names)

    orch = Orchestrator(
        _cfg(tmp_path),
        queries=[_q("q1", "ansible/ansible")],
        pool_factory=_broken_factory,
        run_dir=tmp_path / "run",
    )
    # must not raise; manifest not written
    asyncio.run(orch._maybe_record_deepwiki_index())
    assert not (tmp_path / "run" / "deepwiki_index.json").exists()
