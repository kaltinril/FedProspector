# Phase 125B: Keyword Extractor — Pattern Additions

**Status:** COMPLETE (2026-04-28)
**Priority:** Medium — incremental signal uplift across 32K+ analyzed docs and ~1,000 docs/day forward.
**Depends on:** Phase 125 (COMPLETE) — [125-KEYWORD-EXTRACTOR-DOC-LEVEL-FILTER.md](125-KEYWORD-EXTRACTOR-DOC-LEVEL-FILTER.md)
**Surfaced by:** Phase 125 follow-up pattern audit (2026-04-28). All patterns validated against a random 500-doc sample with verified zero false positives (after the bid-bond context filter on `contract_ceiling`).

## Problem

Phase 125 unblocked the document-level eligibility filter and drained the 5,527-doc keyword-extraction backlog. The follow-up sampling work flagged in Phase 125's "What landed → Validated finding for follow-up" identified five high-precision regex additions the current pattern set in [`fed_prospector/etl/attachment_intel_extractor.py`](../../../fed_prospector/etl/attachment_intel_extractor.py) is missing. The current set captures roughly 80% of the structured signal in attachment text; this phase closes most of the remaining gap with patterns that produced zero false positives across the validation sample.

Three new categories add coverage where today there is none:

| Category | Sample hits | Signal |
|----------|-------------|--------|
| `contract_ceiling` | 14 matches / 8 docs | Explicit "shall not exceed $X" / "NTE $X" — deal-size signal |
| `clin_structure` | 128 matches / 21 docs | CLIN line-item enumeration — work-breakdown signal |
| `tech_specs` | 248 matches / 45 docs | MIL-STD / ASTM standards — capability-match signal |

Two existing categories currently match but throw away the captured value (storing `value: None`). Promoting the captured group into `value` makes the data usable for downstream queries / UI:

| Category | Sample hits | Today | After |
|----------|-------------|-------|-------|
| `naics_size_standard` | 27 matches / 24 docs | matches but `value=None` | captures the dollar amount |
| `wage_wd_number` | 16 matches / 15 docs | matches but `value=None` | captures the WD number |

## Approach

Five additions to `_RAW_PATTERNS` — three new categories and two enhancements to existing entries — plus one new context-check function (`no_bid_bond`) to suppress the only false-positive class identified in validation. No DDL changes, no new dependencies, no schema migration.

### 1. New `contract_ceiling` category

Captures explicit dollar ceilings: "shall not exceed $X", "ceiling of $X", "NTE $X", "maximum order value of $X", "total contract value shall not exceed $X".

Recommended entry (match the style of existing entries in `_RAW_PATTERNS` at [`fed_prospector/etl/attachment_intel_extractor.py:109`](../../../fed_prospector/etl/attachment_intel_extractor.py)):

```python
{"pattern": r"(?:shall\s+not\s+exceed|not[ -]to[ -]exceed|\bNTE\b|ceiling\s+of|maximum\s+(?:order\s+)?value(?:\s+of)?|total\s+(?:dollar\s+|contract\s+)?value\s+(?:shall\s+not\s+exceed|of))\s*[:.]?\s*\$([\d,]+(?:\.\d+)?)\s*(?:million|M|billion|B|K)?", "value": None, "confidence": "medium", "name": "ceiling_amount", "_needs_context_check": "no_bid_bond"}
```

Requires a NEW context check named `no_bid_bond` to be added to `_run_patterns` (around line 1107 where existing context checks live). The check examines the 120 chars BEFORE the match and skips if any of these substrings appear (case-insensitive): `"bid price"`, `"proposal price"`, `"bid guarantee"`, `"proposal guarantee"`, `"bid bond"`, `"20 percent"`, `"20%"`, `"twenty percent"`.

**Rationale:** these all indicate FAR 52.228-1 bid-bond cap boilerplate ("guarantee in an amount not less than 20 percent of the bid price but shall not exceed $3M") — these are NOT contract ceilings.

**Validation:** 14 raw matches across 8 docs in 500-doc sample. Without filter: ~21% FP rate (3 bid-bond caps out of 14). With filter: 0% FP.

