# tool-crowding

> Multi-MCP discrimination interference benchmark for code-retrieval tasks. Pre-registered, reproducible, open methodology.

**Status (2026-05-23):** Pre-pilot. Harness scaffold complete, methodology locked, fake-tool corpus shipped. The 144-trial pre-registered pilot runs Mon 2026-05-26. Public launch with results: Wed 2026-05-27.

## What this measures

When you install multiple MCP servers concurrently, does the agent's tool-selection accuracy degrade? If so:

1. Does the degradation come from prompt-length capacity, or from genuine discrimination interference among semantically-overlapping tool descriptions? (`padded-N=1` control answers this.)
2. Which specific servers contribute most to the degradation? (per-server Marginal Performance Delta answers this.)
3. Does a retriever (top-k=5) close the gap, or does it just trade one failure mode for another? (retriever ON/OFF axis answers this.)

The 6-condition intersection the design fills: code-retrieval task × frontier-model panel × padded-N=1 length control × per-server MPD × pinned-version reproducibility × retriever ON/OFF.

## Quickstart (post-pilot)

```bash
# requires Python 3.11+
git clone https://github.com/DevanshuNEU/tool-crowding
cd tool-crowding/harness
python -m venv .venv && .venv/bin/pip install -e ".[dev,analysis]"
.venv/bin/python -m pytest tests/   # 116 tests, ~2s
```

Running a sweep against the Anthropic API requires `ANTHROPIC_API_KEY` and the pinned server pool. See `harness/SPEC.md` for the full CLI and `design/REPRODUCIBILITY.md` for the 7-artifact identity chain.

## Design

The locked methodology lives in:

- [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md) — canonical 11-section design + reviewer-2 dialectic
- [`design/FOUNDATION.md`](design/FOUNDATION.md) — binding construct definition + ABC checklist score
- [`design/PRE_REGISTRATION.md`](design/PRE_REGISTRATION.md) — four scenario abstracts pre-locked before data
- [`design/PADDING_STRATEGY.md`](design/PADDING_STRATEGY.md) — the load-bearing F1 falsification arm
- [`design/QUERY_SET_HYGIENE.md`](design/QUERY_SET_HYGIENE.md) — six layered contamination defenses
- [`design/REPRODUCIBILITY.md`](design/REPRODUCIBILITY.md) — the 7-artifact content-addressed identity chain
- [`design/SERVER_POOL.md`](design/SERVER_POOL.md) — 15-server pool with reachability + pinning
- [`design/ADVERSARIAL_AUDIT.md`](design/ADVERSARIAL_AUDIT.md) — "how would I game this?"
- [`design/CHART_LAYOUT.md`](design/CHART_LAYOUT.md) — the killer chart spec
- [`design/PILOT_V0.md`](design/PILOT_V0.md) — the 224-trial Saturday pilot scope
- [`harness/SPEC.md`](harness/SPEC.md) — engineering spec with DDIA principle-transfer audit

## Citation

```bibtex
@misc{chicholikar2026toolcrowding,
  title  = {tool-crowding: A pre-registered benchmark for discrimination interference in multi-MCP code retrieval},
  author = {Chicholikar, Devanshu},
  year   = {2026},
  note   = {Pre-pilot; preprint and v1 results forthcoming}
}
```

## Conflict of interest

OCI (OpenCodeIntel) is one of the five primary code-retrieval servers in the pool and is authored by the corresponding author. This is disclosed in `RESEARCH_DESIGN.md §11`. A leave-OCI-out sensitivity analysis is mandatory in the v1 paper.

## License

Apache 2.0. See [LICENSE](LICENSE).
