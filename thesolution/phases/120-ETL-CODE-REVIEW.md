# Phase 120: ETL & Pipeline Code Review

**Status:** PLANNED
**Goal:** Fix bugs, improve performance, and increase accuracy in the core data loading and attachment pipeline commands.

This document captures findings from a comprehensive code review of the production ETL pipeline. Each finding includes severity, file location, and recommended fix.

## Validation Results -- 2026-04-23

All 28 findings were re-validated on 2026-04-23 (32 days after the original 2026-03-22 capture). Five parallel agents validated each finding against current code.

**Headline:**
- 5 findings (P1, P2, P3, P6, A2) are now FIXED by intervening phase work.
- 1 finding (O3) is PARTIALLY FIXED.
- 1 finding (P9) needs RE-TARGETING to a new table.
- The remaining 21 findings are still VALID with line-number updates applied.

**Phase scope (actual):** This phase covers `usaspending-bulk`, `opportunities`, `awards`, and the attachment pipeline -- 4 of ~14 ETL CLI command modules. A follow-up phase would be needed for `fedhier`, `exclusions`, `subaward`, `sca`, `bls`, `calc`, `spending`, `entities`, `agencies`, `normalize`, `backfill`, `demand`, and `load_batch`.

See the Implementation Plan section for the trimmed task list reflecting current state.

---

## Commands Reviewed

| Command | Primary Files |
|---------|--------------|
| `load usaspending-bulk` | `cli/bulk_spending.py`, `etl/usaspending_bulk_loader.py` |
| `load opportunities` | `cli/opportunities.py`, `etl/opportunity_loader.py`, `api_clients/sam_opportunity_client.py` |
| `load awards` | `cli/awards.py`, `etl/awards_loader.py`, `api_clients/sam_awards_client.py` |
| `download attachments` | `etl/attachment_downloader.py` |
| `extract attachment-text` | `etl/attachment_text_extractor.py` |
| `extract attachment-intel` | `etl/attachment_intel_extractor.py` |
| `cleanup attachment-files` | `etl/attachment_cleanup.py` |

All file paths are relative to `fed_prospector/`.

---

## Shared / Cross-Cutting Issues

### S1. MySQL 8.0.20+ VALUES() Deprecation (CRITICAL)

**Status (2026-04-23):** VALID -- lines updated to `etl/batch_upsert.py:57`, `etl/usaspending_bulk_loader.py:1298`. Note: row-alias `AS new` syntax was already adopted in `labor_normalizer.py`, `sca_loader.py`, `bls_loader.py` -- only `batch_upsert.py` and the bulk loader remain unmigrated.
**Files:** `etl/batch_upsert.py:57`, `etl/usaspending_bulk_loader.py:1298`
**Affects:** ALL loaders using batch upsert (opportunities, awards, usaspending, fedhier)

The code uses `VALUES()` in ON DUPLICATE KEY UPDATE clauses:
```python
update_parts.append(f"{c} = VALUES({c})")
```

`VALUES()` was deprecated in MySQL 8.0.20 and removed in later versions. The project runs MySQL 8.4.8 LTS. The correct syntax for MySQL 8.0.20+ is:
```sql
INSERT INTO t (...) VALUES (...) AS new ON DUPLICATE KEY UPDATE col = new.col
```

**Fix:** Update `build_upsert_sql()` in `batch_upsert.py` to use the row alias syntax. This is a single-file fix that resolves the issue for all loaders.

**Verification needed:** Confirm whether MySQL 8.4.8 actually throws an error or just a deprecation warning. If it's still a warning, this is HIGH not CRITICAL -- but it will break on the next MySQL upgrade regardless.

---

## 1. load usaspending-bulk

### U1. Checkpoint Resume Ignores Archive Hash (HIGH)

**Status (2026-04-23):** VALID -- lines updated to 1358-1364. The in-progress resume query (NOT the COMPLETE-checkpoint check at 1339-1346) is the one missing `archive_hash`.
**File:** `etl/usaspending_bulk_loader.py:1358-1364`

