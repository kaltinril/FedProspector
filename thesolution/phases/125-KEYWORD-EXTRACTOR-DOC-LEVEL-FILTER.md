# Phase 125: Keyword Extractor — Switch to Document-Level Filter

**Status:** PLANNED
**Priority:** Medium (silent data drift; affects amendment attachments)
**Depends on:** none
**Surfaced by:** Phase 124 verification — see [completed/124-ATTACHMENT-HASH-DEDUP.md](completed/124-ATTACHMENT-HASH-DEDUP.md) "Known Issues / Follow-ups".

## Problem

The keyword intel extractor in [`fed_prospector/etl/attachment_intel_extractor.py`](../../fed_prospector/etl/attachment_intel_extractor.py) selects work at the **notice level**, not the **document level**. Once any document on a notice produces a `document_intel_summary` row, the entire notice is excluded from re-processing.

When a SAM.gov notice gets amended later (new attachments added), the daily load extracts text from the new documents (`extraction_status='extracted'`), but the keyword extractor's notice-level filter sees that the notice "already has keyword intel" and skips the entire notice. The new documents never get keyword extraction, never get a `keyword_analyzed_at` timestamp, and never appear in any intel rollup.

### Current data (2026-04-28)

| Metric | Count |
|--------|-------|
| Documents with `extraction_status='extracted'` and `keyword_analyzed_at IS NULL` | 5,532 |
| ...of which sit on a notice that already has keyword summaries from sibling docs | **5,527 (99.9%)** |
| ...of which sit on a notice with no keyword summaries | 5 |

The 5,527 figure is the smoking gun: nearly every "missed" document is on a previously-processed notice.

### The faulty SQL

[`_fetch_eligible_notices`](../../fed_prospector/etl/attachment_intel_extractor.py) (around line 728) uses:

```sql
SELECT DISTINCT n.notice_id FROM (
  SELECT m.notice_id FROM opportunity_attachment m
  JOIN attachment_document ad ON ad.attachment_id = m.attachment_id
  WHERE ad.extraction_status = 'extracted' AND ad.extracted_text IS NOT NULL
  UNION
  SELECT notice_id FROM opportunity
  WHERE description_text IS NOT NULL AND description_text != ''
) n
LEFT JOIN opportunity_attachment_summary s
  ON n.notice_id = s.notice_id AND s.extraction_method = %s
WHERE s.summary_id IS NULL
ORDER BY n.notice_id
LIMIT %s
```

`s.summary_id IS NULL` filters out *whole notices* that have a summary, regardless of whether all documents on those notices were the source of that summary.

## Approach: Switch the attachment path to document-level filtering

Three-part fix:

1. **Eligibility query** in `_fetch_eligible_notices` (around line 728) — find notices that have at least one document with `keyword_analyzed_at IS NULL`. The query still returns notice_ids (preserves existing per-notice processing dispatch), but the inclusion criterion is "has unprocessed documents", not "has no summary".

2. **Sibling counter** in `_count_eligible_notices` (around line 803) — must use the SAME filter as `_fetch_eligible_notices`, otherwise the progress counter and the actual work queue will disagree and `pipeline-status` will report wrong numbers. Both functions are called from line 496-497; treat them as a pair.

3. **Per-notice processing loop** — when iterating a notice's documents, skip those where `keyword_analyzed_at IS NOT NULL`. Without this, a notice with mixed processed/unprocessed docs would re-pattern-match the already-done ones (waste CPU, but not destructive).

The `_description_only` branch must NOT change — descriptions really are per-notice (no document analog), and the current "skip if any summary exists" filter is correct there.

## Pre-implementation verification — DONE

Before any code change, the summary INSERT path needed to be classified to determine whether "second-pass" extractions on a notice that already has a summary row are safe. **Verified during phase planning (2026-04-28):**

`opportunity_attachment_summary` writes use `INSERT ... ON DUPLICATE KEY UPDATE` ([`attachment_intel_extractor.py:1707`](../../fed_prospector/etl/attachment_intel_extractor.py) and again at line 1715). This is the ✅ UPSERT case — new evidence from a re-extracted document merges into the existing summary row. **No schema migration needed; no upsert migration needed.** The fix is purely in `attachment_intel_extractor.py`.

## `--force` semantics post-fix

Decide and document:
- Today: `--force` skips the "exclude notices with summaries" filter and re-processes everything on selected notices.
- After fix: `--force` should override BOTH the notice-level eligibility check AND the per-document `keyword_analyzed_at IS NOT NULL` skip — i.e., truly reprocess all documents.

## Tasks

