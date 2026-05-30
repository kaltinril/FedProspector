# Phase 130: Early Attachment Cleanup & Re-Analyze

**Status:** COMPLETE (2026-05-30)
**Depends on:** 110 (Attachment Intelligence) — all complete
**Priority:** Medium — disk space optimization + UX improvement

> **Note:** Task 2 (Re-Download / Re-Analyze UI + endpoint) and Task 3 (demand-loader
> redownload handler) were **SUPERSEDED by Phase 131 (Per-Attachment Re-Analysis)**,
> which delivered a superior **per-attachment** flow: the `redownload` tier in
> `demand_loader.py` plus the re-analyze / re-download buttons in
> `DocumentIntelligenceTab.tsx`. Only **Task 1** (cleanup reorder + gate change)
> remained for this phase, and it is now done.

## Motivation

The attachment pipeline currently gates file cleanup on ALL stages completing (keyword intel + AI analysis). But after text extraction, the raw files on disk are never read again — both keyword intel and AI analysis work from `extracted_text` in the database. This means files sit on disk unnecessarily during AI analysis (which is slow, expensive, and often disabled).

Moving cleanup to right after keyword intel extraction:
- Frees disk space sooner (attachments can be 10s of MB each)
- Decouples cleanup from AI analysis availability/cost decisions
- No data loss — `extracted_text` is preserved in DB

Additionally, there's no way for a user to request re-analysis of an opportunity's attachments from the UI. The API endpoint exists (`POST /opportunities/{noticeId}/analyze`) but the UI never exposes it. This phase adds a re-download/re-analyze flow.

---

## Task 1: Delete Raw Files Once Everything Is Captured (DONE 2026-05-30)

### Key motivation discovered

The old gate required an **AI analysis** record (`ai_haiku`/`ai_sonnet`) before a raw
file could be deleted. But **the daily pipeline runs no AI step** — AI analysis is
on-demand only. In normal operation the AI gate was never satisfied, so raw
attachment files were **never cleaned up and leaked forever**.

### 1A. Cleanup eligibility SQL — implemented gate

**File:** `fed_prospector/etl/attachment_cleanup.py`

The intel gating (the `document_intel_summary` EXISTS subquery requiring both
keyword/heuristic AND AI records) was **removed entirely** — not just the AI part.
Keyword intel reads `extracted_text` from the DB, not the raw file, so it is not a
reason to keep the bytes on disk either.

A raw file is now deleted once **all of these are true** (all DB-persisted, so no
data loss; re-download via Phase 131 is the recovery path if bytes are ever needed):

1. **Downloaded:** `sa.download_status = 'downloaded'` AND `sa.file_path IS NOT NULL`
2. **Hashed:** `sa.content_hash IS NOT NULL`
3. **File details captured:** `sa.file_size_bytes IS NOT NULL`
4. **Text extracted:** `ad.extraction_status = 'extracted'` AND `ad.text_hash IS NOT NULL`

Implemented query body:
```sql
SELECT sa.attachment_id, sa.file_path, sa.file_size_bytes
FROM sam_attachment sa
JOIN attachment_document ad ON ad.attachment_id = sa.attachment_id
WHERE sa.download_status = 'downloaded'
  AND sa.file_path IS NOT NULL
  AND sa.content_hash IS NOT NULL
  AND sa.file_size_bytes IS NOT NULL
  AND ad.extraction_status = 'extracted'
  AND ad.text_hash IS NOT NULL
```
The optional `--notice-id` filter (`opportunity_attachment` EXISTS subquery) and
`ORDER BY sa.attachment_id LIMIT %s` are unchanged.

### 1B. Update daily load pipeline order

**File:** `fed_prospector/cli/load_batch.py`

The `attachment_cleanup` step (previously near the end, after `intel_backfill`) was
moved to run **immediately after `attachment_intel`** so disk is freed as soon as
text + hashes are captured. Both `DAILY_SEQUENCE` and `_get_daily_steps()` were
reordered, and the `load_daily` docstring step listing was renumbered:

