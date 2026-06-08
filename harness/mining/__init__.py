"""Query-mining helpers (run at queries.jsonl construction time).

Mining-time tools are separate from the runtime harness (`tcrun`) and from
the preflight validators (`preflight`). They produce the artifacts that
preflight validates.
"""
