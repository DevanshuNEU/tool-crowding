# tool-crowding — Project Operating Manual

> **Last session context:** read `sessions/latest.md` before starting new work in this folder.

> Auto-loads when Claude works in `DevVault/tool-crowding/`. The locked research design is `RESEARCH_DESIGN.md`. Read it before suggesting any change.

## Status (as of 2026-05-20)

- **Phase 1 (research design):** LOCKED. See RESEARCH_DESIGN.md.
- **Phase 2 (paper reading):** scheduled Wed 2026-05-21 (per strategy daily file).
- **Phase 3 (harness build):** Thu-Sat 2026-05-22 to 24.
- **Phase 4 (MVE 1,400 trials):** Sat-Sun.
- **Phase 5 (public launch):** Sun 2026-05-25.
- **Phase 6 (arXiv preprint draft):** Weeks 4-6 of the strategy sprint.
- **Phase 7 (workshop submission):** Aug-Sep 2026 deadlines.

## The locked thesis (one paragraph)

Real users install 10-20 MCP servers simultaneously. Existing benchmarks use a fixed pool. `tool-crowding` varies N (number of installed servers) as a continuous independent variable and measures pass@1 degradation, marginal token cost, and per-server Marginal Performance Delta (MPD) on a held-constant code-retrieval task. Output: public reproducible harness + arXiv preprint + workshop submission.

## Hard rules

- NEVER start harness code without first reading the 5 must-read papers (per `../strategy/week-1/2026-05-21.md`).
- NEVER run trials without a committed `design/PRE_REGISTRATION.md`.
- NEVER publish results without 7-day pre-disclosure to maintainers (Section 11 of RESEARCH_DESIGN.md).
- NEVER call this project `mcp-bench` (Accenture owns the name).
- NEVER skip the padded-N=1 control (it rules out long-prompt degradation).
- COI disclosure: OCI is authored by the corresponding author. "Leave-OCI-out" sensitivity analysis is mandatory in the paper.
- Rename `Interference Score` → `Marginal Performance Delta (MPD)` consistently. Causal-sounding terminology is banned.

## Kill criteria (re-check before any phase transition)

1. Flat curve: pass@1 differs by < ±3pp across N ∈ {1, 5, 10}.
2. Pure context-overflow explanation (drop only at tokens > 180k on Sonnet 4.6's 200k).
3. Pure long-prompt degradation (padded-N=1 == unpadded-N=20).
4. Non-stable per-server MPD (Spearman ρ < 0.3 across re-runs).
5. Scoop (concurrent publication with same scope).
6. Unfixable contamination.

If any kill criterion fires: stop. Document. Pivot or shelve. Do not push through.

## Where things live

- `RESEARCH_DESIGN.md` — the locked 11-section design (canonical source)
- `design/SERVER_POOL.md` — per-server install + reachability + version pinning
- `design/METHODOLOGY.md` — public methodology doc (TBD; pre-publish before results)
- `design/PRE_REGISTRATION.md` — committed before MVE runs (TBD Thu 2026-05-22)
- `notes/` — paper reading notes (filled Wed 2026-05-21)
- `harness/` — code; eventually mirrored to `github.com/DevanshuNEU/tool-crowding`
- `data/` — per-trial logs, results.json (PII-stripped)
- `figures/` — N curves, Pareto plot
- `paper/` — arXiv preprint + workshop submission drafts

## Open [VERIFY] items (resolve Wed 2026-05-21 reading day)

- `[VERIFY-LIVEMCPBENCH]`: read arXiv 2508.01780 in full; confirm whether they sweep N as an IV; update novelty claim accordingly.
- `[VERIFY-RAGMCP-100]`: read arXiv 2505.03275 in full; confirm whether "fails above 100" is in the paper text or only in third-party coverage.

## Related

- `[[../strategy/week-1/2026-05-20]]` — pivot record
- `[[../strategy/week-1/2026-05-21]]` — Wed reading day
- `[[../strategy/personas.md]]` — 4 mentor voices
- `[[RESEARCH_DESIGN]]` — canonical design
- `[[design/SERVER_POOL]]` — server pool spec
- `~/.claude/projects/.../memory/project_tool_crowding.md` — global memory entry
