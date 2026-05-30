"""tcrun CLI entry point per SPEC.md §8.

Subcommands:
    tcrun run --config CFG        Run a sweep (default)
    tcrun resume RUN_ID           Resume a crashed run
    tcrun status RUN_ID           Per-cell completion report
    tcrun verify RUN_ID           Re-run 5 random trials + schema check
    tcrun runid --config CFG      Compute run_id without executing
    tcrun reproduce TRIAL_ID      Single-trial replay (REPRODUCIBILITY.md §4.1)
    tcrun validate --config CFG   Validate config without API calls

LOC budget per the implementation prompt: ~120 LOC.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from pathlib import Path

import typer

from tcrun.config import compute_run_id, load_config
from tcrun.orchestrator import Orchestrator
from tcrun.preflight import PreflightError, PreflightGate
from tcrun.results import read_jsonl
from tcrun.runner import make_default_agent_factory, make_default_pool_factory
from tcrun.servers import load_pinned_servers
from tcrun.snapshot import (
    snapshot_all_descriptions,
    snapshot_server_descriptions,
    update_descriptions_file,
    write_env_lock,
)
from tcrun.tasks import load_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _find_run_dir(run_id: str, search_root: Path = Path("results")) -> Path:
    """Locate results/<run_id>/ even when nested under a per-config out dir."""
    direct = search_root / run_id
    if direct.exists():
        return direct
    if search_root.exists():
        for parent in search_root.iterdir():
            if not parent.is_dir():
                continue
            candidate = parent / run_id
            if candidate.exists():
                return candidate
    raise typer.BadParameter(f"run_id {run_id} not found under {search_root}/")


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", help="YAML config path"),
    skip_preflight: bool = typer.Option(False, "--skip-preflight", help="DEBUG only"),
    cost_cap: float | None = typer.Option(
        None,
        "--cost-cap",
        help="Hard USD ceiling; halt once a completed trial pushes the running "
        "cost over this. Operational guardrail, NOT hashed into run_id. "
        "Omit to use the 200.0 default.",
    ),
) -> None:
    """Run a sweep per SPEC.md §8."""
    cfg = load_config(config)
    if not skip_preflight:
        try:
            PreflightGate(cfg).run()
        except PreflightError as e:
            typer.echo(f"preflight failed: {e}", err=True)
            raise typer.Exit(code=2)
    try:
        queries = load_tasks(cfg.task_set)
    except Exception as e:
        typer.echo(f"task load failed: {e}", err=True)
        raise typer.Exit(code=2)
    # Resolve run_dir up front so the agent factory writes traces alongside
    # trials.jsonl. compute_run_id is idempotent so calling it here + inside
    # Orchestrator yields the same path.
    from tcrun.config import compute_run_id
    run_dir = Path(cfg.out) / compute_run_id(cfg)
    orchestrator = Orchestrator(
        cfg,
        run_dir=run_dir,
        queries=queries,
        pool_factory=make_default_pool_factory(cfg),
        agent_factory=make_default_agent_factory(cfg, run_dir=run_dir),
        cost_cap_usd=cost_cap,  # None -> Orchestrator's 200.0 fallback (unchanged when omitted)
    )
    summary = asyncio.run(orchestrator.run())
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def resume(run_id: str = typer.Argument(..., help="run_id to resume")) -> None:
    """Resume a crashed run from its checkpoint."""
    run_dir = _find_run_dir(run_id)
    typer.echo(f"resuming run {run_id} from {run_dir}")
    # The Orchestrator constructor auto-loads checkpoint.json; just re-invoke .run().
    # The config used to start the run lives in run_dir/config.yaml (written at run start).
    cfg_path = run_dir / "config.yaml"
    if not cfg_path.exists():
        typer.echo(f"config snapshot missing at {cfg_path}", err=True)
        raise typer.Exit(code=2)
    cfg = load_config(cfg_path)
    queries = load_tasks(cfg.task_set)
    orchestrator = Orchestrator(
        cfg,
        run_dir=run_dir,
        queries=queries,
        pool_factory=make_default_pool_factory(cfg),
        agent_factory=make_default_agent_factory(cfg, run_dir=run_dir),
    )
    summary = asyncio.run(orchestrator.run())
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def status(run_id: str = typer.Argument(..., help="run_id to report on")) -> None:
    """Per-cell completion report (SPEC.md §8)."""
    run_dir = _find_run_dir(run_id)
    ckpt_path = run_dir / "checkpoint.json"
    if not ckpt_path.exists():
        typer.echo(f"no checkpoint at {ckpt_path}", err=True)
        raise typer.Exit(code=1)
    data = json.loads(ckpt_path.read_text(encoding="utf-8"))
    typer.echo(
        json.dumps(
            {
                "run_id": data["run_id"],
                "n_completed": len(data.get("completed_trial_ids", [])),
                "running_cost_usd": data.get("running_cost_usd", 0.0),
            },
            indent=2,
        )
    )


@app.command()
def verify(run_id: str = typer.Argument(..., help="run_id to verify")) -> None:
    """Re-validate 5 random trials' schema (SPEC.md §8 verify)."""
    run_dir = _find_run_dir(run_id)
    trials_path = run_dir / "trials.jsonl"
    if not trials_path.exists():
        typer.echo(f"no trials at {trials_path}", err=True)
        raise typer.Exit(code=1)
    rows = list(read_jsonl(trials_path))
    if not rows:
        typer.echo("no trials to verify", err=True)
        raise typer.Exit(code=1)
    sample = random.sample(rows, k=min(5, len(rows)))
    for t in sample:
        # model_validate already ran in read_jsonl; affirm schema_version too.
        assert t.schema_version, "missing schema_version"
    typer.echo(json.dumps({"verified": len(sample), "run_id": run_id}, indent=2))


