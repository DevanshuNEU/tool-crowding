# tool-crowding analysis

Jupyter-notebook-driven analysis of `results/<run_id>/results.jsonl` per harness/SPEC.md §6.

## Layout

```
analysis/
├── README.md                    this file
├── dashboard.ipynb              main notebook (TBD): load + N curves + Pareto + MPD + failure modes + padded-N=1 sanity
├── readers/
│   └── v1.py                    schema_version=1.* reader (TBD; frozen the day the first MVE result lands)
├── pareto.py                    Pareto frontier computation (TBD; per RESEARCH_DESIGN.md §5)
├── mpd.py                       Marginal Performance Delta (TBD; per RESEARCH_DESIGN.md §4 operational definition)
└── external_validity.ipynb      RAG-MCP replication analysis (TBD; per RESEARCH_DESIGN.md §3 RAG-MCP cell)
```

## Sat AM work

1. Implement `readers/v1.py` per harness/SPEC.md §4 schema evolution rules. Frozen the day the first MVE result lands.
2. Implement `pareto.py` per RESEARCH_DESIGN.md §5 (upper-left envelope of (input-tokens, pass@1) cloud at N=10; bootstrap CIs).
3. Implement `mpd.py` per RESEARCH_DESIGN.md §4 MPD operational definition (paired bootstrap over query × ordering pairs, B=10,000).
4. Build `dashboard.ipynb` scaffolding with the 6 cells listed in harness/SPEC.md §6.

## Cells in dashboard.ipynb (per SPEC.md §6)

1. Load + filter by schema_version
2. N curves per primary server (figure 1)
3. Pareto frontier (figure 2)
4. MPD table (table 1)
5. Failure-mode breakdown (table 2; FOUNDATION.md §4.5 taxonomy + tool-crowding additions)
6. Padded-N=1 control comparison (figure 3, sanity check)

## Status

All TBD. Scaffolding only as of 2026-05-22 Fri PM. Implementation Sun 2026-05-24 after pilot results land.