- [ ] **Task 1:** Modify `_fetch_eligible_notices` attachment path (around line 728) to filter by document-level `keyword_analyzed_at IS NULL` instead of notice-level summary existence. Leave the `_description_only` branch unchanged.
- [ ] **Task 2:** Apply the **same** filter change to `_count_eligible_notices` (around line 803). Both functions are called as a pair from line 496-497; if they disagree, the progress counter shown to the user during a run will be wrong.
- [ ] **Task 3:** Add per-document `keyword_analyzed_at IS NULL` skip inside the per-notice processing loop. The loop is in `_process_notice` (around line 898) — it's the function that iterates a notice's documents and calls the pattern extractor on each. Skip docs where `keyword_analyzed_at IS NOT NULL` unless `force=True` is passed (Task 4 pairs with this).
- [ ] **Task 4:** Update `--force` to override the new doc-level skip as well (truly reprocess all docs on selected notices). Existing `--force` behavior already deletes stale `opportunity_attachment_summary` rows for keyword/heuristic methods (around line 2011-2015) and the corresponding `document_intel_summary` rows (around line 2042-2045) — preserve that. The new `--force` semantics are *additive*: still delete those rows, AND override the per-doc `keyword_analyzed_at` skip from Task 3.
- [ ] **Task 5:** Add `INDEX idx_keyword_analyzed_at (keyword_analyzed_at)` to `attachment_document` in `fed_prospector/db/schema/tables/36_attachment.sql`. **Verified during planning (2026-04-28): no index exists today** — only the column declaration at line 47. The new query in Tasks 1-2 scans on `keyword_analyzed_at IS NULL` and would full-scan ~50K rows without the index. Apply to live DB (per project rule: keep DDL and live DB in sync).
- [ ] **Task 6:** Tests:
  - Notice where all docs are already analyzed → not selected
  - Notice with mixed analyzed/unanalyzed → selected, only unanalyzed processed (verify via `keyword_analyzed_at` after the run)
  - Notice with only unanalyzed → selected, all processed
  - `--force` reprocesses everything regardless of `keyword_analyzed_at`
  - `_count_eligible_notices` returns the same number as `len(_fetch_eligible_notices(... batch_size=large))`
  - Description-only path behavior unchanged (regression check)

  Reference style: model after `fed_prospector/tests/test_attachment_text_dedup.py` and `test_attachment_dedup_backfill.py` (added by Phase 124) — pytest, fixture-based, mocks `get_connection`.
- [ ] **Task 7:** Run `python fed_prospector/main.py extract attachment-intel` once after deploy to drain the 5,527-doc backlog. Confirm via `python fed_prospector/main.py health pipeline-status` that "Stage 3 Keyword Intel — remaining" drops to ~5 (the genuine other edge cases). The pipeline-status query that produces this metric lives in [`fed_prospector/cli/attachments.py`](../../fed_prospector/cli/attachments.py) (the `attachment_pipeline_status` command, around the "Stage 3" comment block).

## Files Affected

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Eligibility query in BOTH `_fetch_eligible_notices` and `_count_eligible_notices` (attachment path only); per-doc skip in processing loop; `--force` override |
| `fed_prospector/tests/test_attachment_intel_extractor.py` (new) | New test cases for mixed-state notices and counter/fetcher agreement |
| `fed_prospector/db/schema/tables/36_attachment.sql` | Add `INDEX idx_keyword_analyzed_at` on `attachment_document(keyword_analyzed_at)` (verified missing during planning). Apply to live DB in same step. |

## Out of Scope (decided 2026-04-28)

- **Race-condition mitigation between concurrent extractor runs.** The user manually serializes pipeline operations — no concurrent runs in practice. Skip `SELECT ... FOR UPDATE SKIP LOCKED` or advisory locks unless that operating model changes.
- **The Stage 4B (description intel) metric in `pipeline-status`.** Same metric-bug pattern as Stage 3 had before [`ddce9e0`](../../fed_prospector/cli/attachments.py), but description intel really IS per-notice — verify the bug exists there before fixing.

## Notes

- The 5 documents on notices with no keyword summaries are a separate edge case (likely empty extracted_text or other extractor-internal skip). Worth a quick query during Task 7 verification, but probably not worth scope expansion.
- Once this phase ships, the `pipeline-status` "Keyword Intel remaining" should genuinely reflect "documents the extractor needs to look at next time" — currently it only does after commit `ddce9e0` fixed the metric, but the *count itself* will only become small (≤ ~50 docs from the most recent load) once this filter bug is fixed.
- The Phase 124 dedup means `attachment_dedup_map`-resolved attachments never reach this code path at all (Layer 2 skips them before extraction). So the 5,527 figure is post-dedup and represents real, distinct documents.
- The existing `--force` path in `attachment_intel_extractor.py` includes summary-row cleanup before re-extraction (search for `_replace_source_rows` or similar `DELETE FROM opportunity_attachment_summary` calls). Task 4 should preserve that behavior — the new `--force` semantics are additive (also override the per-doc `keyword_analyzed_at` skip), not a rewrite of the existing force flow.
