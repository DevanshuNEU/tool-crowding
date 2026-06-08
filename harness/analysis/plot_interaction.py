"""Render the exploratory framing x ambiguity interaction figure.

$0, no API calls. Reads the four frozen exploratory-probe trial records committed
under ``analysis/probe_data/`` and renders a grouped bar chart of mis-routing rates
across the four probe conditions. Run:

    python analysis/plot_interaction.py          # writes ../figures/interaction_mis_routing.png

This is NOT a headline result. Three of the four conditions show zero mis-routing
(the naive "more tools / similar tools breaks routing" hypothesis is falsified); the
signal appears only in the fourth (ambiguous task + neutral persona) and rests on a
single lure-solve event that landed on ordering 0. The caption owns that thinness.
Read FINDINGS.md and RESULTS.md before citing this figure anywhere.

Renaming note: this replaces the dead ``pareto.py`` stub. The original plan was a
Pareto frontier over N (server count), but the count axis is null in the probe data,
so the honest figure is the interaction across conditions, not a curve over N.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless / deterministic; no display required
import matplotlib.pyplot as plt  # noqa: E402

from tcrun.results import read_jsonl  # noqa: E402

# Repo layout: this file is harness/analysis/plot_interaction.py.
_ANALYSIS_DIR = Path(__file__).resolve().parent
_PROBE_DATA_DIR = _ANALYSIS_DIR / "probe_data"
_DEFAULT_FIG = _ANALYSIS_DIR.parents[1] / "figures" / "interaction_mis_routing.png"

# The four frozen probes, in the order they tell the story. The persona/framing
# factors are hashed into run_id rather than stored as flat trial fields, so the
# condition label is carried here by directory name (see probe_data/PROVENANCE.md),
# not derived from the trial rows. Each entry: (subdir, short x-tick label).
_CONDITIONS: list[tuple[str, str]] = [
    ("count-null_n6-dissimilar_named_code-retrieval", "N=6 dissimilar\nnamed | code-retrieval"),
    ("similarity-null_n4-similar_named_code-retrieval", "N=4 similar\nnamed | code-retrieval"),
    ("ambiguity-only_n4-similar_ambiguous_code-retrieval", "N=4 similar\nambiguous | code-retrieval"),
    ("interaction_n4-similar_ambiguous_neutral", "N=4 similar\nambiguous | NEUTRAL"),
]


def _condition_rates(trials_path: Path) -> tuple[int, int, int]:
    """Return (n_trials, n_distractor_touch, n_lure_solve) for one probe.

    distractor-touch: the trial made at least one tool call to a server other than
        its grounded primary (``server_called != primary_server``).
    lure-solve: the answer surfaced from a non-primary server
        (``solving_server`` is set and is not the grounded primary). In this probe
        set that server is always ``deepwiki``, the pre-registered lure.
    Both are derived purely from committed trial fields; no distractor list is
    hardcoded, so the metric is robust to pool changes.
    """
    n = 0
    touched = 0
    lured = 0
    for trial in read_jsonl(trials_path):
        n += 1
        primary = trial.primary_server
        if any(tc.server_called != primary for tc in trial.tool_calls):
            touched += 1
        if trial.solving_server is not None and trial.solving_server != primary:
            lured += 1
    return n, touched, lured


def build_figure(probe_dir: Path = _PROBE_DATA_DIR) -> plt.Figure:
    labels: list[str] = []
    touch_rates: list[float] = []
    lure_rates: list[float] = []
    touch_ann: list[str] = []
    lure_ann: list[str] = []

    for subdir, label in _CONDITIONS:
        path = probe_dir / subdir / "trials.jsonl"
        if not path.exists():
            raise FileNotFoundError(
                f"probe data missing: {path}\n"
                "Expected the committed fixture under analysis/probe_data/ "
                "(see probe_data/PROVENANCE.md)."
            )
        n, touched, lured = _condition_rates(path)
        labels.append(label)
        touch_rates.append(touched / n)
        lure_rates.append(lured / n)
        touch_ann.append(f"{touched}/{n}")
        lure_ann.append(f"{lured}/{n}")

    x = range(len(labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(10, 5.6))
    bars_touch = ax.bar(
        [i - width / 2 for i in x], touch_rates, width,
        label="distractor-touch rate", color="#4C72B0",
    )
    bars_lure = ax.bar(
        [i + width / 2 for i in x], lure_rates, width,
        label="lure-solve rate (answered via deepwiki)", color="#C44E52",
    )

    for bar, ann in zip(bars_touch, touch_ann):
        ax.annotate(ann, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9, xytext=(0, 2),
                    textcoords="offset points")
    for bar, ann in zip(bars_lure, lure_ann):
        ax.annotate(ann, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9, xytext=(0, 2),
                    textcoords="offset points")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("rate (fraction of trials)")
    ax.set_ylim(0, 1.0)
    ax.set_title(
        "Tool mis-routing appears only under task ambiguity + an under-specified agent\n"
        "Server count and surface similarity alone do not degrade routing",
        fontsize=12,
    )
    ax.legend(loc="upper left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    caption = (
        "EXPLORATORY probes, not a result. One task, Claude Sonnet 4.6, temperature 0, retriever OFF; "
        "n=4-5 trials per condition (one ordering each).\n"
        "Grounded route = github_mcp; deepwiki = pre-registered lure. The single lure-solve "
        "landed on ordering 0 (position bias is an unmodelled confound).\n"
        "This falsifies the naive count/similarity hypothesis and motivates a framing x ambiguity "
        "design; it is not an effect size. See FINDINGS.md / RESULTS.md."
    )
    fig.text(0.5, -0.02, caption, ha="center", va="top", fontsize=8, color="#444444")
    fig.tight_layout()
    return fig


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=_DEFAULT_FIG,
                    help=f"output PNG path (default: {_DEFAULT_FIG})")
    ap.add_argument("--probe-dir", type=Path, default=_PROBE_DATA_DIR,
                    help="directory of committed probe fixtures")
    args = ap.parse_args()

    fig = build_figure(args.probe_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
