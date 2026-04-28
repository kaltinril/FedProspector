# Phase 124: Attachment Hash-Level Deduplication

**Status:** COMPLETE (2026-04-28) — all 11 tasks built, tested, and rolled out; backfill executed against live DB. 7,887 dedup_map entries populated (3,228 content_hash + 4,659 text_hash). Layers 2/3/4 are now active for all incoming loads.
**Priority:** Medium
**Depends on:** Phase 110ZZZ (Attachment Deduplication — resource_guid level)

## Problem

Phase 110ZZZ deduplicated attachments by `resource_guid` (the GUID in the SAM.gov download URL). This correctly prevents downloading the same URL twice, but misses two additional levels of duplication:

1. **Same file bytes, different URL** — The government uploads the same file under multiple URLs (e.g., reposting across amendments). Different `resource_guid`, identical `content_hash`.
2. **Same extracted text, different file** — A .docx and .pdf of the same SOW, or a re-exported PDF. Different file bytes, identical `text_hash`.

Both hashes are already computed and stored but **never checked for duplicates**.

## Pre-backfill Data (2026-03-27, original sample)

| Metric | Count |
|--------|-------|
| Total `sam_attachment` rows | 26,229 |
| Total `attachment_document` rows | 26,244 |
| Rows with `content_hash` | 25,994 |
| Rows with `text_hash` | 24,698 |
| `content_hash` duplicate groups | 622 (covering 1,803 rows — 1,181 redundant extractions) |
| `text_hash` duplicate groups | 625 (covering 3,454 rows — 2,829 redundant intel/AI runs) |
| Largest `content_hash` group | 31 rows (same file downloaded 31 times) |
| Largest `text_hash` group | 476 rows (same text extracted 476 times) |

By the time the backfill ran (2026-04-27, after ~4 weeks of additional loads), duplicate counts had grown to 1,677 content_hash groups and 1,803 text_hash groups (3,480 total).

**Original impact estimate:** ~1,181 unnecessary text extractions, ~2,829 unnecessary keyword intel runs, and ~2,829 unnecessary AI analysis API calls (~$85 wasted at Haiku pricing). Redundant `document_intel_evidence` rows also inflated query results.

## Post-backfill State (2026-04-28)

| Metric | Count |
|--------|-------|
| Total `sam_attachment` rows | 57,484 |
| Total `attachment_document` rows | 49,922 |
| Rows with `content_hash` | 57,107 |
| Rows with `text_hash` | 48,418 |
| `attachment_dedup_map` entries (Layer 3) | 3,228 |
| `attachment_dedup_map` entries (Layer 4) | 4,659 |
| `attachment_dedup_map` entries (total) | 7,887 |
| `content_hash` duplicate groups remaining | 0 |
| `text_hash` duplicate groups remaining | 1 (residual edge case — see Known Issues) |

**Backfill outcome:** 17,231 `opportunity_attachment` rows remapped to canonicals; 10,803 redundant `attachment_document` rows deleted; 58,062 redundant `document_intel_evidence` and 3,730 redundant `document_intel_summary` rows pruned. ~$236.61 in projected forward-looking AI cost avoidance once AI analysis ramps up across the canonical set. Files were already removed by `attachment_cleanup` so 0 bytes were freed by the backfill itself.

## Known Issues / Follow-ups

- **One residual text_hash dup group (3 rows).** All three documents have `keyword_analyzed_at` set but no `document_intel_summary` row (the keyword extractor produced no findings for this file). The Layer 4 backfill query requires the canonical candidate to have a summary row (signal of "fully processed"); when no candidate satisfies this, the group is skipped. Affects very few rows and self-resolves once any of the three eventually gets an AI summary. If we want zero residual at all times, relax the canonical predicate to "any candidate with `keyword_analyzed_at IS NOT NULL`".
- **Keyword extractor notice-level filter is too aggressive (separate bug, surfaced during Phase 124 verification).** [`attachment_intel_extractor.py:_fetch_eligible_notices`](../../fed_prospector/etl/attachment_intel_extractor.py) joins to `opportunity_attachment_summary` at the *notice* level — once any sibling document on a notice has a summary, the entire notice is excluded from re-processing, so attachments added to that notice in later loads (amendments) silently never get keyword extraction. Live data shows 5,527 of 5,532 unprocessed docs are on notices that already have summaries. Fix: switch the filter to document-level (`WHERE ad.keyword_analyzed_at IS NULL`) so new docs on previously-processed notices get picked up. Should be its own small phase.

