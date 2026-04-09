# Phase 116: Daily Job Performance & Resource Link Architecture

## Status: In Progress

## Problem Statement

The `job daily` pipeline (`python fed_prospector/main.py job daily`) has a fundamental architectural flaw: the `link_metadata` enrichment step (step 8/16) modifies the raw `opportunity.resource_links` JSON column by overwriting plain URL strings with enriched objects containing filename/content_type metadata. On the next daily run, the opportunity loader re-loads the same opportunities from the SAM.gov API (31-day rolling window) and overwrites the enriched data back to plain strings. This creates a Sisyphean loop where the enrichment step must re-process ~5,000+ opportunities every day instead of just the ~1,000 new ones, causing a guaranteed 60-minute timeout.

Additionally, the attachment download pipeline already resolves filenames independently during actual file downloads, making the enrichment step's HEAD requests fully redundant — except that the downloader doesn't save filenames for skipped/oversized files.

## Investigation Findings

### Finding 1: Enrichment overwrites raw API data (root cause)

The `resource_links` column serves two masters:
- The opportunity loader writes raw URL strings from the SAM.gov API: `["https://sam.gov/api/.../download"]`
- The enrichment step overwrites them with metadata objects: `[{"url": "...", "filename": "SOW.pdf", "content_type": "application/pdf"}]`
- The next day's load overwrites them back to raw strings

`resource_links` is in `_UPSERT_COLS` at `fed_prospector/etl/opportunity_loader.py:50`, included in the `ON DUPLICATE KEY UPDATE` clause via `fed_prospector/etl/batch_upsert.py`. Every re-loaded opportunity gets its enrichment destroyed.

**Observed**: 5,341 of 22,151 opportunities flagged for re-enrichment on a daily run that only loaded 1,135 new records.

**Why the download step doesn't have this problem**: The download step (step 9) stores its state in separate tables (`sam_attachment`, `opportunity_attachment`) that the opportunity loader never touches. Its dedup checks those tables and correctly skips already-processed URLs. The enrichment step, by contrast, stores its "processed" state back into the same `resource_links` column the loader overwrites — so its dedup flag gets destroyed daily. This is the core architectural mistake: using a raw source column as a processed/unprocessed flag.

### Finding 2: The enrichment step is redundant

The attachment downloader (`fed_prospector/etl/attachment_downloader.py`) independently resolves filenames from `Content-Disposition` headers during actual file downloads (line 506). It writes them to `sam_attachment.filename`. The enrichment step does the same thing with HEAD requests — it's the same HTTP header parsing, just earlier and lighter.

The normalized table chain already exists:
```
opportunity.resource_links  (raw URLs)
        → sam_attachment              (url, filename, file_size_bytes)
        → opportunity_attachment      (notice_id ↔ attachment_id mapping)
        → attachment_document         (filename, content_type, extracted_text)
```

### Finding 3: Downloader doesn't save filename on skip paths

When the downloader skips a file (oversized, permanent HTTP error, HTML content), it calls `_upsert_attachment_row` without passing `filename` — even though the filename was already resolved from the 303 response at line 506. This means `sam_attachment` rows for 672 skipped files have `filename = NULL`.

Specific skip paths missing filename (all in `attachment_downloader.py`):
- Line 528-531: permanent HTTP errors (e.g., 410 Gone) — no filename passed
- Line 545-548: text/html content rejection — no filename passed  
- Line 557-561: oversized files — passes content_type and file_size_bytes but NOT filename

### Finding 4: No visibility into why files were skipped

The `sam_attachment` table has `skip_reason` and `download_status` columns, but:
- Oversized files get `download_status='skipped'` with no `skip_reason` (lines 557-561)
- The UI has no way to surface skip reasons or file sizes to the user
- For intel/AI analysis, there's no indication that a file was too large to analyze vs simply missing

### Finding 5: UI reads enriched JSON instead of normalized tables

