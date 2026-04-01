# Phase 131: Per-Attachment Re-Analysis

**Status:** COMPLETE
**Priority:** Low — nice-to-have enhancement for the Document Intel tab
**Dependencies:** Phase 113C (side-by-side display)

---

## Summary

Add per-attachment keyword/AI analysis controls to the Attachments table in the Document Intel tab. Currently, re-extraction and re-analysis are whole-opportunity operations. This phase enables targeting individual attachments.

## Proposed UX

### Attachments Table — New Columns

Add two columns to the existing Attachments table: **Keyword** and **AI**.

Each cell shows the analysis state for that attachment+method:

| State | Display |
|-------|---------|
| Not yet analyzed | `[Keyword]` / `[AI]` button to trigger |
| Already analyzed | `[Re-analyze]` button |
| Processing | Spinner |

Example:

```
Filename          | Type | Size | Pages | Download | Extraction | Keyword       | AI
SOW.pdf           | pdf  | 2MB  | 45    | done     | extracted  | [Re-analyze]  | [Re-analyze]
Pricing.xlsx      | xlsx | 1MB  | 3     | done     | extracted  | [Re-analyze]  | [Analyze]
Org_Chart.png     | png  | 500K | 1     | done     | skipped    | —             | —
```

### Backend Requirements

1. **New API endpoint**: `POST /api/v1/opportunities/{noticeId}/attachments/{attachmentId}/analyze?tier=basic|haiku`
2. **New request type**: `ATTACHMENT_ANALYSIS_SINGLE` in `data_load_request` with `lookup_key_type = 'ATTACHMENT_ID'`
3. **Demand loader handler**: Route single-attachment requests to the keyword extractor or AI analyzer for just that document
4. **Keyword extractor**: Add `extract_single(attachment_id)` method
5. **AI analyzer**: Add `analyze_single(attachment_id)` method
6. **AttachmentSummaryDto**: Add `hasKeywordIntel` and `hasAiIntel` boolean fields

### UI Changes

1. Add Keyword and AI columns to `AttachmentsTable` component
2. Per-cell mutation for single-attachment analysis
3. Status polling for in-progress single-attachment requests
4. After completion, invalidate the document intelligence query to refresh all cards

## Open Questions

1. Should single-attachment analysis also trigger a summary rollup? Probably yes — after any single doc is re-analyzed, the opportunity summary should be recomputed.
2. Should skipped/failed extractions (e.g., images, corrupted files) show a disabled button or be hidden entirely?
