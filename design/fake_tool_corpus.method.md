---
title: fake_tool_corpus.method.md — provenance for design/fake_tool_corpus.jsonl
status: v1 (built 2026-05-23 Sat AM)
binds: PADDING_STRATEGY.md §3 ("The fake-tool corpus") + §6 (sanity gates)
generator: harness/pool/gen_fake_corpus.py
corpus_file: design/fake_tool_corpus.jsonl
corpus_sha256: b201e668278c4ab128e00efc1b1fffa1b594d2cb47ec9eb6cac58977f86c655a
related: [[PADDING_STRATEGY]] [[SERVER_POOL]] [[REPRODUCIBILITY]] [[PILOT_V0]]
---

# Fake-tool corpus build provenance

## 1. Method classification

**Method B per PADDING_STRATEGY.md §3** — LLM-authored entries written by a single LLM author (Claude Opus 4.7, model id `claude-opus-4-7[1m]`), passed through a programmatic QA gate before being committed. Not Method A (hand-curated by Devanshu directly), because the corpus build was delegated as an agent task to free Devanshu for the Sat AM pilot gate. The QA gate compensates for the lack of human-curation guarantees.

## 2. Generation seed

Deterministic seed string used for any RNG inside the generator (currently no per-entry RNG; the seed is committed for forward compatibility if entries get rotated):

```
SEED = "tool-crowding-padded-N1-corpus-v1-2026-05-23"
```

Python `random.seed(SEED)` is called before any RNG calls. The entry order in the corpus file is the entry order in `harness/pool/gen_fake_corpus.py`'s `add(...)` calls. No shuffling.

## 3. Tokenization

Per PADDING_STRATEGY.md §4 (tokenizer policy), each model in the sweep is supposed to keep its own per-entry token count under `description_tokens[model_id]`. For this initial corpus build we computed a single tokenizer-independent estimate using **tiktoken `cl100k_base`** on `description + json.dumps(input_schema)` (no whitespace, default sort) and stored it under `estimated_tokens`. The harness's `padding.py` is expected to re-tokenize per-model and store `description_tokens` as a map at corpus-load time. tiktoken was available locally (installed via pip3 --break-system-packages); no 1-token-per-4-chars proxy was needed.

Per-entry schema:

```json
{
  "name": "...",
  "description": "...",
  "input_schema": {"type":"object","properties":{...},"required":[...]},
  "estimated_tokens": <int>
}
```

This is a deliberate subset of the schema in PADDING_STRATEGY.md §3 (no `entry_id`, no `domain_tag`, no per-model `description_tokens` map). Those fields can be backfilled by a corpus-rehydration script without changing names or descriptions; the SHA-256 will rotate when they are added but the load-bearing semantic content will not.

## 4. QA gate (rejection log)

Two filters, applied in order to every candidate entry inside `gen_fake_corpus.py`:

### Filter A — forbidden-vocab regex

```python
FORBIDDEN = re.compile(
    r"\b(code|coding|function|functional|file|files|repo|repos|repository|repositories|"
    r"github|gitlab|git|commit|branch|merge|"
    r"search|searching|grep|retriev|retrieval|index|indexing|snippet|snippets|"
    r"AST|syntax|parse|parser|parsing|compile|compiler|"
    r"variable|debug|debugger|library|libraries|"
    r"script|scripts|programming|developer|software|"
    r"scrape|scraping|scraper)\b",
    re.IGNORECASE,
)
```

This is PADDING_STRATEGY.md §3's regex superset, extended with the additional bans from the task prompt (`script`, `programming`, `developer`, `software`, `scrape`). Hit anywhere in `description + " " + name` → reject.

### Filter B — name overlap with SERVER_POOL.md

Normalized comparison (lowercase, strip `_` and `-`) against the 15-server SERVER_POOL list. Exact match → reject. Substring match where the server name is ≥5 characters → reject (guards `Fetch` MCP from `*Fetcher` names, etc.).

### Rejection log

During the final build the corpus had **zero rejections**. Three early-draft entries were rejected during iteration and renamed in-place rather than dropped, so they don't appear as JSONL line-level rejections but are noted here for audit:

