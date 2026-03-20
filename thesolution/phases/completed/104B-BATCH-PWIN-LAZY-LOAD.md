# Phase 104B: Batch pWin Endpoint & Lazy-Load Grid Scores

**Status:** COMPLETE
**Priority:** Medium — UX improvement, removes click-to-calculate friction
**Dependencies:** Phase 104 (JV Past Performance), Phase 103 (qScore & pWin Visibility)

---

## Goal

Replace the per-row "Calculate" button on the Recommended Opportunities grid (and future grid pages) with automatic lazy-loaded pWin scores. Scores load in the background after the grid renders, filling in via a batch API call.

---

## Current State

- pWin is computed on-demand via `GET /api/v1/opportunities/{noticeId}/pwin` (one opportunity at a time)
- RecommendedOpportunitiesPage shows a "Calculate" button in the pWin column — user must click each row individually
- OpportunityDetailPage auto-fetches pWin on load (works fine for single-opportunity view)
- PWinService.CalculatePWinAsync() handles one opportunity at a time
- No batch pWin endpoint exists

---

## Implementation Plan

### Task 1: Batch pWin API Endpoint

**New endpoint:** `POST /api/v1/opportunities/pwin/batch`

**Request body:**
```json
{
  "noticeIds": ["opp1", "opp2", "opp3", ...]
}
```

**Response:**
```json
{
  "results": {
    "opp1": { "score": 72.5, "category": "High" },
    "opp2": { "score": 45.0, "category": "Medium" },
    "opp3": { "score": 18.2, "category": "Low" }
  }
}
```

**Files to change:**
- `api/src/FedProspector.Core/DTOs/Intelligence/PWinDtos.cs` — Add `BatchPWinRequest` and `BatchPWinResponse` DTOs
- `api/src/FedProspector.Core/Interfaces/IPWinService.cs` — Add `CalculateBatchPWinAsync(List<string> noticeIds, int orgId)` method signature
- `api/src/FedProspector.Infrastructure/Services/PWinService.cs` — Implement batch method. Should:
  - Accept up to 25 noticeIds per request (guard against abuse)
  - Loop through and call existing `CalculatePWinAsync` for each (reuse existing logic)
  - Return a dictionary of noticeId → { score, category }
  - If a single pWin calculation fails, return null for that entry (don't fail the whole batch)
  - Log warnings for individual failures
- `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` — Add `[HttpPost("pwin/batch")]` action

**Design decisions:**
- Keep the response lightweight — only score + category, not the full factor breakdown (that's for the detail page)
- Max 25 per batch — matches typical grid page size, prevents expensive bulk computation
- Reuse existing `CalculatePWinAsync` internally rather than optimizing with bulk queries (simpler, and the per-item computation is already fast enough)
- Uses POST because the request body contains an array of IDs

### Task 2: TypeScript API Client

**Files to change:**
- `ui/src/types/api.ts` — Add `BatchPWinRequest`, `BatchPWinResponse`, `BatchPWinEntry` types
- `ui/src/api/` or wherever API functions live — Add `fetchBatchPWin(noticeIds: string[])` function

### Task 3: useBatchPWin Hook

**New file:** `ui/src/hooks/useBatchPWin.ts` (or add to existing hooks file if there is one)

A TanStack Query hook that:
- Accepts an array of noticeIds (the current visible page of results)
- Calls the batch endpoint
- Returns a `Map<string, { score: number; category: string }>`
- Uses `enabled: noticeIds.length > 0` so it doesn't fire on empty pages
- Caches results so navigating back to a page doesn't re-fetch
- Uses a query key like `['pwin', 'batch', ...sortedNoticeIds]` for proper cache invalidation

### Task 4: Update RecommendedOpportunitiesPage

**File:** `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx`

Changes:
- Remove the existing PWinCell component that shows a "Calculate" button
- Replace with a cell that reads from the batch query results:
  - While batch is loading: show a small Skeleton (MUI) in the cell
  - When loaded: show the PWinGauge (small size) with score and category
  - If the batch returned null for that row: show a dash or "N/A"
- Extract the current page's noticeIds from the grid's pagination state
- Pass those noticeIds to the `useBatchPWin` hook
- When the user changes pages, the hook fires for the new page's noticeIds
- Remove the per-row `usePWin` individual query calls

**UX behavior:**
1. User navigates to Recommended Opportunities
2. Grid loads instantly with recommendation data (qScore, title, agency, etc.)
3. pWin column shows small Skeletons for each row
4. ~200-500ms later, batch pWin response arrives
5. Skeletons replaced with PWinGauge components showing scores
6. User changes page → same cycle repeats for new rows

### Task 5: (Future) Apply to Other Grid Pages

Not in this phase, but the pattern is reusable:
- Opportunity Search results page
- Prospects list page
- Expiring Contracts page

Document this as a pattern for future phases.

---

## Out of Scope

- Optimizing PWinService internals for bulk DB queries (premature — measure first)
- Adding pWin to search/list endpoint responses (that's option B, not doing this)
- Server-side pWin caching/precomputation
- Applying lazy-load pattern to other pages (future work, document the pattern)

---

## Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Batch of 25 pWin calculations could be slow | Each calculation is fast (~50ms); 25 sequential = ~1.2s worst case. Acceptable for lazy load. Monitor and optimize if needed. |
| Grid page size might vary | Default to 25 max in the endpoint; UI sends only the current page's IDs |
| Cache invalidation when org entities change | pWin cache keys include noticeIds; TanStack Query staleTime handles this naturally |
| User sorts/filters rapidly causing many batch calls | TanStack Query deduplicates and cancels stale queries automatically |

---

## Testing Checklist

- [ ] POST /opportunities/pwin/batch returns scores for multiple noticeIds
- [ ] Batch endpoint rejects >25 noticeIds with 400 Bad Request
- [ ] Individual pWin failure doesn't fail the whole batch (returns null for that entry)
- [ ] RecommendedOpportunitiesPage shows Skeleton while pWin loads
- [ ] Scores appear after batch resolves without full page re-render
- [ ] Page change triggers new batch fetch for new visible rows
- [ ] Navigating back to a previously loaded page uses cached scores
- [ ] Existing single pWin endpoint still works (no regression)

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Batch pWin API endpoint (POST /opportunities/pwin/batch) | C# Backend | Medium | — |
| 2 | TypeScript API client + types | Frontend | Low | Task 1 |
| 3 | useBatchPWin TanStack Query hook | Frontend | Low | Task 2 |
| 4 | Update RecommendedOpportunitiesPage with lazy-load pattern | Frontend | Medium | Task 3 |
| 5 | (Future) Apply pattern to other grid pages | Frontend | Low | Task 4 |
