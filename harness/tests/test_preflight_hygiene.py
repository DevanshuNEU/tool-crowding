"""Tests for the query-set hygiene preflight gates (preflight/* package).

Each test exercises one of the 7 gates with synthetic Query objects. The gates
are pure (date, fivegram, per-repo-cap, tier-count, tokenizer) or have explicit
online/offline switches (license, repo_eligibility).

These are separate from test_preflight.py, which tests the 7-artifact
*reproducibility* gate (tcrun.preflight).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make `preflight` importable from harness/ root, matching production layout.
HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from preflight import (  # noqa: E402
    date_check,
    fivegram_check,
    license_check,
    per_repo_cap_check,
    repo_eligibility_check,
    tier_count_check,
    tokenizer_cache_check,
)
from tcrun.tasks import Query  # noqa: E402


def _q(**overrides) -> Query:
    base = {
        "query_id": "v1-pub-001",
        "tier": "public",
        "text": "find a function that parses YAML config files",
        "ground_truth_target": "parse_yaml_config_unique_name",
        "ground_truth_code": (
            "def parse_yaml_config_unique_name(path):\n"
            "    handle = open(path)\n"
            "    return safe_load(handle.read())"
        ),
        "source_repo": "exampleorg/example-tool",
        "source_publication_date": "2026-02-15",
        "source_license": "GPL-3.0",
        "difficulty_quartile": "q2",
        "primary_server": "oci",
        "fivegram_audit": [
            {"ngram": "parse_yaml_config_unique_name path safe_load handle read", "github_hits": 0, "web_hits": 0},
            {"ngram": "yaml safe_load open path read text", "github_hits": 0, "web_hits": 0},
        ],
    }
    base.update(overrides)
    return Query.model_validate(base)


# ---------- date_check ----------

def test_date_check_public_passes_after_threshold():
    r = date_check.check([_q(source_publication_date="2026-02-01")])
    assert r.passed, r.errors

def test_date_check_public_fails_at_threshold():
    r = date_check.check([_q(source_publication_date="2026-01-31")])
    assert not r.passed
    assert "strictly after" in r.errors[0]

def test_date_check_public_fails_before_threshold():
    r = date_check.check([_q(source_publication_date="2025-12-31")])
    assert not r.passed

def test_date_check_held_back_uses_april_threshold():
    q_ok = _q(query_id="v1-held-001", tier="held_back",
              source_publication_date="2026-05-01")
    q_bad = _q(query_id="v1-held-002", tier="held_back",
               source_publication_date="2026-04-30")
    r = date_check.check([q_ok, q_bad])
    assert not r.passed
    assert any("v1-held-002" in e for e in r.errors)
    assert not any("v1-held-001" in e for e in r.errors)

def test_date_check_sealed_exempt():
    q = _q(query_id="v1-sealed-001", tier="sealed",
           source_repo="DevanshuNEU/oci-private",
           source_publication_date="2024-01-01",
           source_license="proprietary")
    r = date_check.check([q])
    assert r.passed

def test_date_check_malformed_date():
    r = date_check.check([_q(source_publication_date="2026/02/15")])
    assert not r.passed
    assert "ISO-8601" in r.errors[0]


# ---------- license_check ----------

def test_license_check_offline_passes_on_gpl_family():
    queries = [_q(source_license="GPL-3.0"), _q(query_id="v1-pub-002", source_license="LGPL")]
    r = license_check.check(queries, online=False)
    assert r.passed, r.errors

def test_license_check_rejects_proprietary_on_public_tier():
    # The Query schema allows "proprietary" only because sealed tier needs it;
    # license_check has to catch the case where a public-tier row claims it.
    r = license_check.check([_q(source_license="proprietary")], online=False)
    assert not r.passed
    assert "not in GPL family" in r.errors[0]

def test_license_check_sealed_must_be_proprietary():
    q_ok = _q(query_id="v1-sealed-001", tier="sealed",
              source_publication_date="2024-01-01",
              source_license="proprietary",
              source_repo="DevanshuNEU/oci-private")
    q_bad = _q(query_id="v1-sealed-002", tier="sealed",
               source_publication_date="2024-01-01",
               source_license="GPL-3.0",
               source_repo="DevanshuNEU/oci-private")
    r = license_check.check([q_ok, q_bad], online=False)
    assert not r.passed
    assert any("sealed tier must" in e for e in r.errors)


# ---------- repo_eligibility_check ----------

def test_repo_eligibility_banned_repo_fails():
    r = repo_eligibility_check.check([_q(source_repo="numpy/numpy")], online=False)
    assert not r.passed
    assert "banned-repos list" in r.errors[0]

def test_repo_eligibility_non_banned_passes_offline():
    r = repo_eligibility_check.check([_q(source_repo="exampleorg/example-tool")], online=False)
    assert r.passed

def test_repo_eligibility_sealed_exempt():
    q = _q(query_id="v1-sealed-001", tier="sealed",
           source_repo="DevanshuNEU/oci-private",
           source_publication_date="2024-01-01",
           source_license="proprietary")
    r = repo_eligibility_check.check([q], online=False)
    assert r.passed


# ---------- fivegram_check ----------

def test_fivegram_check_empty_audit_fails():
    r = fivegram_check.check([_q(fivegram_audit=[])])
    assert not r.passed
    assert "fivegram_audit is empty" in r.errors[0]

def test_fivegram_check_zero_hits_passes():
    r = fivegram_check.check([_q()])  # default audit has zeros
    assert r.passed

def test_fivegram_check_one_hit_passes():
    audit = [
        {"ngram": "a b c d e", "github_hits": 1, "web_hits": 0},
        {"ngram": "f g h i j", "github_hits": 0, "web_hits": 0},
    ]
    r = fivegram_check.check([_q(fivegram_audit=audit)])
    assert r.passed, r.errors

def test_fivegram_check_two_hits_fails():
    audit = [
        {"ngram": "a b c d e", "github_hits": 1, "web_hits": 0},
        {"ngram": "f g h i j", "github_hits": 0, "web_hits": 1},
    ]
    r = fivegram_check.check([_q(fivegram_audit=audit)])
    assert not r.passed
    assert "2 high-entropy 5-grams" in r.errors[0]


# ---------- per_repo_cap_check ----------

def test_per_repo_cap_under_cap_passes():
    qs = [_q(query_id=f"v1-pub-{i:03d}", source_repo="orgA/tool1") for i in range(10)]
    r = per_repo_cap_check.check(qs)
    assert r.passed, r.errors

def test_per_repo_cap_over_cap_public_fails():
    qs = [_q(query_id=f"v1-pub-{i:03d}", source_repo="orgA/tool1") for i in range(11)]
    r = per_repo_cap_check.check(qs)
    assert not r.passed
    assert "cap 10" in r.errors[0]

def test_per_repo_cap_held_back_uses_seven():
    qs = [
        _q(query_id=f"v1-held-{i:03d}", tier="held_back",
           source_repo="orgA/tool1",
           source_publication_date="2026-05-15")
        for i in range(8)
    ]
    r = per_repo_cap_check.check(qs)
    assert not r.passed
    assert "cap 7" in r.errors[0]


# ---------- tier_count_check ----------

def test_tier_count_public_only_exact_30_passes():
    qs = [_q(query_id=f"v1-pub-{i:03d}") for i in range(30)]
    r = tier_count_check.check(qs, mode="public-only")
    assert r.passed, r.errors

def test_tier_count_public_only_short_fails():
    qs = [_q(query_id=f"v1-pub-{i:03d}") for i in range(29)]
    r = tier_count_check.check(qs, mode="public-only")
    assert not r.passed
    assert "expected 30, got 29" in r.errors[0]

def test_tier_count_all_tiers_passes_with_30_10_10():
    qs = (
        [_q(query_id=f"v1-pub-{i:03d}") for i in range(30)]
        + [_q(query_id=f"v1-held-{i:03d}", tier="held_back",
              source_publication_date="2026-05-15") for i in range(10)]
        + [_q(query_id=f"v1-sealed-{i:03d}", tier="sealed",
              source_repo="DevanshuNEU/oci-private",
              source_publication_date="2024-01-01",
              source_license="proprietary") for i in range(10)]
    )
    r = tier_count_check.check(qs, mode="all-tiers")
    assert r.passed, r.errors


# ---------- tokenizer_cache_check ----------

def test_tokenizer_cache_writes_when_absent(tmp_path):
    cache = tmp_path / "tokenizer_cache.json"
    r = tokenizer_cache_check.check([_q()], cache_path=cache, read_only=False)
    assert r.passed, r.errors
    assert cache.exists()
    data = json.loads(cache.read_text())
    assert "v1-pub-001" in data and isinstance(data["v1-pub-001"], int)

def test_tokenizer_cache_fails_read_only_with_missing_entry(tmp_path):
    cache = tmp_path / "tokenizer_cache.json"  # absent
    r = tokenizer_cache_check.check([_q()], cache_path=cache, read_only=True)
    assert not r.passed
    assert "no entry" in r.errors[0]

def test_tokenizer_cache_detects_stale_count(tmp_path):
    cache = tmp_path / "tokenizer_cache.json"
    cache.write_text(json.dumps({"v1-pub-001": 99999}))
    r = tokenizer_cache_check.check([_q()], cache_path=cache, read_only=True)
    assert not r.passed
    assert "stale cache" in r.errors[0]
