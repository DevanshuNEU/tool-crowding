# tcrun

The Python package that runs tool-crowding experiments. The full project README, design docs, and methodology live in the [project root](../README.md).

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,analysis]"
.venv/bin/python -m pytest tests/   # 116 passing as of v0.1.0-pre-pilot
```

## Commands

```bash
tcrun run --config configs/pilot_v1.yaml      # run a sweep
tcrun resume <run_id>                          # resume a crashed run
tcrun status <run_id>                          # per-cell completion report
tcrun verify <run_id>                          # re-run 5 random trials + schema check
tcrun runid --config configs/pilot_v1.yaml    # compute run_id without executing
tcrun reproduce <trial_id>                     # single-trial replay
tcrun validate --config configs/pilot_v1.yaml # validate config without API calls
```

## Layout

```
harness/
├── tcrun/                  # the Python package (12 modules)
│   ├── config.py           # PATH_FIELDS run_id derivation
│   ├── seed.py             # cell + trial + padding seeds
│   ├── results.py          # Trial schema v1.1 + JSONL writer
│   ├── env.py              # EnvFingerprint capture
│   ├── retry.py            # tenacity-backed bounded retry
│   ├── tasks.py            # TaskLoader for queries.jsonl
│   ├── padding.py          # padded-N=1 filler selection
│   ├── servers.py          # ServerPoolManager (hermetic per cell)
│   ├── agent.py            # Anthropic API + MCP tool-use loop
│   ├── orchestrator.py     # cell loop + checkpoint + cost monitor
│   ├── preflight.py        # 7-artifact verification gate
│   ├── cli.py              # Typer CLI entry point
│   └── oracles/
│       └── pass_v1.py      # symbol-match + 50% token-overlap (RESEARCH_DESIGN §4)
├── tests/                  # pytest suite (116 cases)
├── tasks/v1/               # query set (release pending v0.2.0-pilot)
├── pool/                   # fake-tool corpus generator
├── configs/                # YAML sweep configs
└── SPEC.md                 # engineering spec with DDIA principle-transfer audit
```

## Identity chain

Every run produces a content-addressed `run_id` from the resolved Config plus SHA-256 of each path-typed artifact. See [`design/REPRODUCIBILITY.md`](../design/REPRODUCIBILITY.md) §1 for the 7-artifact chain.

## License

Apache 2.0. See [LICENSE](../LICENSE).