## How Hashes Are Computed

- **`content_hash`** (`sam_attachment`): SHA-256 of the raw downloaded file bytes. Computed in `attachment_downloader.py` at download time.
- **`text_hash`** (`attachment_document`): SHA-256 of the extracted text string (`text.encode("utf-8")`). Computed in `attachment_text_extractor.py` at extraction time (line 861).

## Approach: Prevent Duplicates Upstream

Rather than checking for duplicates at every downstream step (intel, AI, cleanup), prevent them from entering the pipeline in the first place. Dedup at the point of creation so downstream steps never see a second document to process.

### The Four Dedup Layers

The current pipeline already has layer 1. This phase adds layers 2, 3, and 4.

```
Step 3: Download Attachments
  ├─ Layer 1 (existing): resource_guid check BEFORE download → skip if same URL
  ├─ Layer 2 (new):      known-duplicate check BEFORE download → skip if resource_guid is in dedup map
  ├─ Layer 3 (new):      content_hash check AFTER download  → reuse existing attachment if same bytes
  │
Step 4: Extract Text
  └─ Layer 4 (new):      text_hash check AFTER extraction   → reuse existing attachment if same text
```

Once deduped, the duplicate `sam_attachment` maps to the existing canonical `attachment_id` via `opportunity_attachment`. Steps 5-8 (keyword intel, AI analysis, backfill, cleanup) never see the duplicate — they only process the canonical document.

**Key insight:** Layers 3 and 4 record their dedup decisions in `attachment_dedup_map`. Layer 2 checks this table BEFORE downloading, so known duplicates are skipped entirely on future runs — no download, no extraction, no hashing. The system learns from every dedup it discovers.

### Layer 2: Known-duplicate check in `attachment_downloader.py`

**When:** BEFORE downloading a file, after resolving its `resource_guid`. Inserted between the existing Layer 1 check (line ~517) and the SSRF check (line ~532).

**Logic:**
1. Check `attachment_dedup_map` for this `resource_guid`.
2. Validate the canonical still exists — JOIN to `sam_attachment` to confirm the row is present. If the canonical is missing, evict the stale map entry and fall through to normal download (self-healing).
3. If found and valid: skip the download entirely. Map `opportunity_attachment` to the canonical `attachment_id`. Log: "known duplicate: resource_guid=X maps to canonical attachment_id=Y (discovered via {method})".
4. If not found: proceed to download.
5. **When `check_changed=True` (force redownload):** bypass this check entirely. Redownload, recompute hashes, re-evaluate whether it's still a duplicate.

**Savings:** Avoids downloading files we already know are duplicates from prior runs. Zero network, disk, or CPU cost.

### Layer 3: Content-hash dedup in `attachment_downloader.py`

**When:** Immediately after downloading a file and computing its `content_hash`. **CRITICAL: must run BEFORE `_upsert_attachment_row()` (line ~835)** — otherwise an `attachment_document` row with `extraction_status = 'pending'` gets created, the file gets deleted, and the extractor later tries to open a missing file. Insertion point is line ~713, after `content_hash` is computed.

**Logic:**
1. Download the file and compute `content_hash` as usual.
2. Check if another `sam_attachment` with the same `content_hash` already has an `attachment_document` with `extraction_status = 'extracted'`.
3. If a match exists:
   - Do NOT call `_upsert_attachment_row()` — no `attachment_document` row should be created.
   - Map `opportunity_attachment` to the existing canonical `attachment_id`.
   - Record in `attachment_dedup_map`: this `resource_guid` → canonical `attachment_id`, method = 'content_hash', with both `content_hash` and `text_hash` (if known).
   - Delete the downloaded file and set `file_path = NULL` on the `sam_attachment` row.
   - Log: "content-hash dedup: resource_guid=X is duplicate of canonical attachment_id=Y".
   - Return early — do not proceed to extraction.
4. If no match, proceed normally — call `_upsert_attachment_row()`, continue to extraction.

**Savings:** ~1,181 text extractions skipped (PDF parsing, OCR), plus all downstream intel/AI runs for those documents.

