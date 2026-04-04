# Phase 115C-G Validation Report

**Date:** 2026-04-02
**Scope:** QA validation of all unstaged changes for Phases 115C, 115D, 115E, 115F, 115G
**Method:** Automated agent review of SQL migrations, C# API layer, UI layer, and cross-layer consistency

---

## Summary

| Phase | HIGH | MEDIUM | LOW | Consistency |
|-------|------|--------|-----|-------------|
| 115C — Competitive Intel Advanced | 0 | 1 | 5 | All pass |
| 115D — Teaming & Partnerships | 2 | 4 | 4 | All pass |
| 115E — Pipeline Workflow Enhancements | 2 | 4 | 5 | All pass |
| 115F — Onboarding & Past Performance | 3 | 5 | 6 | All pass |
| 115G — UX Review & Insights | 2 | 6 | 6 | All pass |
| **Total** | **9** | **20** | **26** | |

---

## Phase 115C — Competitive Intel Advanced

### HIGH — None

### MEDIUM

1. **Route naming collision on `agency-patterns`**
   - **Files:** `CompetitiveIntelController.cs:43,55`
   - `GET agency-patterns` returns recompete patterns; `GET agency-patterns/{agencyCode}` returns buying patterns. Semantically different resources share a route prefix. A request to `/agency-patterns/DOD` hits buying patterns even if caller intended recompete patterns.
   - **Fix:** Rename buying patterns route to `buying-patterns/{agencyCode}`. Update UI API client (`ui/src/api/competitiveIntel.ts:31`).

### LOW

2. **`v_competitor_dossier` "top NAICS" ordered alphabetically, not by frequency** — `GROUP_CONCAT` uses `ORDER BY fc.naics_code` (alphabetical), not by count. Label "Top 3 NAICS by contract count" is misleading.
   - **Fix:** Change to subquery ordering by frequency.

3. **`new_entrant_win_rate_pct` metric name is misleading** — Measures new vendor penetration rate (% of vendor pool that is new), not win rate (wins/attempts).
   - **Fix:** Rename to `new_vendor_penetration_rate_pct` across view, model, DTO, and TS type.

4. **Dossier only returns active registrations** — `WHERE e.registration_status = 'A'` filters out expired competitors who still have useful historical data. May confuse users searching for known competitors with lapsed registrations.

5. **PIID-based dedup edge case** — `ROW_NUMBER() PARTITION BY c.piid` may drop legitimate different delivery orders under IDVs sharing a PIID. Known trade-off.

6. **`v_competitor_dossier` performance on broad queries** — Joins entity with 4 CTEs + 3 sub-tables, GROUP BY on 25+ columns. Mitigated by service filtering by UEI (single-row lookup).

---

## Phase 115D — Teaming & Partnerships

### HIGH

1. **SBA type code mismatch — `v_mentor_protege_candidate` returns zero rows**
   - **File:** `115d_teaming_partnerships.sql:217`
   - View filters `sba_type_code IN ('8A', 'WOSB', 'EDWOSB', 'HUBZONE', 'SDVOSB')` but actual stored values are SAM.gov API codes: `A4` (8(a)), `A6` (8(a) JV), `XX` (HUBZone), `27` (WOSB), `A2` (EDWOSB). No SDVOSB code exists in `ref_sba_type`.
   - **Impact:** Entire Mentor-Protege page will always be empty.
   - **Fix:** Replace with actual codes from `ref_sba_type`: `IN ('A4', 'A6', 'XX', '27', 'A2')`. Add SDVOSB to seed data if applicable.

2. **Certification filter uses human-readable names but view stores raw codes**
   - **Files:** `115d_teaming_partnerships.sql:44`, `PartnerSearchPage.tsx:24-30`, `TeamingService.cs:32`
   - View `GROUP_CONCAT(DISTINCT esc.sba_type_code)` produces `A4, 27, XX`. UI sends `'8(a)'`, `'WOSB'`, etc. Service `.Contains(certification)` will never match.
   - **Impact:** Certification filtering in Partner Search is completely broken.
   - **Fix:** JOIN `ref_sba_type` in view and use `program_name` instead of `sba_type_code`.

### MEDIUM

