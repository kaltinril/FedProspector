# Phase 111: Manual Testing Issues

**Status:** PLANNED
**Priority:** Medium — UI bugs found during manual testing
**Dependencies:** None

---

## Issue 1: pWin Column Overflow in Opportunity Grid

The pWin circular gauge in the opportunity list/grid overflows its row cell. The animated circle graphic is too large for the table row height, causing it to bleed into adjacent rows. This is visible on the main opportunity search results page.

Screenshot evidence: the pWin column shows circular progress indicators (54%, 51%, 62%, etc.) that extend beyond the row boundaries, overlapping with rows above and below.

### Options

1. **Shrink the circular gauge** — reduce the diameter to fit within the standard row height
2. **Replace with a colored number** — remove the circle entirely, show just the percentage with a color indicator (green >=60%, orange 40-59%, red <40%). Simpler, more compact, better for dense data grids.
3. **Replace with a small colored chip** — MUI Chip with colored background showing the percentage (similar to qScore column)
4. **Hybrid** — small inline progress bar or mini gauge that fits in the row

### Recommendation

Option 2 or 3 — match the qScore column's chip style for visual consistency. The circular gauge is cool for the detail page but too bulky for a dense list view.

### Files to Investigate

- The pWin column renderer in the opportunity list/grid component
- The `PWinGauge` component (likely in `ui/src/components/shared/`)
- The grid/table column definitions

---

## Issue 2: Award Detail Page — 503 Service Unavailable

The Award detail page (`/awards/{awardId}`) fails to load with "Failed to load award — Could not connect to the server." Console shows 503 (Service Unavailable) errors on:
- `/api/v1/awards/47QRCA25DW004`

Additional 401 (Unauthorized) errors on multiple endpoints suggest the API may not be running or the auth session expired:
- `/api/v1/auth/me`
- `/api/v1/notifications`
- `/api/v1/opportunities/...` (document-intelligence, pwin)

### Investigation needed

- Is the awards detail endpoint returning 503 even when the API is running?
- Is this a new regression from Phase 110 changes (new controller injection breaking DI)?
- Or was the API simply not running / not rebuilt after code changes?
- Check if the `document-intelligence` endpoint 401 is expected (auth required) or a bug

---

## Issue 3: Entity Detail Page — Hydration Error (nested `<div>` inside `<p>`)

The Entity detail page (`/entities/{uei}`, e.g. `/entities/DNJPS1CVCP17`) shows console errors:

- `In HTML, <div> cannot be a descendant of <p>. This will cause a hydration error.`
- `<p> cannot contain a nested <div>.`

The page renders visually (Company Profile tab with business types, SBA certifications, NAICS codes) but the React DOM nesting violation produces 26 issues in the console. This is likely a MUI `Typography` component with `variant="body1"` (renders as `<p>`) wrapping a child component that renders `<div>` elements (e.g., `StatusChip`, `KeyFactsGrid`, or a `Box`).

### Fix

Find the `<Typography variant="body1">` in the entity/company profile components that wraps block-level children and change it to `variant="body1" component="div"` (or replace with `<Box>`).

---

---

## Issue 4: Entity Competitor Analysis Tab — 503 Service Unavailable

The Competitor Analysis tab on the Entity detail page (`/entities/DNJPS1CVCP17`, "Competitor Analysis" tab) fails with "Failed to load competitor profile — Could not retrieve competitor analysis data."

Console shows repeated 503 errors on:
- `GET /api/v1/entities/DNJPS1CVCP17/competitor-profile` → 503 (Service Unavailable)
- `GET /api/v1/entities/CERYAHZCEVE5/competitor-profile` → 503 (Service Unavailable)

Confirmed on multiple entities (MSONE LLC and MSONE 1PROSPECT JV LLC) — this is systemic, not entity-specific. Called from `getCompetitorProfile` in `entities.ts:23`, triggered by `CompetitorAnalysisTab` via `EntityDetailPage.tsx:561`.

### Investigation needed

- Is the competitor-profile endpoint failing at the DI/service level (similar to Issue 2)?
- Could be the same root cause as the awards 503 — possibly the API needs a rebuild after Phase 110 DI changes, or a service dependency is failing

---

---

