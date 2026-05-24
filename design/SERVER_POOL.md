# Server Pool Specification

> Locked 2026-05-20. 15-server pool: 5 primary code-retrieval + 10 distractors. Verified via Phase 1 enumeration. Excluded servers documented with rationale.

## Primary code-retrieval servers (5)

| # | Server | Install | Repo / package | Auth | Reachability |
|---|---|---|---|---|---|
| 1 | OCI (OpenCodeIntel) | self-hosted | `DevanshuNEU/lco-fork` | none (local) | 1 |
| 2 | GitHub MCP | npx | `@modelcontextprotocol/server-github` | OAuth (PAT) | 2 |
| 3 | Git MCP | npx | `@modelcontextprotocol/server-git` | none | 1 |
| 4 | Aider MCP | npx / pip | `disler/aider-mcp-server` | none | 1 |
| 5 | Fetch MCP | npx | `@modelcontextprotocol/server-fetch` | none | 1 |

**COI disclosure**: OCI is authored by the corresponding author. Leave-OCI-out sensitivity analysis is mandatory in the paper. Rationale for inclusion: OCI is the hosted MCP under test in the case study; excluding it would defeat the purpose of evaluating production code-retrieval servers head-to-head.

**Rationale for choosing these 5**:
- Free or self-hosted: paywalled options (Sourcegraph, Glean, Cody) excluded for reproducibility.
- Category coverage: OCI (hybrid AST+BM25+Cohere), GitHub (remote search), Git (local grep/log), Aider (code-agent integration), Fetch (naive web-retrieval baseline). These span the realistic competitive set.
- Reachability ≤ 2: every server installable in a fresh Claude Desktop environment within 5 minutes, no enterprise gate.

## Distractor pool (10)

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

## Version pinning (install state 2026-05-22 Fri PM)

Each server install must be pinned by git SHA or registry version-lock. Per RESEARCH_DESIGN.md Section 3 ("Confounders to control"), server-version drift is a controlled confounder.

**Install location:** `harness/server-pool/` (node_modules for npm, `.venv/` for Python). package.json + requirements file frozen at install time.

**Ecosystem reality check (caught during the 2026-05-22 install):** Half the `@modelcontextprotocol/server-*` namespace was deprecated or removed from npm between the original 2026-05-20 SERVER_POOL.md draft and this install. server-git / server-fetch / server-time / server-sqlite are 404 on npm and live only on PyPI as Python packages. server-github / server-postgres / server-brave-search / server-slack are marked deprecated on npm. The official GitHub MCP migrated to a Go binary distributed as a Docker image (`ghcr.io/github/github-mcp-server`). This is itself a methodology threat to T.6 (frozen environment at release): pinning to deprecated registry entries is not durable. Mitigation: tarball the deprecated npm packages locally + commit hashes into `h_pool` per `REPRODUCIBILITY.md §1`, do not rely on npm reachability for re-runs. The Aug→Feb registry churn already demonstrates how fast this surface shifts.

| Server | Source | Pinned version | Status (2026-05-22 Fri PM) | Notes |
|---|---|---|---|---|
| OCI | self-hosted git fork | TBD (head of `DevanshuNEU/lco-fork`) | PEND | Pin SHA when fork's pilot branch lands |
| GitHub MCP | Docker `ghcr.io/github/github-mcp-server` | TBD | PEND | npm package deprecated 2025; official replacement is the Go binary in Docker. Needs PAT for non-public reads. |
| Git MCP | PyPI `mcp-server-git` | 2026.1.14 | INSTALLED | venv `.venv/bin/mcp-server-git` reachable |
| Aider MCP | github `disler/aider-mcp-server` (PyPI not surfaced) | TBD | PEND | Independent repo; needs Aider runtime; pin SHA at install |
| Fetch MCP | PyPI `mcp-server-fetch` | 2025.4.7 | INSTALLED | venv `.venv/bin/mcp-server-fetch` reachable |
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

**Coverage as of 2026-05-22 Fri PM:** 8 of 15 servers installed and pinned (4 npm: filesystem, memory, sequential-thinking + 1 reference server "everything" not in matrix; 4 PyPI: git, fetch, time, sqlite). Remaining 7 break into: 1 self-hosted (OCI), 1 independent repo (Aider), 1 Docker swap (GitHub MCP), 4 with credential / API-key friction (PostgreSQL, Brave, Linear, Notion, Slack — overlap because Slack needs both deprecation handling and OAuth). Bonus "everything" reference server (npm `@modelcontextprotocol/server-everything` 2026.1.26) added to the install for smoke-testing the harness's MCP client; not in the experimental matrix.

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