### 2. New `clin_structure` category

Pattern: `\bCLIN\s+(\d{4})\b`. Single entry, `value=None` (the captured CLIN ID becomes the evidence). 21 docs / 128 matches in sample, zero FPs.

### 3. New `tech_specs` category

Patterns:

- `\bMIL-STD-(\d+[A-Z]?)\b` — military standards
- `\bMIL-SPEC-(\d+[A-Z]?)\b`
- `\bMIL-HDBK-(\d+[A-Z]?)\b`
- `\bMIL-PRF-(\d+[A-Z]?)\b`
- `\bASTM\s+([A-Z]\d+(?:[/-]\d+)?M?)\b`

45 docs / 248 matches combined in sample, zero FPs.

### 4. Enhance existing `naics_size_standard` pattern

Located in `_RAW_PATTERNS["naics_code"]` around line 222 of `attachment_intel_extractor.py`. Currently has `value: None`. Update the regex to capture the dollar amount and store it in `value`:

```python
r"\bsize\s+standard\s+(?:is\s+|of\s+)?\$([\d,.]+)\s*(million|M|billion|B)?\b"
```

The pattern already has high confidence; just enrich the captured value.

**Validation:** 24 docs / 27 matches in sample, zero FPs. Examples: "$34 million", "$45,000,000", "$12.5M", "$16.5 Million".

**NOTE:** Phase 129 (NAICS Code Intelligence & SBA Size Standards) is the authoritative consumer of NAICS size data via the `ref_sba_size_standard` reference table. This pattern does NOT replace 129 — it provides a per-attachment cross-validation signal that the contracting officer's stated size standard matches the official SBA value for the assigned NAICS.

### 5. Enhance existing `wage_wd_number` pattern

Located in `_RAW_PATTERNS["wage_determination"]` around line 228. Currently has `value: None`. Update the capture group so the WD number is stored in `value`:

```python
r"\bWage\s+Determination\s*(?:No\.?|Number|#)?\s*[:.]?\s*((?:\d{4}-\d{4}|[A-Z]{2}\d{8,}))\b"
```

**Validation:** 15 docs / 16 matches in sample, zero FPs. Examples: "2015-5237", "2015-4217".

## Pre-implementation verification

Empirical sampling against live DB completed 2026-04-28. All five pattern additions validated zero-FP across 500 random docs spanning 1KB-200KB text size range. The bid-bond FP risk on `contract_ceiling` was specifically tested and the `no_bid_bond` context filter eliminates it.

## Tasks

- [x] **Task 1:** Add the new `no_bid_bond` context check to `_run_patterns` in `attachment_intel_extractor.py` around line 1107 (alongside existing context-check functions).
- [x] **Task 2:** Add `contract_ceiling` category to `_RAW_PATTERNS` with the regex above and `_needs_context_check: "no_bid_bond"`.
- [x] **Task 3:** Add `clin_structure` category to `_RAW_PATTERNS`.
- [x] **Task 4:** Add `tech_specs` category to `_RAW_PATTERNS` with the five patterns above (MIL-STD, MIL-SPEC, MIL-HDBK, MIL-PRF, ASTM).
- [x] **Task 5:** Enhance `naics_size_standard` and `wage_wd_number` to capture values into `value` (regexes above).
- [x] **Task 6:** Tests in `fed_prospector/tests/test_attachment_intel_extractor.py` (the file added by Phase 125):
  - Each new category produces matches on a sample text containing the keyword
  - `no_bid_bond` context check correctly excludes the FAR 52.228-1 bid-bond boilerplate
  - `naics_size_standard` and `wage_wd_number` matches now have `value` populated
- [x] **Task 7:** Operational follow-up — corpus-wide re-extraction with `--force`. Run `python fed_prospector/main.py extract attachment-intel --force --batch-size 1000` in a loop until eligibility count drops to ~5. Verify via `health pipeline-status`. This is a one-time cost (~32K docs × ~85ms/doc ≈ 45 minutes wall time at workers=4). NOTE: re-extraction repopulates the per-document intel rows and per-notice summaries, but evidence rows for already-matched categories will be replaced; downstream UI consumers should not be affected.

