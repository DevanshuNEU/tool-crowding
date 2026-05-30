# Tool-result character cap

> Status: binding methodology note. Added 2026-05-29 after the github-smoke
> diagnosis. Governs how much of a single tool result the agent sees.

## The bug this addresses

`tcrun/agent.py::_dispatch_tool_call` truncated every tool result to a
hard-coded **4,096 characters** before forwarding it to the model
(`truncated = payload[:4096]`). In the github-only smoke (`v1-pub-001`,
target file `pylint/checkers/refactoring/implicit_booleaness_checker.py`,
16,895 chars), the answer method `def visit_call` sits at **character offset
4,417** — *behind* the cap. The agent therefore never saw the answer no
matter how many times it re-fetched the file, perceived the file as
"truncated," looped through alternate retrieval paths (`get_commit`,
`search_code`, SHA/pagination attempts), and exhausted `max_turns=16` →
`agent_gave_up` on every trial. Measured directly via a zero-API MCP probe
(2026-05-29): `get_file_contents` returns the full file as an
`EmbeddedResource`; the loss was entirely the harness-side 4,096 cap (the
EmbeddedResource-unwrap fix in `_flatten_tool_result` was a necessary
predecessor — without it the model saw only a "successfully downloaded
(SHA …)" metadata line).

**Why this is methodology-critical, not cosmetic:** a cap that clips the
answer makes a trial fail for reasons unrelated to tool discrimination under
crowding. Left unfixed it would confound the entire benchmark — every task
whose answer falls past the cap fails regardless of N.

## The decision

The cap is now a **configurable, runtime-swappable, value-hashed** parameter,
mirroring the `TC_EMBEDDER` precedent (locked 2026-05-25):

- `Config.tool_result_char_cap: int` (non-path field → value-hashed into
  `run_id` by `compute_run_id`).
- Runtime override via the `TC_TOOL_RESULT_CHAR_CAP` env var (resolved in
  `load_config`), so a cap sweep is one `export` away and never requires
  editing a committed config.
- Because the *resolved* Config is hashed, every cap value produces a
  distinct `run_id` — a cap sweep is reproducibility-honest by construction.

### Default: 65,536 chars (~16k tokens)

Chosen from the measurable evidence on hand:

- Largest known target source file = 16,895 chars (the smoke file). 64 KiB
  gives ~3.9× headroom.
- v1 ground-truth *snippets* max at 3,827 chars, but the agent reads the whole
  source file, so the snippet size is not the binding constraint — the source
  file is.
- ~16k tokens per result bounds context growth so a single large retrieved
  file cannot, on its own, push a trial past the ~180k-token threshold that
  would trigger **kill criterion #2 (context overflow)** as a competing
  explanation for any degradation.

### Open validation tasks (before the science run)

1. **Validate the default against the realized v1 source-file size
   distribution.** v1 tasks record `source_repo` but not the target file path
   (path discovery is part of the task), so the per-file sizes were not
   measurable at decision time. Once the v1 target files are pinned, confirm
   the 95th-percentile source-file size fits under the default; raise the
   default if not.
2. **Cap sensitivity analysis (mandatory in the paper).** Sweep
   `tool_result_char_cap ∈ {8k, 16k, 32k, 64k}` via `TC_TOOL_RESULT_CHAR_CAP`
   and show the per-server MPD / degradation curve is stable across caps. This
   is the reviewer-facing proof that the result cap does not drive the
   findings. Interacts with N: at high N the agent may issue several large
   reads, so report total-context distributions per (N, cap) cell to keep
   kill-criterion-2 separable.

## Reproducibility note

Adding `tool_result_char_cap` to `Config` changes the canonical hashed JSON,
so **all `run_id`s shift** relative to pre-2026-05-29 runs. This is intended:
the cap is a reproducibility-relevant parameter. Archived pre-fix runs
(`results/github-smoke-001/_archived_*`) predate the parameter and are not
comparable by `run_id`.