3. **Relationship direction values mismatch in UI**
   - **Files:** `115d_teaming_partnerships.sql:317,329`, `PartnerDetailPage.tsx:307`
   - View produces `'PRIME_OF'` and `'SUB_TO'`. UI checks `dir === 'PRIME'` / `dir === 'SUB'`. Chip colors always fall through to `'default'` (gray).
   - **Fix:** Change line 307 to match `'PRIME_OF'` / `'SUB_TO'`.

4. **`agencyCode` parameter name misleading**
   - **Files:** `TeamingController.cs:30`, `TeamingService.cs:36`
   - `agencies_worked_with` column contains full agency names (e.g., "DEPARTMENT OF DEFENSE"), not codes. Users entering a code get no results.
   - **Fix:** Rename parameter to `agency` across controller/service/UI/types. Add placeholder text.

5. **`v_mentor_protege_candidate` Cartesian join on NAICS codes**
   - **File:** `115d_teaming_partnerships.sql:267-272`
   - Joins every protege with every mentor through shared NAICS codes. No built-in limit. `CountAsync()` with no filter will be very expensive.
   - **Fix:** Require at least one filter (protegeUei or naicsCode) at the controller level.

6. **Hop-2 network query loads unbounded hop-1 into memory**
   - **File:** `TeamingService.cs:195-218`
   - Hop-1 loads all direct relationships with no `Take()` limit. For highly connected vendors, this causes memory pressure and large IN-lists.
   - **Fix:** Add `Take(200)` to hop-1 query.

### LOW

7. **DataGrid `getRowId` produces duplicate keys** — `MentorProtegePage.tsx:217` uses `${protegeUei}-${mentorUei}` but same pair can appear with different `sharedNaics`. Fix: include `sharedNaics` in key.

