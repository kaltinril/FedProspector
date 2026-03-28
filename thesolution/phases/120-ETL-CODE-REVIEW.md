# Phase 120: ETL & Pipeline Code Review

**Status:** PLANNED
**Goal:** Fix bugs, improve performance, and increase accuracy in the core data loading and attachment pipeline commands.

This document captures findings from a comprehensive code review of the production ETL pipeline. Each finding includes severity, file location, and recommended fix.

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

**Files:** `etl/batch_upsert.py:57`, `etl/usaspending_bulk_loader.py:1280`
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

**File:** `etl/usaspending_bulk_loader.py:1340-1346`

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

**File:** `etl/usaspending_bulk_loader.py:300-301, 1130-1159, 1461-1498`

Delta loads use `fiscal_year=0` as a sentinel. But `_derive_fiscal_year()` also returns `0` when it cannot parse the start date. This means valid delta records with null/bad dates get deduplicated as if they were from a previous load, causing silent data loss on re-runs.

**Fix:** Use a distinct sentinel (e.g., `-1`) for delta loads, or handle NULL fiscal years separately from the delta sentinel.

### U3. Resume Stats Double-Counting (HIGH)

**File:** `etl/usaspending_bulk_loader.py:759-813`

When resuming from a checkpoint, `stats["records_inserted"]` is initialized from the checkpoint's `total_rows_loaded`, then each new batch adds to it, and the checkpoint is updated with the cumulative total. On the next resume, the inflated total is loaded again. After N resumes, the same rows are counted N times.

**Fix:** Track `rows_loaded_this_session` separately from `total_rows_loaded_cumulative`.

### U4. Checkpoint Dedup Query is O(n^2) (MEDIUM)

**File:** `etl/usaspending_bulk_loader.py:1478-1490`

The NOT EXISTS subquery in the dedup check scans the checkpoint table for each row of the outer query. With many checkpoint rows across multiple FYs, this becomes quadratic.

**Fix:** Replace with GROUP BY / HAVING or add appropriate composite index.

### U5. Record Hash Never Computed (MEDIUM)

**File:** `etl/usaspending_bulk_loader.py:1254`

`record_hash` is hardcoded to `None`. The change detection system cannot detect updates for USASpending records, so duplicate records can be inserted across different loads.

**Fix:** Compute SHA-256 hash from a stable set of columns (e.g., piid, award_amount, vendor_name, dates).

### U6. TSV Write Errors Leave Corrupted Files (MEDIUM)

**File:** `etl/usaspending_bulk_loader.py:724-732`

TSV file writes are not wrapped in try/except. If disk fills mid-write, the partial TSV remains and LOAD DATA INFILE may skip malformed rows silently.

**Fix:** Write to a temp file and rename on success, or clean up on error.

### U7. VARCHAR Truncation Risk (MEDIUM)

**File:** `db/schema/tables/70_usaspending.sql:7-50`

Several VARCHAR columns may be too narrow for real data:
- `piid` VARCHAR(50) -- API contract IDs can exceed 50 chars
- `solicitation_identifier` VARCHAR(100)
- `pop_city` VARCHAR(100)

**Fix:** Audit actual data lengths from loaded records and widen as needed.

---

## 2. load opportunities

### O1. Insert/Update Stats Classification Bug (HIGH)

**File:** `etl/opportunity_loader.py:189-195, 244-245`

Records are classified using hash comparison (`old_hash == new_hash`), but statistics are counted using a different check (`notice_id in existing_hashes`). A record with a changed hash is always counted as "updated" even if it's actually a new insert.

**Fix:** Use `old_hash is not None` for the statistics classification, consistent with the initial hash comparison.

### O2. Pagination Boundary Off-by-One (HIGH)

**File:** `api_clients/base_client.py:455-457`

When `offset == total` exactly, the loop breaks before checking whether there's a final partial page. The break condition should also check whether the last page returned fewer records than `page_size`.

**Fix:** Add `len(results) < page_size` as an additional break condition.

### O3. UEI Column Too Short (MEDIUM)

**File:** `db/schema/tables/30_opportunity.sql:37`

`awardee_uei` is VARCHAR(12) but SAM.gov UEIs are 13 characters. Data is silently truncated.

**Fix:** Change to VARCHAR(13) or CHAR(13). Also check `incumbent_uei` (line 29).

### O4. POC Officer Lookup Race (MEDIUM)

**File:** `etl/opportunity_loader.py:561-577`

After upserting a contracting officer, `lastrowid` is 0 if the record already existed. The fallback SELECT can return None in edge cases (race condition, manual delete), causing the POC link to be silently skipped.

