---
doc: Model versions and training cutoffs for tool-crowding v1
updated: 2026-05-24
binding: yes (ABC T.6 reproducibility + query-set contamination control)
---

# Models under test

The v1 frontier panel (per `RESEARCH_DESIGN.md §3` + `FOUNDATION.md §1.1`) is Opus 4.7, Sonnet 4.6, GPT-5-class, Gemini 2.5-class. Haiku 4.5 is tracked here for cost-tier robustness but is not in the headline N-curve panel.

Vendors publish distinct cutoff types. For ABC query-set hygiene we use **training data cutoff** (broader, upper-bound on what could be in weights). Where a vendor publishes only "knowledge cutoff" without distinguishing training vs reliable, we treat the published value as the training cutoff (conservative; this is what GPT-5 and Gemini publish).

| Model ID | Training / knowledge cutoff | Reliable knowledge cutoff | Source URL | Verified |
|---|---|---|---|---|
| claude-opus-4-7 | 2026-01 (Jan 2026) | 2026-01 (Jan 2026) | https://docs.anthropic.com/en/docs/about-claude/models/overview | 2026-05-21 |
| claude-sonnet-4-6 | 2026-01 (Jan 2026) | 2025-08 (Aug 2025) | https://docs.anthropic.com/en/docs/about-claude/models/overview | 2026-05-21 |
| claude-haiku-4-5 | 2025-07 (Jul 2025) | 2025-02 (Feb 2025) | https://docs.anthropic.com/en/docs/about-claude/models/overview | 2026-05-21 |
| gpt-5 (base) | 2024-09-30 (Sep 30, 2024) | — | https://developers.openai.com/api/docs/models/gpt-5 | 2026-05-24 |
| gpt-5.5 | 2025-12-01 (Dec 1, 2025) | — | https://developers.openai.com/api/docs/models/gpt-5.5 | 2026-05-24 |
| gemini-2.5-pro | 2025-01-01 (Jan 1, 2025) | — | https://www.prompthub.us/models/gemini-2-5-pro (secondary — primary deepmind.google page now only lists 3.1 Pro) | 2026-05-24 |
| gemini-3.1-pro | 2025-01 (Jan 2025) | — | https://deepmind.google/models/gemini/pro/ | 2026-05-24 |

Anthropic publishes only the month; we treat the cutoff as the **last day of the published month**. OpenAI and Google publish either the day or only the month; same convention applies where only month is published.

- claude-opus-4-7 training cutoff: 2026-01-31
- claude-sonnet-4-6 training cutoff: 2026-01-31
- claude-haiku-4-5 training cutoff: 2025-07-31
- gpt-5 cutoff: 2024-09-30
- gpt-5.5 cutoff: 2025-12-01
- gemini-2.5-pro cutoff: 2025-01-01 (treated as 2025-01-31 with month-last-day convention; 2025-01-01 is what PromptHub publishes)
- gemini-3.1-pro cutoff: 2025-01-31

# Implications for query-set hygiene

- **Latest cutoff date across the v1 frontier panel (Opus 4.7, Sonnet 4.6, GPT-5-class, Gemini 2.5-class):** 2026-01-31 (Opus 4.7 and Sonnet 4.6 tied). All non-Anthropic models have older cutoffs (GPT-5.5 = 2025-12-01, all earlier GPT-5 variants earlier; all known Gemini Pro variants ≤ 2025-01-31).
- **§11.1 + §11.2 of `QUERY_SET_HYGIENE.md` closed (2026-05-24):** GPT-5 + Gemini 2.5 cutoffs verified. Binding cutoff for the public tier remains **2026-01-31**; the held-back tier's stricter 2026-04-30 cutoff remains.
- **Earliest cutoff date across SUT models:** 2024-09-30 (GPT-5 base) or 2025-01-01 (Gemini 2.5 Pro). Pre-2025-01-31 queries are in training set for all panel models; apply 5-gram filtering or exclude.
- **Contamination-safe window:** queries scraped from data published *strictly after* 2026-01-31 are contamination-safe for all panel models.

Operational rule for v1 query set: **prefer post-2026-01-31 sources** (GitHub issues, Stack Overflow questions, doc updates) so the entire panel faces the same contamination-safe surface. Mark each query with its publication date in the query manifest.

# Verification trail

**Anthropic models (2026-05-21):**
- Searched: "Claude Opus 4.7 training cutoff", "Anthropic model cutoff dates 2026", "Anthropic Claude Opus 4.7 training data cutoff date docs.anthropic.com 2026"
- Sources consulted:
  - https://docs.anthropic.com/en/docs/about-claude/models (301 redirects to https://platform.claude.com/docs/en/docs/about-claude/models, same Anthropic-owned content)
  - https://docs.anthropic.com/en/docs/about-claude/models/overview (same redirect; "Latest models comparison" table is the canonical source)
- Cutoffs read directly from the "Reliable knowledge cutoff" and "Training data cutoff" rows of the "Latest models comparison" table on the official Anthropic docs page.

**OpenAI GPT-5 family (2026-05-24):**
- Primary source attempted: https://platform.openai.com/docs/models/gpt-5 (HTTP 403; auth-gated)
- Working source: https://developers.openai.com/api/docs/models/gpt-5 (public dev portal; "Sep 30, 2024 knowledge cutoff" verbatim)
- GPT-5.5 source: https://developers.openai.com/api/docs/models/gpt-5.5 ("Dec 01, 2025 knowledge cutoff" verbatim)
- Note: developers.openai.com is OpenAI-owned; equivalent to platform.openai.com for model card data.

**Google Gemini family (2026-05-24):**
- Primary sources attempted: https://ai.google.dev/gemini-api/docs/models, https://ai.google.dev/gemini-api/docs/models/gemini (no cutoff data published on either)
- Working source for current flagship: https://deepmind.google/models/gemini/pro/ (only lists Gemini 3.1 Pro now, knowledge cutoff January 2025)
- Working source for Gemini 2.5 Pro specifically: https://www.prompthub.us/models/gemini-2-5-pro (secondary; states "knowledge cut-off date is January 1, 2025" and confirms in FAQ)
- Caveat: Gemini 2.5 Pro is no longer the current frontier; deepmind.google has moved on to 3.1 Pro. If the v1 panel intends "whatever Gemini Pro is current at run time," 3.1 Pro (cutoff 2025-01) is the binding entry. Either way, binding cutoff for v1 query mining is < 2026-01-31 and Anthropic dominates.

# Open question for panel composition

`QUERY_SET_HYGIENE.md` and `FOUNDATION.md` name "GPT-5-class" and "Gemini 2.5-class" — class names, not version pins. As of 2026-05-24 the current frontier in each class is **GPT-5.5** and **Gemini 3.1 Pro**. The pilot needs an explicit pin per `REPRODUCIBILITY.md` h_endpoints. Recommended: use `gpt-5.5-snapshot-YYYY-MM-DD` and `gemini-3.1-pro-snapshot-YYYY-MM-DD` snapshot IDs in `config.model_panel`. This does not change the binding cutoff (Anthropic dominates regardless).

# Re-verification trigger

Re-run this verification whenever:
- A new model is added to the SUT set
- Any vendor ships a new version in a class on the panel (Anthropic / OpenAI / Google)
- Any current model ID is deprecated (check vendor deprecation pages)
