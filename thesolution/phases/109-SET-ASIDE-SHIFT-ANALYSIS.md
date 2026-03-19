# Phase 109: Set-Aside Shift Analysis

**Status:** PLANNED
**Priority:** Medium — strategic intelligence for bid decisions
**Dependencies:** None (all required data already loaded)

---

## Goal

Enable users to see how a contract's set-aside classification has changed between the **previous award** and the **current re-solicitation**. This reveals procurement trends — e.g., agencies shifting work from full & open to 8(a), or from WOSB to SDVOSB — giving users actionable intelligence about where contracting dollars are moving.

---

## Problem Statement

FedProspect already loads set-aside data from three sources:
- **Opportunities** → `opportunity.set_aside_code` (current solicitation)
- **FPDS Contracts** → `fpds_contract.set_aside_type` (historical awards)
- **USASpending** → `usaspending_award.type_of_set_aside` (historical awards)

And we already link opportunities to prior contracts via `solicitation_number`. But **nowhere in the system do we compare the previous contract's set-aside to the current opportunity's set-aside** to surface shifts. Users have no way to answer:

- "Was this contract previously full & open but is now set aside for 8(a)?"
- "Are more contracts in my NAICS moving toward WOSB?"
- "Which agencies are increasing small business set-asides?" *(skipped — agency-level rollups deferred, see Out of Scope)*

This is high-value analysis that requires no new data collection — just new queries and UI.

---

## Implementation Plan

### Task 1: Create Set-Aside Shift View

**Layer:** Database (DDL)
**Files:** `fed_prospector/db/schema/views/` (new view file)

Create `v_set_aside_shift` that joins current opportunities with their predecessor contracts:

```sql
CREATE OR REPLACE VIEW v_set_aside_shift AS
SELECT
    o.notice_id,
    o.title,
    o.solicitation_number,
    o.department_name,
    o.sub_tier,
    o.naics_code,
    o.set_aside_code         AS current_set_aside,
    o.set_aside_description  AS current_set_aside_desc,
    fc.set_aside_type        AS previous_set_aside,
    fc.contract_id           AS previous_contract_id,
    fc.vendor_name           AS previous_vendor,
    fc.vendor_uei            AS previous_vendor_uei,
    fc.date_signed           AS previous_award_date,
    fc.ultimate_completion_date AS previous_end_date,
    fc.base_and_all_options  AS previous_value,
    -- Shift detection
    CASE
        WHEN fc.set_aside_type IS NULL THEN 'NEW'
        WHEN fc.set_aside_type = o.set_aside_code THEN 'NO_CHANGE'
        ELSE 'SHIFTED'
    END AS shift_status,
    ref_prev.category        AS previous_category,
    ref_curr.category        AS current_category
FROM opportunity o
LEFT JOIN (
    SELECT fc1.*
    FROM (
        SELECT fc.*,
               ROW_NUMBER() OVER (PARTITION BY solicitation_number
                                  ORDER BY date_signed DESC, contract_id DESC) AS rn
        FROM fpds_contract fc
        WHERE modification_number = '0'
          AND solicitation_number IS NOT NULL
          AND solicitation_number != ''
    ) fc1
    WHERE fc1.rn = 1
) fc ON o.solicitation_number = fc.solicitation_number
    AND o.solicitation_number IS NOT NULL
    AND o.solicitation_number != ''
LEFT JOIN ref_set_aside_type ref_prev ON fc.set_aside_type = ref_prev.set_aside_code
LEFT JOIN ref_set_aside_type ref_curr ON o.set_aside_code = ref_curr.set_aside_code
WHERE o.set_aside_code IS NOT NULL;
```

**Implementation note:** The existing `v_procurement_intelligence` view joins on `award_number` rather than `solicitation_number`. Before finalizing this view, run a match-rate query against live data to confirm `solicitation_number` linkage produces sufficient results. If match rates are low, consider a fallback join on `o.award_number = fc.contract_id`.

**Considerations:**
- SAM opportunities and FPDS contracts both use the same short code format (WOSB, 8A, SDVOSBC, HZC, etc.), so raw codes can be compared directly. The `ref_set_aside_type.category` column is useful for grouping related codes (e.g., 8A and 8AN both map to the "8(a)" category) when doing aggregate trend analysis.
- Only match base awards (`modification_number = '0'`) to avoid counting modifications as separate contracts.