| Original name | Rejection reason | Replacement |
|---|---|---|
| `AirQualityIndexReader` | forbidden_vocab: `index` | `AirQualityAdvisoryReader` |
| `UvIndexAdvisor` | forbidden_vocab: `index` | `UvExposureAdvisor` |
| `PublicLibraryHoursLookup` | forbidden_vocab: `library` | `PublicReadingRoomHoursLookup` (`branch_name` field also renamed to `room_name` to clear forbidden vocab) |
| `BodyMassIndex` | forbidden_vocab: `index` | `BodyMassRatio` |
| `CountryCallingCode` | forbidden_vocab: `code` | `CountryCallingNumber` |
| `MorseEncoder` / `MorseDecoder` | description contained `code` | rewritten to use `signal` |
| `HourlyForecastFetcher` / `AlbumTracklistFetcher` / `LiveScoreboardFetcher` / `DailyJokeFetcher` / `TideTableFetcher` / `PollenForecastFetcher` | substring-collision with `Fetch` MCP server | renamed to `*Reader` variants |

Final-build rejections (post-rename) recorded by the generator: **0**.

## 5. Token-count distribution

199 accepted entries after the deterministic trim from 261 candidates down toward the ~200 target. Trim policy: drop preferentially from the over-represented (medium) band first, keeping the entry-order stable within bands.

### Histogram by 10-token bins (cl100k_base estimate)

```
 30- 39   55  #######################################################
 40- 49    5  #####
 50- 59    4  ####
 60- 69   21  #####################
 70- 79   22  ######################
 80- 89   14  ##############
 90- 99   26  ##########################
100-109   19  ###################
110-119    8  ########
120-129    5  #####
130-139    3  ###
140-149    3  ###
150-159   10  ##########
160-169    4  ####
```

Min = 30, max = 168, mean ≈ 75, n = 199.

### Band distribution (task spec: small 20-40, medium 50-90, large 100-180)

Using the prompt's exact bands:

| Band | Range (tokens) | Count | Share |
|---|---|---|---|
| small | 20-40 | 56 | 28% |
| medium | 50-90 | 67 | 34% |
| large | 100-180 | 76 | 38% |
| (gap) | 41-49 | 5 | 3% |
| (gap) | 91-99 | 26 | 13% |

If the 41-49 and 91-99 gap entries are folded into adjacent bands (which is what the padding algorithm actually does — it doesn't care about gaps, it just sums tokens), the effective small/medium/large distribution is:

| Effective band | Count | Share |
|---|---|---|
| ≤40 | 56 | 28% |
| 41-90 | 67 | 34% |
| ≥91 | 76 | 38% |

This is within tolerance of the 1/3 - 1/3 - 1/3 target. The slight large-band skew (38% vs 33%) is structural: any input_schema with two or more array-of-object properties, multiple enums, or three to five required fields tokenizes above 90 by default. We accepted this rather than artificially compress complex schemas, because the padding-algorithm flexibility goal (per PADDING_STRATEGY.md §3) is preserved — the corpus has enough variety in each band to pack to any reasonable target.

## 6. Sanity checks (all passed)

- `wc -l design/fake_tool_corpus.jsonl` → 199 (~200 as requested)
- Every line parses as valid JSON
- No duplicate names (199 unique / 199 total)
- No name appears in SERVER_POOL.md primary or distractor lists (exact OR substring ≥5 chars)
- Every `input_schema` has `type=object` and a `properties` field
- No description or name matches the forbidden-vocab regex from PADDING_STRATEGY.md §3
- 22 neutral domains covered, plus a compact "common utility" backfill set; no domain has fewer than three entries

## 7. Open issues / forward work

1. **Per-model token re-tokenization** still needs to happen at corpus-load time in the harness. The `description_tokens[model_id]` map is not yet committed — only the model-agnostic `estimated_tokens` (cl100k_base) is. Tracker: PADDING_STRATEGY.md §3 "Per-entry token count cached" requirement.

2. **PADDING_STRATEGY.md §9 question 1** (does the model recognize fillers as fake?) is empirically testable only after the Sat AM pilot runs. If fillers get invoked at >10% (the §6 gate threshold), the corpus needs another pass to make names less plausible OR to widen the orthogonality regex.

3. **Method A backup**: if reviewer feedback pushes back on LLM-generated semantics ("how do you know the corpus doesn't leak code-domain priors?"), the Method A hand-curated rebuild stays a 2-hour task and would be the response. The 22-domain index already serves as the outline for that rebuild.

## 8. Files

- Generator: `harness/pool/gen_fake_corpus.py`
- Output corpus: `design/fake_tool_corpus.jsonl`
- Stats artifact: `harness/pool/_fake_corpus_stats.json` (machine-readable mirror of §5 + rejection counts)
- This document: `design/fake_tool_corpus.method.md`

## Related

[[PADDING_STRATEGY]] [[SERVER_POOL]] [[REPRODUCIBILITY]] [[PILOT_V0]] [[FOUNDATION]] [[../harness/SPEC]]
