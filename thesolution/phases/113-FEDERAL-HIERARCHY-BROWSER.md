# Phase 113: Federal Hierarchy Browser

**Status:** IN PROGRESS
**Priority:** Medium
**Dependencies:** Phase 70 (UI Complete), Phase 5D (Federal Hierarchy ETL Complete)

---

## Summary

Add a full-featured Federal Hierarchy browser to the UI, letting users explore the three-level government org structure (Department > Sub-Tier > Office), search and filter organizations, view detail pages for each org with related opportunities/awards, and trigger hierarchy data refreshes from the UI instead of the CLI.

Cross-reference linking (making agency/office names throughout the app clickable) is deferred to Phase 113B.

## Problem / Current State

1. **No visibility into hierarchy data.** The `federal_organization` table holds ~3,400 records (20 departments, ~738 sub-tiers, ~2,500 offices) loaded via CLI, but the UI has no way to browse, search, or inspect them.
2. **Office/agency names are dead text.** Opportunity detail pages show `departmentName`, `subTier`, and `office` as plain strings. Award and entity pages show agency names the same way. Users can't click through to see what else that office is buying.
3. **Data refresh requires CLI access.** Running `load hierarchy` and `load offices` requires terminal access and knowledge of CLI flags. A non-technical user can't trigger a refresh.
4. **No cross-reference.** Users can't answer "What opportunities does this office have?" or "How much has this agency awarded?" without manually searching.

## Design

### Data Model

No schema changes required. The existing `federal_organization` table with its self-referencing `parent_org_id` and `level` column (1=Department, 2=Sub-Tier, 3=Office) supports the full tree.

Cross-references to opportunities and awards use string matching against existing columns:
- `opportunity.department_name`, `opportunity.sub_tier`, `opportunity.office`
- `opportunity.full_parent_path_code` (contains agency codes dot-separated)
- `fpds_contract.agency_name`, `fpds_contract.contracting_office_name`
- `usaspending_award.awarding_agency_name`, `usaspending_award.awarding_sub_agency_name`

Phase 200 (Database Normalization) will add proper FK columns; this phase uses string/code matching which is sufficient for browsing.

### API Endpoints (C# ASP.NET Core)