**Edge case:** Two files with the same bytes but different filenames. The filename is stored on `sam_attachment`, not in `extracted_text`, so this is safe. Filename-only keyword matches (from the Phase 110ZZZ fix) will still be generated correctly because the intel extractor scans `sam_attachment.file_name` independently.

### Layer 4: Text-hash dedup in `attachment_text_extractor.py`

**When:** Immediately after extracting text and computing `text_hash`. Implemented as a new `_handle_text_hash_dedup()` method called right after `_save_extraction()` succeeds.

**Logic:**
1. Extract text and compute `text_hash` as usual.
2. Check if another `attachment_document` with the same `text_hash` already exists and has been fully processed (has intel).
3. If a match exists:
   - Remap `opportunity_attachment` to point to the canonical `attachment_id`.
   - Record in `attachment_dedup_map`: this `resource_guid` → canonical `attachment_id`, method = 'text_hash', with both `content_hash` and `text_hash`.
   - Delete the current `attachment_document` row, the physical file, and set `file_path = NULL` on `sam_attachment`.
   - Log: "text-hash dedup: resource_guid=X is duplicate of canonical attachment_id=Y".
4. If no match, proceed normally to keyword intel extraction.

**Savings:** Catches the case where different file formats (.docx vs .pdf) or re-exported files produce identical extracted text. ~625 additional duplicate groups beyond what content-hash catches.

**Edge case:** A .docx and .pdf with the same text but different filenames. Same as Layer 3 — filename-only evidence is generated separately.

## Schema Changes

### Add index for text-hash lookups
```sql
ALTER TABLE attachment_document ADD INDEX idx_text_hash (text_hash);
```
Currently no index exists on `text_hash`. Without it, Layer 4's lookup is a full table scan on 26K+ rows.

### Add dedup lookup table
```sql
CREATE TABLE attachment_dedup_map (
    resource_guid            CHAR(32) NOT NULL PRIMARY KEY,
    canonical_attachment_id   INT NOT NULL,
    dedup_method             ENUM('content_hash', 'text_hash') NOT NULL,
    content_hash             CHAR(64),
    text_hash                CHAR(64),
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_canonical (canonical_attachment_id)
);
```
Maps known-duplicate `resource_guid` values to their canonical `attachment_id`. Populated by Layers 3 and 4 when they discover duplicates. Checked by Layer 2 before downloading to skip known duplicates entirely.

Stores both hash values for auditing and debugging. If a dedup decision needs to be verified or investigated, both hashes are available without querying other tables.

## Backfill: Clean Up Existing Duplicates

A one-time migration to resolve the ~622 content-hash and ~625 text-hash duplicate groups already in the database. Processes one group at a time with its own transaction. Resumable — already-processed groups have entries in `attachment_dedup_map`, so re-running skips them.

**Strict ordering per group:**
1. Pick canonical (prefer the one with the most complete intel — has keyword + AI analysis, highest evidence count).
2. For each non-canonical row:
   a. INSERT the canonical mapping into `opportunity_attachment` (if not already present).
   b. DELETE the non-canonical `opportunity_attachment` row. (INSERT before DELETE so we never lose a reference. If the INSERT hits a duplicate key, the mapping already exists — just proceed to delete.)
3. Record in `attachment_dedup_map`: non-canonical `resource_guid` → canonical `attachment_id`.
4. DELETE orphaned `document_intel_evidence` rows (must be before summaries — evidence references `intel_id`).
5. DELETE orphaned `document_intel_summary` rows (must be before documents — summaries reference `document_id`).
6. DELETE orphaned `attachment_document` rows.
7. Delete physical files for non-canonical rows, set `file_path = NULL` on their `sam_attachment` rows.

**Run as a dry-run first** — report what would be remapped/deleted before committing.

## In-Batch Race Conditions

If two documents with the same hash appear in the same download/extraction batch:
- Both could pass the "no existing match" check before either is committed.
- **Mitigation:** Maintain a thread-safe `seen_hashes` dict (protected by `threading.Lock`) during batch processing. The downloader uses `ThreadPoolExecutor` with 10 workers (default) — the lock protects a tiny dict lookup/insert (microseconds), no performance impact. When a second document with the same hash appears, skip it and let the next ETL run pick it up.

## Force Redownload (`--force`)

