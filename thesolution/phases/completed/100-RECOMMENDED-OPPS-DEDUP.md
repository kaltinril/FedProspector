# Phase 100: Opportunity Deduplication, Filtering & History

## Problem

Multiple pages that list opportunities show duplicate rows — the same opportunity title repeated 7–14 times — because SAM.gov creates separate `notice_id` entries per awardee, amendment, lifecycle stage, and task order. Non-biddable notice types (Award Notices, Justifications, IDIQ task orders) are also shown as if they are opportunities to pursue.

## Background: Why SAM.gov Data Has Duplicates

The `opportunity` table (PK: `notice_id`) stores every notice from SAM.gov. SAM.gov creates separate `notice_id` entries for several legitimate reasons:

1. **Multi-award contracts (IDIQs/MACs/BOAs)**: When one solicitation is awarded to multiple vendors, SAM.gov creates a separate Award Notice per awardee. Example: solicitation `W912CH25RA005` (AWSM Zone 1 CONUS) has **14 rows** — one per winning company. All share the same title, NAICS, set-aside, but each has a unique `notice_id` and different `awardee_name`.

2. **IDIQ task orders**: Individual task orders issued under an existing IDIQ vehicle get their own solicitation numbers. Example: "I and L LP IDIQ MAC Follow on" appears 7 times with solicitation numbers `M9549426D1002` through `D1007`. These are **not biddable** — they are notifications of work being issued under an already-awarded contract vehicle. Only the original IDIQ holders can perform task orders.

3. **Amendments and modifications**: When the government extends a deadline, changes requirements, or modifies scope, SAM.gov may create a new `notice_id` while keeping the same `solicitation_number`.

4. **Lifecycle stages**: A procurement can progress through presolicitation → synopsis → solicitation → award, each potentially getting its own `notice_id`.

This data is **correct** — SAM.gov tracks each notice as a discrete event. But for a prospecting tool, list pages need to show **unique biddable opportunities**, while detail pages should expose the full notice history for intelligence.

### Scale of the Problem (actual data as of 2026-03-18)

| Metric | Count |
|--------|-------|
| Total active opportunity rows | 35,956 |
| Award Notices | 5,189 |
| Justifications (J&A, sole-source — not biddable) | 432 |
| Sale of Surplus Property (government selling, not buying) | 14 |
| Consolidate/Bundle notifications | 2 |
| **Total non-biddable by type** | **5,637** |
| Remaining rows after type exclusion | 30,319 |
| Duplicate solicitation_numbers among remaining | ~2,352 |
| **Estimated unique biddable opportunities** | **~28,000** |

### Opportunity Type Reference

| Type | Count | Biddable? | Action |
|------|-------|-----------|--------|
| Combined Synopsis/Solicitation | 17,093 | Yes | Keep |
| Solicitation | 6,113 | Yes | Keep |
| Presolicitation | 2,798 | Pre-solicitation intel | Keep |
| Sources Sought | 2,796 | Pre-solicitation intel | Keep |
| Special Notice | 1,519 | Mixed — often RFIs, Industry Days | Keep |
| Award Notice | 5,189 | No — already awarded | **Exclude** |
| Justification | 432 | No — J&A sole-source justification | **Exclude** |
| Sale of Surplus Property | 14 | No — government selling assets | **Exclude** |
| Consolidate/(Substantially) Bundle | 2 | No — bundling notification | **Exclude** |

### Known Data Edge Cases

1. **Empty-string solicitation_number**: 231 rows have `solicitation_number = ''` (not NULL). All are Special Notices. SQL `COALESCE` and C# `??` do NOT catch empty strings — must use `NULLIF(solicitation_number, '')` in SQL and `string.IsNullOrEmpty()` in C#.

2. **Only 1 truly NULL solicitation_number**: The empty-string problem is 231x more common than NULL.

