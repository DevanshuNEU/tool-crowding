#!/usr/bin/env python3
"""Generate tasks/stage1-factorial.jsonl for the Phase F Stage 1 confirmatory 2x2.

Each of the 5 verified post-cutoff anchors produces TWO query records that share
the same ground_truth (target + code + provenance) and differ ONLY in whether the
source repo is named:
    - ambiguous     (s1-amb-*)   : conceptual question, names neither repo nor symbol
    - target-named  (s1-named-*) : same question, prefixed with the GitHub repo name

So the ONLY thing that changes between the two variants is Factor B (task
ambiguity). Factor A (agent framing) is swept at the RUN level via
TC_SYSTEM_PROMPT_VARIANT, not encoded here.

Verbatim function bodies live in _stage1_bodies.txt (written literally to avoid
JSONL escaping hazards — e.g. the synapse docstring contains triple quotes).

DRAFT: anchors are verified post-cutoff + verbatim + copyleft, but the canonical
5-gram contamination audit (mining/audit_ngrams), the deepwiki-lure-fresh check,
and the no-MCP 0/5 baseline are PENDING gates per the Phase F provenance note.
The fivegram_audit below records only grams the sourcing fleet found at ZERO total
public hits; github_hits/web_hits here mean "hits anywhere", and 0 is unambiguous.
"""

from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BODIES = HERE / "_stage1_bodies.txt"
OUT = HERE / "stage1-factorial.jsonl"


def load_bodies() -> dict[str, str]:
    """Split _stage1_bodies.txt on <<<<ANCHOR=name>>>> delimiter lines."""
    text = BODIES.read_text(encoding="utf-8")
    bodies: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("<<<<ANCHOR=") and line.endswith(">>>>"):
            if current is not None:
                bodies[current] = "\n".join(buf).strip("\n")
            current = line[len("<<<<ANCHOR="):-len(">>>>")]
            buf = []
        elif line == "<<<<END>>>>":
            if current is not None:
                bodies[current] = "\n".join(buf).strip("\n")
            current = None
        elif current is not None:
            buf.append(line)
    return bodies