**Fix:** Use `SELECT ... FOR UPDATE` or query by the unique constraint deterministically.

### O5. Resource Links Double JSON Encoding (LOW)

**File:** `etl/opportunity_loader.py:404-408`

If `resourceLinks` is already a JSON string (not a dict/list), `json.dumps()` double-encodes it.

**Fix:** Check `isinstance(resource_links_raw, str)` and skip encoding if already a string.

### O6. Resume Query Missing Secondary Sort (LOW)

**File:** `cli/opportunities.py:164-174`

The resume query sorts by `pages_fetched DESC` but has no tiebreaker. Old loads without `pages_fetched` all get `CAST(NULL AS UNSIGNED) = 0`, ordering them unpredictably.

**Fix:** Add `started_at DESC` as secondary sort.

### O7. Partial-Width Index on department_name (LOW)

**File:** `db/schema/tables/30_opportunity.sql:62`

`KEY idx_opp_department (department_name(50))` uses a 50-char prefix on a 200-char column. Departments sharing the first 50 chars cause index collisions.

**Fix:** Use full-width index or shorten the column.

---

## 3. load awards

### A1. Set-Aside Code Not Validated (MEDIUM)

**File:** `cli/awards.py:259, 433`

Set-aside codes from CLI are passed directly to the SAM.gov API without validation. A typo like `--set-aside 8AA` silently returns 0 results while the load appears to complete successfully.

**Fix:** Validate against a whitelist of known SAM.gov set-aside codes before starting the load.

### A2. Fallback Upsert Path Doesn't Update last_load_id (MEDIUM)

**File:** `etl/awards_loader.py:284-306, 569-573`

The batch upsert path correctly updates `last_load_id` via `VALUES()`. But the row-by-row fallback path (`_upsert_award()`) omits `last_load_id` from the UPDATE clause. When a batch fails and falls back to row-by-row, updated records lose their load tracking.

**Fix:** Add `last_load_id` to the UPDATE clause in `_upsert_award()`.

### A3. Full Table Scan for Hash Cache (LOW-MEDIUM)

**File:** `etl/awards_loader.py:517-551`

Every awards load scans the entire `fpds_contract` table to build an in-memory hash dict (500K+ rows). This takes 200-500ms per invocation.

**Fix:** Add index on `fpds_contract(record_hash)`, or fetch only records modified since last load using `last_load_id`.

### A4. NAICS Code Not Validated (LOW)

**File:** `cli/awards.py:245`

NAICS codes are not validated as 6-digit numbers. Invalid codes silently return 0 results.

**Fix:** Validate format before starting the load.

### A5. Offset/Page Parameter Naming Confusion (LOW)

**File:** `cli/awards.py:438`

The CLI passes `offset=page` where `page` is a page index (0, 1, 2...), not a record offset. This accidentally works because SAM.gov treats offset as page index, but is confusing and fragile.

**Fix:** Rename internal variable to `page` for clarity. Add a comment documenting SAM.gov's non-standard behavior.

---

## 4. Attachment Pipeline

### P1. Intel Consolidation Overwrites Per-Source Rows (CRITICAL)

**File:** `etl/attachment_intel_extractor.py:359-381`

When multiple sources exist (attachment + description_text), the per-source loop creates an intel row with `attachment_id=NULL` for description_text. Then the consolidation block creates another row with `attachment_id=NULL`. Due to the UNIQUE constraint `(notice_id, attachment_id, extraction_method)`, the second INSERT updates the first via ON DUPLICATE KEY UPDATE, and `_replace_source_rows` deletes the description_text-specific source rows.

**Result:** Description_text-specific source rows are lost; provenance tracking breaks.

**Fix:** The consolidation block condition at line 360 should be `if len(sources) > 1:` (not `or single attachment`). Or skip description_text from the per-source loop and only include it in the consolidated row.

### P2. Incomplete Notice Filtering in Eligible Query (CRITICAL)

**File:** `etl/attachment_intel_extractor.py:290-303`

The LEFT JOIN to find unprocessed notices matches only on `notice_id`, not `attachment_id`. A notice with 3 attachments where only 1 has intel is excluded entirely, causing the other 2 attachments to never get processed.

**Fix:** Join on `(notice_id, attachment_id)` or use a more granular query that checks per-attachment completion.

### P3. Duplicate Consolidated Row for Single Attachments (HIGH)

**File:** `etl/attachment_intel_extractor.py:360`

Condition `if len(sources) > 1 or (len(sources) == 1 and sources[0][0] is not None)` creates a consolidated NULL-attachment row even for single attachments. The comment says "if multiple sources" but the code includes single attachments too.