3. **Tied posted_date**: ~234 solicitation groups have multiple rows with the same latest `posted_date` (e.g., Presolicitation and Solicitation posted same day). Any dedup using `MAX(posted_date)` will leak duplicates. Must use `ROW_NUMBER()` with a tiebreaker.

4. **GSA MAS monster**: Solicitation `47QSMD20R0001` has **695 rows** (694 Award Notices + 1 Combined Synopsis/Solicitation). After Award Notice filter, only 1 survives. Regression canary — if the type filter ever breaks, this single solicitation floods results.

## Root Cause

The core issue is that `RecommendedOpportunityService.cs` (lines 82-106) queries `_context.Opportunities` with only two filters (`Active != "N"` and deadline not passed). No type filter, no solicitation-level dedup. Every matching `notice_id` becomes a separate recommendation.

This same gap exists in multiple other consumers (see Affected Consumers below).

## Affected Consumers

| Consumer | File | Has Dedup? | Has Type Filter? | Action Needed |
|----------|------|-----------|-----------------|---------------|
| **RecommendedOpportunityService** | `api/src/.../Services/RecommendedOpportunityService.cs` (lines 82-106) | No | No | Add both (100-1, 100-2) |
| **OpportunityService.SearchAsync** | `api/src/.../Services/OpportunityService.cs` (lines 66-72) | **Yes** (sol# dedup exists) | No | Add type filter only (100-4) |
| **OpportunityService.ExportCsvAsync** | `api/src/.../Services/OpportunityService.cs` (lines 487-493) | **Yes** (same dedup) | No | Add type filter only (100-4) |
| **SavedSearchService.RunAsync** | `api/src/.../Services/SavedSearchService.cs` (lines 84-136) | No | Conditional (user criteria only) | Add both (100-5) |
| **AutoProspectService.GetCandidateNoticeIdsAsync** | `api/src/.../Services/AutoProspectService.cs` (lines 307-353) | No | Conditional (user criteria only) | Add both (100-6) |
| **v_target_opportunities view** | `fed_prospector/db/schema/views/10_target_opportunities.sql` | No | No | Add both (100-7) |
| ExpiringContractService | `api/src/.../Services/ExpiringContractService.cs` | N/A | N/A | **Not affected** — queries `fpds_contract`, not `opportunity` |
| DashboardService | `api/src/.../Services/DashboardService.cs` | N/A | N/A | **Not affected** — queries prospects, not raw opportunities |
| PWinService | `api/src/.../Services/PWinService.cs` | N/A | N/A | **Not affected** — single notice_id input |

## Tasks

| # | Task | Status |
|---|------|--------|
| 100-1 | Exclude non-biddable notice types from Recommended candidates | DONE |
| 100-2 | Deduplicate by solicitation_number in Recommended service | DONE |
| 100-3 | Create shared DB view `v_opportunity_latest` | DONE |
| 100-4 | Add type filter to Search and Export endpoints | DONE |
| 100-5 | Add dedup and type filter to SavedSearchService | DONE |
| 100-6 | Add dedup and type filter to AutoProspectService | DONE |
| 100-7 | Add dedup and type filter to v_target_opportunities view | DONE |
| 100-8 | Enrich existing Amendment History with award data | DONE |
| 100-9 | Remove isRecompete gate on History tab | DONE |
| 100-10 | Add noticeType column to Recommended page | DONE |
| 100-11 | Verify all list pages show unique biddable opportunities | DONE |

---

### 100-1: Exclude Non-Biddable Notice Types from Recommended Candidates

**File**: `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs`

**What**: Add a type filter to the EF Core query at line ~84 to exclude notice types that are not biddable.

**Types to exclude**:
- `Award Notice` — contract already awarded
- `Justification` — J&A sole-source justification, not biddable (390 of 432 have no companion biddable notice)
- `Sale of Surplus Property` — government selling assets, not buying services
- `Consolidate/(Substantially) Bundle` — bundling notification, not a solicitation

**Implementation**: Add to the `.Where()` clause after `o.Active != "N"`:
```csharp
&& !new[] { "Award Notice", "Justification", "Sale of Surplus Property", "Consolidate/(Substantially) Bundle" }
    .Contains(o.Type)
```

Consider defining this exclusion list as a shared constant (e.g., `OpportunityFilters.NonBiddableTypes`) since it will be reused in tasks 100-4 through 100-7.

**IDIQ task orders**: These share the same `type` values as regular solicitations (often "Award Notice" or "Combined Synopsis/Solicitation"), so they are handled by the solicitation-level dedup in 100-2, not by type filtering. The original IDIQ solicitation will be the one shown; individual task orders underneath it will be collapsed into the history timeline.

---

### 100-2: Deduplicate by solicitation_number in Recommended Service

**File**: `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs`

**What**: After fetching candidates (line 106) and before scoring (line 111), group results by `solicitation_number` and keep only the most recent row per group.

**Implementation** (after `ToListAsync()`, before the scoring loop):
```csharp
// Dedup: keep latest notice per solicitation
var deduped = candidates
    .GroupBy(c => string.IsNullOrEmpty(c.SolicitationNumber) ? c.NoticeId : c.SolicitationNumber)
    .Select(g => g.OrderByDescending(c => c.PostedDate).ThenByDescending(c => c.NoticeId).First())
    .ToList();
```

Then iterate `deduped` instead of `candidates` in the scoring loop at line 111.

**Key details**:
- `string.IsNullOrEmpty()` handles both NULL (1 row) and empty-string (231 rows). Using `??` alone misses empty strings.
- `.ThenByDescending(c => c.NoticeId)` is the tiebreaker for rows with the same `posted_date` (238 groups have ties).
- Task 100-1 (type exclusion) MUST be applied before this dedup runs. If an Award Notice happens to be the latest for a solicitation, it gets excluded first, so the dedup correctly picks the next-latest biddable notice.

---

### 100-3: Create Shared DB View `v_opportunity_latest`

**File to create**: `fed_prospector/db/schema/views/v_opportunity_latest.sql`

**What**: A MySQL view returning one row per solicitation — the latest biddable notice. Provides a shared dedup foundation for SQL consumers (Python CLI, the targets view in 100-7, any future reports).

```sql
CREATE OR REPLACE VIEW v_opportunity_latest AS
SELECT o.*
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY COALESCE(NULLIF(solicitation_number, ''), notice_id)
               ORDER BY posted_date DESC, notice_id DESC
           ) AS rn
    FROM opportunity
    WHERE active <> 'N'
      AND type NOT IN ('Award Notice', 'Justification', 'Sale of Surplus Property', 'Consolidate/(Substantially) Bundle')
) o
WHERE o.rn = 1;
```

**Why `ROW_NUMBER()` instead of `MAX(posted_date)` join**: 238 solicitation groups have multiple rows with the same latest `posted_date`. A `MAX` join leaks duplicates; `ROW_NUMBER()` with a `notice_id DESC` tiebreaker always returns exactly one row per group.

**Why `NULLIF(solicitation_number, '')`**: 231 rows have empty-string (not NULL) solicitation numbers. Without `NULLIF`, they all group into one bucket keyed on `''`.

**Note**: The C# service-layer dedup (100-2) is the primary fix for the Recommended endpoint. This view is for SQL-based consumers and could optionally back the EF Core queries too if mapped as a keyless entity.

---

### 100-4: Add Type Filter to Search and Export Endpoints

**File**: `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`

**What**: The search endpoint (`SearchAsync`, line 66) and CSV export (`ExportCsvAsync`, line 487) **already have solicitation-level dedup** using a correlated subquery:
```csharp
query = query.Where(o =>
    o.SolicitationNumber == null ||
    o.PostedDate == _context.Opportunities
        .Where(o2 => o2.SolicitationNumber == o.SolicitationNumber)
        .Max(o2 => o2.PostedDate));
```

However, they do **not** filter out non-biddable types. Add the same type exclusion from 100-1 to both methods.

**Also fix**: The existing dedup doesn't handle empty-string solicitation numbers (231 rows). The `o.SolicitationNumber == null` check passes empty strings through without dedup. Fix to:
```csharp
query = query.Where(o =>
    string.IsNullOrEmpty(o.SolicitationNumber) ||
    o.PostedDate == _context.Opportunities
        .Where(o2 => o2.SolicitationNumber == o.SolicitationNumber)
        .Max(o2 => o2.PostedDate));
```

**Note**: Dedup must happen before pagination, which it already does (it's in the query, not post-processing). The type filter should also go in the query for the same reason.

**Also consider**: The existing `MAX(posted_date)` dedup in OpportunityService leaks duplicates for ~234 solicitation groups that have tied posted dates. While this is a pre-existing issue (not introduced by Phase 100), replacing the correlated `MAX` subquery with a `ROW_NUMBER()` approach or adding a secondary tiebreaker would fully resolve it. If not addressed here, document as a known remaining gap.

---

### 100-5: Add Dedup and Type Filter to SavedSearchService

**File**: `api/src/FedProspector.Infrastructure/Services/SavedSearchService.cs`

**What**: `RunAsync()` (lines 84-136) queries `_context.Opportunities` with no dedup and no type filter. When a user runs a saved search, they see duplicate rows and non-biddable notices in results. The `newCount` metric is also inflated by duplicates.

**Implementation**: Apply the same pattern — add type exclusion to the `.Where()` and solicitation-level dedup (either via the correlated subquery pattern from OpportunityService or via post-query grouping like 100-2).

**Edge case**: When applying the mandatory non-biddable type exclusion, ensure it takes precedence over user-configured type criteria. If a user's saved search criteria explicitly includes "Award Notice", the mandatory exclusion should still apply. The implementation should apply the non-biddable exclusion first, then layer the user's type filter on top of the remaining biddable types.

---

### 100-6: Add Dedup and Type Filter to AutoProspectService

**File**: `api/src/FedProspector.Infrastructure/Services/AutoProspectService.cs`

**What**: `GetCandidateNoticeIdsAsync()` (lines 307-353) queries opportunities with no dedup and no type filter. Without the fix, auto-prospect can create **duplicate prospects for the same solicitation** — two different `notice_id` values for the same solicitation each generate a separate prospect record.

**Implementation**: Apply type exclusion and solicitation-level dedup before returning candidate notice IDs.

---

### 100-7: Add Dedup and Type Filter to v_target_opportunities View

**File**: `fed_prospector/db/schema/views/10_target_opportunities.sql`

**What**: This SQL view is consumed by the `/api/v1/opportunities/targets` endpoint (`GetTargetsAsync`). It currently filters only by `active = 'Y'` and set-aside codes, with no solicitation-level dedup and no type exclusion.

**Implementation**: Either rewrite this view to select from `v_opportunity_latest` (created in 100-3) with additional set-aside filtering, or apply the same `ROW_NUMBER()` dedup pattern directly. Using `v_opportunity_latest` as a base is cleaner since the dedup logic stays in one place.

---

### 100-8: Enrich Existing Amendment History with Award Data

**What**: The Opportunity Detail page **already has** an Amendment History section in the Overview tab (lines 296-335 of `OpportunityDetailPage.tsx`) that renders `opp.amendments` — an `AmendmentSummary[]` returned by `OpportunityService.GetDetailAsync()` (lines 264-281).

The existing `AmendmentSummaryDto` includes: `noticeId`, `title`, `type`, `postedDate`, `responseDeadline`. It is **missing** `awardeeName` and `awardAmount` — the competitive intelligence that makes Award Notices valuable.

**Backend change**: In `OpportunityService.GetDetailAsync()`, add `AwardeeName` and `AwardAmount` to the amendments query and to `AmendmentSummaryDto`.

**Frontend change**: In the Amendment History table in `OpportunityDetailPage.tsx`, render Award Notice entries with visual distinction — e.g., a green "Awarded" chip, the awardee name, and the dollar amount. This transforms the existing amendments list into a full solicitation lifecycle timeline without building a separate UI.

**Files**:
- `api/src/FedProspector.Core/DTOs/Opportunities/OpportunityDetailDto.cs` (AmendmentSummaryDto, lines 87-94)
- `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` (amendments query, lines 264-281)
- `ui/src/pages/opportunities/OpportunityDetailPage.tsx` (Amendment History rendering, lines 296-335)
- `ui/src/types/api.ts` (AmendmentSummary type)

**Note**: The `opportunity_relationship` table (defined in `30_opportunity.sql`, lines 77-90) with `parent_notice_id`, `child_notice_id`, and `relationship_type` exists but is currently empty (0 rows), so the solicitation_number-based approach is the only option for now.

---

### 100-9: Remove isRecompete Gate on History Tab

**File**: `ui/src/pages/opportunities/OpportunityDetailPage.tsx` (line 411)

**What**: The "History & Awards" tab currently returns an `EmptyState("New Solicitation / No incumbent information")` when `isRecompete` is false. After 100-8 enriches amendment data with award info, even non-recompete solicitations have useful timeline data (amendments, modifications, award decisions). The `isRecompete` gate should be removed or loosened so the tab always shows the solicitation lifecycle.

---

### 100-10: Add noticeType Column to Recommended Page

**File**: `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx`

**What**: The `RecommendedOpportunityDto` already has a `noticeType` field (api.ts line 1040) but the DataGrid columns (lines 60-141) don't display it. After dedup, the remaining types (Combined Synopsis/Solicitation, Solicitation, Presolicitation, Sources Sought, Special Notice) carry meaningful signal — a Presolicitation is a very different action item than an active Solicitation.

Add a `noticeType` column with short chip/badge rendering so users can quickly see what stage the opportunity is in.

---

### 100-11: Verify All List Pages Show Unique Biddable Opportunities

**What**: After implementing 100-1 through 100-7, verify every page that displays opportunity lists:

**Pages to verify**:
- `/opportunities/recommended` — primary target (100-1, 100-2)
- `/opportunities` (search/browse) — 100-4
- `/opportunities/targets` — 100-7
- Saved Search run results — 100-5
- Dashboard "Top Recommendations" widget (calls `getRecommendedOpportunities(5)`, keyed on `noticeId`) — inherits fix from 100-1/100-2

**Not affected** (no verification needed):
- `/awards/expiring` — queries `fpds_contract`, not `opportunity`
- Dashboard prospect widgets — queries `prospect` table

**Verification queries**:
```sql
-- Check for remaining duplicates after fix
SELECT solicitation_number, COUNT(*) as cnt
FROM v_opportunity_latest
GROUP BY solicitation_number
HAVING cnt > 1;
-- Should return 0 rows

-- Confirm no non-biddable types leaked through
SELECT DISTINCT type FROM v_opportunity_latest;
-- Should only show: Combined Synopsis/Solicitation, Solicitation,
-- Presolicitation, Sources Sought, Special Notice
```

## Scope Boundaries

**In scope**: Deduplication on all list pages/endpoints, non-biddable type exclusion, enriching existing amendment history with award data, removing isRecompete gate, adding noticeType column.

**Out of scope**: Changing how the Python ETL loads data (the raw notice-level data is correct and valuable — the issue is presentation layer only). No changes to the `opportunity` table schema. No changes to ExpiringContractService, DashboardService, or PWinService.

## Dependencies

- 100-1 MUST be implemented before 100-2 (type exclusion before dedup, so Award Notices don't win the "latest" selection)
- 100-3 should be created before 100-7 (view can build on view)
- 100-8 before 100-9 (enrich data before removing the gate that hides empty state)
- All other tasks are independent and can be parallelized