# Per-anchor metadata. `core` is the shared conceptual question; the ambiguous
# variant uses it verbatim, the target-named variant is `named_prefix + core`.
ANCHORS = [
    {
        "key": "ansible",
        "target": "parse_distribution_file_UnionTech",
        "repo": "ansible/ansible",
        "license": "GPL-3.0",
        "pubdate": "2026-05-20",
        "difficulty": "q3",
        "core": (
            "In a Python system-facts library that gathers operating-system details, which "
            "function parses a Linux distribution identification file to recognize an RPM-based "
            "server distribution that shares its vendor name with a Debian-based desktop edition, "
            "disambiguating the two via a PLATFORM_ID prefix and extracting the version and "
            "codename with a two-path regex fallback? Identify the specific function."
        ),
        "named_prefix": "In the GitHub repository ansible/ansible, ",
        "fivegram_audit": [
            {"ngram": "uniontech_facts distribution_release release group", "github_hits": 0, "web_hits": 0},
            {"ngram": "PLATFORM_ID platform uel distribution UnionTech", "github_hits": 0, "web_hits": 0},
            {"ngram": "distribution_version group split dot 0 uniontech", "github_hits": 0, "web_hits": 0},
            {"ngram": "release redhat-release uos-release UnionTech kongzi fuyu", "github_hits": 0, "web_hits": 0},
        ],
    },
    {
        "key": "paperless",
        "target": "build_localization_prompt",
        "repo": "paperless-ngx/paperless-ngx",
        "license": "GPL-3.0",
        "pubdate": "2026-06-01",
        "difficulty": "q3",
        "core": (
            "In a self-hosted document management system's AI module, which function takes a "
            "dictionary of generated classification suggestions and a target language code and "
            "builds a language-model prompt that rewrites only the human-visible fields (title, "
            "tags, document types, storage paths) into that language while preserving proper "
            "nouns, organization names, correspondents, and dates, and returns the same JSON "
            "schema? Identify the specific function."
        ),
        "named_prefix": "In the GitHub repository paperless-ngx/paperless-ngx, ",
        "fivegram_audit": [
            {"ngram": "get_language_name output_language", "github_hits": 0, "web_hits": 0},
            {"ngram": "build_localization_prompt suggestions output_language", "github_hits": 0, "web_hits": 0},
            {"ngram": "Translate generic category words when a equivalent exists", "github_hits": 0, "web_hits": 0},
            {"ngram": "Return the same JSON schema with all fields present", "github_hits": 0, "web_hits": 0},
        ],
    },
    {
        "key": "synapse",
        "target": "split_dict_to_fit_to_size",
        "repo": "element-hq/synapse",
        "license": "AGPL",
        "pubdate": "2026-06-02",
        "difficulty": "q3",
        "core": (
            "In a Python server for a federated messaging protocol, which generator function "
            "partitions a string-keyed dictionary into the fewest sub-dictionaries whose canonical "
            "JSON encoding each stays within a caller-supplied byte budget (accounting for optional "
            "wrapper overhead), emits an oversized singleton when one entry alone exceeds the "
            "budget, and lazily yields each (subset, estimated-size) pair? Identify the specific "
            "function."
        ),
        "named_prefix": "In the GitHub repository element-hq/synapse, ",
        "fivegram_audit": [
            {"ngram": "skip the splitting logic fit within the size limit", "github_hits": 0, "web_hits": 0},
        ],
    },
    {
        "key": "calibre",
        "target": "path_from_root",
        "repo": "kovidgoyal/calibre",
        "license": "GPL-3.0",
        "pubdate": "2026-05-23",
        "difficulty": "q3",
        "core": (
            "In a Python e-book management application's filename utilities, which function "
            "resolves an untrusted relative path against a root directory and raises ValueError if "
            "the input is absolute, carries a drive qualifier, contains empty/dot/dot-dot traversal "
            "components, or resolves outside the root, with optional flags to allow the root "
            "itself, reject colons, and toggle case sensitivity? Identify the specific function."
        ),
        "named_prefix": "In the GitHub repository kovidgoyal/calibre, ",
        "fivegram_audit": [
            {"ngram": "absolute paths are not allowed drive-qualified traversal components", "github_hits": 0, "web_hits": 0},
        ],
    },
    {
        "key": "weblate",
        "target": "repo_matches_exact_repos",
        "repo": "WeblateOrg/weblate",
        "license": "GPL-3.0",
        "pubdate": "2026-06-01",
        "difficulty": "q3",
        "core": (
            "In a Python translation-management system that processes incoming version-control "
            "webhooks, which function takes an incoming repository URL and a list of configured "
            "repository URLs and returns whether the incoming URL exactly matches any configured "
            "one, treating a trailing slash as equivalent and matching credential-embedded "
            "HTTP/HTTPS URLs against their credential-free form? Identify the specific function."
        ),
        "named_prefix": "In the GitHub repository WeblateOrg/weblate, ",
        "fivegram_audit": [
            {"ngram": "repo_matches_exact_repos repo_matches_fallback hook weblate", "github_hits": 0, "web_hits": 0},
            {"ngram": "fallback_repository_evidence weblate hooks", "github_hits": 0, "web_hits": 0},
        ],
    },
]


def main() -> None:
    bodies = load_bodies()
    records = []
    for a in ANCHORS:
        code = bodies[a["key"]]
        assert a["target"] in code, f"target {a['target']} not in body for {a['key']}"
        common = {
            "tier": "public",
            "ground_truth_target": a["target"],
            "ground_truth_code": code,
            "source_repo": a["repo"],
            "source_publication_date": a["pubdate"],
            "source_license": a["license"],
            "difficulty_quartile": a["difficulty"],
            "primary_server": "github_mcp",
            "fivegram_audit": a["fivegram_audit"],
        }
        records.append({
            "query_id": f"s1-amb-{a['key']}-001",
            "text": a["core"],
            **common,
        })
        records.append({
            "query_id": f"s1-named-{a['key']}-001",
            "text": a["named_prefix"] + a["core"][0].lower() + a["core"][1:],
            **common,
        })
    with open(OUT, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records to {OUT}")


if __name__ == "__main__":
    main()
