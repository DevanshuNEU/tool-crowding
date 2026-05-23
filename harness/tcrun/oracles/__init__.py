"""Oracles package: pass criterion implementations.

v1 oracle: pass_v1.pass_criterion_v1 per RESEARCH_DESIGN.md §4 (Pass@1 primary).

Oracle files are version-pinned by SHA-256 of file contents, recorded in
every Trial.oracle_version per SPEC.md §4 schema. Oracle audit protocol:
hand-label 10 held-out gold queries; if oracle disagrees on > 1 of 10,
fix oracle, bump version, re-score all trials (traces are pinned).
"""
