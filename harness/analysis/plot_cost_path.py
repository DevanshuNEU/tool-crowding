"""Render the exploratory path-cost figure (cost vs trajectory length).

$0, no API calls. Reads the four frozen exploratory-probe trial records committed
under ``analysis/probe_data/`` and renders a scatter of per-trial cost against the
number of tool calls, colored by task framing. Run:

    python analysis/plot_cost_path.py            # writes ../figures/cost_vs_path.png

The companion accuracy figure (``plot_interaction.py``) shows routing is robust:
mis-routing is null in 3 of 4 conditions and pass@1 is 18/19 (the single miss is an
``api_fault``, not a mis-route). This figure is the *other* half of the same data:
even when routing is clean, the **cost** of a trial is set by how long the agent
wanders, and the agent wanders far more under an ambiguous task framing.

EXPLORATORY, not a result. One task, Claude Sonnet 4.6, temperature 0, retriever OFF,
n=19 trials across 4 conditions. N (server count) co-varies with framing in this probe
set (N=6 exists only in the named/code-retrieval cell), so this is a directional
observation about path cost, not an isolated N or distractor effect. The per-trial
``context_input_tokens`` is cumulative over the agent loop, so it is dominated by
trajectory length, not by the static tool-definition prefix. Read FINDINGS.md /
RESULTS.md before citing this figure anywhere.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")  # headless / deterministic; no display required
import matplotlib.pyplot as plt  # noqa: E402

from tcrun.results import read_jsonl  # noqa: E402

_ANALYSIS_DIR = Path(__file__).resolve().parent
_PROBE_DATA_DIR = _ANALYSIS_DIR / "probe_data"
_DEFAULT_FIG = _ANALYSIS_DIR.parents[1] / "figures" / "cost_vs_path.png"

# (subdir, framing). Framing is carried by directory name (see PROVENANCE.md), not a
# flat trial field. "named" = target named in the task; "ambiguous" = it is not.
_CONDITIONS: list[tuple[str, str]] = [
    ("count-null_n6-dissimilar_named_code-retrieval", "named"),
    ("similarity-null_n4-similar_named_code-retrieval", "named"),
    ("ambiguity-only_n4-similar_ambiguous_code-retrieval", "ambiguous"),
    ("interaction_n4-similar_ambiguous_neutral", "ambiguous"),
]

_COLORS = {"named": "#4C72B0", "ambiguous": "#DD8452"}


def _load(probe_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for subdir, framing in _CONDITIONS:
        path = probe_dir / subdir / "trials.jsonl"
        if not path.exists():
            raise FileNotFoundError(
                f"probe data missing: {path}\n"
                "Expected the committed fixture under analysis/probe_data/ "
                "(see probe_data/PROVENANCE.md)."
            )
        for trial in read_jsonl(path):
            rows.append(
                {
                    "framing": framing,
                    "calls": len(trial.tool_calls),
                    "cost": trial.cost_usd,
                    "passed": trial.pass_,
                    "api_fault": trial.error_type == "api_fault",
                }
            )
    return rows


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) ** 0.5) * (sum((y - my) ** 2 for y in ys) ** 0.5)
    return num / den if den else float("nan")


def build_figure(probe_dir: Path = _PROBE_DATA_DIR) -> plt.Figure:
    rows = _load(probe_dir)
    r = _pearson([row["calls"] for row in rows], [row["cost"] for row in rows])

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    for framing in ("named", "ambiguous"):
        grp = [row for row in rows if row["framing"] == framing]
        n = len(grp)
        ax.scatter(
            [row["calls"] for row in grp if row["passed"]],
            [row["cost"] for row in grp if row["passed"]],
            s=90, color=_COLORS[framing], alpha=0.85, edgecolors="white", linewidths=0.6,
            label=(
                f"{framing} target  (n={n}, mean ${mean(row['cost'] for row in grp):.2f}, "
                f"{mean(row['calls'] for row in grp):.1f} calls)"
            ),
        )
    # the single failed trial (api_fault, not a mis-route) marked distinctly
    for row in rows:
        if not row["passed"]:
            ax.scatter(
                row["calls"], row["cost"], s=180, marker="X", color="#C44E52",
                edgecolors="black", linewidths=0.8, zorder=5,
                label="failed trial (api_fault, not a mis-route)",
            )

    ax.set_xlabel("number of tool calls in the trial (trajectory length)")
    ax.set_ylabel("trial cost (USD)")
    ax.set_title(
        "Path cost is set by trajectory length, not tool count\n"
        f"Cost rises with how far the agent wanders (Pearson r = {r:.2f}, n={len(rows)}); "
        "ambiguous framing wanders ~4x further",
        fontsize=12,
    )
    ax.legend(loc="upper left", fontsize=8.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)

    caption = (
        "EXPLORATORY probes, not a result. One task, Claude Sonnet 4.6, temperature 0, retriever OFF; "
        "n=19 trials across 4 conditions. pass@1 = 18/19 (the one miss is an api_fault, not a mis-route); "
        "routing is null in 3 of 4 cells (see plot_interaction.py).\n"
        "N (server count) co-varies with framing here (N=6 only in the named cell), and the requested "
        "per-trial tool-definition tax cannot be isolated from this data: context_input_tokens is cumulative\n"
        "over the agent loop, so it tracks trajectory length, not the static tool-def prefix. The honest read: "
        "ambiguous tasks make the agent wander, and the wandering is where the cost goes. See FINDINGS.md / RESULTS.md."
    )
    fig.text(0.5, -0.02, caption, ha="center", va="top", fontsize=7.8, color="#444444")
    fig.tight_layout()
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_DEFAULT_FIG)
    parser.add_argument("--probe-dir", type=Path, default=_PROBE_DATA_DIR)
    args = parser.parse_args()

    fig = build_figure(args.probe_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