@app.command()
def runid(
    config: Path = typer.Option(..., "--config", "-c", help="YAML config path"),
) -> None:
    """Compute the run_id for a config without executing (SPEC.md §8)."""
    cfg = load_config(config)
    typer.echo(compute_run_id(cfg))


@app.command()
def reproduce(trial_id: str = typer.Argument(..., help="trial_id to replay")) -> None:
    """Single-trial replay per REPRODUCIBILITY.md §4.1."""
    # Locate the trial by scanning every run_dir's trials.jsonl.
    root = Path("results")
    candidate_dirs: list[Path] = []
    if root.exists():
        for p in root.iterdir():
            if p.is_dir():
                candidate_dirs.append(p)
                # One level deeper (results/<exp>/<run_id>/) too.
                for sub in p.iterdir() if p.is_dir() else []:
                    if sub.is_dir():
                        candidate_dirs.append(sub)
    for run_dir in candidate_dirs:
        trials_path = run_dir / "trials.jsonl"
        if not trials_path.exists():
            continue
        for trial in read_jsonl(trials_path):
            if trial.trial_id == trial_id:
                typer.echo(
                    json.dumps(
                        {
                            "trial_id": trial.trial_id,
                            "run_id": trial.run_id,
                            "cell_id": trial.cell_id,
                            "would_replay": True,
                        },
                        indent=2,
                    )
                )
                return
    typer.echo(f"trial {trial_id} not found", err=True)
    raise typer.Exit(code=1)


@app.command()
def validate(
    config: Path = typer.Option(..., "--config", "-c", help="YAML config path"),
) -> None:
    """Validate the config (schema + artifact hashes) without dispatching trials."""
    cfg = load_config(config)
    gate = PreflightGate(cfg)
    try:
        result = gate.run()
    except PreflightError as e:
        typer.echo(f"validate failed: {e}", err=True)
        raise typer.Exit(code=2)
    typer.echo(
        json.dumps(
            {"run_id": compute_run_id(cfg), "gates": [g[0] for g in result.gates]},
            indent=2,
        )
    )


@app.command(name="snapshot-env")
def snapshot_env_cmd(
    out: Path = typer.Option(Path("environment.lock"), "--out", "-o", help="env.lock output path"),
    servers_pinned: Path = typer.Option(
        Path("tcrun/servers_pinned.yaml"),
        "--servers-pinned",
        help="servers_pinned.yaml for docker digest capture (omit to skip docker)",
    ),
) -> None:
    """Write environment.lock (OS + Python + sorted pip freeze + docker SHAs).

    Re-run when Python deps or docker images change. Output is deterministic
    given identical environment state (no timestamps) so re-snapshotting on
    an unchanged box produces byte-identical content and a stable run_id.
    """
    yaml_arg = servers_pinned if servers_pinned.exists() else None
    payload = write_env_lock(out, servers_yaml_path=yaml_arg)
    typer.echo(
        json.dumps(
            {
                "out": str(out),
                "python_version": payload["python_version"],
                "pip_freeze_count": len(payload.get("pip_freeze", [])),
                "docker_images_count": len(payload.get("docker_images", {})),
            },
            indent=2,
        )
    )