8. **No SDVOSB code in `ref_sba_type` seed data** — `reference_loader.py:740-748`. Even after code fix (#1), SDVOSB entities can't match.

9. **Gap analysis filter is imprecise** — `TeamingService.cs:283-289`. Returns partners who have *any* non-overlapping NAICS, even if they share 95% of codes. Could be more targeted.

10. **View includes zero-contract-history entities** — LEFT JOIN on `contract_agg` means entities with no contracts inflate total count.

---

## Phase 115E — Pipeline Workflow Enhancements

### HIGH

1. **No validation of `NewStatus` in `BulkUpdateStatusAsync` — arbitrary status injection**
   - **File:** `PipelineService.cs:279-334`
   - Checks prospect is not terminal, but does NOT validate `request.NewStatus` is a valid value. Caller can set any arbitrary string. Also skips status transition validation (e.g., `NEW` -> `WON` directly), unlike single-prospect `UpdateStatusAsync` which validates against `StatusFlow`.
   - **Fix:** Add allowlist validation against `StatusFlow` dictionary used by `ProspectService`.

2. **`GenerateReverseTimelineAsync` appends milestones without checking for duplicates**
   - **File:** `PipelineService.cs:229-277`
   - Calling generate-timeline multiple times on the same prospect creates duplicate milestone sets. No check, no warning, no replace option.
   - **Fix:** Check for existing milestones and return error/warning, or add `replaceExisting` parameter.

### MEDIUM

3. **`BulkUpdateStatusAsync` inconsistent SaveChanges timing with `RecordStatusChangeAsync`**
   - **File:** `PipelineService.cs:302-333`
   - `RecordStatusChangeAsync` queries DB with `AsNoTracking()` for last history entry. In a bulk loop, previous iterations' records aren't saved yet (SaveChanges is after loop). Duplicate prospect IDs in request would produce incorrect `timeInOldHours`.
   - **Fix:** Deduplicate `request.ProspectIds` at the start.

4. **`UpdateMilestoneRequest` cannot clear `Notes` to null**
   - **File:** `PipelineService.cs:192-206`
   - `if (request.Notes != null)` means client cannot explicitly clear notes. `null` means "don't change." TS type `notes?: string | null` suggests clearing should be possible.
   - **Fix:** Use empty string to clear, or sentinel pattern.

5. **`v_pipeline_funnel` duplicates win/loss counts across all status rows**
   - **File:** `115e_pipeline_workflow.sql:56-103`
   - `outcomes` CTE computes org-level `won_count`/`lost_count`, then LEFT JOINs to `status_counts` on `organization_id` only. Every status row for the same org gets identical win/loss values. Semantically confusing.
   - **Fix:** Move win rate to separate endpoint, or document as org-level aggregate.

6. **`PipelineCalendarPage` weekday header misaligned with `date-fns` v4 default**
   - **File:** `PipelineCalendarPage.tsx:48,59`
   - `WEEKDAYS` array starts with `'Sun'` but `date-fns` v4 `startOfWeek` defaults to Monday (ISO).
   - **Fix:** Pass `{ weekStartsOn: 0 }` to `startOfWeek`/`endOfWeek`, or change array to start Monday.

### LOW

7. **`BulkStatusUpdateResult.Errors` nullability mismatch** — C# initializes as empty list (non-null), TS marks as `errors?: string[]`. Minor inconsistency.

8. **`ProspectStatusHistory` lacks `[Column]` attributes while `ProspectMilestone` uses them** — Both work via `UseSnakeCaseNamingConvention()` but inconsistent style.

9. **Stale prospect view uses hardcoded 14-day threshold** — `115e_pipeline_workflow.sql:153`. Phase plan mentions "configurable threshold" but it's hardcoded. Acceptable for initial impl.

10. **Calendar view excludes WON prospects** — `115e_pipeline_workflow.sql:128`. Design choice, not a bug, but users may want context.

11. **Revenue forecast groups by `response_deadline` month, not expected award month** — No `expected_award_date` column exists, so `response_deadline` is used as approximation. "Forecast" label is slightly misleading.

---

## Phase 115F — Onboarding & Past Performance

### HIGH

1. **Non-unique `getRowId` on PastPerformanceRelevancePage will crash DataGrid**
   - **File:** `PastPerformanceRelevancePage.tsx:170`
   - `getRowId` uses `row.pastPerformanceId`, but `v_past_performance_relevance` produces multiple rows per `past_performance_id` (one per matched opportunity). MUI DataGrid will throw on duplicate IDs.
   - **Fix:** Change to composite key: `` `${row.pastPerformanceId}-${row.noticeId}` ``

2. **SizeStandardMonitorPage `formatValue` never formats revenue as currency**
   - **File:** `SizeStandardMonitorPage.tsx:30-36`
   - Checks `type?.toLowerCase().includes('revenue')` but SQL view returns `size_standard_type` as `'R'` (revenue) or `'E'` (employees). `'R'` does not contain `'revenue'`, so revenue values display as raw numbers.
   - **Fix:** Check `type === 'R'` instead. Display units (millions) alongside value.

3. **`v_past_performance_relevance` Cartesian explosion**
   - **File:** `115f_onboarding_past_performance.sql:183-246`
   - Joins `organization_past_performance` to `organization_naics` (1:many) then to `opportunity` (1:many) on NAICS match. `DISTINCT` mitigates duplicates but DB must compute full cross-join first. Service `.Take(100)` doesn't help DB performance.
   - **Recommendation:** Materialized summary table or restructure to avoid Cartesian.

### MEDIUM

4. **ProfileCompletenessCard recommendation keys don't match SQL `missing_fields` output**
   - **Files:** `ProfileCompletenessCard.tsx:22-32`, `115f_onboarding_past_performance.sql:59-71`
   - SQL produces `'NAICS Codes'`, `'PSC Codes'`, `'Past Performance'`, `'Business Type'`, `'Size Standard'`. UI `FIELD_RECOMMENDATIONS` uses keys `'NAICS'`, `'PSC'`, `'PastPerformance'`, etc. None match. Per-field recommendations never display (falls back to generic).
   - **Fix:** Align keys to match SQL output strings.

5. **Missing PSC code validation against `ref_psc_code`**
   - **File:** `OnboardingService.cs:312-338`
   - `AddPscCodeAsync` checks duplicates but never validates the code exists in `ref_psc_code`. Users can add arbitrary strings.
   - **Fix:** Add validation against `RefPscCodes`.

6. **Missing null/empty validation on `UeiImportRequest.Uei`**
   - **File:** `UeiImportRequest.cs:8`
   - `[Required]` + `[MaxLength(13)]` but no `[MinLength]`. Empty string passes `[Required]`. UEI codes are exactly 12 characters.
   - **Fix:** Add `[MinLength(12)]`.

7. **UEI VARCHAR length mismatch across tables**
   - `entity.uei_sam` is `VARCHAR(12)`, `organization.uei_sam` is `VARCHAR(13)`. DTO allows `MaxLength(13)`. Schema inconsistency could cause subtle join issues.

8. **PSC code add/delete mutations don't invalidate `profileCompleteness` query**
   - **File:** `useOnboarding.ts:75-94`
   - After adding/deleting PSC codes, only `pscCodes` query is invalidated. Profile completeness card stays stale until manual refresh.
   - **Fix:** Also invalidate `queryKeys.onboarding.profileCompleteness` in both mutations.

### LOW

9. **`CertificationExpirationAlertView.DaysUntilExpiration` typed as `int` but `DATEDIFF` returns `BIGINT`** — Practically fine for 90-day range.

10. **`v_past_performance_relevance` agency_match uses exact string equality** — `pp.agency_name = opp.department_name` requires exact match. User-entered vs SAM.gov values will rarely match exactly (e.g., "Department of Defense" vs "DEPT OF DEFENSE").

11. **`v_portfolio_gap_analysis` `NO_DATA` gap type not handled in UI** — `PortfolioGapAnalysisPage.tsx` `GAP_CONFIG` doesn't include it. Renders with default chip color and raw type string.

12. **No PSC import during UEI auto-import** — `ImportFromUeiAsync` imports NAICS codes and certifications but not PSC codes despite `entity_psc` table existing. Phase plan mentions this as a goal.

13. **`UeiImportResultDto` has no `PscCodesImported` field** — Related to #12.

14. **`v_sba_size_standard_monitor` integer division risk** — `employee_count / ss.size_standard` is safe since `size_standard` is `DECIMAL(13,2)`, but adding explicit cast would be defensive.

---

## Phase 115G — UX Review & Insights

### HIGH

1. **EF Core DbContext thread-safety violation**
   - **File:** `InsightsService.cs:153-159`
   - `GetDataQualityDashboardAsync` runs 3 parallel queries via `Task.WhenAll` on the same `_context`. EF Core DbContext is not thread-safe — will produce intermittent `InvalidOperationException`.
   - **Fix:** Execute sequentially, or inject `IDbContextFactory<FedProspectorDbContext>` and create separate context instances per query.

2. **`FromSqlRaw` with parameterized LIMIT fails on MySQL**
   - **File:** `InsightsService.cs:75-80`
   - Uses `LIMIT @maxResults` with `MySqlParameter`. MySQL does not support parameterized LIMIT in prepared statements.
   - **Fix:** Use `FromSqlInterpolated`, or inject the validated integer directly into the SQL string (safe since validated to 1-100).

### MEDIUM

3. **`v_cross_source_validation` label says `sam_entity` but table is `entity`** — Cosmetic mismatch in migration labels.

4. **`v_data_completeness` division-by-zero when tables are empty** — `SUM(...) / total.cnt * 100` will error when `total.cnt = 0`.
   - **Fix:** Use `NULLIF(total.cnt, 0)`.

5. **`v_similar_opportunity` is O(N^2) Cartesian product** — Self-join on `opportunity` without WHERE clause. Any unfiltered query will be extremely expensive. Service uses raw SQL with WHERE, but direct DB queries are dangerous.

6. **Controller double-fetches data for single prospect** — `InsightsController.cs:126-138` calls `GetProspectCompetitorSummaryAsync` then `GetProspectCompetitorSummariesAsync` for ownership check. First call is wasted.
   - **Fix:** Only call the org-filtered version.

7. **`LATERAL` join requires MySQL 8.0.14+** — `115g_ux_review_insights.sql:412,427`. Current env is 8.4.8 so no issue, but worth documenting as minimum version requirement.

8. **`v_data_completeness` silently omits empty tables** — Cross join with empty table returns 0 rows. Dashboard will not show 0% completeness for empty sources.

### LOW

9. **DTO omits `OrganizationId`** — Forces double-query pattern in controller (related to #6).

10. **`DataFreshnessView.RecordsLoaded` is `int`** — Could overflow for very large loads. `long` would be safer.

11. **Similarity score displayed as `%` but is a weighted point total** — `SimilarOpportunitiesPanel.tsx:169` renders `{score}%`. Score is 0-100 points, not a percentage. Semantically fine but could confuse if weights change.

12. **Data Quality page has no `AdminGuard` in UI routes** — `routes.tsx:457-464`. Backend enforces `OrgAdmin` but UI shows the page (then 403 error). Should wrap in `AdminGuard` or hide sidebar link.

13. **Sidebar placement for admin-only Data Quality page** — Listed under "Tools" but other admin items are under "Settings".

14. **Static query key for data quality** — No parameterization. Correct for this global endpoint.

---

## Cross-Layer Consistency (All Phases)

All validated phases passed these checks:

- **Program.cs** — All services registered as scoped
- **DbContext** — All views and new tables mapped with correct names
- **View models** — `[Column]` attributes match SQL column names
- **DTOs** — Properties match view models
- **TypeScript types** — camelCase equivalents match C# PascalCase DTOs
- **API client URLs** — Match controller route attributes
- **Routes** — All pages registered in `routes.tsx`
- **Sidebar** — Navigation links present for all primary pages
- **Query keys** — All key factories registered in `queryKeys.ts`
- **Imports** — All UI imports resolve to existing files

---

## Recommended Fix Priority

### Must Fix Before Merge (HIGH)

| # | Phase | Issue | Effort |
|---|-------|-------|--------|
| 1 | 115D | SBA type code mismatch in `v_mentor_protege_candidate` | Small — swap IN-list values |
| 2 | 115D | Certification filter code vs name mismatch | Medium — JOIN ref_sba_type in view |
| 3 | 115E | No status validation in `BulkUpdateStatusAsync` | Small — add allowlist check |
| 4 | 115E | `GenerateReverseTimelineAsync` creates duplicate milestones | Small — check existing first |
| 5 | 115F | Non-unique `getRowId` crashes DataGrid on PastPerformancePage | Small — composite key |
| 6 | 115F | `formatValue` never formats revenue as currency | Small — check `type === 'R'` |
| 7 | 115F | `v_past_performance_relevance` Cartesian explosion | Medium — restructure view |
| 8 | 115G | DbContext thread-safety in `GetDataQualityDashboardAsync` | Small — make sequential |
| 9 | 115G | `FromSqlRaw` parameterized LIMIT | Small — use interpolated string |

### Should Fix (MEDIUM)

| # | Phase | Issue | Effort |
|---|-------|-------|--------|
| 10 | 115C | Route naming collision `agency-patterns` | Small — rename route |
| 11 | 115D | Relationship direction value mismatch | Small — fix string comparison |
| 12 | 115D | `agencyCode` parameter name misleading | Small — rename parameter |
| 13 | 115D | Mentor-protege Cartesian join performance | Medium — require filter |
| 14 | 115D | Unbounded hop-1 network query | Small — add Take() |
| 15 | 115E | Bulk update SaveChanges timing with duplicate IDs | Small — deduplicate IDs |
| 16 | 115E | `UpdateMilestoneRequest` can't clear Notes to null | Small — use empty string |
| 17 | 115E | `v_pipeline_funnel` duplicates win/loss across rows | Small — document or separate |
| 18 | 115E | Calendar weekday header misaligned with date-fns v4 | Small — pass weekStartsOn |
| 19 | 115F | ProfileCompletenessCard recommendation keys mismatch | Small — align keys to SQL |
| 20 | 115F | Missing PSC code validation against `ref_psc_code` | Small — add lookup |
| 21 | 115F | Missing `[MinLength(12)]` on UEI import | Small — add annotation |
| 22 | 115F | UEI VARCHAR length mismatch (12 vs 13) | Small — align schema |
| 23 | 115F | PSC mutations don't invalidate profileCompleteness query | Small — add invalidation |
| 24 | 115G | Division-by-zero in `v_data_completeness` | Small — add NULLIF |
| 25 | 115G | Cartesian product in `v_similar_opportunity` | Medium — document or restructure |
| 26 | 115G | Controller double-fetch | Small — remove redundant call |
| 27 | 115G | Empty table omission in completeness view | Medium — restructure query |
| 28 | 115G | `LATERAL` join MySQL version requirement | Small — document |