**Fix:** Change condition to `if len(sources) > 1:`.

### P4. Empty Text Extraction Misclassified as Scanned (MEDIUM)

**File:** `etl/attachment_text_extractor.py:854-856`

When text extraction produces no content, the file is marked `is_scanned=True` even if it wasn't scanned -- it may have been a genuinely empty document or extraction failure. This conflates three states.

**Fix:** Only set `is_scanned=True` when OCR was actually attempted.

### P5. No Recovery for Failed Attachments After 10 Retries (MEDIUM)

**File:** `etl/attachment_text_extractor.py:1042`

Files that fail extraction 10 times are permanently stuck with no way to reset or force re-extraction.

**Fix:** Add a `--reset-retries` CLI flag or a command to reset retry counts for specific attachment IDs.

### P6. No Intel Row for Attachments With Zero Matches (MEDIUM)

**File:** `etl/attachment_intel_extractor.py:341-343`

Attachments with extracted text but zero pattern matches don't get an intel row. You can't distinguish "not processed" from "processed, no matches."

**Fix:** Create a row with empty intel JSON for processed-but-empty attachments.

### P7. Redundant file.close() in Context Manager (LOW)

**File:** `etl/attachment_downloader.py:411`

Explicit `f.close()` inside a `with open()` block. The file gets closed twice.

**Fix:** Remove the explicit `f.close()`. Let the context manager handle cleanup (break or raise to exit the loop).

### P8. Cleanup Query Double EXISTS (LOW)

**File:** `etl/attachment_cleanup.py:149-158`

Two separate EXISTS subqueries on `opportunity_attachment_intel` for keyword and AI methods. Could be combined into one query.

> **STALE (Phase 110ZZZ):** `opportunity_attachment_intel` was replaced by `document_intel_summary`. The cleanup code has been updated accordingly.

**Fix:** Use a single subquery with `COUNT(DISTINCT ...)` or `GROUP BY ... HAVING`.

### P9. Missing Index on extraction_method (LOW)

**File:** `db/schema/tables/36_attachment.sql`

The `extraction_method` column is used in WHERE and EXISTS clauses across multiple queries but has no index.

> **STALE (Phase 110ZZZ):** `opportunity_attachment_intel` was replaced by `document_intel_summary`. Index recommendations should target the new table.

**Fix:** Add index on `opportunity_attachment_intel(extraction_method)` or a composite index `(attachment_id, extraction_method)`.

---

## Implementation Plan

### Priority 1 -- Blocking / Data Loss Bugs
| Task | Finding | Estimated Effort |
|------|---------|-----------------|
| Fix VALUES() deprecation in batch_upsert.py | S1 | Small -- single file |
| Fix checkpoint resume to include archive_hash | U1 | Small |
| Fix FY=0 sentinel collision | U2 | Small |
| Fix intel consolidation overwrite | P1 | Medium |
| Fix eligible notice query join | P2 | Small |

### Priority 2 -- Incorrect Data / Silent Failures
| Task | Finding | Estimated Effort |
|------|---------|-----------------|
| Fix opportunity insert/update stats | O1 | Small |
| Fix pagination boundary | O2 | Small |
| Fix UEI column width | O3 | Small (ALTER TABLE) |
| Fix resume stats double-counting | U3 | Small |
| Fix fallback upsert last_load_id | A2 | Small |
| Fix duplicate consolidated row | P3 | Small |
| Validate set-aside codes | A1 | Small |

### Priority 3 -- Performance & Quality
| Task | Finding | Estimated Effort |
|------|---------|-----------------|
| Compute USASpending record hash | U5 | Medium |
| Optimize checkpoint dedup query | U4 | Small |
| Optimize hash cache loading | A3 | Small |
| Add extraction_method index | P9 | Small |
| Add empty-match intel rows | P6 | Small |
| Add retry reset mechanism | P5 | Small |

### Priority 4 -- Low / Cosmetic
| Task | Finding | Estimated Effort |
|------|---------|-----------------|
| Fix resource links double encoding | O5 | Small |
| Fix resume query sort | O6 | Small |
| Clean up redundant file.close() | P7 | Trivial |
| Optimize cleanup EXISTS queries | P8 | Small |
| Rename offset->page variable | A5 | Trivial |
| Validate NAICS codes | A4 | Small |

---

## Notes

- All line numbers reference code as of 2026-03-22. Lines may shift after edits.
- Finding S1 (VALUES() deprecation) should be verified against actual MySQL 8.4.8 behavior before starting -- if it's still just a warning, priority can be lowered.
- Findings were identified through static code review, not runtime testing. Some "bugs" may be mitigated by runtime behavior not visible in code.