@app.command(name="snapshot-descriptions")
def snapshot_descriptions_cmd(
    config: Path = typer.Option(..., "--config", "-c", help="YAML config path"),
    server: str = typer.Option(
        "",
        "--server",
        help="Snapshot one named server (incremental); empty + --all for everyone",
    ),
    all_servers: bool = typer.Option(
        False, "--all", help="Snapshot every server in servers_pinned.yaml"
    ),
    out: Path = typer.Option(
        Path("pool/descriptions.json"),
        "--out",
        "-o",
        help="descriptions.json output path",
    ),
    timeout: float = typer.Option(30.0, "--timeout", help="Per-server timeout (s)"),
) -> None:
    """Snapshot one (or all) MCP server(s) tool definitions into descriptions.json.

    Single-server mode is incremental: it merges one entry into the existing
    file, leaving every other server's entry untouched. The --all mode
    tolerates per-server failures (logged, returned in the summary, exit
    code 1 if anything failed) so a single un-runnable server doesn't block
    the rest of the snapshot.
    """
    cfg = load_config(config)
    if not server and not all_servers:
        typer.echo("must pass --server NAME or --all", err=True)
        raise typer.Exit(code=2)
    if server and all_servers:
        typer.echo("--server and --all are mutually exclusive", err=True)
        raise typer.Exit(code=2)
    if server:
        pins = load_pinned_servers(cfg.servers_pinned)
        if server not in pins:
            typer.echo(
                f"unknown server {server!r}; known: {sorted(pins)}", err=True
            )
            raise typer.Exit(code=2)
        entry = asyncio.run(
            snapshot_server_descriptions(pins[server], timeout_s=timeout)
        )
        update_descriptions_file(out, server, entry)
        typer.echo(
            json.dumps(
                {"server": server, "tools_count": len(entry["tools"]), "out": str(out)},
                indent=2,
            )
        )
        return
    final, failures = asyncio.run(
        snapshot_all_descriptions(cfg.servers_pinned, out, timeout_s=timeout)
    )
    typer.echo(
        json.dumps(
            {
                "out": str(out),
                "servers_count": len(final.get("servers", {})),
                "failures": [{"server": n, "reason": r} for n, r in failures],
            },
            indent=2,
        )
    )
    if failures:
        raise typer.Exit(code=1)


def _load_env() -> None:
    """Auto-load harness/.env so OPENAI_API_KEY, TC_EMBEDDER, etc. resolve.

    Anchored to the harness package root (not CWD) so `tcrun` invocations
    from outside `harness/` (e.g. parent dir, or via absolute path from
    elsewhere) still pick up the .env. Scoped to the CLI entry so test
    imports stay env-isolated (tests drive os.environ explicitly).

    override=True is deliberate: .env is the source of truth for tcrun
    credentials. A stale `export ANTHROPIC_API_KEY=...` in the user's shell
    rc would otherwise shadow the .env value, every subprocess inherits the
    stale shell key, and Anthropic returns 401 against a key the dashboard
    swears is live (2026-05-26 smoke wasted a session diagnosing exactly
    this). If the override discards a shell value, log a warning naming the
    key so the surprise is loud, not silent.
    """
    try:
        from dotenv import dotenv_values, load_dotenv  # base dep per pyproject.toml
    except ImportError:
        return  # graceful no-op if dotenv missing (e.g., partial install)
    env_path = Path(__file__).parents[1] / ".env"
    if not env_path.exists():
        return
    file_values = dotenv_values(env_path)
    for k, file_v in file_values.items():
        shell_v = os.environ.get(k)
        if shell_v is not None and file_v is not None and shell_v != file_v:
            print(
                f"[load_dotenv] WARNING: {k} in shell env != .env; .env wins "
                f"(shell ended ...{shell_v[-4:]}, .env ends ...{file_v[-4:]}). "
                f"Remove the stale export from your shell rc to silence this.",
                file=sys.stderr,
            )
    load_dotenv(dotenv_path=env_path, override=True)


def main() -> int:
    """CLI entry point (registered in pyproject.toml [project.scripts])."""
    _load_env()
    app()
    return 0


if __name__ == "__main__":
    main()