The API endpoint `GET /api/v1/opportunities/{noticeId}` returns `ResourceLinkDetails` by parsing the `opportunity.resource_links` JSON column directly (`OpportunityService.cs:724-758`). It does NOT query `sam_attachment` for this data. The Resource Links section in `OpportunityDetailPage.tsx` consumes this enriched JSON for filenames and content_type icons.

The Document Intelligence tab already reads from `sam_attachment` via `AttachmentIntelService.cs` — so the pattern exists, it's just not used for the Resource Links display.

### Finding 6: Other daily job issues

| Issue | Step | Details |
|-------|------|---------|
| `award_number` too short | opportunities (1/16) | 223-char multi-award value rejected. Notice `58b0b8a1...` lost each run. |
| 404 descriptions retried forever | fetch_descriptions (2/16) | 15 of 100 daily API calls wasted on permanently-404'd notice_ids with no failure tracking |
| usaspending_award_summary slow | usaspending_bulk (3/16) | Full rebuild from 28.7M rows takes 372s even when only 8,112 rows changed |
| 100ms sleep per HEAD request | link_metadata (8/16) | Unnecessary — SAM.gov HEAD requests have no rate limit per the code's own docstring |
| Full table scan + Python JSON parse | link_metadata (8/16) | Scans all 22,151 rows and parses JSON in Python to find ~5,000 needing enrichment |

## Design Principles

These principles address the root causes identified in the investigation. Each includes the reasoning to prevent future regressions or shortcuts that re-introduce the same problems.

1. **Filenames must be visible for all active opportunities** — even if the file was skipped or too large to download. WHY: Users need to see what attachments exist for an opportunity regardless of whether we could download them. A NULL filename with no context is useless for bid/no-bid decisions.

2. **Never modify the raw API response** — `opportunity.resource_links` should only be written by the SAM.gov API loader. WHY: The enrichment step was overwriting raw API data with metadata objects, which then got clobbered on the next day's re-load, creating a Sisyphean loop where 5,000+ opportunities needed re-enrichment daily. Raw source columns must be owned exclusively by their source loader.

3. **The API and UI must not read raw JSON** — they should use normalized DB tables, not `opportunity.resource_links`. WHY: Raw JSON is an ETL staging format. The app layer should consume transformed, structured data from proper relational tables — JSON shape can change with API versions, it's not indexed, and parsing it at query time is fragile and slow.

4. **The API should always query transformed data** — `sam_attachment` + `opportunity_attachment` + `attachment_document`, not the raw JSON column. WHY: These are the canonical tables after ETL processing — indexed, normalized, and queryable. They contain download status, skip reasons, file sizes, and extracted text that raw JSON never has.

5. **Skipped/oversized files must explain why** — display skip reason and file size so users (and AI/intel) know "too large to analyze" vs "download failed" vs "unsupported format". WHY: A missing file with no explanation is confusing and not actionable — users can't tell if they should try downloading it themselves or if it's permanently unavailable.

6. **Skipped files should still show filename/size** — even if we can't download them, surface what we know from the HTTP headers. WHY: The HTTP 303 redirect and response headers give us filename and content-length for free during the download attempt. Not saving this metadata wastes information the user cares about for bid evaluation.

7. **Kill the enrichment step entirely, don't patch it** — remove `link_metadata` from the pipeline, not fix its overwrite behavior. WHY: The enrichment step is fully redundant with the download step — both resolve filenames from the same HTTP `Content-Disposition` headers. Patching the overwrite bug would be a band-aid that preserves unnecessary complexity and ~20,000 daily HEAD requests to SAM.gov. The correct fix is to make the downloader save filenames on skip paths (Task 1), then delete the enrichment step entirely.

## Path Forward

### Task 1: Fix the downloader to save filename on all paths
**Why**: The downloader already resolves the filename from HTTP headers before deciding to skip. It just doesn't pass it to `_upsert_attachment_row` on skip paths. This is the prerequisite for everything else.

