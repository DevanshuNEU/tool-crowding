# Security Policy

tool-crowding is a research benchmark, not a production service. The security surface is narrower than a typical application, but real:

- **Pinned npm tarballs.** Deprecated MCP server packages are preserved as local tarballs with SHA-256 hashes committed in `harness/tcrun/servers_pinned.yaml`. A tampered tarball or a hash mismatch is a security event; please disclose.
- **API key handling.** Users supply their own `ANTHROPIC_API_KEY` (and other provider keys) via environment variables. The harness logs trial-level audit records to `results/<run_id>/trials.jsonl` and does NOT log API keys. Verify the logs in your environment if you have concerns.
- **Oracle code.** `harness/tcrun/oracles/pass_v1.py` runs against agent-returned snippets. A maliciously crafted snippet could in principle exploit a vulnerability here. Report any.
- **Subprocess management.** `harness/tcrun/servers.py` spawns MCP server subprocesses via stdio. Sandboxing the subprocess tree is the user's responsibility in untrusted environments.
- **Benchmark gameability.** Documented separately in `design/ADVERSARIAL_AUDIT.md`. Six attack vectors with detection criteria. Gameability disclosures should use the maintainer-disclosure issue template, not the security channel below, because they are scientific corrections, not exploits.

## Reporting a vulnerability

For security-sensitive issues that should NOT be disclosed publicly:

**Email:** chicholkar.d@northeastern.edu
**Subject line:** `[tool-crowding security] <one-line summary>`

We will acknowledge within 72 hours and coordinate disclosure timing.

For benchmark gameability or methodology disclosures (not security-sensitive), use the maintainer-disclosure issue template; the 7-day embargo protocol from `RESEARCH_DESIGN.md` §11 applies.

## Supported versions

Pre-1.0 releases get security patches on a best-effort basis. v1.0 onward will get explicit support window commitments.

| Version | Supported |
|---|---|
| 0.1.x-pre-pilot | yes (best-effort) |
| 0.2.x-pilot | yes (best-effort) |
| 0.3.x-v1 (planned) | yes |
