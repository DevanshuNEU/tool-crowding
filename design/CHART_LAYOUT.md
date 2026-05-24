---
title: tool-crowding Launch-Day Killer Chart — Layout Spec
date_locked: 2026-05-23 (Sat AM, pre-pilot)
status: design spec; fixture-driven; populates from real data post-pilot
companion: RESEARCH_DESIGN.md §3 + §4 + §5
purpose: THE chart that travels on Twitter, LinkedIn, HN, arXiv abstract figure
---

# Killer Chart Layout Spec

> One visualization that travels. Designed before the pilot runs so it is sketched empty on Sunday and filled Monday morning. SWE-bench has the leaderboard table; RAG-MCP has the Figure 3 heatmap; tool-crowding has this.

## Layout

Two stacked panels. 16:10 aspect ratio for social cards. Top panel is the headline story (pass@1 vs N curves). Bottom panel is the per-server diagnostic (MPD bars).

### Top panel: pass@1 vs N curves

- **x-axis**: N ∈ {1, 5, 10, 15, 20}. Log-spaced tick labels (matplotlib `xscale("log")` with manual ticks at the 5 measured points).
- **y-axis**: pass@1, 0.0 to 1.0. Major gridlines every 0.1, alpha 0.3.
- **Lines** (4 traces; pre-registered in RESEARCH_DESIGN.md §3 + FOUNDATION.md §1.0):
  - **Solid line, Wong blue (#0072B2)**: unpadded Claude Sonnet 4.6 (the headline result).
  - **Dashed line, Wong orange (#E69F00)**: padded-N=1 control. Per P2 in PRE_REGISTRATION.md, this should be FLAT if discrimination interference is real; SLOPED DOWN if capacity dominates. The visual gap between dashed and solid IS the construct.
  - **Dotted line, Wong vermillion (#D55E00)**: retriever-ON condition (second experimental axis per RESEARCH_DESIGN.md §3).
  - **Solid line, Wong bluish-green (#009E73)**: GPT-5-class for cross-model robustness.
- **Error bars**: paired-bootstrap 99% CI per cell (B=10,000), capped, lineweight 1pt.
- **Annotations**:
  - Horizontal dotted reference line at the unpadded N=1 pass@1 (baseline), light gray, alpha 0.5.
  - Horizontal dotted reference line at (baseline − 0.05) marking the 5pp falsification threshold from P1/P2, light gray with "5pp threshold" label at right edge.
- **Legend**: top-right inside plot area. Order: Sonnet 4.6 unpadded, Sonnet 4.6 padded-N=1, Sonnet 4.6 retriever-ON, GPT-5 unpadded.
- **Panel title**: "pass@1 degrades as concurrent MCPs increase; padding alone does not explain it" (replace with actual finding post-pilot).

### Bottom panel: per-server MPD bars

- **x-axis**: 15 servers (5 primary code-retrieval + 10 distractors), sorted by MPD magnitude (most-favorable left → most-harmful right). Server names rotated 30°.
- **y-axis**: MPD, −0.2 to +0.2. Zero line bold black. Major gridlines every 0.05, alpha 0.3.
- **Bars**: width 0.7. Color-coded per `RESEARCH_DESIGN.md §3` domain-overlap tags:
  - **Primary code-retrieval (5)**: Wong sky-blue (#56B4E9).
  - **Code-adjacent distractors (Filesystem, SQLite, PostgreSQL)**: Wong orange (#E69F00).
  - **Orthogonal distractors (Memory, Sequential Thinking, Time, Brave Search, Linear, Notion, Slack)**: Wong gray (#999999).
- **CI brackets**: paired-bootstrap 95% CI per bar, lineweight 1.5pt, capped.
- **OCI annotation**: star marker "★" above OCI's bar; footnote "★ COI-disclosed: authored by corresponding author. Leave-OCI-out sensitivity in appendix." (per RESEARCH_DESIGN.md §11 item 5).
- **Panel title**: "Per-server Marginal Performance Delta (MPD) at N=10; positive = hurts neighbors".

## Style

- **Palette**: Wong's 8-color colorblind-safe palette (deuteranopia + protanopia safe). Avoid the red/green pair. Hex codes inlined above; locked.
- **Font**: DejaVu Sans (matplotlib default, ships everywhere). 12pt body, 14pt panel titles, 11pt tick labels, 10pt legend.
- **Grid**: light gray, alpha 0.3, behind data (zorder=0).
- **Spines**: top + right hidden; left + bottom kept.
- **Background**: white. No dark-mode variant for launch (high-contrast print-safe wins universally).
- **Aspect**: 16:10 → 1600×1000px. Matplotlib `figsize=(16, 10)` at dpi=100 for SVG; dpi=200 for PNG.
- **Footnote (bottom of figure)**: "n=3 trial repeats per cell × 3 queries (pilot, 144 trials); paired-bootstrap CIs; pre-registered per design/PRE_REGISTRATION.md. Full v1 sweep: n=5 orderings × 50 queries × 5 primary servers."

## Output formats

| Format | Resolution | Use |
|---|---|---|
| SVG | vector | Paper figure (arXiv preprint, workshop submission) |
| PNG @ 2x | 3200×2000px (dpi=200) | LinkedIn, X, HN, blog inline |
| PNG @ 1x | 1600×1000px (dpi=100) | Slack/Discord preview, social card thumbs |

All three regenerate from the same matplotlib code below; differ only by `savefig(..., format=..., dpi=...)`.

## Matplotlib code skeleton (fixture-driven)

```python
"""
analysis/figures/killer_chart.py
Generates the two-panel launch chart from a results dataframe.
Fixture mode (FIXTURE=True) uses synthetic data until real data lands.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Wong colorblind-safe palette
WONG = {
    "blue":          "#0072B2",  # Sonnet 4.6 unpadded
    "orange":        "#E69F00",  # padded-N=1 + code-adjacent distractors
    "vermillion":    "#D55E00",  # retriever-ON
    "bluish_green":  "#009E73",  # GPT-5-class
    "sky_blue":      "#56B4E9",  # primary code-retrieval servers
    "gray":          "#999999",  # orthogonal distractors
    "black":         "#000000",
    "yellow":        "#F0E442",  # reserved
}

FIXTURE = True  # flip to False post-pilot

def load_results():
    """Return (curves_df, mpd_df). Replace with parquet load post-pilot."""
    if FIXTURE:
        Ns = np.array([1, 5, 10, 15, 20])
        curves_df = pd.DataFrame({
            "N": np.tile(Ns, 4),
            "condition": (["sonnet_unpadded"] * 5 + ["sonnet_padded"] * 5
                          + ["sonnet_retrieverON"] * 5 + ["gpt5_unpadded"] * 5),
            "pass1":   [0.78, 0.74, 0.69, 0.63, 0.58,   # sonnet unpadded
                        0.78, 0.77, 0.76, 0.77, 0.76,   # sonnet padded (flat = construct holds)
                        0.78, 0.77, 0.74, 0.71, 0.68,   # retriever-ON
                        0.81, 0.76, 0.72, 0.67, 0.62],  # gpt5 unpadded
            "ci_lo":   [0.74, 0.70, 0.65, 0.59, 0.54,
                        0.74, 0.73, 0.72, 0.73, 0.72,
                        0.74, 0.73, 0.70, 0.67, 0.64,
                        0.77, 0.72, 0.68, 0.63, 0.58],
            "ci_hi":   [0.82, 0.78, 0.73, 0.67, 0.62,
                        0.82, 0.81, 0.80, 0.81, 0.80,
                        0.82, 0.81, 0.78, 0.75, 0.72,
                        0.85, 0.80, 0.76, 0.71, 0.66],
        })
        servers = ["OCI", "GitHub-MCP", "Git-MCP", "Aider", "Fetch",
                   "Filesystem", "SQLite", "PostgreSQL",
                   "Memory", "Seq-Think", "Time", "Brave", "Linear", "Notion", "Slack"]
        tags = (["primary"] * 5 + ["code_adj"] * 3 + ["orthogonal"] * 7)
        mpds = [-0.08, -0.03, -0.02, 0.01, 0.04,
                 0.06, 0.09, 0.11,
                -0.01, 0.00, 0.02, 0.03, 0.05, 0.07, 0.10]
        mpd_df = pd.DataFrame({"server": servers, "tag": tags, "mpd": mpds,
                               "ci_lo": [m - 0.03 for m in mpds],
                               "ci_hi": [m + 0.03 for m in mpds]})
        return curves_df, mpd_df
    raise NotImplementedError("Wire to results/<run_id>/aggregated.parquet")

def plot_killer_chart(curves_df, mpd_df, outpath_svg, outpath_png):
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(16, 10), gridspec_kw={"height_ratios": [3, 2]}
    )
    # Top panel: pass@1 vs N
    styles = [("sonnet_unpadded",   WONG["blue"],         "-",  "Sonnet 4.6 (unpadded)"),
              ("sonnet_padded",     WONG["orange"],       "--", "Sonnet 4.6 (padded-N=1 control)"),
              ("sonnet_retrieverON",WONG["vermillion"],   ":",  "Sonnet 4.6 (retriever-ON)"),
              ("gpt5_unpadded",     WONG["bluish_green"], "-",  "GPT-5-class (unpadded)")]
    for cond, color, ls, label in styles:
        sub = curves_df[curves_df["condition"] == cond]
        yerr = [sub["pass1"] - sub["ci_lo"], sub["ci_hi"] - sub["pass1"]]
        ax_top.errorbar(sub["N"], sub["pass1"], yerr=yerr,
                        color=color, linestyle=ls, linewidth=2,
                        marker="o", markersize=6, capsize=4, label=label)
    baseline = curves_df[(curves_df["condition"] == "sonnet_unpadded")
                         & (curves_df["N"] == 1)]["pass1"].iloc[0]
    ax_top.axhline(baseline, color="gray", linestyle=":", alpha=0.5)
    ax_top.axhline(baseline - 0.05, color="gray", linestyle=":", alpha=0.5)
    ax_top.text(20.5, baseline - 0.05, "5pp threshold", fontsize=10, va="center", color="gray")
    ax_top.set_xscale("log"); ax_top.set_xticks([1, 5, 10, 15, 20])
    ax_top.set_xticklabels(["1", "5", "10", "15", "20"])
    ax_top.set_xlabel("N (concurrently-installed MCP servers)", fontsize=12)
    ax_top.set_ylabel("pass@1", fontsize=12)
    ax_top.set_ylim(0.0, 1.0); ax_top.grid(alpha=0.3, zorder=0)
    ax_top.spines["top"].set_visible(False); ax_top.spines["right"].set_visible(False)
    ax_top.legend(loc="upper right", fontsize=10, framealpha=0.95)
    ax_top.set_title("pass@1 degrades as concurrent MCPs increase; padding alone does not explain it",
                     fontsize=14, loc="left")
    # Bottom panel: per-server MPD bars
    mpd_sorted = mpd_df.sort_values("mpd").reset_index(drop=True)
    tag_to_color = {"primary":    WONG["sky_blue"],
                    "code_adj":   WONG["orange"],
                    "orthogonal": WONG["gray"]}
    colors = [tag_to_color[t] for t in mpd_sorted["tag"]]
    yerr = [mpd_sorted["mpd"] - mpd_sorted["ci_lo"],
            mpd_sorted["ci_hi"] - mpd_sorted["mpd"]]
    ax_bot.bar(mpd_sorted["server"], mpd_sorted["mpd"], yerr=yerr,
               color=colors, edgecolor="black", linewidth=0.5, capsize=3, width=0.7)
    ax_bot.axhline(0, color="black", linewidth=1)
    for i, row in mpd_sorted.iterrows():
        if row["server"] == "OCI":
            ax_bot.text(i, row["ci_hi"] + 0.01, "★", ha="center", fontsize=14)
    ax_bot.set_ylim(-0.2, 0.2); ax_bot.set_ylabel("MPD", fontsize=12)
    ax_bot.set_xlabel("MCP server (sorted by MPD)", fontsize=12)
    ax_bot.tick_params(axis="x", rotation=30); ax_bot.grid(alpha=0.3, axis="y", zorder=0)
    ax_bot.spines["top"].set_visible(False); ax_bot.spines["right"].set_visible(False)
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=tag_to_color[t]) for t in
                      ["primary", "code_adj", "orthogonal"]]
    ax_bot.legend(legend_handles, ["Primary code-retrieval", "Code-adjacent distractor",
                                    "Orthogonal distractor"], loc="upper left", fontsize=10)
    ax_bot.set_title("Per-server MPD at N=10; positive = hurts neighbors", fontsize=14, loc="left")
    fig.text(0.5, 0.01,
             "★ OCI: COI-disclosed (corresponding author). Leave-OCI-out sensitivity in appendix.    "
             "n=3 repeats × 3 queries (pilot); paired-bootstrap CIs; pre-registered per design/PRE_REGISTRATION.md.",
             ha="center", fontsize=9, style="italic", color="#444444")
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(outpath_svg, format="svg", bbox_inches="tight")
    fig.savefig(outpath_png, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    curves_df, mpd_df = load_results()
    plot_killer_chart(curves_df, mpd_df,
                      outpath_svg="figures/killer_chart.svg",
                      outpath_png="figures/killer_chart.png")
```

## What this chart says in one sentence

"pass@1 falls with N; the padded-N=1 control stays flat, so length is not the explanation; some MCPs hurt their neighbors more than others, and we name which ones."

## What it does NOT say (and we resist adding)

- It does not show pass@3, latency, token cost, or RAG-MCP replication; those go in supplementary figures.
- It does not include Opus 4.7 (deferred to v2 retriever-ON sweep per RESEARCH_DESIGN.md §3).
- It does not include 8 servers; we tested 15. The bottom panel shows all 15.
- It does not smooth, fit a logistic, or extrapolate beyond N=20.

## Related

[[FOUNDATION]] [[PRE_REGISTRATION]] [[../RESEARCH_DESIGN]] [[ADVERSARIAL_AUDIT]] [[SERVER_POOL]]