```
New daily order (relevant slice):
   9. extract_text          Extract text from attachments
  10. attachment_intel      Keyword intel from attachment text
  11. attachment_cleanup    Clean up fully-extracted attachment files   <-- moved here
  12. description_intel     Keyword intel from description text
  ...
  15. intel_backfill        Backfill opportunity intel
  16. sca_revisions         Check SCA WD revisions
```

### 1C. Update CLI `maintain attachment-files` help text

Update any help text or docstrings that mention "fully analyzed" to say "keyword intel extracted" since AI analysis is no longer required.

---

## Task 2: UI Re-Analyze Button

### 2A. Add "Re-Analyze Attachments" action to Opportunity Detail Page

**Location:** OpportunityDetailPage — likely the Actions tab or a button near the document intelligence section.

**Behavior:**
1. Button labeled "Re-Analyze Attachments" (or "Refresh Attachments")
2. On click: call `POST /api/v1/opportunities/{noticeId}/analyze?tier=haiku`
3. Show confirmation dialog first with cost estimate from `GET /api/v1/opportunities/{noticeId}/analyze/estimate`
4. After request: show success toast with "Analysis queued — results appear when the pipeline next runs"
5. Disabled state if no attachments exist for the opportunity

**Existing infrastructure (no backend changes needed for AI re-analyze):**
- API endpoint: `POST /opportunities/{noticeId}/analyze` — already exists
- Cost estimate: `GET /opportunities/{noticeId}/analyze/estimate` — already exists
- Demand loader: `_process_attachment_analysis()` — already exists
- These insert into `data_load_request` table with `request_type='ATTACHMENT_ANALYSIS'`

### 2B. Add "Re-Download & Re-Analyze" option

For cases where the user wants to re-download files (e.g., the source document was updated), we need a new API endpoint and flow:

**New endpoint:** `POST /api/v1/opportunities/{noticeId}/redownload`

**Backend logic (new request type):**
1. Insert `data_load_request` with `request_type='ATTACHMENT_REDOWNLOAD'`
2. Demand loader handler resets the attachment records for that notice_id:
   ```sql
   -- Reset download state so downloader picks them up again
   UPDATE opportunity_attachment
   SET download_status = 'pending',
       file_path = NULL,
       extraction_status = 'pending',
       extracted_text = NULL,
       text_hash = NULL,
       extraction_retry_count = 0,
       download_retry_count = 0
   WHERE notice_id = %s;

   -- Remove all intel (will be re-extracted from fresh text)
   DELETE FROM opportunity_attachment_intel
   WHERE notice_id = %s;
   ```
3. Next pipeline run will re-download, re-extract, re-analyze

**UI:** Dropdown or secondary button alongside the AI re-analyze button. Confirmation dialog should warn: "This will re-download all attachments and re-run all analysis. Previous results will be replaced."

---

## Task 3: Impact Analysis & Edge Cases

### 3A. Demand loader: add ATTACHMENT_REDOWNLOAD handler

**File:** `fed_prospector/etl/demand_loader.py`

Add a new handler for `request_type='ATTACHMENT_REDOWNLOAD'` that:
1. Resets `opportunity_attachment` rows (download_status, extraction_status, file_path, extracted_text, etc.)
2. Deletes `opportunity_attachment_intel` rows
3. Marks the request as COMPLETED
4. The actual re-download happens on next pipeline run (not inline — downloading is slow)

### 3B. Backfill impact

**File:** `fed_prospector/etl/intel_backfill.py` (or similar)

The intel backfill step copies extracted intel from `opportunity_attachment_intel` into columns on the `opportunity` table. When attachments are re-analyzed:
- New intel records will have different `extracted_at` timestamps
- Backfill should naturally pick up the new records on next run
- **Verify:** backfill uses latest intel record, not first — check for any `LIMIT 1` without `ORDER BY extracted_at DESC`

### 3C. AI analysis after cleanup

After this change, AI analysis may run on opportunities whose files are already cleaned up. This is fine because:
- AI analyzer reads `extracted_text` from DB, not files from disk
- `extracted_text` is preserved by cleanup (only `file_path` is set to NULL)
- **Verify:** AI analyzer does not check `file_path IS NOT NULL` anywhere

