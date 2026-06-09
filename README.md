# tool-crowding

> A pre-registered, open-methodology benchmark for measuring discrimination interference among concurrently-installed MCP servers on code retrieval.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-336%20passing-brightgreen.svg)](harness/tests/)
[![Pre-registered](https://img.shields.io/badge/predictions-pre--registered-purple.svg)](design/PRE_REGISTRATION.md)
[![Status](https://img.shields.io/badge/status-pre--pilot-orange.svg)](CHANGELOG.md)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-blueviolet.svg)](CITATION.cff)

When you install 10 to 20 Model Context Protocol servers simultaneously (the realistic 2026 deployment), does your agent's ability to select the right tool degrade? If so, is the degradation caused by prompt-length capacity, by genuine discrimination interference among semantically-overlapping tool descriptions, or by retriever errors? tool-crowding measures all three under controlled conditions, isolates them via a padded-N=1 control adapted from Chroma's text-retrieval methodology, and publishes per-server Marginal Performance Delta as a diagnostic.

---

## Table of contents

- [Status](#status)
- [What we measure](#what-we-measure)
- [Quickstart](#quickstart)
- [Design](#design)
- [Pre-registration](#pre-registration)
- [What this is NOT](#what-this-is-not)
- [Roadmap](#roadmap)
- [Conflict of interest](#conflict-of-interest)
- [Acknowledgments](#acknowledgments)
- [Citation](#citation)
- [Contributing](#contributing)
- [License](#license)

## Status

**Pre-pilot.** Methodology locked across 10 binding design docs. 12-module Python harness with 336 passing pytest cases. 199-entry fake-tool corpus. Five hand-curated oracle smoke tests (5/5 pass). Pre-registered predictions and four scenario abstracts committed before the pilot runs. One round of cheap exploratory probes is in — 19 trials, one task, one model (see [`FINDINGS.md`](FINDINGS.md)) — directional signal only, not pre-registered results.

| Milestone                                | State                          |
| ---------------------------------------- | ------------------------------ |
| Methodology locked (10 design docs)      | done                           |
| Harness + corpus + tests                 | done — 336 tests passing       |
| Exploratory probes (cheap falsification) | done — 19 trials, exploratory  |
| Pre-registered pilot                     | gated on API credits           |
| Public launch + arXiv preprint draft     | gated on the pilot             |

The confirmatory pilot and everything downstream are gated on funding the API run (see [Roadmap](#roadmap)). This README will be updated with verified numbers only after the pre-registered pilot lands. We do not over-claim.

## What we measure

Tool-crowding is operationalized as **discrimination interference**: the degradation in tool-selection accuracy attributable to the presence of other concurrently-installed tools whose descriptions are semantically similar enough to compete with the correct tool for selection, isolated from prompt-length effects via padded-N=1 controls. Full operational definition in [`design/FOUNDATION.md`](design/FOUNDATION.md) §1.0.

The 6-condition intersection that the prior-art coverage map leaves open:

1. **Code retrieval as the held-constant task**, not web search (RAG-MCP), booking APIs (LongFuncEval), or general agent tasks (MCPVerse)
2. **A frontier-model panel** (Claude Sonnet 4.6, Opus 4.7, GPT-5-class, Gemini 2.5-class), not single-model or non-frontier-mixed
3. **Padded-N=1 prompt-length control** adapted from Chroma into the MCP tool regime
4. **Per-server Marginal Performance Delta** as a published per-server diagnostic
5. **Full server SHA + tool-description + JSON-schema hashing into `run_id`** for reproducibility
6. **Retriever ON/OFF as a second axis**, motivated by LiveMCPBench's 50% retrieval-side-error finding

## Quickstart

Requires Python 3.11 or later.

```bash
git clone https://github.com/DevanshuNEU/tool-crowding
cd tool-crowding/harness
python -m venv .venv
.venv/bin/pip install -e ".[dev,analysis]"
.venv/bin/python -m pytest tests/   # 336 tests, ~7 seconds
```

Running a sweep against the Anthropic API requires `ANTHROPIC_API_KEY` and the pinned server pool. See [`harness/SPEC.md`](harness/SPEC.md) for the CLI and [`design/REPRODUCIBILITY.md`](design/REPRODUCIBILITY.md) for the 7-artifact identity chain.

### Reproduce the exploratory figure (no API key, $0)

The current figure is regenerated from committed probe records, so it needs no API
key and makes no network calls:

```bash
cd tool-crowding/harness
python -m venv .venv
.venv/bin/pip install -e ".[analysis]"
.venv/bin/python analysis/plot_interaction.py   # writes figures/interaction_mis_routing.png
```

The input data is the four frozen probes under
[`harness/analysis/probe_data/`](harness/analysis/probe_data/) (see its `PROVENANCE.md`);
the writeup is [`FINDINGS.md`](FINDINGS.md) and [`RESULTS.md`](RESULTS.md). This is an
exploratory falsification of the naive count hypothesis plus a single directional signal,
not a headline result.

### With API credits: the deferred crowding sweep

The crowding axis (a pass-rate-over-N curve) is wired but not yet run, because it costs
real money. [`harness/configs/nsweep-minimal.yaml`](harness/configs/nsweep-minimal.yaml)
is the cheapest valid 3-point sweep (8 trials, ~$1.60 at the measured rate); the full
funded pilot is specified in [`design/PILOT_V0.md`](design/PILOT_V0.md). Run with:

```bash
tcrun run -c configs/nsweep-minimal.yaml --cost-cap 6   # requires ANTHROPIC_API_KEY + credits
```

## Design

The methodology is locked in 10 binding documents. Read them in this order:

1. [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md) — canonical 11-section design with a reviewer-2 dialectic
2. [`design/FOUNDATION.md`](design/FOUNDATION.md) — binding construct definition + ABC checklist (16/30 SAT-D)
3. [`design/PRE_REGISTRATION.md`](design/PRE_REGISTRATION.md) — four scenario abstracts locked before data
4. [`design/PADDING_STRATEGY.md`](design/PADDING_STRATEGY.md) — the load-bearing F1 falsification arm
5. [`design/QUERY_SET_HYGIENE.md`](design/QUERY_SET_HYGIENE.md) — six layered contamination defenses
6. [`design/REPRODUCIBILITY.md`](design/REPRODUCIBILITY.md) — the 7-artifact content-addressed identity chain
7. [`design/SERVER_POOL.md`](design/SERVER_POOL.md) — 18-server pool (5 chart-primaries + 13 distractors) with reachability + pinning
8. [`design/ADVERSARIAL_AUDIT.md`](design/ADVERSARIAL_AUDIT.md) — six attack vectors on the benchmark itself
9. [`design/CHART_LAYOUT.md`](design/CHART_LAYOUT.md) — the headline figure specification
10. [`design/PILOT_V0.md`](design/PILOT_V0.md) — the 224-trial pilot scope

Engineering spec lives at [`harness/SPEC.md`](harness/SPEC.md). It includes a principle-transfer audit against DDIA (Kleppmann 2017) that names the nine principles which DO NOT TRANSFER to a single-author research harness.

## Pre-registration

Predictions are locked in [`design/PRE_REGISTRATION.md`](design/PRE_REGISTRATION.md) before the pilot runs. Four scenario abstracts cover the outcome space with explicit priors:

| Scenario                 | Prior | One-line claim                                                                                                             |
| ------------------------ | ----- | -------------------------------------------------------------------------------------------------------------------------- |
| Clean win                | 15%   | Both frontier models show ≥5pp degradation; padded-N=1 leaves ≥5pp residual; MPD stable; description-similarity correlates |
| Methodology contribution | 35%   | Padded-N=1 accounts for most of the gap; contribution narrows to methodology port + per-server diagnostic                  |
| Frontier robust          | 25%   | Both frontier models show <5pp degradation; per-server MPD becomes the lasting contribution                                |
| Mixed by model class     | 25%   | Sonnet 4.6 inverted-U; GPT-5-class monotonic; deployment recommendations model-conditional                                 |

Decision rules per scenario are locked. **No post-hoc rationalization.** Kill criteria are documented at [`design/FOUNDATION.md`](design/FOUNDATION.md) §3 and reviewed weekly. If any fires, the project pivots or shelves cleanly.

## What this is NOT

- **NOT a leaderboard of MCP servers.** It is a methodology + diagnostic. Leaderboard framing implies competitive ranking; ours is descriptive.
- **NOT a multi-task benchmark.** Code retrieval only for v1. API tasks, browser, file ops are v2.
- **NOT a model-axis comparison.** Single primary model (Sonnet 4.6) carries the headline claim; other frontier models are robustness, not core.
- **NOT a recommendation tool.** "Which server should you install" is downstream of the diagnostic, not its output.
- **NOT a replacement for RAG-MCP, MCP-Zero, or LiveMCPBench.** It complements them by porting Chroma's length-isolation methodology into the tool regime.
- **NOT a paper about whether tool-crowding exists.** It exists; six controlled studies and five production-engineering anchors confirm it. We measure its curve.

## Roadmap

- **v0.1.0-pre-pilot** (current) — methodology + harness + corpus + exploratory probes, no confirmatory numbers yet
- **v0.2.0-pilot** (next; gated on API credits) — pre-registered pilot results + headline chart
- **v0.3.0-v1** (after the pilot) — full sweep across the frontier panel + arXiv preprint draft
- **v1.1.0** (post-launch) — community PR contributions via `tcrun submit`, expanded server pool
- **v2.0.0** (later) — API tasks, browser tasks, mitigation comparison, mechanism study

## Conflict of interest

OpenCodeIntel (OCI) is one of the five primary code-retrieval servers in the pool and is authored by the corresponding author. This is disclosed in [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md) §11. A leave-OCI-out sensitivity analysis is mandatory in the v1 paper.

## Acknowledgments

This work extends, rather than originates, multi-tool interference measurement. Specific prior art we lean on:

- **RAG-MCP** ([Gan & Sun, arXiv 2505.03275](https://arxiv.org/abs/2505.03275)) for N-sweep methodology and the open question of retrieval-side errors at scale
- **LongFuncEval** ([Kate et al., arXiv 2505.10570](https://arxiv.org/abs/2505.10570)) for per-position control as a separate axis from prompt-length
- **MCPVerse** ([arXiv 2508.16260](https://arxiv.org/abs/2508.16260)) for three-condition pool variation with v1-v2 stability red flags
- **LiveMCPBench** ([arXiv 2508.01780](https://arxiv.org/abs/2508.01780)) for the 50% retrieval-side-error finding that motivated our retriever ON/OFF second axis
- **Chroma Context Rot** + **Liu et al.** ([arXiv 2510.05381](https://arxiv.org/abs/2510.05381)) for padded-length controls on text retrieval, which we port here to tools
- **ABC** ([Zhu et al. arXiv 2505.10573](https://arxiv.org/abs/2505.10573)) for the 42-item benchmark discipline checklist this work scores against
- **SWE-bench Pro** ([arXiv 2509.16941](https://arxiv.org/abs/2509.16941)) for failure-mode taxonomy + contamination defense patterns we adopt
- **Anthropic Tool Search Tool** (Nov 2025) for the closed-eval anchor showing production impact (Opus 4 49→74%, Opus 4.5 79.5→88.1%)
- **GitHub Copilot's 40-to-13 tools reduction** (Nov 2025) for the cleanest public production-engineering precedent (+2-5pp on SWE-Lancer + SWE-bench-Verified, -400ms TTFT)

Community qualitative observations on multi-MCP interference (Simon Willison's _Too many MCPs_, Anthropic's _Code Execution with MCP_ engineering blog, Block's Linear MCP restructure, Cursor's 40-tool cap) anchored the project's motivation.

## Support this research

This is a self-funded, open-methodology research project. The harness, design docs, and
exploratory probes are done; the confirmatory runs are gated on Anthropic API credits,
and every run is small, reproducible, and published regardless of outcome (negative
results welcome). The compute asks are deliberately tiny and map to specific deliverables:

| Tier | What it funds | Cost |
| ---- | ------------- | ---- |
| **Minimum real result** | The within-task 2×2 factorial (`configs/stage1-factorial.yaml`, 60 trials at 3 orderings) — turns the directional probe into a confound-clean, position-bias-controlled pilot | **~$20** |
| **Full pre-registered pilot** | The RQ1 count sweep over N ∈ {1, 5, 10, 15, 20}, ≥50 queries × 5 orderings, single model (`design/PILOT_V0.md`) | **~$200** |

Costs are estimated at the measured ~$0.18 (named-target) / ~$0.39 (ambiguous) per-trial
rate from the committed probe data, so they may move with trajectory length. If you want
to fund a specific run, [support it on Ko-fi](https://ko-fi.com/devanshuc) — or open
an issue to collaborate. Sponsored runs are acknowledged in the preprint.

## Citation

If you use this benchmark, methodology, or data, please cite via [CITATION.cff](CITATION.cff) or:

```bibtex
@misc{chicholikar2026toolcrowding,
  title  = {tool-crowding: A pre-registered benchmark for discrimination interference in multi-MCP code retrieval},
  author = {Chicholikar, Devanshu},
  year   = {2026},
  url    = {https://github.com/DevanshuNEU/tool-crowding},
  note   = {Pre-pilot release; preprint and v1 results forthcoming}
}
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pre-registration discipline, negative-results-welcome culture, and the maintainer-disclosure protocol are non-negotiable. Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Security disclosures: [SECURITY.md](SECURITY.md).

## License

Apache 2.0. See [LICENSE](LICENSE).

---

_Pre-pilot status. Confirmatory numbers and the headline chart land after the pre-registered pilot is funded and run._