### Task 2: Create NAICS-Level Trend Aggregation View

**Layer:** Database (DDL)
**Files:** `fed_prospector/db/schema/views/` (new view file)

Create `v_set_aside_trend` for aggregate analysis — how set-aside distribution is changing year-over-year within a NAICS code:

```sql
CREATE OR REPLACE VIEW v_set_aside_trend AS
SELECT
    naics_code,
    YEAR(date_signed) AS award_year,
    set_aside_type,
    ref.category AS set_aside_category,
    COUNT(*) AS contract_count,
    SUM(base_and_all_options) AS total_value,
    AVG(base_and_all_options) AS avg_value
FROM fpds_contract fc
LEFT JOIN ref_set_aside_type ref ON fc.set_aside_type = ref.set_aside_code
WHERE modification_number = '0'
  AND date_signed IS NOT NULL
  AND naics_code IS NOT NULL
GROUP BY naics_code, YEAR(date_signed), set_aside_type, ref.category;
```

This powers the "trend over time" charts showing whether 8(a), WOSB, etc. are growing or shrinking in a given NAICS.

### Task 3: Backend API Endpoint — Set-Aside Shift for an Opportunity

**Layer:** C# Backend
**Files:**
- `api/src/FedProspector.Core/DTOs/Intelligence/SetAsideShiftDtos.cs` (new)
- `api/src/FedProspector.Infrastructure/Services/MarketIntelService.cs` (extend)
- `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` (new endpoint)

Add `GET /api/v1/opportunities/{noticeId}/set-aside-shift` returning:

```csharp
public class SetAsideShiftDto
{
    public string CurrentSetAside { get; set; }
    public string CurrentSetAsideDescription { get; set; }
    public string PreviousSetAside { get; set; }
    public string PreviousContractId { get; set; }
    public string PreviousVendor { get; set; }
    public DateTime? PreviousAwardDate { get; set; }
    public decimal? PreviousValue { get; set; }
    public string ShiftStatus { get; set; }  // NEW, NO_CHANGE, SHIFTED
    public string ShiftDescription { get; set; }  // e.g., "Changed from Full & Open to 8(a)"
}
```

**Logic:** Query `v_set_aside_shift` by `notice_id`. This queries public procurement data, so no org-scoping is needed.

### Task 4: Backend API Endpoint — NAICS Set-Aside Trends

**Layer:** C# Backend
**Files:**
- `api/src/FedProspector.Core/DTOs/Intelligence/SetAsideShiftDtos.cs` (extend — same file as Task 3, following multi-class-per-file convention)
- `api/src/FedProspector.Infrastructure/Services/MarketIntelService.cs` (extend)
- `api/src/FedProspector.Api/Controllers/AwardsController.cs` (extend existing)

Add `GET /api/v1/awards/set-aside-trends?naicsCode={code}&years={n}` returning:

```csharp
public class SetAsideTrendDto
{
    public string NaicsCode { get; set; }
    public int Years { get; set; }
    public List<YearlyBreakdown> Breakdown { get; set; }
}

public class YearlyBreakdown
{
    public int Year { get; set; }
    public List<SetAsideBucket> Buckets { get; set; }
    public int TotalContracts { get; set; }
    public decimal TotalValue { get; set; }
}

public class SetAsideBucket
{
    public string SetAsideCategory { get; set; }  // "8(a)", "WOSB", "Full & Open", etc.
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal Percentage { get; set; }
}
```

**Note:** EF Core keyless entity mappings will be needed for both `v_set_aside_shift` and `v_set_aside_trend` in `FedProspectorDbContext`.

### Task 5: UI — Set-Aside Shift Indicator on Opportunity Detail

**Layer:** Frontend
**Files:**
- `ui/src/types/api.ts` (add DTOs)
- `ui/src/api/opportunities.ts` (add API call)
- `ui/src/pages/opportunities/CompetitiveIntelTab.tsx` (add shift section)

Add a **"Set-Aside Shift" card** to the Competitive Intel tab showing:
- Previous contract's set-aside vs. current opportunity's set-aside
- Visual indicator (arrow, color-coded chip) for SHIFTED / NO_CHANGE / NEW
- Previous contract details (ID, vendor, award date, value)