When resuming an in-progress load, the checkpoint query does not include `archive_hash`:
```python
cursor.execute(
    "SELECT ... FROM usaspending_load_checkpoint "
    "WHERE load_id = %s AND csv_file_name = %s",
    (load_id, csv_file_name),
)
```

If the user re-downloads a different archive version but the CSV filename matches, the loader resumes using the old checkpoint, mixing data from two different files.

**Fix:** Add `AND archive_hash = %s` to the WHERE clause.

### U2. Fiscal Year 0 Sentinel Causes Deduplication Failures (HIGH)

**Status (2026-04-23):** VALID -- lines updated to 307-308, 1149-1177.
**File:** `etl/usaspending_bulk_loader.py:307-308, 1149-1177`

Delta loads use `fiscal_year=0` as a sentinel. But `_derive_fiscal_year()` also returns `0` when it cannot parse the start date. This means valid delta records with null/bad dates get deduplicated as if they were from a previous load, causing silent data loss on re-runs.

**Fix:** Use a distinct sentinel (e.g., `-1`) for delta loads, or handle NULL fiscal years separately from the delta sentinel.

### U3. Resume Stats Double-Counting (HIGH)

**Status (2026-04-23):** VALID -- lines updated to 777-784.
**File:** `etl/usaspending_bulk_loader.py:777-784`

When resuming from a checkpoint, `stats["records_inserted"]` is initialized from the checkpoint's `total_rows_loaded`, then each new batch adds to it, and the checkpoint is updated with the cumulative total. On the next resume, the inflated total is loaded again. After N resumes, the same rows are counted N times.

**Fix:** Track `rows_loaded_this_session` separately from `total_rows_loaded_cumulative`.

### U4. Checkpoint Dedup Query is O(n^2) (MEDIUM)

**Status (2026-04-23):** VALID -- lines updated to 1496-1506.
**File:** `etl/usaspending_bulk_loader.py:1496-1506`

The NOT EXISTS subquery in the dedup check scans the checkpoint table for each row of the outer query. With many checkpoint rows across multiple FYs, this becomes quadratic.

**Fix:** Replace with GROUP BY / HAVING or add appropriate composite index.

### U5. Record Hash Never Computed (MEDIUM)

**Status (2026-04-23):** VALID -- line updated to 1272.
**File:** `etl/usaspending_bulk_loader.py:1272`

`record_hash` is hardcoded to `None`. The change detection system cannot detect updates for USASpending records, so duplicate records can be inserted across different loads.

**Fix:** Compute SHA-256 hash from a stable set of columns (e.g., piid, award_amount, vendor_name, dates).

### U6. TSV Write Errors Leave Corrupted Files (MEDIUM)

**Status (2026-04-23):** VALID -- lines updated to 742, 1000.
**File:** `etl/usaspending_bulk_loader.py:742, 1000`

TSV file writes are not wrapped in try/except. If disk fills mid-write, the partial TSV remains and LOAD DATA INFILE may skip malformed rows silently.

**Fix:** Write to a temp file and rename on success, or clean up on error.

### U7. VARCHAR Truncation Risk (MEDIUM)

**Status (2026-04-23):** VALID -- lines updated to 8, 47, 50.
**File:** `db/schema/tables/70_usaspending.sql:8, 47, 50`

Several VARCHAR columns may be too narrow for real data:
- `piid` VARCHAR(50) -- API contract IDs can exceed 50 chars
- `solicitation_identifier` VARCHAR(100)
- `pop_city` VARCHAR(100)

**Fix:** Audit actual data lengths from loaded records and widen as needed.

---

## 2. load opportunities

### O1. Insert/Update Stats Classification Bug (HIGH)

**Status (2026-04-23):** VALID -- lines updated to 229-235, 283-285, 301-302.
**File:** `etl/opportunity_loader.py:229-235, 283-285, 301-302`

Records are classified using hash comparison (`old_hash == new_hash`), but statistics are counted using a different check (`notice_id in existing_hashes`). A record with a changed hash is always counted as "updated" even if it's actually a new insert.