### 3D. Pipeline status health check

**File:** `fed_prospector/cli/health.py` (or wherever `pipeline-status` lives)

If pipeline status reports on cleanup eligibility or "files awaiting cleanup," the criteria should match the new gating (keyword intel only, not AI). Check for any health/status queries that reference the old AI intel requirement.

### 3E. Existing `--notice-id` cleanup still works

The `maintain attachment-files --notice-id` command should still work for targeted cleanup with the same relaxed gating.

---

## Files to Modify

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_cleanup.py` | Remove AI intel EXISTS clause from eligibility query |
| `fed_prospector/cli/load_batch.py` | Reorder `attachment_cleanup` step in `_get_daily_steps()` (move earlier, after keyword intel, before backfill) |
| `fed_prospector/etl/demand_loader.py` | Add ATTACHMENT_REDOWNLOAD handler |
| `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` | Add redownload endpoint |
| `api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs` | Add redownload request method |
| `ui/src/pages/opportunities/OpportunityDetailPage.tsx` | Add re-analyze and re-download buttons |
| `ui/src/api/opportunities.ts` (or similar) | Add API client methods for new endpoints |

## Files to Verify (no changes expected)

| File | Verify |
|------|--------|
| `fed_prospector/etl/attachment_ai_analyzer.py` | Does NOT check `file_path IS NOT NULL` |
| `fed_prospector/etl/intel_backfill.py` | Uses latest intel record, not first |
| `fed_prospector/cli/health.py` | Pipeline status queries match new gating |
| `fed_prospector/etl/attachment_cleanup.py` | Help text / docstrings updated |

---

## Out of Scope

- Changing the attachment download or text extraction logic (only cleanup gating changes)
- Modifying AI analysis behavior (it already works from DB text)
- Phase 110H (Intel Backfill Ranking) — separate concern
- Phase 110Y (Request Poller Service) — complementary but independent

---

## Future Enhancement (Deferred): Native-PDF Fallback for Scanned / Low-OCR Documents

**Design decision recorded (2026-05-30):** AI analysis sends **extracted text** from the
database (`attachment_document.extracted_text`), **not** the raw file. Confirmed in code:
`attachment_ai_analyzer.py` reads `ad.extracted_text` and builds the user message as
`"Analyze this federal solicitation document:\n\n{text}"` (see `_analyze_document`, plus the
on-demand and batch query paths, which all require `extracted_text IS NOT NULL`). There is no
file-upload, base64, or Files API path. This is what makes the early-cleanup change in this
phase safe: deleting raw files after text extraction + hashing **cannot** break current or
on-demand AI re-analysis, because AI never reads the raw file.

**Why text-based is the right default (keep it):**
- **Cost:** text tokens are much cheaper than feeding whole documents, and the prompt caches cleanly.
- **Retention:** decouples AI from file storage — exactly what allows raw-file cleanup and stops the disk leak that motivated this phase.
- **Format coverage:** one extraction step handles PDF, `.docx`, `.xlsx` uniformly; native-file analysis is effectively PDF-only (and capped around 32MB / 100 pages).
- **Determinism:** same text in, cache-friendly, no re-extraction.

**The one place native-file analysis would win:** layout-heavy content (complex pricing tables,
org charts, maps, figures) and especially **scanned / poor-OCR** documents where flat text
extraction loses fidelity. These are the minority of solicitation content — the extraction
targets (clearance, eval method, vehicle type, labor categories, scope) are overwhelmingly
textual prose.

**Deferred recommendation (do NOT build now):** If AI is later found to miss information on
scanned or table-heavy documents, the targeted fix is **not** to switch all analysis to native
files. Instead: detect low-fidelity documents using the signals already stored on
`attachment_document` (`ocr_quality IN ('fair','poor')` and/or `is_scanned = 1`), and route
**only** those documents through a native-PDF analysis path — re-downloading the bytes on demand
via the existing Phase 131 `redownload` tier (since the raw file may have been cleaned up). This
captures the quality win on the documents that need it without paying the cost and
file-retention penalty on the ~95% that extract cleanly.

**Status:** deferred — implement only if a quality gap is observed in practice.