## Issue 5: Document Intel Tab — Empty State UX & Progressive Action Buttons

When viewing an opportunity that hasn't been processed yet (e.g., `/opportunities/63d402fe...`), the Document Intel tab shows "No Document Intelligence Available" with an "Analyze with AI" button. This is confusing because:

1. There's nothing downloaded yet — AI analysis requires text to already be extracted
2. The button implies one click gets results, but the actual pipeline is: download → extract text → keyword intel → (optionally) AI
3. Clicking "Analyze with AI" would just queue a request that has nothing to process

### Proposed UX: Progressive action buttons based on pipeline state

The tab should show different actions depending on where the opportunity is in the pipeline:

**State 1: No attachments downloaded**
- Show: "Run Basic Analysis" button (or "Extract Intelligence")
- This queues a `data_load_request` that triggers: download → extract text → keyword intel
- Empty state message: "No document intelligence available yet. Click below to download and analyze attachments."
- No "Analyze with AI" button visible yet

**State 2: Keyword intel extracted, showing results**
- Show the intel cards with keyword confidence levels
- Show: "Enhance with AI" button (NOT "Re-analyze with AI" — that implies AI already ran)
- This queues AI analysis via Claude Batch API on already-extracted text

**State 3: AI analysis complete**
- Show the intel cards with AI confidence levels
- Show: "Re-analyze" button (for manual refresh)

### How to determine state

The API already returns `attachmentCount` and `analyzedCount`. Add a field like `pipelineStatus` to the DTO:
- `"none"` — no attachments in DB for this opportunity
- `"pending"` — attachments cataloged but not downloaded
- `"downloaded"` — files downloaded, text not yet extracted
- `"extracted"` — text extracted, keyword intel not yet run
- `"analyzed_keyword"` — keyword intel complete
- `"analyzed_ai"` — AI analysis complete

Or simpler: just check `attachmentCount == 0` → State 1, `analyzedCount > 0 && latestExtractionMethod == 'keyword'` → State 2, `latestExtractionMethod contains 'ai'` → State 3.

### Backend consideration

State 1 requires a new endpoint or extending the existing `POST .../analyze` to support a `mode` parameter:
- `POST /opportunities/{noticeId}/analyze?mode=basic` — queues download + extract + keyword
- `POST /opportunities/{noticeId}/analyze?mode=ai&tier=haiku` — queues AI analysis (existing)

The Python CLI poller would need to handle the `basic` mode by running the full pipeline (download → extract → keyword) instead of just AI analysis.

---

---

## Issue 6: Recommended Opportunities — Batch pWin 400 Bad Request

The Recommended Opportunities page (`/opportunities/recommended`) shows a 400 (Bad Request) error on the batch pWin endpoint:
- `POST /api/v1/opportunities/pwin/batch` → 400 (Bad Request)

Called from `fetchBatchPWin` in `opportunities.ts:59`, triggered by `useBatchPWin.ts:17`. The pWin column shows "—" for all rows as a result. The page otherwise loads and displays opportunities correctly (qScore shows values, other columns populate).

Also visible: the pWin circular gauges are missing entirely (showing "—"), which ties back to Issue 1 — even if the batch endpoint worked, the gauges would overflow the rows.

### Reproduction

Only occurs when selecting "Top 50" with 100 per page — works fine with smaller page sizes. Likely the batch endpoint has a max payload size or limit on notice IDs per request, and sending ~100 at once exceeds it.

### Investigation needed

- Check the batch endpoint's max accepted notice IDs (is there a validation limit?)
- If there's a hard limit, the UI should chunk requests (e.g., 25 at a time)
- Or increase the server-side limit to accommodate 100+ IDs

---

## Task Summary

| # | Task | Complexity |
|---|------|-----------|
| 1 | Fix pWin column overflow in opportunity grid | Low |
| 2 | Investigate and fix award detail page 503 error | Medium |
| 3 | Verify document-intelligence endpoint auth behavior | Low |
| 4 | Fix entity detail page hydration error (div nested in p) | Low |
| 5 | Investigate entity competitor-profile 503 error | Medium |
| 6 | Implement progressive Document Intel empty state with pipeline-aware buttons | Medium |
| 7 | Investigate batch pWin 400 error on recommended opportunities | Medium |
