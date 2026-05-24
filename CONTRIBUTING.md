# Contributing to tool-crowding

Thank you for considering a contribution. tool-crowding is a pre-registered, open-methodology benchmark. The contribution norms below exist to keep it that way.

## Table of contents

- [Spirit of contributions](#spirit-of-contributions)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Adding a server to the pool](#adding-a-server-to-the-pool)
- [Submitting a result or replication](#submitting-a-result-or-replication)
- [Reporting a bug in the harness](#reporting-a-bug-in-the-harness)
- [Proposing a methodology change](#proposing-a-methodology-change)
- [Code standards](#code-standards)
- [Commit and PR conventions](#commit-and-pr-conventions)

## Spirit of contributions

Three commitments make this benchmark worth the effort. Contributions that violate them will be rejected, however polished the code.

1. **Pre-registration discipline.** Predictions are locked before data. If a change touches `design/PRE_REGISTRATION.md`, the linked predictions or thresholds, or the four scenario abstracts, the PR must include an explicit pre-registration update with a date, a justification, and a confirmation that no pilot data has been peeked at to motivate the change.
2. **Negative results are first-class.** A replication that contradicts our findings is more welcome than one that confirms them. If your run lands a kill criterion (per `design/FOUNDATION.md` §3), open an issue with the data, not silence.
3. **Honest scope.** Do not over-claim. If a contribution adds capability, the PR description states the falsification condition that would prove the capability does not work.

If you are unsure whether something fits, open a discussion before a PR.

## Ways to contribute

- Replicate the headline N-curve on a different host, model, or hardware
- Add a server to the public pool (subject to the disclosure rules below)
- Report a maintainer-disclosure for a server in the pool (use the dedicated issue template)
- File a bug in `tcrun` or in `oracles/pass_v1.py`
- Propose a methodology extension (new task, new metric, new mitigation arm) for v2
- Improve documentation, tests, or developer ergonomics
- Translate the README or design docs

## Development setup

Requires Python 3.11 or later.

```bash
git clone https://github.com/DevanshuNEU/tool-crowding
cd tool-crowding/harness
python -m venv .venv
.venv/bin/pip install -e ".[dev,analysis]"
.venv/bin/python -m pytest tests/   # should report 116 passing
```

We use `ruff` for lint, `pyright` for type checking, and `pytest` for tests. Install the pre-commit hooks for an automatic local check:

```bash
.venv/bin/pip install pre-commit
.venv/bin/pre-commit install
```

## Adding a server to the pool

The 15-server pool is documented in `design/SERVER_POOL.md`. Adding a server is a methodology change and requires a PR with:

1. The server entry in `harness/tcrun/servers_pinned.yaml` with a populated `git_sha`, `npm_lock_hash`, `docker_digest`, or `tarball_sha256`. Sentinel `TBD` values are not accepted in main.
2. A `reachability` rating (per `design/SERVER_POOL.md` legend) and a documented domain-overlap tag.
3. A smoke test that the server returns a valid tool list within 30 seconds of MCP handshake.
4. A conflict-of-interest disclosure if you are a maintainer of the server or have a financial interest in its adoption.
5. If the server is paywalled or reachability rated higher than 2, an explicit justification for inclusion.

We will run the smoke test and verify the SHA chains before merging.

## Submitting a result or replication

If you ran `tcrun` against your own environment and want to contribute the result:

1. Run `tcrun verify <run_id>` first and confirm the schema check passes.
2. Open an issue using the "Replication result" template (forthcoming) and attach the `results/<run_id>/summary.json` and the run config.
3. State what scenario (per `design/PRE_REGISTRATION.md`) your run lands in, and whether it agrees or disagrees with the headline.

Disagreement is more useful than agreement. Do not silently drop disagreements.

## Reporting a bug in the harness

Use the "Bug report" issue template. Include:

- The `run_id` and `trial_id` if applicable
- The environment fingerprint from `results/<run_id>/summary.json` (we use `tcrun.env.capture_run_summary`)
- A minimal reproduction or, if not possible, the logs from `results/<run_id>/trials.jsonl`
- Your hypothesis about the cause

We treat halt-the-run errors (F1, F4, F18 in `harness/SPEC.md` §7) as priority bugs.

## Proposing a methodology change

Methodology changes are deferred to v2 unless they fix an outright defect in v1. Open a discussion before a PR. Include:

- The falsification condition the proposed change is intended to address
- Whether the change interacts with the pre-registered predictions or scenario abstracts
- A literature reference if the proposed change adapts a method from another field

If the change is post-hoc (motivated by pilot data we have not yet released), say so explicitly.

## Code standards

- Python 3.11+
- pydantic v2 for all data schemas; no dictionary-typed boundary contracts
- Type hints everywhere; `pyright` strict mode targets are documented in `pyproject.toml`
- `ruff` is the linter; no warnings on merge to main
- All trial-level data writes use append-only JSONL with explicit `schema_version`
- Tests for new behavior; we are at 116 pytest cases as of the pre-pilot drop and want that to grow
- Module docstrings cite the `harness/SPEC.md` section they implement

## Commit and PR conventions

- Commit message subject is imperative present tense; under 70 characters
- Body explains the why, not the what
- Reference the issue or design doc section the commit closes or implements
- Squash before merge unless the PR is genuinely multi-commit
- Pull request descriptions follow the `.github/PULL_REQUEST_TEMPLATE.md` checklist

If you found a real bug, write the test first.

## Communication

GitHub Issues for bugs, replications, and disclosures. GitHub Discussions for methodology proposals and open questions. Direct contact for embargo-period coordination: see the maintainer-disclosure issue template.

## Code of Conduct

This project adheres to the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0 (see `LICENSE`).
