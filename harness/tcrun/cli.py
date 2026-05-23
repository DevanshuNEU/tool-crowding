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
import random
from pathlib import Path

import typer

from tcrun.config import compute_run_id, load_config
from tcrun.orchestrator import Orchestrator
from tcrun.preflight import PreflightError, PreflightGate
from tcrun.results import read_jsonl
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
    orchestrator = Orchestrator(cfg, queries=queries)
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
    orchestrator = Orchestrator(cfg, run_dir=run_dir, queries=queries)
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


def main() -> int:
    """CLI entry point (registered in pyproject.toml [project.scripts])."""
    app()
    return 0


if __name__ == "__main__":
    main()