**Changes**:
- `fed_prospector/etl/attachment_downloader.py`: Pass `filename` to `_upsert_attachment_row` on all skip/fail paths (oversized, permanent HTTP error, HTML content)
- Also pass `skip_reason` for oversized files (currently missing — only status is set)
- Ensure `sam_attachment` always has filename when the HTTP headers provided one

**Files**: `fed_prospector/etl/attachment_downloader.py`

- [ ] Pass `filename` to all `_upsert_attachment_row` calls after line 506 where filename is in scope
- [ ] Add `skip_reason='oversized'` to the oversized file skip path (line 557-561)
- [ ] Verify skipped files in `sam_attachment` now have filenames

### Task 2: Kill the enrichment step
**Why**: With Task 1 done, `sam_attachment` has filenames for all files (downloaded, skipped, and failed). The enrichment step's HEAD requests are fully redundant.

**IMPORTANT**: `attachment_downloader.py` (line 28) imports `_ALLOWED_PREFIXES` and `_parse_content_disposition` from `resource_link_resolver.py`. These must be moved before deletion.

**Changes**:
- `fed_prospector/etl/resource_link_resolver.py`: Move `_ALLOWED_PREFIXES` and `_parse_content_disposition` into `attachment_downloader.py` (or a shared utility), then delete this file
- `fed_prospector/cli/load_batch.py`: Remove `link_metadata` from the daily job step list
- `fed_prospector/cli/update.py`: Remove the `enrich resource-links` CLI command
- `fed_prospector/main.py`: Remove import and registration of `enrich_link_metadata` command
- `fed_prospector/etl/opportunity_loader.py`: Remove `enrich_resource_links()` and `_needs_enrichment()` methods
- `fed_prospector/etl/scheduler.py`: Remove `link_metadata` job entry from `JOBS` dict; update `download_attachments` scheduling comment that references "after link-metadata"
- `thesolution/phases/500-DEFERRED-ITEMS.md`: Remove TEST-2 entry for `resource_link_resolver.py` tests (file deleted)

**Files**: `fed_prospector/etl/resource_link_resolver.py`, `fed_prospector/etl/attachment_downloader.py`, `fed_prospector/cli/load_batch.py`, `fed_prospector/cli/update.py`, `fed_prospector/main.py`, `fed_prospector/etl/opportunity_loader.py`, `fed_prospector/etl/scheduler.py`, `thesolution/phases/500-DEFERRED-ITEMS.md`

- [ ] Move `_ALLOWED_PREFIXES` and `_parse_content_disposition` from `resource_link_resolver.py` into `attachment_downloader.py`
- [ ] Delete `resource_link_resolver.py`
- [ ] Remove `link_metadata` step from daily job in `load_batch.py`
- [ ] Remove `enrich resource-links` CLI command from `update.py`
- [ ] Remove import and registration in `main.py`
- [ ] Remove `enrich_resource_links()` and `_needs_enrichment()` from `opportunity_loader.py`
- [ ] Remove `link_metadata` job entry from `scheduler.py`
- [ ] Remove TEST-2 deferred item from `500-DEFERRED-ITEMS.md`
- [ ] Verify daily job runs without enrichment step

### Task 2.5: Backfill filenames for historically-skipped attachments
**Why**: There are ~672 existing `sam_attachment` rows (skipped/oversized files) with `filename = NULL` because the downloader didn't save filenames on skip paths before Task 1. The API (Task 3) will read from these rows, so they need filenames populated.

**Changes**:
- Write a one-time migration script or CLI command that:
  1. Queries `sam_attachment` rows where `filename IS NULL` and `url IS NOT NULL`
  2. Makes HEAD requests to resolve filenames from `Content-Disposition` headers
  3. Updates the `filename` column
- Alternatively, re-run the downloader with `--missing-only` after Task 1 is deployed — it will re-attempt skipped files and now save filenames on skip paths

- [ ] Backfill filenames for existing NULL-filename `sam_attachment` rows
- [ ] Verify no active-opportunity attachments have NULL filenames

