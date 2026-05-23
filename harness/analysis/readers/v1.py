"""Schema v1.* reader.

TODO Sat AM (frozen the day the first MVE result lands).

Reads results.jsonl + filters by schema_version per harness/SPEC.md §4
schema evolution rules. v1 reader handles v1.0 and v1.1 records
(v1.1 adds is_padded_n1, fake_tool_invoked, padding_skipped optional fields).
"""
