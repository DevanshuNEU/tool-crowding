# Server Pool Specification

> Locked 2026-05-20; substantially revised 2026-05-25 PM after strategic reframe. 18-server pool: 5 chart-primaries (reported in the headline per-server MPD chart) + 13 distractors. Verified via Phase 1 enumeration + 5 install-research subagent reports (see `research/install_*_2026-05-25.md`). Excluded servers documented with rationale.

## Chart-primaries (5; headline MPD chart) — locked 2026-05-25 PM

| # | Server | Install | Repo / package | Auth | Reachability | Query-primary fit |
|---|---|---|---|---|---|---|
| 1 | GitHub MCP | Docker | `ghcr.io/github/github-mcp-server` (pinned by digest, see Version pinning below) | GitHub PAT | 2 | direct |
| 2 | DeepWiki | hosted HTTP | `https://mcp.deepwiki.com/mcp` (Cognition Labs Streamable HTTP) | none | 2 (hosted) | direct |
| 3 | Git MCP | PyPI | `mcp-server-git` (Anthropic reference, MIT) | none | 1 | direct |
| 4 | Context7 | npx | `@upstash/context7-mcp` | Upstash API key | 2 | **none** (library docs, not source-code retrieval) |
| 5 | Sentry MCP | npx | `@sentry/mcp-server` | `SENTRY_ACCESS_TOKEN` (org scopes) | 2 | **none** (observability, not source-code retrieval) |

**Chart-vs-query primaries split (locked 2026-05-25)**. All 5 servers above are reported in the headline per-server MPD chart and treated as primaries in MPD computation. **Only servers 1-3 (GitHub MCP, DeepWiki, Git MCP) appear as `primary_server` on any query** in `harness/tasks/v1/queries.jsonl`, because servers 4-5 (Context7, Sentry) have tool surfaces orthogonal to source-code retrieval. The orthogonality is intentional and load-bearing for the composition hypothesis (see `RESEARCH_DESIGN.md §3 "Composition-sensitivity arm"` and `design/PRE_REGISTRATION.md P5`).

