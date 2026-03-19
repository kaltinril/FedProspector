# Phase 105: Fix Competitive Intelligence Tab — Static/Placeholder Data

**Status:** PLANNED
**Priority:** High — users see identical values across opportunities, undermining trust
**Dependencies:** None

---

## Problem

The Competitive Intel tab on the Opportunity Detail page shows the same data regardless of which opportunity is viewed:

1. **"Average Award Contract Value" is identical across opportunities** — the Market Landscape section queries by NAICS code only (`getIntelMarketShare(opp.naicsCode, 3, 10)`), so all opportunities sharing a NAICS code show the exact same market stats, vendor chart, and average award value. This makes the tab feel like static placeholder data.

2. **Top Vendors chart looks the same** — same root cause. The `MarketShareChart` renders NAICS-level data, not opportunity-specific competitive data. Users expect to see competitors relevant to *this specific solicitation*, not just anyone who ever won a contract in the same NAICS code.

3. **Incumbent Analysis may be empty for many opportunities** — `GetIncumbentAnalysisAsync` requires `solicitation_number` to find linked contracts. Many opportunities (especially new requirements) have no matching solicitation in `fpds_contract`, so the section shows "No incumbent identified" even when the agency has a known preferred vendor.

---

## Root Cause Analysis

### Market Landscape (`MarketIntelService.GetMarketShareAsync`)
- Queries `fpds_contract` grouped by vendor, filtered only by NAICS code and 3-year window
- Returns the same result for every opportunity with the same NAICS — this is by design for NAICS-level intel, but it's the *only* competitive data shown
- The "Average Award Value" is a NAICS-wide average, not specific to the opportunity's agency, set-aside type, or dollar range

### Incumbent Analysis (`MarketIntelService.GetIncumbentAnalysisAsync`)
- Matches on `solicitation_number` — correct approach but low hit rate
- Does not fall back to agency + NAICS + vendor patterns when no solicitation match exists
- Vulnerability signals and burn rate calculations are solid when data exists

### Frontend (`CompetitiveIntelTab.tsx`)
- Correctly calls both APIs and renders results
- No caching bug — TanStack Query keys include `naicsCode` and `noticeId`, so the "sameness" is real data, not stale cache
- `MarketShareChart` renders total award value bars but doesn't show market share percentage alongside

---

## Implementation Plan

### Task 1: Add opportunity-scoped competitive data

Create a new endpoint or extend the existing market share query to accept additional filters that make results specific to the opportunity context:

**Filters to add:**
- `agency_code` — narrow to vendors who won contracts from the same agency
- `set_aside_code` — narrow to vendors eligible for the same set-aside
- `dollar_range` — optional, filter to similar contract sizes (±50% of estimated value)

**New DTO: `CompetitiveLandscapeDto`**
```
- naicsCode, agencyCode, setAsideCode (context)
- totalContracts, totalValue, averageAwardValue (scoped stats)
- topVendors[] (scoped to agency + NAICS + set-aside)
- competitionLevel: "Low" / "Moderate" / "High" / "Very High" (based on distinct vendor count)
- distinctVendorCount (the number behind the level)
```

This gives each opportunity a unique competitive picture instead of just NAICS-wide stats.

### Task 2: Fix "Average Award Value" to be meaningful per-opportunity

Instead of showing a single NAICS-wide average, show tiered stats:
- **This Agency + NAICS average** — what this agency typically awards in this NAICS
- **NAICS-wide average** — kept for context, but labeled as such
- **This opportunity's estimated value vs. averages** — show where the opportunity falls relative to norms

This immediately differentiates the display across opportunities even when NAICS is the same.

### Task 3: Improve incumbent identification fallback

When `solicitation_number` match fails, try alternative matching:
1. **Agency + NAICS + PSC code** — find recent awards from the same agency in the same NAICS/PSC
2. **Agency + description keyword match** — use `fpds_contract.description_of_requirement` similarity if available
3. **Show "Likely competitors" instead of "No incumbent"** — list vendors who recently won similar contracts from the same agency, even if we can't identify the specific incumbent

### Task 4: Show competition level prominently

Add a "Competition Level" summary card at the top of the Competitive Intel tab:
- Distinct vendor count in NAICS (+ agency-scoped count)
- Competition level chip: Low (≤3), Moderate (4-6), High (7-10), Very High (>10)
- Trend indicator if historical data supports it (more/fewer vendors over time)

This reuses the logic from `PWinService.ScoreCompetitionLevelAsync()` but displays it to the user.

### Task 5: Enhance MarketShareChart with percentages

Current chart only shows absolute dollar bars. Add:
- Market share percentage labels on each bar (already in `VendorShareDto.MarketSharePercent`)
- Contract count as secondary info (already in DTO, not rendered)
- Optional toggle: view by dollar value vs. contract count

### Task 6: Update CompetitiveIntelTab layout

Reorganize the tab to lead with the most useful information:
1. **Competition Level card** (new — Task 4)
2. **Incumbent Analysis** (existing, improved with fallback — Task 3)
3. **Top Competitors for This Opportunity** (new scoped data — Task 1)
4. **NAICS Market Landscape** (existing, relabeled to clarify it's NAICS-wide)

---

## Out of Scope

- Real-time competitive monitoring or alerts
- Competitor company profile pages
- Bid/no-bid recommendation engine (that's pWin's job)
- GovWin or other paid data source integration

---

## Risks

| Risk | Mitigation |
|------|------------|
| Agency-scoped queries may return too few results for niche NAICS | Fall back to NAICS-only when agency-scoped count < 3 vendors |
| Incumbent fallback may identify wrong vendor | Label as "Likely incumbent" with confidence indicator |
| Additional queries per opportunity detail load | Cache aggressively — competitive landscape doesn't change hourly |
| `fpds_contract` may lack agency_code for some records | Use `contracting_agency_code` or `funding_agency_code` with fallback |

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Add opportunity-scoped competitive landscape endpoint | Backend | Medium | — |
| 2 | Show per-agency + per-NAICS average award values (not just NAICS-wide) | Backend + Frontend | Medium | Task 1 |
| 3 | Improve incumbent identification with agency+NAICS fallback | Backend | Medium | — |
| 4 | Show competition level summary card on Competitive Intel tab | Frontend | Low | Task 1 |
| 5 | Enhance MarketShareChart with percentage labels and contract counts | Frontend | Low | — |
| 6 | Reorganize CompetitiveIntelTab layout for better information hierarchy | Frontend | Low | Tasks 1-5 |