**Fix:** Use `old_hash is not None` for the statistics classification, consistent with the initial hash comparison.

### O2. Pagination Boundary Off-by-One (HIGH)

**Status (2026-04-23):** VALID -- lines updated to 454-457.
**File:** `api_clients/base_client.py:454-457`

When `offset == total` exactly, the loop breaks before checking whether there's a final partial page. The break condition should also check whether the last page returned fewer records than `page_size`.

**Fix:** Add `len(results) < page_size` as an additional break condition.

### O3. UEI Column Too Short (MEDIUM)

**Status (2026-04-23):** PARTIALLY FIXED -- `incumbent_uei` (line 31) is correctly VARCHAR(13). `awardee_uei` at line 41 is still VARCHAR(12) -- that's the only remaining work.
**File:** `db/schema/tables/30_opportunity.sql:41`

`awardee_uei` is VARCHAR(12) but SAM.gov UEIs are 13 characters. Data is silently truncated.

**Fix:** Change `awardee_uei` to VARCHAR(13) or CHAR(13). (`incumbent_uei` at line 31 is already corrected.)

### O4. POC Officer Lookup Race (MEDIUM)

**Status (2026-04-23):** VALID -- lines updated to 615-629.
**File:** `etl/opportunity_loader.py:615-629`

After upserting a contracting officer, `lastrowid` is 0 if the record already existed. The fallback SELECT can return None in edge cases (race condition, manual delete), causing the POC link to be silently skipped.

**Fix:** Use `SELECT ... FOR UPDATE` or query by the unique constraint deterministically.

### O5. Resource Links Double JSON Encoding (LOW)

**Status (2026-04-23):** VALID -- lines updated to 444-448.
**File:** `etl/opportunity_loader.py:444-448`

If `resourceLinks` is already a JSON string (not a dict/list), `json.dumps()` double-encodes it.

**Fix:** Check `isinstance(resource_links_raw, str)` and skip encoding if already a string.

### O6. Resume Query Missing Secondary Sort (LOW)

**Status (2026-04-23):** VALID -- lines unchanged (164-174).
**File:** `cli/opportunities.py:164-174`

The resume query sorts by `pages_fetched DESC` but has no tiebreaker. Old loads without `pages_fetched` all get `CAST(NULL AS UNSIGNED) = 0`, ordering them unpredictably.

**Fix:** Add `started_at DESC` as secondary sort.

### O7. Partial-Width Index on department_name (LOW)

**Status (2026-04-23):** VALID -- line updated to 68.
**File:** `db/schema/tables/30_opportunity.sql:68`

`KEY idx_opp_department (department_name(50))` uses a 50-char prefix on a 200-char column. Departments sharing the first 50 chars cause index collisions.

**Fix:** Use full-width index or shorten the column.

---

## 3. load awards

### A1. Set-Aside Code Not Validated (MEDIUM)

**Status (2026-04-23):** VALID -- lines unchanged (259, 433).
**File:** `cli/awards.py:259, 433`

Set-aside codes from CLI are passed directly to the SAM.gov API without validation. A typo like `--set-aside 8AA` silently returns 0 results while the load appears to complete successfully.

**Fix:** Validate against a whitelist of known SAM.gov set-aside codes before starting the load.

### A2. Fallback Upsert Path Doesn't Update last_load_id (MEDIUM)

**Status (2026-04-23):** FIXED -- `last_load_id` is in `_UPSERT_COLS` (line 53) and is included in the UPDATE clause via the existing VALUES() pattern, so the bug claimed here doesn't exist (S1's VALUES() deprecation still applies, but that's tracked separately).
**File:** `etl/awards_loader.py`

The batch upsert path correctly updates `last_load_id` via `VALUES()`. But the row-by-row fallback path (`_upsert_award()`) omits `last_load_id` from the UPDATE clause. When a batch fails and falls back to row-by-row, updated records lose their load tracking.

**Resolution:** On 2026-04-23 re-validation, `last_load_id` is present in `_UPSERT_COLS` (line 53) and included in the generated UPDATE clause for both batch and fallback paths. No additional code change required for this finding (S1 still applies separately).

