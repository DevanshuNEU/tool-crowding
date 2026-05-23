---
doc: Model versions and training cutoffs for tool-crowding v1
updated: 2026-05-21
binding: yes (ABC T.6 reproducibility + query-set contamination control)
---

# Models under test

Anthropic publishes two distinct cutoff dates per model:

- **Training data cutoff** = the broader date range of training data used. This is the upper bound on what could be in the model's weights; contamination control must use this date.
- **Reliable knowledge cutoff** = the date through which a model's knowledge is most extensive and reliable. Earlier than the training cutoff; useful as a conservative bound for "what the model knows well," but NOT the right gate for contamination filtering.

For ABC query-set hygiene we use **training data cutoff** as the contamination boundary.

| Model ID | Training data cutoff | Reliable knowledge cutoff | Source URL |
|---|---|---|---|
| claude-opus-4-7 | 2026-01 (Jan 2026) | 2026-01 (Jan 2026) | https://docs.anthropic.com/en/docs/about-claude/models/overview |
| claude-sonnet-4-6 | 2026-01 (Jan 2026) | 2025-08 (Aug 2025) | https://docs.anthropic.com/en/docs/about-claude/models/overview |
| claude-haiku-4-5 | 2025-07 (Jul 2025) | 2025-02 (Feb 2025) | https://docs.anthropic.com/en/docs/about-claude/models/overview |

Anthropic publishes only the month, not the day. We treat the cutoff as the **last day of the published month** when used as an inequality (safest contamination boundary).

- claude-opus-4-7 training cutoff: 2026-01-31
- claude-sonnet-4-6 training cutoff: 2026-01-31
- claude-haiku-4-5 training cutoff: 2025-07-31

# Implications for query-set hygiene

- **Latest cutoff date across SUT models:** 2026-01-31 (Opus 4.7 and Sonnet 4.6 tied)
- **Earliest cutoff date across SUT models:** 2025-07-31 (Haiku 4.5)
- **Contamination-safe window:** queries scraped from data published *strictly after* 2026-01-31 are contamination-safe for all three models.
- **Mixed window (2025-08-01 to 2026-01-31):** safe for Haiku 4.5 only. Queries pulled from this window cannot be used to score Opus 4.7 or Sonnet 4.6 without contamination risk.
- **Pre-2025-07-31 queries:** in the training set for all three models. Apply 5-gram filtering per SWE-Bench Illusion methodology before inclusion, or exclude entirely.

Operational rule for v1 query set: **prefer post-2026-01-31 sources** (GitHub issues, Stack Overflow questions, doc updates) so all three models face the same contamination-safe surface. Mark each query with its publication date in the query manifest.

# Verification trail

- Searched: "Claude Opus 4.7 training cutoff", "Anthropic model cutoff dates 2026", "Anthropic Claude Opus 4.7 training data cutoff date docs.anthropic.com 2026"
- Sources consulted:
  - https://docs.anthropic.com/en/docs/about-claude/models (301 redirects to https://platform.claude.com/docs/en/docs/about-claude/models, same Anthropic-owned content)
  - https://docs.anthropic.com/en/docs/about-claude/models/overview (same redirect; "Latest models comparison" table is the canonical source)
- Cutoffs read directly from the "Reliable knowledge cutoff" and "Training data cutoff" rows of the "Latest models comparison" table on the official Anthropic docs page.
- Date verified: 2026-05-21

# Re-verification trigger

Re-run this verification whenever:
- A new model is added to the SUT set
- Anthropic ships a new Opus/Sonnet/Haiku version (the table on the docs page changes)
- Any of the three current model IDs is deprecated (check https://docs.anthropic.com/en/docs/about-claude/model-deprecations)
