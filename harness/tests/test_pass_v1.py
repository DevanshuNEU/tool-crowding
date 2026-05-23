"""Smoke tests for the pass_v1 oracle (RESEARCH_DESIGN.md §4 Pass@1).

5 hand-curated cases (3 PASS + 2 FAIL) covering the full decision matrix
for symbol-match × token-overlap. Plus 4 edge-case cases.
"""

from __future__ import annotations

from tcrun.oracles.pass_v1 import pass_criterion_v1, _tokenize


# -- 5 hand-curated smoke cases per the Sat AM gate ------------------------

class TestPassV1HandCurated:
    """The 5 cases required by today's oracle smoke-test task."""

    def test_case_1_exact_match_passes(self):
        # exact match: symbol present + 100% token overlap
        gt_sym = "compute_mpd"
        gt_code = "def compute_mpd(server, n_ref): return performance_delta(server)"
        snippet = "def compute_mpd(server, n_ref): return performance_delta(server)"
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is True

    def test_case_2_wrapped_in_explanation_passes(self):
        # symbol present + >50% overlap despite surrounding prose
        gt_sym = "tokenize"
        gt_code = "def tokenize(text): return text.lower().split()"
        snippet = (
            "Here is the function I found in the repo. "
            "def tokenize(text): return text.lower().split()  # tokenizes input"
        )
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is True

    def test_case_3_minor_reformat_passes(self):
        # symbol present + >50% overlap with slight syntactic reordering
        gt_sym = "binary_search"
        gt_code = "def binary_search(arr, target): low = 0; high = len(arr) - 1"
        snippet = "def binary_search(arr, target): low, high = 0, len(arr) - 1"
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is True

    def test_case_4_symbol_present_but_body_stubbed_fails(self):
        # symbol present but content is just `pass`; overlap < 50%
        gt_sym = "validate_config"
        gt_code = (
            "def validate_config(cfg): return "
            "cfg.path_fields and cfg.seed and cfg.model and cfg.host and cfg.runs_per_cell"
        )
        snippet = "def validate_config(cfg): pass"
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is False

    def test_case_5_renamed_function_fails(self):
        # no symbol match even though the snippet is semantically similar
        gt_sym = "compute_mpd"
        gt_code = "def compute_mpd(server, n_ref): return performance_delta(server)"
        snippet = "def calculate_marginal_performance(server, n): return delta(server)"
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is False


# -- 4 edge cases -----------------------------------------------------------

class TestPassV1EdgeCases:

    def test_empty_snippet_fails(self):
        assert pass_criterion_v1("", "compute_mpd", "def compute_mpd(): pass") is False

    def test_empty_ground_truth_symbol_fails(self):
        # an oracle call with no expected symbol is meaningless; refuse
        assert pass_criterion_v1("def x(): pass", "", "def x(): pass") is False

    def test_empty_ground_truth_code_passes_on_symbol_match(self):
        # degenerate case: no tokens to compare; symbol match alone passes
        assert pass_criterion_v1("def foo(): pass", "foo", "") is True

    def test_symbol_as_substring_inside_other_identifier_still_matches(self):
        # documented behavior: pass_v1 uses literal substring; "compute_mpd"
        # would match "compute_mpd_v2" (a known v1 limitation; v2 oracle may
        # tighten to word-boundary match)
        gt_sym = "compute_mpd"
        gt_code = "def compute_mpd(s): return s"
        snippet = "def compute_mpd_v2(s): return s"
        # symbol substring present + >50% token overlap
        assert pass_criterion_v1(snippet, gt_sym, gt_code) is True


# -- tokenizer internals ----------------------------------------------------

class TestTokenize:

    def test_strips_punctuation(self):
        assert _tokenize("hello, world!") == {"hello", "world"}

    def test_lowercases(self):
        assert _tokenize("Hello WORLD") == {"hello", "world"}

    def test_dedup_via_set(self):
        assert _tokenize("foo foo foo") == {"foo"}

    def test_empty_returns_empty_set(self):
        assert _tokenize("") == set()