New controller: `FederalHierarchyController`

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/v1/hierarchy` | List/search organizations (paginated, filterable) |
| GET | `/api/v1/hierarchy/{fhOrgId}` | Single organization detail |
| GET | `/api/v1/hierarchy/{fhOrgId}/children` | Direct children of an organization |
| GET | `/api/v1/hierarchy/tree` | Top-level departments with child counts (for tree root) |
| GET | `/api/v1/hierarchy/{fhOrgId}/opportunities` | Opportunities linked to this org (paginated) |
| GET | `/api/v1/hierarchy/{fhOrgId}/awards` | Awards linked to this org (paginated) |
| GET | `/api/v1/hierarchy/{fhOrgId}/stats` | Aggregate stats (opportunity count, award $, active contracts) |
| POST | `/api/v1/hierarchy/refresh` | Trigger hierarchy data refresh (admin only) |
| GET | `/api/v1/hierarchy/refresh/status` | Check refresh job status |

### UI Pages & Components

#### 1. Hierarchy Browse Page (`/hierarchy`)
- **Tree panel** (left): Expandable tree starting at departments. Lazy-loads children on expand. Shows org count badge per node.
- **List panel** (right): DataTable of orgs at the selected level. Columns: Name, Type, Status, Agency Code, CGAC, Opportunity Count, Award Count.
- **Search bar**: Filter tree/list by name, agency code, or CGAC. Debounced, searches all levels.
- **Breadcrumb trail**: Department > Sub-Tier > Office navigation.
- **Status filter**: Active / Inactive / All toggle.
- **Export**: CSV export of current filtered list.

#### 2. Organization Detail Page (`/hierarchy/:fhOrgId`)
- **Header**: Org name, type badge (Dept/Sub-Tier/Office), status chip, agency code, CGAC.
- **Breadcrumb**: Full path from department down to current org.
- **Tabs**:
  - **Overview**: Description, dates (created, last modified, last loaded), parent org link, code identifiers.
  - **Child Organizations**: DataTable of direct children (if Dept or Sub-Tier). Clickable rows navigate to child detail.
  - **Opportunities**: Paginated table of opportunities where department/sub_tier/office matches this org's name (or descendant names). Clickable rows link to opportunity detail.
  - **Awards**: Paginated table of awards where agency/office matches. Links to award detail.
  - **Statistics**: Opportunity counts by type/status, total award dollars, top NAICS codes, set-aside breakdown. Simple charts (bar/pie).

#### 3. Hierarchy Refresh Panel (Admin only)
- Located on the browse page header or as a settings sub-page.
- **Refresh Hierarchy** button: Triggers Level 1-2 load (departments + sub-tiers).
- **Refresh Offices** button: Triggers Level 3 load.
- **Full Refresh** button: Truncate + reload all levels (with confirmation dialog).
- **Status display**: Shows last refresh timestamp, record counts per level, and any in-progress job status.
- **API key selector**: Choose Key 1 or Key 2 (shows remaining quota if available).
- Requires `isSystemAdmin` flag.

> **Note:** Cross-reference links (wrapping agency/office names app-wide with clickable links into this browser) are deferred to Phase 113B.

### Refresh Backend Design

The refresh endpoints trigger Python CLI commands server-side. Two approaches (choose during implementation):

**Option A — Direct subprocess** (simpler):
- C# API spawns `python ./fed_prospector/main.py load hierarchy --key=2` as a background process.
- Polls process status. Returns job ID for frontend polling.

**Option B — Job queue via etl_load_log** (if Phase 110Y Request Poller is done):
- C# API inserts a "requested" row into a job queue table.
- The Python poller service picks it up and executes.
- Frontend polls job status via the refresh/status endpoint.

Option B is preferred if 110Y is complete; Option A is the fallback.

---

## Tasks

### Task 1: C# API — FederalHierarchyController + Service

- [x] Create `FederalHierarchyController` with routes listed above.
- [x] Create `IFederalHierarchyService` / `FederalHierarchyService` in Infrastructure layer.
- [x] Search/list endpoint: paginated query on `federal_organization` with filters (name, type, status, agency code, CGAC). Full-text search on name.
- [x] Detail endpoint: single org by `fh_org_id`, include parent chain (recursive CTE or iterative lookup for breadcrumb).
- [x] Children endpoint: `WHERE parent_org_id = @fhOrgId ORDER BY fh_org_name`.
- [x] Tree endpoint: `WHERE level = 1 AND status = 'Active'` with `COUNT(*)` of descendants per department (subquery or CTE).
- [x] Opportunities endpoint: Match org name against `opportunity.department_name`, `sub_tier`, or `office`. Include descendant matching (a department should show all its sub-tier and office opportunities).
- [ ] Awards endpoint: Match against `fpds_contract.agency_name`, `contracting_office_name`, or `usaspending_award` fields. Include descendant matching. *(Removed from detail page — too slow for large orgs)*
- [ ] Stats endpoint: Aggregate counts and sums from opportunity/award tables for the org and its descendants. *(Removed from detail page — too slow for large orgs)*
- [x] Refresh endpoint: Admin-only (`[Authorize(Policy = "SystemAdmin")]`), triggers appropriate Python CLI command. Returns job ID. *(Returns 501 stub — needs Phase 110Y or subprocess implementation)*
- [x] Refresh status endpoint: Returns last load info from `etl_load_log WHERE source = 'fedhier'`.

**DTOs:**
```
FederalOrgListItemDto { fhOrgId, fhOrgName, fhOrgType, status, agencyCode, cgac, level, parentOrgId, opportunityCount?, awardCount? }
FederalOrgDetailDto { ...ListItem, description, oldfpdsOfficeCode, createdDate, lastModifiedDate, lastLoadedAt, parentChain: FederalOrgBreadcrumb[] }
FederalOrgBreadcrumb { fhOrgId, fhOrgName, fhOrgType, level }
FederalOrgTreeNodeDto { fhOrgId, fhOrgName, childCount, descendantCount }
FederalOrgSearchRequest { keyword?, fhOrgType?, status?, agencyCode?, cgac?, page, pageSize, sortBy?, sortDescending? }
FederalOrgStatsDto { opportunityCount, openOpportunityCount, awardCount, totalAwardDollars, topNaicsCodes: {code,count}[], setAsideBreakdown: {type,count}[] }
HierarchyRefreshRequestDto { level: "hierarchy"|"offices"|"full", apiKey: 1|2 }
HierarchyRefreshStatusDto { isRunning, lastRefreshAt, lastRefreshRecordCount, levelsLoaded: {level,count}[], jobId? }
```

### Task 2: UI — Hierarchy Browse Page

- [x] Create `HierarchyBrowsePage` component at route `/hierarchy`.
- [x] Add "Federal Hierarchy" nav item to Sidebar under **Research** section (icon: `AccountTree`).
- [x] **Tree Panel**: MUI `TreeView` component (or custom expandable list). Load departments on mount, lazy-load children on expand via `/hierarchy/{id}/children`.
- [x] **List Panel**: MUI DataGrid showing orgs at selected tree node level. Paginated, sortable.
- [x] **Search**: Debounced text input searching name/code. Calls `/hierarchy?keyword=...`. Results replace list panel content.
- [x] **Filters**: Status toggle (Active/Inactive/All), org type filter (Department/Sub-Tier/Office).
- [x] **Breadcrumb**: Show hierarchy path. Clicking a breadcrumb level navigates to that org's children.
- [x] URL state: `/hierarchy?type=Office&status=Active&keyword=navy&page=1`.

### Task 3: UI — Organization Detail Page

- [x] Create `OrganizationDetailPage` component at route `/hierarchy/:fhOrgId`.
- [x] **Header**: Org name, type badge (`Chip`), status chip, identifiers (agency code, CGAC, FPDS code).
- [x] **Breadcrumb**: Full parent chain from API, each level clickable.
- [x] **Overview Tab**: Description, dates, parent org link, all code identifiers.
- [x] **Children Tab** (Dept/Sub-Tier only): DataGrid of child orgs, clickable rows.
- [x] **Opportunities Tab**: Paginated DataGrid from `/hierarchy/{id}/opportunities`. Columns: Title, Solicitation #, Type, Status, Response Deadline, Set-Aside, Value. Row click → opportunity detail.
- [ ] **Awards Tab**: *(Removed — too slow for large orgs, causes timeouts)*
- [ ] **Statistics Tab**: *(Removed — too slow for large orgs, causes timeouts)*

### Task 4: UI — Hierarchy Refresh Panel (Admin)

- [x] Add refresh controls to browse page header (visible only to `isSystemAdmin` users).
- [x] **Refresh Hierarchy** button: POST `/hierarchy/refresh` with `{level: "hierarchy"}`. Confirm dialog.
- [x] **Refresh Offices** button: POST with `{level: "offices"}`. Confirm dialog explaining ~738 API calls.
- [x] **Full Refresh** button: POST with `{level: "full"}`. Double-confirm dialog (destructive).
- [x] **API Key selector**: Radio/toggle for Key 1 vs Key 2. Show note about rate limits (Key 1: 10/day, Key 2: 1000/day).
- [x] **Status indicator**: Poll `/hierarchy/refresh/status` while job is running. Show progress bar or spinner with record count.
- [x] **Last Refresh info**: Display last refresh timestamp and record counts per level in a summary card.

### Task 5: TanStack Query Hooks

- [x] `useHierarchySearch(params)` — paginated search/list query.
- [x] `useHierarchyDetail(fhOrgId)` — single org detail with parent chain.
- [x] `useHierarchyChildren(fhOrgId)` — lazy-loaded children for tree expansion.
- [x] `useHierarchyTree()` — top-level departments with counts.
- [x] `useHierarchyOpportunities(fhOrgId, pagination)` — related opportunities.
- [ ] `useHierarchyAwards(fhOrgId, pagination)` — related awards. *(Not implemented — Awards tab removed)*
- [ ] `useHierarchyStats(fhOrgId)` — aggregate stats. *(Not implemented — Statistics tab removed)*
- [x] `useHierarchyRefresh()` — mutation hook for triggering refresh.
- [x] `useHierarchyRefreshStatus()` — polling query for refresh status.

### Task 6: TypeScript Types

- [x] Add all DTOs to `ui/src/types/api.ts`:
  - `FederalOrgListItem`, `FederalOrgDetail`, `FederalOrgBreadcrumb`
  - `FederalOrgTreeNode`, `FederalOrgSearchParams`
  - `FederalOrgStats`, `NaicsBreakdown`, `SetAsideBreakdown`
  - `HierarchyRefreshRequest`, `HierarchyRefreshStatus`
- [x] Add API client functions to `ui/src/api/`.
- [x] Note: `AgencyLink`-related types (e.g., `OrgLookupResult`) belong in Phase 113B.

### Task 7: Testing

- [ ] C# xUnit tests for `FederalHierarchyService` (search, detail, children, tree, stats, descendant matching).
- [ ] C# integration tests for controller endpoints.
- [ ] Python: No changes needed (existing CLI/loader tests cover ETL).
- [ ] Manual test plan: Tree navigation, search, detail page tabs, refresh flow.

---

## Code Touchpoints

| File | What to do |
|------|------------|
| `api/src/FedProspector.Api/Controllers/FederalHierarchyController.cs` | **NEW** — All hierarchy endpoints |
| `api/src/FedProspector.Core/DTOs/FederalHierarchy/` | **NEW** — Request/response DTOs |
| `api/src/FedProspector.Core/Interfaces/IFederalHierarchyService.cs` | **NEW** — Service interface |
| `api/src/FedProspector.Infrastructure/Services/FederalHierarchyService.cs` | **NEW** — Service implementation (queries, matching, stats) |
| `api/src/FedProspector.Infrastructure/Data/AppDbContext.cs` | Verify `FederalOrganization` DbSet exists (it does) |
| `ui/src/pages/HierarchyBrowsePage.tsx` | **NEW** — Browse/search page |
| `ui/src/pages/OrganizationDetailPage.tsx` | **NEW** — Detail page with tabs |
| `ui/src/components/hierarchy/HierarchyTree.tsx` | **NEW** — Expandable tree panel |
| `ui/src/components/hierarchy/HierarchyRefreshPanel.tsx` | **NEW** — Admin refresh controls |
| `ui/src/components/hierarchy/OrgStatsCards.tsx` | **NEW** — Statistics display cards/charts |
| `ui/src/hooks/useHierarchy.ts` | **NEW** — TanStack Query hooks |
| `ui/src/api/hierarchy.ts` | **NEW** — Axios API client functions |
| `ui/src/types/api.ts` | Add hierarchy DTOs |
| `ui/src/routes.tsx` | Add `/hierarchy` and `/hierarchy/:fhOrgId` routes |
| `ui/src/components/layout/Sidebar.tsx` | Add "Federal Hierarchy" nav item under Research |
| `api/tests/` | **NEW** — xUnit tests for hierarchy service/controller |

---

## Known Issues / Deferred

- **Refresh endpoint returns 501 (stub)** — The POST `/hierarchy/refresh` endpoint is wired in the UI but the backend returns 501 Not Implemented. Needs Phase 110Y (Request Poller Service) or a direct subprocess implementation to actually trigger Python CLI loads.
- **Awards tab and Statistics tab removed from detail page** — These tabs were cut because the underlying queries are too slow for large orgs (e.g., Department of Defense). The queries time out on departments with thousands of descendant orgs. Needs query optimization or pre-aggregation before re-enabling.
- **5,023 orgs have NULL names** — SAM.gov data quality issue. These records exist in `federal_organization` with valid `fh_org_id` but no `fh_org_name`. They appear as blank rows in search results.
- **33 MAJOR COMMAND orgs have NULL level** — These orgs have `fh_org_type = 'MAJOR COMMAND'` but `level` is NULL (SAM.gov does not assign them a numeric level). They are shown in the tree as children of their parent org but hidden from the Children tab DataGrid to avoid confusion.

---

## Out of Scope

- **Cross-reference links** (clickable agency/office names app-wide) — That's Phase 113B.
- **Database normalization** (adding FK columns from opportunity/award to federal_organization) — That's Phase 200.
- **FPDS agency code mapping table** — Deferred to Phase 200 where a proper crosswalk can be built.
- **Org-level notifications/alerts** — Future enhancement (e.g., "notify me when this office posts new opportunities").
- **Historical hierarchy tracking** — The current table tracks current state only; point-in-time hierarchy snapshots are out of scope.
- **Hierarchy data editing** — This phase is read-only + refresh from SAM.gov. No manual org creation/editing.
- **Sub-office (Level 4+) support** — SAM.gov hierarchy has three levels only.
