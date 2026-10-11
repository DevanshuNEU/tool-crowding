# Gate data: the no-MCP floor (2026-06-11 UTC)

Raw per-trial records for the pre-registered no-MCP floor gate in [`design/PRE_REGISTRATION.md`](../../../design/PRE_REGISTRATION.md) (Phase F: the no-MCP baseline runs once per query as the uncontaminated floor and must hold before any confirmatory Stage-1 spend). Summarised in [`RESULTS.md`](../../../RESULTS.md).

Like `../probe_data/`, these are an exception to the FAIR policy that keeps `results/` gitignored: they are committed so the gate outcome can be checked from a clean clone at $0. They are append-only.

## Runs

| directory | config | run_id (prefix) | trials | spend |
|---|---|---|---|---|
| `smoke-no-mcp` | `harness/configs/smoke-no-mcp.yaml` | `29b3ddd0` | 2 | $0.21 |
| `floor-stage1-nomcp` | `harness/configs/floor-stage1-nomcp.yaml` | `56bd3276` | 10 | $1.50 |

Both: Claude Sonnet 4.6, temperature 1.0 (the Stage-1 sampling), retriever off, `github_mcp` as the only server in the grounded arm. `tcrun validate -c <config>` on the committed config and task file reports `run_id_match` for both.

## Edits

Two `error_detail` strings in `floor-stage1-nomcp/trials.jsonl` carried the Anthropic organization id inside a rate-limit message; it is replaced with `[redacted]`. Nothing else was changed. SHA-256 of the original files:

- `floor-stage1-nomcp/trials.jsonl`: `664802b203056b80eba8f0b4af299a86205ee34681474a3e0bbe82298d3ce9cc`
- `smoke-no-mcp/trials.jsonl`: `b5b5c11bffe7703cb57e45922d83d3dd074757f758e3d54781bfb57da7a8b766`

Traces (`traces/`) are not committed.
