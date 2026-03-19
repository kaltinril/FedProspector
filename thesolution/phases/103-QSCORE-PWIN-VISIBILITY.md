# Phase 103: qScore & pWin Visibility

**Status:** PLANNED
**Priority:** Medium — UX clarity, no data bugs
**Dependencies:** None

---

## Goal

Make the two scoring systems (qScore and pWin) visible, understandable, and accessible without drilling into opportunity details.

Currently the Recommended page shows a "Score" column with no explanation. Users don't know what it is, how it's calculated, or how it differs from pWin. pWin is only visible after clicking into an opportunity and navigating to the Qualification & pWin tab.

---

## The Two Scores

### qScore (Quick Score) — currently labeled "Score"

**Source:** `RecommendedOpportunityService`
**Purpose:** Fast opportunity ranking for the Recommended page and dashboard.
**Formula:** 4 factors, 60 raw points normalized to 0-100:

| Factor | Max Points | Criteria |
|--------|-----------|----------|
| Set-Aside Match | 20 | Exact cert (20), any SB cert (10), none (0) |
| NAICS Match | 20 | Primary (20), secondary (15) |
| Time Remaining | 10 | 30+ days (10), 14-30 (7), 7-14 (4), <7 (1) |
| Contract Value | 10 | >$1M (10), >$500K (8), >$100K (6), >$50K (4), <$50K (2) |

**Categories:** High (≥70), Medium (40-69), Low (15-39), Very Low (<15)

### pWin (Probability of Win)

**Source:** `PWinService`
**Purpose:** Detailed win probability assessment for a specific opportunity.
**Formula:** 7 weighted factors, 0-100:

| Factor | Weight | What it checks |
|--------|--------|----------------|
| Set-Aside Match | 20% | Cert match (exact/related/none) |
| NAICS Experience | 20% | Past performance count in NAICS |
| Competition Level | 15% | Vendor count in NAICS + agency |
| Incumbent Advantage | 15% | Is org the incumbent? |
| Teaming Strength | 10% | JV/teaming partners linked |
| Time to Respond | 10% | Days until deadline |
| Contract Value Fit | 10% | Historical contract size match |

**Categories:** High (≥70), Medium (40-69), Low (15-39), Very Low (<15)

---

## Implementation Plan

### Task 1: Rename "Score" to "qScore" across UI

**Files:**
- `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx` — column header
- `ui/src/pages/dashboard/DashboardPage.tsx` — recommendations widget (if score shown)
- Backend DTO if the field name changes (check `RecommendedOpportunityDto`)

Rename the column from "Score" to "qScore". Use a tooltip on the column header explaining: "Quick Score — rates how well this opportunity matches your profile based on set-aside, NAICS, timeline, and value."

### Task 2: Add qScore tooltip/popover breakdown

On hover or click of a qScore value, show a mini-breakdown:
```
qScore: 88.3
  Set-Aside Match    20/20
  NAICS Match        20/20
  Time Remaining      7/10
  Value               6/10
```

This requires the backend to return the factor breakdown, not just the total. Check if `RecommendedOpportunityService` already returns this or if the DTO needs extending.

### Task 3: Show pWin on opportunity list pages

Add a "pWin" column (or badge) to:
- **Recommended Opportunities page** — next to qScore
- **Opportunity search results** — as an optional column
- **Dashboard recommendations widget** — if space allows

This means calling `PWinService` for each displayed opportunity. Consider:
- **Performance:** pWin is more expensive than qScore (7 factors, DB queries). May need to batch or lazy-load.
- **Caching:** Cache pWin results with a reasonable TTL (e.g., 1 hour) since the factors don't change frequently.
- **Alternative:** Only compute pWin for the top N qScore results on the Recommended page, not all search results.

### Task 4: Show qScore on Opportunity Detail page

When navigating from the Recommended page to an opportunity detail:
- Show the qScore value (and breakdown) on the Overview tab, near the qualification summary
- The qScore is already computed — just needs to be passed through or re-fetched

### Task 5: pWin visible without deep drilling

On the Opportunity Detail page Overview tab:
- Show pWin value prominently (the number + category chip)
- Already partially done by the `QualificationSummary` component from Phase 101
- May need to also fetch and display the pWin number alongside the qualification status

---

## Out of Scope

- Changing the qScore or pWin formulas
- Combining qScore and pWin into a single score
- Historical score tracking

---

## Risks

| Risk | Mitigation |
|------|------------|
| pWin computation per-row is expensive | Batch compute for top N, or cache with TTL |
| Two scores confuse users | Clear naming (qScore = quick match, pWin = detailed win probability) + tooltips |
| qScore factor breakdown not in current DTO | Extend DTO — low risk |

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Rename "Score" to "qScore" with tooltip explanation | Frontend | Low | — |
| 2 | Add qScore hover breakdown (extend DTO if needed) | Full stack | Medium | — |
| 3 | Show pWin on Recommended page + search results | Full stack | Medium | — |
| 4 | Show qScore on Opportunity Detail page | Frontend | Low | Task 2 |
| 5 | Show pWin prominently on Opportunity Detail Overview tab | Frontend | Low | — |
