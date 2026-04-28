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

Two-part fix:

1. **Eligibility query** — find notices that have at least one document with `keyword_analyzed_at IS NULL`. The query still returns notice_ids (preserves existing per-notice processing dispatch), but the inclusion criterion is "has unprocessed documents", not "has no summary".

2. **Per-notice processing loop** — when iterating a notice's documents, skip those where `keyword_analyzed_at IS NOT NULL`. Without this, a notice with mixed processed/unprocessed docs would re-pattern-match the already-done ones (waste CPU, but not destructive).

The `_description_only` branch must NOT change — descriptions really are per-notice (no document analog), and the current "skip if any summary exists" filter is correct there.

## CRITICAL: Verify before implementing

Before any code change, **read the summary INSERT path** in `attachment_intel_extractor.py` (and any helpers it calls). The fix only works if the summary write semantics are safe for "second-pass" extractions on a notice that already has a summary row. Three possibilities:

| Behavior | Outcome | Action |
|---|---|---|
| ✅ UPSERT (`INSERT ... ON DUPLICATE KEY UPDATE`) | New evidence merges into existing summary | No extra work — fix is just the WHERE clause |
| ⚠️ `INSERT IGNORE` on `(notice_id, extraction_method)` | New evidence is silently dropped | Must add UPSERT migration to scope |
| ⚠️ Plain `INSERT` with no unique constraint | Duplicate summary rows per notice — corrupts downstream queries | Must add unique constraint AND UPSERT migration |

**Document the answer in this file before starting Task 2.** If it's anything other than UPSERT, scope grows.

## `--force` semantics post-fix

Decide and document:
- Today: `--force` skips the "exclude notices with summaries" filter and re-processes everything on selected notices.
- After fix: `--force` should override BOTH the notice-level eligibility check AND the per-document `keyword_analyzed_at IS NOT NULL` skip — i.e., truly reprocess all documents.

## Tasks

- [ ] **Task 1:** Verify the `opportunity_attachment_summary` INSERT semantics in `attachment_intel_extractor.py`. Document the result in this phase doc under "CRITICAL: Verify". If anything other than UPSERT, expand the task list to include the upsert migration.
- [ ] **Task 2:** Modify `_fetch_eligible_notices` attachment path to filter by document-level `keyword_analyzed_at IS NULL` instead of notice-level summary existence. Leave `_description_only` branch unchanged.
- [ ] **Task 3:** Add per-document `keyword_analyzed_at IS NULL` skip inside the per-notice processing loop, so mixed notices don't re-pattern-match completed docs.
- [ ] **Task 4:** Update `--force` to override the new doc-level skip as well (truly reprocess all docs on selected notices).
- [ ] **Task 5:** Tests:
  - Notice where all docs are already analyzed → not selected
  - Notice with mixed analyzed/unanalyzed → selected, only unanalyzed processed (verify via `keyword_analyzed_at` after the run)
  - Notice with only unanalyzed → selected, all processed
  - `--force` reprocesses everything regardless of `keyword_analyzed_at`
  - Description-only path behavior unchanged (regression check)
- [ ] **Task 6:** Run keyword extraction once after deploy to drain the 5,527-doc backlog. Confirm via `pipeline-status` that the "Keyword Intel remaining" count drops to ~5 (the genuine other edge cases).
- [ ] **Task 7:** If verification (Task 1) revealed `INSERT IGNORE` or no constraint, add the upsert migration as a separate task before Task 2.

## Files Affected

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Eligibility query (attachment path only); per-doc skip in processing loop; `--force` override |
| `fed_prospector/tests/test_attachment_intel_extractor.py` (new or existing) | New test cases for mixed-state notices |
| `fed_prospector/db/schema/tables/*` | (Conditional) summary upsert constraint, only if Task 1 reveals it's missing |

## Out of Scope (decided 2026-04-28)

- **Race-condition mitigation between concurrent extractor runs.** The user manually serializes pipeline operations — no concurrent runs in practice. Skip `SELECT ... FOR UPDATE SKIP LOCKED` or advisory locks unless that operating model changes.
- **The Stage 4B (description intel) metric in `pipeline-status`.** Same metric-bug pattern as Stage 3 had before [`ddce9e0`](../../fed_prospector/cli/attachments.py), but description intel really IS per-notice — verify the bug exists there before fixing.

## Notes

- The 5 documents on notices with no keyword summaries are a separate edge case (likely empty extracted_text or other extractor-internal skip). Worth a quick query during Task 6 verification, but probably not worth scope expansion.
- Once this phase ships, the `pipeline-status` "Keyword Intel remaining" should genuinely reflect "documents the extractor needs to look at next time" — currently it only does after [`ddce9e0`](../../fed_prospector/cli/attachments.py) fixed the metric, but the *count itself* will only become small (≤ ~50 docs from the most recent load) once this filter bug is fixed.
- The Phase 124 dedup means `attachment_dedup_map`-resolved attachments never reach this code path at all (Layer 2 skips them before extraction). So the 5,527 figure is post-dedup and represents real, distinct documents.