### A3. Full Table Scan for Hash Cache (LOW-MEDIUM)

**Status (2026-04-23):** VALID with nuance -- lines unchanged (517-551). Index `idx_fpds_hash` exists per `40_federal.sql:91` but the query uses `WHERE record_hash IS NOT NULL` which doesn't leverage it for incremental loading; full scan still happens.
**File:** `etl/awards_loader.py:517-551`

Every awards load scans the entire `fpds_contract` table to build an in-memory hash dict (500K+ rows). This takes 200-500ms per invocation.

**Fix:** Add index on `fpds_contract(record_hash)`, or fetch only records modified since last load using `last_load_id`.

### A4. NAICS Code Not Validated (LOW)

**Status (2026-04-23):** VALID -- line unchanged (245).
**File:** `cli/awards.py:245`

NAICS codes are not validated as 6-digit numbers. Invalid codes silently return 0 results.

**Fix:** Validate format before starting the load.

### A5. Offset/Page Parameter Naming Confusion (LOW)

**Status (2026-04-23):** VALID -- line unchanged (438).
**File:** `cli/awards.py:438`

The CLI passes `offset=page` where `page` is a page index (0, 1, 2...), not a record offset. This accidentally works because SAM.gov treats offset as page index, but is confusing and fragile.

**Fix:** Rename internal variable to `page` for clarity. Add a comment documenting SAM.gov's non-standard behavior.

---

## 4. Attachment Pipeline

### P1. Intel Consolidation Overwrites Per-Source Rows (CRITICAL)

**Status (2026-04-23):** FIXED -- architecture redesigned by Phase 110H+. Per-document rows now insert with real `document_id`, no NULL collision.
**File:** `etl/attachment_intel_extractor.py:926-976`

When multiple sources exist (attachment + description_text), the per-source loop creates an intel row with `attachment_id=NULL` for description_text. Then the consolidation block creates another row with `attachment_id=NULL`. Due to the UNIQUE constraint `(notice_id, attachment_id, extraction_method)`, the second INSERT updates the first via ON DUPLICATE KEY UPDATE, and `_replace_source_rows` deletes the description_text-specific source rows.

**Result:** Description_text-specific source rows are lost; provenance tracking breaks.

**Resolution:** Phase 110H+ redesigned the intel architecture. Per-document rows now insert with a real `document_id` instead of relying on `attachment_id=NULL`, eliminating the UNIQUE-constraint collision. No further work required.

### P2. Incomplete Notice Filtering in Eligible Query (CRITICAL)

**Status (2026-04-23):** FIXED -- query now JOINs `opportunity_attachment -> attachment_document -> sam_attachment` keying on `m.attachment_id`, processing each attachment independently.
**File:** `etl/attachment_intel_extractor.py:1012-1017`

The LEFT JOIN to find unprocessed notices matches only on `notice_id`, not `attachment_id`. A notice with 3 attachments where only 1 has intel is excluded entirely, causing the other 2 attachments to never get processed.

**Resolution:** The eligible-notice query was rewritten to join through `opportunity_attachment -> attachment_document -> sam_attachment` keyed on `m.attachment_id`. Each attachment is now evaluated independently. No further work required.

### P3. Duplicate Consolidated Row for Single Attachments (HIGH)

**Status (2026-04-23):** FIXED -- consolidation logic redesigned. Opportunity summary row is created once per notice, no per-attachment NULL rows.
**File:** `etl/attachment_intel_extractor.py:926-976`

Condition `if len(sources) > 1 or (len(sources) == 1 and sources[0][0] is not None)` creates a consolidated NULL-attachment row even for single attachments. The comment says "if multiple sources" but the code includes single attachments too.

**Resolution:** Consolidation was redesigned alongside P1's architecture change. The opportunity summary row is now produced once per notice and per-attachment rows carry real `document_id` values. The duplicate-row condition no longer exists.

### P4. Empty Text Extraction Misclassified as Scanned (MEDIUM)

