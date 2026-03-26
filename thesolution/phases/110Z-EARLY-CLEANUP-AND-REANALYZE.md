# Phase 110Z: Early Attachment Cleanup & Re-Analyze

**Status:** PLANNED
**Depends on:** 110 (Attachment Intelligence) — all complete
**Priority:** Medium — disk space optimization + UX improvement

## Motivation

The attachment pipeline currently gates file cleanup on ALL stages completing (keyword intel + AI analysis). But after text extraction, the raw files on disk are never read again — both keyword intel and AI analysis work from `extracted_text` in the database. This means files sit on disk unnecessarily during AI analysis (which is slow, expensive, and often disabled).

Moving cleanup to right after keyword intel extraction:
- Frees disk space sooner (attachments can be 10s of MB each)
- Decouples cleanup from AI analysis availability/cost decisions
- No data loss — `extracted_text` is preserved in DB

Additionally, there's no way for a user to request re-analysis of an opportunity's attachments from the UI. The API endpoint exists (`POST /opportunities/{noticeId}/analyze`) but the UI never exposes it. This phase adds a re-download/re-analyze flow.

---

## Task 1: Move Cleanup After Keyword Intel (Remove AI Gate)

### 1A. Modify cleanup eligibility SQL

**File:** `fed_prospector/etl/attachment_cleanup.py`

Current cleanup requires BOTH keyword intel AND AI intel records:
```sql
-- Current: requires AI intel EXISTS clause
AND EXISTS (
    SELECT 1 FROM opportunity_attachment_intel oai
    WHERE oai.attachment_id = oa.attachment_id
      AND oai.extraction_method IN ('ai_haiku', 'ai_sonnet')
)
```

**Change:** Remove the AI intel EXISTS clause entirely. Cleanup eligibility becomes:
1. `download_status = 'downloaded'`
2. `extraction_status = 'extracted'`
3. `file_path IS NOT NULL`
4. Has keyword/heuristic intel record (unchanged)

Only files that completed keyword intel successfully get cleaned up. Failed, skipped, pending, or unsupported files are untouched.

### 1B. Update daily load pipeline order

**File:** `daily_load.bat`

Move the cleanup step from after AI analysis to after keyword intel extraction:

```
Current order:
  [7/12]  Download attachments
  [8/12]  Extract text
  [9/12]  Extract keyword intel
  [10/12] AI analysis
  [11/12] Backfill opportunity intel
  [12/12] Cleanup files              <-- current position

New order:
  [7/13]  Download attachments
  [8/13]  Extract text
  [9/13]  Extract keyword intel
  [10/13] Cleanup files              <-- moved here
  [11/13] AI analysis
  [12/13] Backfill opportunity intel
  [13/13] (reserved for future steps)
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
| `daily_load.bat` | Move cleanup step to after keyword intel, before AI analysis |
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