### Task 3: Rewire the API to read from normalized tables
**Why**: The API currently parses `opportunity.resource_links` JSON to build `ResourceLinkDetails`. It should instead query `sam_attachment` via `opportunity_attachment` to get filenames, content types, file sizes, download status, and skip reasons.

**Changes**:
- `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`: Replace `ParseResourceLinks()` with a query that joins `opportunity_attachment` → `sam_attachment` → `attachment_document`
- `api/src/FedProspector.Core/DTOs/Opportunities/ResourceLinkDto.cs`: Add fields for `fileSizeBytes`, `downloadStatus`, `skipReason`
- `api/src/FedProspector.Core/DTOs/Opportunities/OpportunityDetailDto.cs`: Remove raw `ResourceLinks` string property (or keep for backward compat but stop using it in the UI)

**Files**: `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`, `api/src/FedProspector.Core/DTOs/Opportunities/ResourceLinkDto.cs`, `api/src/FedProspector.Core/DTOs/Opportunities/OpportunityDetailDto.cs`

- [ ] Query `opportunity_attachment` → `sam_attachment` → `attachment_document` for resource link details
- [ ] Add `fileSizeBytes`, `downloadStatus`, `skipReason` to `ResourceLinkDto`
- [ ] Remove `ParseResourceLinks()` method
- [ ] Verify API returns attachment-backed resource link data

### Task 4: Update the UI to display skip/size info
**Why**: Users need to see why a file wasn't analyzed. "Too large to analyze (97 MB)" is actionable; a missing attachment is confusing.

**Changes**:
- `ui/src/types/api.ts`: Update `ResourceLinkDto` interface with new fields
- `ui/src/pages/opportunities/OpportunityDetailPage.tsx`: Update `ResourceLinksSection` to show download status, skip reason, and file size where applicable. Show appropriate labels like "Too large to download (97 MB)" or "Download failed (HTTP 410)"

**Files**: `ui/src/types/api.ts`, `ui/src/pages/opportunities/OpportunityDetailPage.tsx`

- [ ] Update `ResourceLinkDto` TypeScript interface
- [ ] Update `ResourceLinksSection` to display skip reasons and file sizes
- [ ] Remove `parseResourceLinks()` and `getResourceLinksForDisplay()` fallback logic for raw JSON
- [ ] Verify display for downloaded, skipped, oversized, and failed attachments

### Task 5: Fix remaining daily job issues
**Why**: Independent fixes that improve daily job reliability and performance.

**5a: Widen `award_number` column**
- `fed_prospector/db/schema/tables/30_opportunity.sql`: Change `award_number` to VARCHAR(500)
- Apply ALTER TABLE to live database
- [ ] Widen column in DDL and live DB
- [ ] Verify previously-failing record loads

**5b: Track permanently-failed descriptions**
- Add failure tracking so 404'd notice_ids are not retried after N failures
- `fed_prospector/etl/opportunity_loader.py`: description fetch logic
- `fed_prospector/db/schema/tables/30_opportunity.sql`: add `description_fetch_failures` or similar
- [ ] Add failure counter/timestamp for description fetches
- [ ] Skip notice_ids with 3+ consecutive 404s

**5c: Optimize usaspending_award_summary refresh**
- Profile the 372-second summary rebuild
- Investigate incremental refresh or index improvements
- `fed_prospector/etl/etl_utils.py`: summary refresh function
- [ ] Profile summary refresh query
- [ ] Implement optimization (target: under 60s for daily loads)

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| link_metadata step | 60+ min (timeout) | Removed entirely (0s) |
| Daily enrichment HTTP requests | ~20,000 HEAD requests | 0 |
| Filename visibility | Only after enrichment runs | From download step, including skipped files |
| Skip/size transparency | None | Full — reason and size shown in UI |
| Raw API data integrity | Overwritten daily | Never modified after load |
| award_number data loss | 1+ records/run | 0 |
| Wasted description API calls | ~15/day | 0 |
| usaspending summary refresh | 372s | Target <60s |
| **Total daily job time** | **75+ min (with timeout)** | **~10-15 min** |