**Status (2026-04-23):** VALID -- lines unchanged (854-856).
**File:** `etl/attachment_text_extractor.py:854-856`

When text extraction produces no content, the file is marked `is_scanned=True` even if it wasn't scanned -- it may have been a genuinely empty document or extraction failure. This conflates three states.

**Fix:** Only set `is_scanned=True` when OCR was actually attempted.

### P5. No Recovery for Failed Attachments After 10 Retries (MEDIUM)

**Status (2026-04-23):** VALID -- line updated to 1156. Phase 131 added per-attachment re-analysis; quick-check whether that already provides a reset path before scheduling new work.
**File:** `etl/attachment_text_extractor.py:1156`

Files that fail extraction 10 times are permanently stuck with no way to reset or force re-extraction.

**Fix:** Add a `--reset-retries` CLI flag or a command to reset retry counts for specific attachment IDs.

### P6. No Intel Row for Attachments With Zero Matches (MEDIUM)

**Status (2026-04-23):** FIXED -- intentional design change. Zero-match documents skip the intel row but stamp `keyword_analyzed_at` to distinguish "not processed" from "processed, no matches."
**File:** `etl/attachment_intel_extractor.py:930-934`

Attachments with extracted text but zero pattern matches don't get an intel row. You can't distinguish "not processed" from "processed, no matches."

**Resolution:** The pipeline was changed to stamp `keyword_analyzed_at` on the source document for zero-match cases instead of writing an empty intel row. Provenance is preserved without bloating the intel table. No further work required.

### P7. Redundant file.close() in Context Manager (LOW)

**Status (2026-04-23):** VALID -- lines updated to 687-693.
**File:** `etl/attachment_downloader.py:687-693`

Explicit `f.close()` inside a `with open()` block. The file gets closed twice.

**Fix:** Remove the explicit `f.close()`. Let the context manager handle cleanup (break or raise to exit the loop).

### P8. Cleanup Query Double EXISTS (LOW)

**Status (2026-04-23):** VALID (re-targeted) -- lines unchanged (149-158). Already noted as STALE in the original doc; the cleanup code now correctly targets `document_intel_summary`, but the double-EXISTS pattern persists against the new table -- the optimization is still worth doing.
**File:** `etl/attachment_cleanup.py:149-158`

Two separate EXISTS subqueries on `opportunity_attachment_intel` for keyword and AI methods. Could be combined into one query.

> **STALE (Phase 110ZZZ):** `opportunity_attachment_intel` was replaced by `document_intel_summary`. The cleanup code has been updated accordingly.

**Fix:** Use a single subquery with `COUNT(DISTINCT ...)` or `GROUP BY ... HAVING`.

### P9. Missing Index on extraction_method (LOW)

**Status (2026-04-23):** STALE -- retargeted to the new `document_intel_summary` table in `db/schema/tables/36_attachment.sql` (~lines 66-95). The new table has a UNIQUE index on `(document_id, extraction_method)` (line 93) but no standalone index on `extraction_method`. Cleanup queries scan with `extraction_method IN (...)` and need this index.
**File:** `db/schema/tables/36_attachment.sql` (`document_intel_summary` table, ~lines 66-95)

The `extraction_method` column is used in WHERE and EXISTS clauses across multiple queries but has no standalone index.

> **STALE (Phase 110ZZZ):** `opportunity_attachment_intel` was replaced by `document_intel_summary`. Index recommendations should target the new table.

**Fix:** Add a standalone index on `document_intel_summary(extraction_method)` to support cleanup queries that filter with `extraction_method IN (...)`. The existing UNIQUE `(document_id, extraction_method)` index does not help because the leading column is `document_id`.

---

## Implementation Plan

Reflects the 2026-04-23 re-validation. Five findings (P1, P2, P3, P6, A2) were closed by intervening phase work and are excluded from active tasks but listed for traceability. P9 has been retargeted to the new `document_intel_summary` table.