**Design:**
- Use MUI `Alert` or `Card` component
- Color: green for NO_CHANGE, amber for SHIFTED, gray for NEW
- Show shift direction: e.g., "Full & Open → 8(a)" with an arrow icon

### Task 6: UI — NAICS Set-Aside Trend Chart

**Layer:** Frontend
**Files:**
- `ui/src/types/api.ts` (add DTOs)
- `ui/src/api/awards.ts` (extend existing)
- `ui/src/components/shared/SetAsideTrendChart.tsx` (new component)
- `ui/src/pages/opportunities/CompetitiveIntelTab.tsx` (integrate chart)

Add a **stacked bar chart or area chart** showing set-aside distribution over time for the opportunity's NAICS code. Users can see at a glance whether 8(a) is growing, WOSB is shrinking, etc.

**Chart library:** Use MUI Charts (already available via MUI v7) or a lightweight chart component.

### Task 7: UI — Set-Aside Shift on Expiring Contracts Page

**Layer:** Backend + Frontend
**Files:**
- `api/src/FedProspector.Core/DTOs/Intelligence/SetAsideShiftDtos.cs` (extend `ExpiringContractDto`)
- `api/src/FedProspector.Infrastructure/Services/ExpiringContractService.cs` (extend)
- `ui/src/pages/awards/ExpiringContractsPage.tsx` (extend)

The `ExpiringContractDto` and the expiring contracts endpoint need to be extended to include shift data: the **previous set-aside** comes from the contract itself, and the **current set-aside** comes from any linked re-solicitation opportunity (matched via `solicitation_number`). This lets users see at a glance which recompetes are shifting categories.

**UX concern:** The expiring contracts table already has 13 columns. Rather than adding a 14th "Set-Aside Shift" column, consider enriching the existing "Re-solicitation" column with a shift indicator (e.g., a colored chip or icon showing the set-aside change direction) to avoid horizontal scroll.

---

## Out of Scope

- Predictive analytics ("will this NAICS shift to 8(a) next year?") — future ML phase
- Cross-agency benchmarking dashboards — too broad for this phase
- Alerts/notifications when a tracked NAICS shifts — future feature
- Changes to data loading or ETL pipeline — we use existing data as-is
- Agency-level trend rollups — can be added later; start with NAICS-level

---

## Risks

| Risk | Mitigation |
|------|------------|
| Related set-aside codes need grouping for trend analysis (e.g., 8A vs 8AN) | Use `ref_set_aside_type.category` for aggregate comparisons |
| Many opportunities lack `solicitation_number`, preventing linkage | Fall back to NAICS-level trend analysis; surface "NEW" status clearly |
| FPDS data may be incomplete for older contracts | Limit trend analysis to last 5 years; show data coverage in UI |
| View performance on large datasets | Index on `solicitation_number` already exists; add composite index if needed |
| Chart library choice | MUI Charts is included with MUI v7; avoid adding new dependencies |

---

## Testing Checklist

- [ ] `v_set_aside_shift` returns correct shift_status for: matched contracts with same set-aside, matched with different set-aside, unmatched (new) opportunities
- [ ] `ref_set_aside_type.category` correctly groups related codes (e.g., 8A and 8AN both map to "8(a)")
- [ ] `v_set_aside_trend` produces correct yearly aggregation by NAICS
- [ ] API endpoint returns correct DTO for opportunities with and without predecessor contracts
- [ ] Trend endpoint handles NAICS codes with sparse data (few years, few contracts)
- [ ] UI shift indicator renders correctly for all three states (NEW, NO_CHANGE, SHIFTED)
- [ ] Trend chart displays meaningful data with at least 2 years of history
- [ ] Expiring contracts page shows shift column without performance regression

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Create `v_set_aside_shift` view | Database | Medium | — |
| 2 | Create `v_set_aside_trend` view | Database | Low | — |
| 3 | Set-aside shift API endpoint | Backend | Medium | Task 1 |
| 4 | NAICS trend API endpoint | Backend | Medium | Task 2 |
| 5 | Shift indicator on Competitive Intel tab | Frontend | Medium | Task 3 |
| 6 | NAICS trend chart component | Frontend | Medium | Task 4 |
| 7 | Shift column on Expiring Contracts page | Frontend | Low | Task 3 |