**Author disclosure**: OCI (the corresponding author's MCP server) is excluded from chart-primaries and from any `primary_server` cell. It is included only as a distractor in the pool (row 11 below) for ecological-validity reasons. The leave-OCI-out sensitivity analysis (full removal of OCI from the distractor pool) is the COI defense in the paper.

**Rationale for choosing these 5**:
- Officially first-party / canonical reference. GitHub MCP is from GitHub; DeepWiki from Cognition Labs; Git MCP is the Anthropic reference implementation in `modelcontextprotocol/servers`; Context7 from Upstash; Sentry MCP from Sentry. Recognition flywheel: each company plausibly notices a benchmark involving its server.
- Free or low-cost: Sentry has a free tier sufficient for the trial volume; Context7's free tier (1,000 calls/month) may bind during the full sweep — see `decide-context7-paid-tier` in `DevVault/tool-crowding/DEV_TODO.md`; DeepWiki is free + no auth; GitHub MCP is free with a PAT; Git MCP runs offline.
- Reachability ≤ 2 for all 5. Reproducible by external researchers.
- Two of the five (Context7, Sentry) deliberately tool-domain-orthogonal to source-code retrieval; this is the composition-sensitivity arm of the experimental design (not a flaw).

## Distractor pool (13)

| # | Server | Install | Auth | Reachability | Domain-overlap tag |
|---|---|---|---|---|---|
| 6 | Filesystem MCP | npx | none | 1 | code-adjacent |
| 7 | Memory MCP | npx | none | 1 | orthogonal |
| 8 | Sequential Thinking MCP | npx | none | 1 | orthogonal |
| 9 | Time MCP | npx | none | 1 | orthogonal |
| 10 | SQLite MCP | npx | none | 1 | code-adjacent |
| 11 | PostgreSQL MCP | npx | local pg | 2 | code-adjacent |
| 12 | Brave Search MCP | npx | API key (free 100/day) | 2 | orthogonal |
| 13 | Linear MCP | npx | API key | 2 | orthogonal |
| 14 | Notion MCP | npx | OAuth | 2 | orthogonal |
| 15 | Slack MCP | npx | OAuth | 2 | orthogonal |
| 16 | OCI (OpenCodeIntel) | self-hosted | `DevanshuNEU/lco-fork`; none (local) | 1 | code-adjacent (author's MCP; distractor-only per author disclosure) |
| 17 | Aider MCP | npx / pip | `disler/aider-mcp-server` | 1 | code-adjacent |
| 18 | Fetch MCP | PyPI | `mcp-server-fetch` | 1 | code-adjacent (naive web-retrieval baseline) |

## Reachability legend

- **1**: free, no signup, runs offline or via npx with no credentials
- **2**: free with signup or local install (e.g., postgres)
- **3**: paid (excluded from pool)
- **4**: enterprise-only (excluded from pool)

## Domain-overlap legend

- **code-adjacent**: tool descriptions semantically overlap with code-retrieval (file ops, sql query). Hypothesis: these distractors interfere MORE than orthogonal ones because they compete for attention on similar tokens.
- **orthogonal**: tool descriptions semantically distant from code retrieval. Hypothesis: lower interference per unit token.

Both categories are sampled in every distractor set to test the hypothesis (RQ2 sub-analysis).

## Excluded servers (with reason)

| Server | Reason for exclusion |
|---|---|
| Sourcegraph MCP | Reachability 3: requires Cody Enterprise or paid Sourcegraph account |
| Glean MCP | Reachability 4: enterprise-only |
| Cody MCP | Reachability 3: integrated only; requires Cody Free/Pro subscription |
| Perplexity Sonar API MCP | Reachability 3: paid API |
| Exa Search MCP | Reachability 3: paid API |
| HubSpot MCP | Reachability 3: paid HubSpot account |
| Gmail MCP | OAuth setup adds reproducibility friction; equivalent messaging functionality from Slack/Linear/Notion distractors |
| Twilio MCP | Reachability 2 but phone verification adds friction |
| Supabase MCP | Redundant with PostgreSQL MCP |
| Docker MCP | Useful but adds Docker as a hard prerequisite for runners; defer to v2 |
| Continue MCP | Category error: Continue is an MCP client, not a server. Rejected 2026-05-25 from shortlist subagent. |
| Cline MCP | Category error: Cline is an MCP client, not a server. Rejected 2026-05-25 from shortlist subagent. |
| AWS Labs `git-repo-research-mcp-server` | Officially deprecated per its README. Rejected 2026-05-25. |
| Cloudflare MCP (14 servers) | All ops/observability surfaces (Workers, KV, Logpush, Radar, etc.); wrong domain for code retrieval. Rejected 2026-05-25 from shortlist subagent. |

## Version pinning (install state 2026-05-22 Fri PM)

Each server install must be pinned by git SHA or registry version-lock. Per RESEARCH_DESIGN.md Section 3 ("Confounders to control"), server-version drift is a controlled confounder.

**Install location:** `harness/server-pool/` (node_modules for npm, `.venv/` for Python). package.json + requirements file frozen at install time.

**Ecosystem reality check (caught during the 2026-05-22 install):** Half the `@modelcontextprotocol/server-*` namespace was deprecated or removed from npm between the original 2026-05-20 SERVER_POOL.md draft and this install. server-git / server-fetch / server-time / server-sqlite are 404 on npm and live only on PyPI as Python packages. server-github / server-postgres / server-brave-search / server-slack are marked deprecated on npm. The official GitHub MCP migrated to a Go binary distributed as a Docker image (`ghcr.io/github/github-mcp-server`). This is itself a methodology threat to T.6 (frozen environment at release): pinning to deprecated registry entries is not durable. Mitigation: tarball the deprecated npm packages locally + commit hashes into `h_pool` per `REPRODUCIBILITY.md §1`, do not rely on npm reachability for re-runs. The Aug→Feb registry churn already demonstrates how fast this surface shifts.

| Server | Source | Pinned version / digest | Status (2026-05-25 PM) | Notes |
|---|---|---|---|---|
| **GitHub MCP** (chart-primary 1) | Docker `ghcr.io/github/github-mcp-server` | `@sha256:e3816a476a977cfb836e7d221510011436c654d11861db66ecfd826601aba6a4` (re-pinned 2026-05-26 — earlier `fc0318a...` digest was the 2026-05-25 PM pull; current digest is the v1.0.4 image verified via post-fix snapshot 2026-05-27 PM) | PINNED | **11 tools** under `--toolsets=repos --read-only` (down from 40 default) — see "Per-server tool-surface scoping" section below; PAT required (fine-grained scope `repo` read-only + `metadata` read-only is sufficient); spawn via `docker run` per trial for isolation |
| **DeepWiki** (chart-primary 2) | Hosted `https://mcp.deepwiki.com/mcp` | snapshot bundle (initialize handshake + tools/list + representative-query trace dated 2026-05-25 PM) | SNAPSHOT-PINNED | 3 tools (`read_wiki_structure`, `read_wiki_contents`, `ask_question`); no auth; Cognition does not publish API rate limits — 50-call smoke test required pre-pilot per `read-deepwiki-tos` and `decide-context7-paid-tier`-adjacent rate-limit checks |
| **Git MCP** (chart-primary 3) | PyPI `mcp-server-git` | 2026.1.14 (Anthropic reference; MIT; date-tagged monthly CalVer cadence; latest pre-cutoff) | PINNED | 12 tools; local stdio; no auth |
| **Context7** (chart-primary 4) | npx `@upstash/context7-mcp` | `@2.3.0` (NOT 3.0.0 — that release flipped to stateful Redis architecture that contaminates per-trial isolation) | PINNED | 2 tools (`resolve-library-id`, `query-docs`); Upstash API key; free tier 1,000 calls/month may bind during full sweep |
| **Sentry MCP** (chart-primary 5) | npx `@sentry/mcp-server` | `@0.29.0` (published 2026-01-26; FSL-1.1-Apache-2.0; permits non-commercial research) | PINNED | 19 read-only tools after filtering the 5 mutation tools at MCP-client level; `SENTRY_ACCESS_TOKEN` with org-level scopes (`org:read`, `project:read`, `project:write`, `team:read`, `team:write`, `event:write`); lock `EMBEDDED_AGENT_PROVIDER` env var so the search/Seer tools stay enabled across machines |
| Filesystem MCP | npm `@modelcontextprotocol/server-filesystem` | 2026.1.14 | INSTALLED | node_modules path verified |
| Memory MCP | npm `@modelcontextprotocol/server-memory` | 2026.1.26 | INSTALLED | node_modules path verified |
| Sequential Thinking MCP | npm `@modelcontextprotocol/server-sequential-thinking` | 2025.12.18 | INSTALLED | node_modules path verified |
| Time MCP | PyPI `mcp-server-time` | 2026.1.26 | INSTALLED | venv `.venv/bin/mcp-server-time` reachable |
| SQLite MCP | PyPI `mcp-server-sqlite` | 2025.4.25 | INSTALLED | venv `.venv/bin/mcp-server-sqlite` reachable |
| PostgreSQL MCP | npm `@modelcontextprotocol/server-postgres` (deprecated) | 0.6.2 (last published) | PEND | Tarball locally; runs against a Docker pg instance (per global "Docker only for services" rule) |
| Brave Search MCP | npm `@modelcontextprotocol/server-brave-search` (deprecated) | 0.6.2 (last published) | PEND | Tarball locally; needs Brave API key (free 100/day) |
| Linear MCP | hosted OR `@tacticlaunch/mcp-linear` | TBD | PEND | OAuth required; verify reproducibility implications |
| Notion MCP | npm `@notionhq/notion-mcp-server` (verify) | TBD | PEND | OAuth required |
| Slack MCP | npm `@modelcontextprotocol/server-slack` (deprecated) | 2025.4.25 (last published) | PEND | Tarball locally; OAuth required |
| OCI (distractor-only) | self-hosted git fork | TBD (head of `DevanshuNEU/lco-fork` as-of audit date) | PEND | Distractor-only role per author disclosure; not in any `primary_server` cell |
| Aider MCP | github `disler/aider-mcp-server` (PyPI not surfaced) | TBD | PEND | Independent repo; needs Aider runtime; pin SHA at install |
| Fetch MCP | PyPI `mcp-server-fetch` | 2025.4.7 | INSTALLED | venv `.venv/bin/mcp-server-fetch` reachable |

**Coverage as of 2026-05-25 PM**: 5 of 5 chart-primaries pinned (newly captured this session); 6 of 13 distractors installed/pinned; 7 distractors pending (PostgreSQL, Brave, Linear, Notion, Slack with credential/deprecation friction, plus OCI and Aider with separate pinning workflows). Track-2-server-pool-pinning (in DEV_TODO) drives the remaining 7 to PINNED.

## Per-server tool-surface scoping (locked 2026-05-27 PM)

A server's natural-out-of-box tool count is a property, not a constraint. Two of the five chart-primaries are now scoped at launch time to a deliberately chosen subset of their default surface, captured per-server via a `server_args` yaml field threaded through `tcrun/servers.py::stdio_params_for`. The scoping participates in `run_id` via the `pool/descriptions.json` content hash, so a scoped run and an unscoped run are by construction different experimental configurations.

**Rationale (three independent reasons):**

1. **Cost empiricism (decisive).** First live N=1 trial against unscoped github_mcp (38 tools) on Sonnet 4.6 cost $0.89 (input 284,871 tokens, output 2,388). The pre-registered PILOT_V0 budget (line 80-85) assumed ~$0.05/trial. Empirically the 224-trial pilot is ~$200; the v1 1,400-trial sweep is ~$1,200. Tool-listing tokens scale with both N (servers) AND within-server tool count, so the multiplicative axis hits worst at high N. Scoping the dominant primary cuts the per-trial token volume substantially. The post-scope per-trial cost is captured in the methodology fit-check at the bottom of `DevVault/tool-crowding/sessions/latest.md`.

2. **Ecological validity (already cited in FOUNDATION.md).** GitHub Copilot publicly reduced its default toolset 40→13 in Nov 2025 for +2-5pp on SWE-Lancer and SWE-bench-Verified (FOUNDATION.md §1.1). Cursor caps installed-tool count at 40. Real-user deployments scope; benchmarks at OOTB-default measure something users do not actually run. Our scoped configuration of `github_mcp` to 11 read-only `repos` tools is closer to what a user actually exposes via their `.cursor/mcp.json` or Copilot config than the un-tweaked 38-tool surface is.

3. **Existing precedent in this same doc.** Sentry MCP (chart-primary 5, line 90 of the version-pinning table) is already documented as "19 read-only tools after filtering the 5 mutation tools at MCP-client level." Per-server tool-surface filtering is established methodology; the github_mcp scoping extends the precedent to a new server via a different mechanism (CLI launch flag vs MCP-client-side filter).

**Decision matrix (per chart-primary):**

| Server | Default tools | Scoping mechanism | Scoped tools | Justification |
|---|---|---|---|---|
| github_mcp | 38 | `server_args: ["stdio", "--toolsets=repos", "--read-only"]` (CLI flag, captured in `servers_pinned.yaml`) | 11 | `repos` toolset covers every code-retrieval query in `tasks/v1/queries.jsonl`; read-only matches PAT scope (defense-in-depth) and our queries' actual needs |
| deepwiki | 3 | no scoping (server already small) | 3 | natural-fit; nothing to scope |
| git_mcp | 12 | no scoping (no CLI scope flags) | 12 | mcp/git docker image exposes the full git toolset; all 12 are read-or-local and appropriate for our queries |
| context7 | 2 | no scoping (already minimal) | 2 | natural-fit |
| sentry_mcp | 24 | MCP-client-level filter to 19 (documented row 90) | 19 | pre-existing decision; mutation tools filtered for reproducibility + zero side-effect risk |

**Distractor pool:** un-scoped (default surfaces). The chart-primary scoping is methodology-relevant because chart-primaries appear in per-server MPD; distractors are sampled for crowding effects in aggregate. Scoping distractors would mute the very interference we're measuring.

**Reproducibility.** The yaml `server_args` field content-hashes through `descriptions.json` into `run_id`. Changing scope → different `run_id` → different experiment. The pre-scope github_mcp configuration is recoverable from git history at `harness/tcrun/servers_pinned.yaml` (prior to the 2026-05-27 PM commit). A sensitivity analysis re-running at 38-tool github_mcp can be done as a paper-appendix robustness check if reviewers ask, at marginal additional cost (the methodology supports it; no design changes required).

**Kill criterion (new, applies to scoped configuration only):** if any post-scope smoke shows the agent can no longer solve a representative public-tier query that was solvable un-scoped (i.e., scoping was too aggressive and removed a load-bearing tool), the scope was wrong. Open `pylint visit_call` query as the canonical reference: scoped github_mcp must retain `search_code` + `get_file_contents` at minimum.

## Installation smoke tests (TBD Thu 2026-05-22)

Each server must pass before being included in trials:

1. Installable from a fresh Claude Desktop environment in < 5 minutes
2. Returns valid tool list within 30 seconds of MCP handshake
3. Successfully completes one trivial tool call (e.g., GitHub MCP can list a single public repo's files; Filesystem MCP can read a sandbox file)

Smoke test results: `design/SMOKE_TESTS.md` (TBD).

## Tool-count and description-token-length measurements (TBD Thu 2026-05-22)

Per RESEARCH_DESIGN.md Section 3, these are controlled covariates:

| Server | Tool count | Total description tokens | Avg tokens per tool |
|---|---|---|---|
| TBD | TBD | TBD | TBD |

Fill via a one-off harness script that connects to each server, dumps tool schemas, and tokenizes via the model's tokenizer.

## Related

- `[[../RESEARCH_DESIGN]]` — full design context (Section 3 server pool)
- `[[../CLAUDE]]` — project operating manual
- `[[REPRODUCIBILITY]]` — 7-artifact identity chain that consumes the pinning table