### Priority 1 -- Blocking / Data Loss Bugs (VERIFY-FIRST)
| Task | Finding | Effort | Notes |
|------|---------|--------|-------|
| Verify S1 -- does MySQL 8.4.8 throw an error or just a warning for VALUES()? | S1 | Trivial -- single test query | Decides whether S1 is CRITICAL or HIGH. Block other batch_upsert work until decided. |
| Fix VALUES() deprecation in `batch_upsert.py` (and `usaspending_bulk_loader.py:1298`) | S1 | Small -- single helper | Affects all batch-upsert loaders |
| Fix in-progress checkpoint resume to include `archive_hash` | U1 | Small | |
| Fix FY=0 sentinel collision | U2 | Small | |

### Priority 2 -- Incorrect Data / Silent Failures
| Task | Finding | Effort |
|------|---------|--------|
| Fix opportunity insert/update stats classification | O1 | Small |
| Fix pagination boundary off-by-one | O2 | Small |
| Widen `awardee_uei` to VARCHAR(13) | O3 | Small (ALTER TABLE) |
| Fix resume stats double-counting | U3 | Small |
| ~~Fix duplicate consolidated row~~ -- Removed (P3 FIXED) | -- | -- |
| ~~Fix intel consolidation overwrite~~ -- Removed (P1 FIXED) | -- | -- |
| ~~Fix eligible notice query join~~ -- Removed (P2 FIXED) | -- | -- |
| ~~Fix fallback upsert last_load_id~~ -- Removed (A2 FIXED) | -- | -- |

### Priority 3 -- Performance & Quality
| Task | Finding | Effort |
|------|---------|--------|
| Compute USASpending record hash | U5 | Medium |
| Optimize checkpoint dedup query | U4 | Small |
| Optimize hash cache loading (or use `last_load_id` filter) | A3 | Small |
| Add `extraction_method` index on `document_intel_summary` | P9 (retargeted) | Small |
| ~~Add empty-match intel rows~~ -- Removed (P6 FIXED by design change) | -- | -- |
| Add retry reset mechanism | P5 | Small (verify whether Phase 131 covers this) |
| Validate set-aside codes | A1 | Small |

### Priority 4 -- Low / Cosmetic
| Task | Finding | Effort |
|------|---------|--------|
| Fix resource links double encoding | O5 | Small |
| Fix resume query secondary sort | O6 | Small |
| Clean up redundant `file.close()` | P7 | Trivial |
| Optimize cleanup EXISTS queries | P8 | Small |
| Rename `offset`->`page` variable | A5 | Trivial |
| Validate NAICS codes | A4 | Small |
| Audit VARCHAR widths in `70_usaspending.sql` | U7 | Small (investigation + ALTER) |
| Fix POC officer lookup race | O4 | Medium (warning is logged, not silent -- lower urgency) |
| TSV write error handling | U6 | Small |
| Wider/full index on `department_name` | O7 | Small |

---

## Acceptance Criteria

A finding is "done" when ALL of the following are true:
1. Code change merged on the branch and visible in main
2. Affected loaders run end-to-end without errors against staging data
3. For data-loss findings (S1, U1, U2, U3, P1, P2, A2): a regression test exists or a manual verification log entry is recorded in this phase doc
4. For schema findings (O3, U7, P9): the DDL file is updated AND the live database has been altered (per CLAUDE.md rule #9)
5. The phase doc finding is updated with `**Status:** RESOLVED -- <commit hash>`

## Notes

- Findings re-validated 2026-04-23. Line numbers in this doc reflect that validation; further drift requires re-checking before edit.
- Five findings (P1, P2, P3, P6, A2) were closed by intervening phase work (110H, 110ZZZ, 121, 131). They remain in the doc above for traceability but are excluded from the Implementation Plan.
- S1 (VALUES() deprecation) is the only finding whose severity is unresolved -- verify behavior on MySQL 8.4.8 LTS before scheduling.
- This phase is intentionally scoped to SAM/USASpending/Attachments. A future Phase 120B should cover the remaining ETL CLI modules (fedhier, exclusions, subaward, sca, bls, calc, spending, entities, agencies, normalize, backfill, demand, load_batch).