When `--force` or `check_changed=True` is used:
- Layer 2 (dedup map lookup) is bypassed — the file is redownloaded fresh.
- After download, Layer 3 re-evaluates the `content_hash`. If it still matches the canonical, the dedup stands. If the file has changed (government replaced it), the dedup map entry is evicted and the file is processed normally.
- Other notices mapped to the canonical are unaffected — `--force` only operates on the specific notice's attachments.

## Tasks

- [x] **Task 1:** Schema — add `INDEX idx_text_hash (text_hash)` to `attachment_document`
- [x] **Task 2:** Schema — create `attachment_dedup_map` table
- [x] **Task 3:** Layer 2 — known-duplicate check in `attachment_downloader.py` before download, with canonical validation and self-healing eviction
- [x] **Task 4:** Layer 3 — content-hash check in `attachment_downloader.py` after download but BEFORE `_upsert_attachment_row()`, record to `attachment_dedup_map`, delete file, set `file_path = NULL`
- [x] **Task 5:** Layer 4 — new `_handle_text_hash_dedup()` method in `attachment_text_extractor.py` after extraction, record to `attachment_dedup_map`, delete document row and file
- [x] **Task 6:** `--force` / `check_changed=True` bypasses Layer 2 and re-evaluates Layer 3
- [x] **Task 7:** Thread-safe in-batch dedup tracking (`seen_hashes` dict with `threading.Lock`) in both downloader and extractor
- [x] **Task 8:** Add dedup stats section to `pipeline-status` CLI command
- [x] **Task 9:** Add logging so daily loads report dedup skips (count, canonical references, method)
- [x] **Task 10:** Backfill — clean up existing duplicate groups with strict ordering (remap → insert dedup_map → delete evidence → delete summaries → delete documents → delete files)
- [x] **Task 11:** Backfill dry-run mode — report what would be remapped/deleted before committing

## Files Affected

| File | Change |
|------|--------|
| `fed_prospector/db/schema/tables/36_attachment.sql` | Add text_hash index, create `attachment_dedup_map` table |
| `fed_prospector/etl/attachment_downloader.py` | Layer 2 (known-duplicate lookup with validation) + Layer 3 (content-hash check before `_upsert_attachment_row`), `--force` bypass, thread-safe `seen_hashes` |
| `fed_prospector/etl/attachment_text_extractor.py` | Layer 4 (`_handle_text_hash_dedup` method), thread-safe `seen_hashes` |
| `fed_prospector/cli/attachments.py` | Dedup stats in pipeline-status |

## Notes

- This phase does NOT change the `resource_guid` dedup from 110ZZZ — that remains Layer 1 (same URL = skip download).
- Layer 2 (known-duplicate lookup) is a single indexed SELECT on `attachment_dedup_map` with a JOIN to validate the canonical — effectively free.
- Layers 3 and 4 add one SELECT per document on indexed hash columns. For the daily load (~50-100 new attachments), negligible overhead.
- No changes needed to `attachment_intel_extractor.py`, `attachment_ai_analyzer.py`, or `attachment_cleanup.py` — by deduping upstream, these never see duplicate documents.
- The system learns over time: every dedup discovered by Layers 3/4 is recorded in `attachment_dedup_map`, so Layer 2 catches it instantly on future runs.
- Layer 2 is self-healing: if a canonical attachment is deleted, the stale map entry is evicted and the file is redownloaded/re-evaluated.
- The 476-row text_hash group is likely a standard government template or boilerplate document. Worth investigating to confirm.
- Physical files for confirmed duplicates are deleted immediately and `file_path` is set to NULL. The `sam_attachment` row is kept with `download_status = 'downloaded'` so Layer 1 continues to skip the URL.
- `sam_attachment` rows for deduped files are kept (not deleted) — they serve as Layer 1's "I've seen this URL" record and provide audit trail.
- **After backfill (Task 10), re-run `backfill opportunity-intel`** to refresh opportunity-level rollups (`opportunity_attachment_summary`, opportunity columns). The backfill remaps `attachment_id` values in `opportunity_attachment`, which changes document counts per opportunity — the rollups need to reflect the deduplicated state.
- Five downstream files join through `opportunity_attachment` → `attachment_document` (`cli/backfill.py`, `attachment_ai_analyzer.py`, `attachment_identifier_extractor.py`, `attachment_intel_extractor.py`, `attachment_text_extractor.py`). All joins remain valid after remapping — fewer unique documents per opportunity is the intended outcome.