## What landed

- **Implementation:** commits `ae81397` (Tasks 1-5: `no_bid_bond` context check, three new pattern categories `contract_ceiling` / `clin_structure` / `tech_specs`, value-capture enhancements on `naics_size_standard` and `wage_wd_number`), `183b3c3` (Task 6: 25 unit tests in `test_attachment_intel_extractor.py`), `33151ef` (added `--future-only` flag on the attachment-intel CLI — added during operational closeout, not in the original spec).
- **Smoke validation:** load 1058 (100 random force=True notices) produced 225 intel rows and 5,706 evidence rows; 678 of those evidence rows (~12%) came from the new categories — `tech_specs` (627), `clin_structure` (44), `contract_ceiling` (7). Confirms the new patterns produce real net-new signal on production data, not just on the planning sample. Combined-flag smoke test (load 1060, 100 future-only force notices) produced 336 intel rows and 17,150 evidence rows — roughly 3× richer per-notice than the random sample because active SOWs are more content-heavy than expired/closed notices.
- **`--future-only` flag (added during closeout, scope expansion beyond original spec):** wires up to the existing notion of "active or future-deadline" notices. Shrinks the force-mode universe from 23,286 notices to 6,806 active-future notices (~29% of corpus) — re-extracting on closed/expired opportunities is wasted work. Wired only on the attachment-intel CLI; NOT wired on description-intel (deferred — same logic would apply but was out of scope for this closeout).
- **Full corpus re-extraction (load 1061):** 6,574 future notices processed in 30 minutes (workers=4). Result: 20,926 intel rows + 947,012 evidence rows.
- **Backfill (`backfill opportunity-intel`):** 243 opportunities updated, 43,925 fields applied (43,829 by keyword frequency, 3 by AI, 93 fallback), 33 incumbent UEIs resolved.
- **Known transient — left as-is per user decision:** 22 of the 6,574 force-mode notices hit MySQL deadlocks during concurrent worker writes (workers=4 contending on summary rows under force mode). Their transactions rolled back and they kept their pre-existing intel. Acceptable — they will be picked up naturally by future amendments. **Worth a future small phase to add retry-on-deadlock logic in the per-notice write path, but explicitly NOT in scope for 125B.**

## Files Affected

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Add `no_bid_bond` context check; add 3 new pattern categories (`contract_ceiling`, `clin_structure`, `tech_specs`); enhance 2 existing patterns (`naics_size_standard`, `wage_wd_number`) to populate `value` |
| `fed_prospector/tests/test_attachment_intel_extractor.py` | New test cases for each new category and the `no_bid_bond` context filter |
| `fed_prospector/cli/attachments.py` (closeout addition) | New `--future-only` flag on `extract attachment-intel` to restrict force-mode universe to active/future-deadline notices |

No DDL changes. No new dependencies.

## Out of Scope

- **New columns on `opportunity_attachment_summary`** (e.g. `max_contract_ceiling_usd`, `clin_count`). Evidence rows already capture all data; UI/AI consumers can aggregate. Defer to a future phase if filter/sort by deal size becomes a concrete UI requirement.
- **AI analyzer prompt changes** (`fed_prospector/etl/attachment_ai_analyzer.py`). The AI analyzer already extracts richer semantic data; adding regex-style fields to its prompt would create double-extraction. Phase 125B is regex-only.
- **Submission deadline / proposal due date extraction** from attachment text — only 0.4% match rate in sample, and SAM.gov metadata already provides this. Skip.
- **Generic FAR/DFARS clause extraction** — 40% / 7% match rate but mostly boilerplate with no signal. Skip.
- **Q&A semantic content extraction** — better suited for AI analyzer; produced unicode-garbage matches in regex testing.
- **`--future-only` on description-intel CLI** — deferred. Same active/future-deadline filter would apply but was not wired during 125B closeout.
- **Retry-on-deadlock logic** for force-mode concurrent writes — 22 notices hit deadlocks in load 1061 and kept their prior intel; acceptable transient. Worth a small future phase, not 125B scope.
