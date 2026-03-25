# Phase 113: Federal Hierarchy Browser

**Status:** PLANNED
**Priority:** Medium
**Dependencies:** Phase 70 (UI Complete), Phase 5D (Federal Hierarchy ETL Complete)

---

## Summary

Add a full-featured Federal Hierarchy browser to the UI, letting users explore the three-level government org structure (Department → Sub-Tier → Office), search and filter organizations, view detail pages for each org with related opportunities/awards, and trigger hierarchy data refreshes from the UI instead of the CLI.

Every place in the app that currently displays an office name, department, or agency as plain text becomes a clickable link into this new hierarchy browser.

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

#### 4. Cross-Reference Links (App-Wide)
Anywhere the app displays an agency/office name, make it a clickable link:
- **Opportunity Detail Page**: `departmentName`, `subTier`, `office` fields → link to matching hierarchy org.
- **Opportunity Search Results**: Department column → link.
- **Award Detail Page**: `agencyName`, `contractingOfficeName`, `fundingAgencyName` → links.
- **Entity Detail Page**: If agency references exist → links.

Link resolution: Match by name against `federal_organization.fh_org_name` (and optionally by code against `agency_code`). Since names aren't normalized FKs yet, use best-match lookup (exact match preferred, fallback to LIKE).

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

- [ ] Create `FederalHierarchyController` with routes listed above.
- [ ] Create `IFederalHierarchyService` / `FederalHierarchyService` in Infrastructure layer.
- [ ] Search/list endpoint: paginated query on `federal_organization` with filters (name, type, status, agency code, CGAC). Full-text search on name.
- [ ] Detail endpoint: single org by `fh_org_id`, include parent chain (recursive CTE or iterative lookup for breadcrumb).
- [ ] Children endpoint: `WHERE parent_org_id = @fhOrgId ORDER BY fh_org_name`.
- [ ] Tree endpoint: `WHERE level = 1 AND status = 'Active'` with `COUNT(*)` of descendants per department (subquery or CTE).
- [ ] Opportunities endpoint: Match org name against `opportunity.department_name`, `sub_tier`, or `office`. Include descendant matching (a department should show all its sub-tier and office opportunities).
- [ ] Awards endpoint: Match against `fpds_contract.agency_name`, `contracting_office_name`, or `usaspending_award` fields. Include descendant matching.
- [ ] Stats endpoint: Aggregate counts and sums from opportunity/award tables for the org and its descendants.
- [ ] Refresh endpoint: Admin-only (`[Authorize(Policy = "SystemAdmin")]`), triggers appropriate Python CLI command. Returns job ID.
- [ ] Refresh status endpoint: Returns last load info from `etl_load_log WHERE source = 'fedhier'`.

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

- [ ] Create `HierarchyBrowsePage` component at route `/hierarchy`.
- [ ] Add "Federal Hierarchy" nav item to Sidebar under **Research** section (icon: `AccountTree`).
- [ ] **Tree Panel**: MUI `TreeView` component (or custom expandable list). Load departments on mount, lazy-load children on expand via `/hierarchy/{id}/children`.
- [ ] **List Panel**: MUI DataGrid showing orgs at selected tree node level. Paginated, sortable.
- [ ] **Search**: Debounced text input searching name/code. Calls `/hierarchy?keyword=...`. Results replace list panel content.
- [ ] **Filters**: Status toggle (Active/Inactive/All), org type filter (Department/Sub-Tier/Office).
- [ ] **Breadcrumb**: Show hierarchy path. Clicking a breadcrumb level navigates to that org's children.
- [ ] URL state: `/hierarchy?type=Office&status=Active&keyword=navy&page=1`.

### Task 3: UI — Organization Detail Page

- [ ] Create `OrganizationDetailPage` component at route `/hierarchy/:fhOrgId`.
- [ ] **Header**: Org name, type badge (`Chip`), status chip, identifiers (agency code, CGAC, FPDS code).
- [ ] **Breadcrumb**: Full parent chain from API, each level clickable.
- [ ] **Overview Tab**: Description, dates, parent org link, all code identifiers.
- [ ] **Children Tab** (Dept/Sub-Tier only): DataGrid of child orgs, clickable rows.
- [ ] **Opportunities Tab**: Paginated DataGrid from `/hierarchy/{id}/opportunities`. Columns: Title, Solicitation #, Type, Status, Response Deadline, Set-Aside, Value. Row click → opportunity detail.
- [ ] **Awards Tab**: Paginated DataGrid from `/hierarchy/{id}/awards`. Columns: Contract #, Vendor, Award Amount, Period, NAICS. Row click → award detail.
- [ ] **Statistics Tab**: Cards showing counts + totals. Bar chart for NAICS breakdown. Pie chart for set-aside distribution.

### Task 4: UI — Hierarchy Refresh Panel (Admin)

- [ ] Add refresh controls to browse page header (visible only to `isSystemAdmin` users).
- [ ] **Refresh Hierarchy** button: POST `/hierarchy/refresh` with `{level: "hierarchy"}`. Confirm dialog.
- [ ] **Refresh Offices** button: POST with `{level: "offices"}`. Confirm dialog explaining ~738 API calls.
- [ ] **Full Refresh** button: POST with `{level: "full"}`. Double-confirm dialog (destructive).
- [ ] **API Key selector**: Radio/toggle for Key 1 vs Key 2. Show note about rate limits (Key 1: 10/day, Key 2: 1000/day).
- [ ] **Status indicator**: Poll `/hierarchy/refresh/status` while job is running. Show progress bar or spinner with record count.
- [ ] **Last Refresh info**: Display last refresh timestamp and record counts per level in a summary card.

### Task 5: Cross-Reference Links (App-Wide)

- [ ] Create shared `AgencyLink` component: Given an org name (and optional code), renders a clickable link to `/hierarchy?keyword={name}` (or direct `/hierarchy/{id}` if ID is known).
- [ ] **Resolution strategy**: The `AgencyLink` component first tries exact name match via a lightweight API call (or client-side cache of org names). Falls back to search link if no exact match.
- [ ] **Caching**: Use TanStack Query with long `staleTime` (30 min) for org name→ID lookups since hierarchy data rarely changes.
- [ ] Update `OpportunityDetailPage`: Wrap `departmentName`, `subTier`, `office` with `AgencyLink`.
- [ ] Update `OpportunitySearchPage`: Make department column render as `AgencyLink`.
- [ ] Update `AwardDetailPage`: Wrap `agencyName`, `contractingOfficeName`, `fundingAgencyName` with `AgencyLink`.
- [ ] Update any other pages displaying agency/office names (entity detail, subaward detail, etc.).

### Task 6: TanStack Query Hooks

- [ ] `useHierarchySearch(params)` — paginated search/list query.
- [ ] `useHierarchyDetail(fhOrgId)` — single org detail with parent chain.
- [ ] `useHierarchyChildren(fhOrgId)` — lazy-loaded children for tree expansion.
- [ ] `useHierarchyTree()` — top-level departments with counts.
- [ ] `useHierarchyOpportunities(fhOrgId, pagination)` — related opportunities.
- [ ] `useHierarchyAwards(fhOrgId, pagination)` — related awards.
- [ ] `useHierarchyStats(fhOrgId)` — aggregate stats.
- [ ] `useHierarchyRefresh()` — mutation hook for triggering refresh.
- [ ] `useHierarchyRefreshStatus()` — polling query for refresh status.
- [ ] `useOrgLookup(name)` — lightweight name→ID resolution for `AgencyLink`.

### Task 7: TypeScript Types

- [ ] Add all DTOs to `ui/src/types/api.ts`:
  - `FederalOrgListItem`, `FederalOrgDetail`, `FederalOrgBreadcrumb`
  - `FederalOrgTreeNode`, `FederalOrgSearchParams`
  - `FederalOrgStats`, `NaicsBreakdown`, `SetAsideBreakdown`
  - `HierarchyRefreshRequest`, `HierarchyRefreshStatus`
- [ ] Add API client functions to `ui/src/api/`.

### Task 8: Testing

- [ ] C# xUnit tests for `FederalHierarchyService` (search, detail, children, tree, stats, descendant matching).
- [ ] C# integration tests for controller endpoints.
- [ ] Python: No changes needed (existing CLI/loader tests cover ETL).
- [ ] Manual test plan: Tree navigation, search, detail page tabs, cross-reference links, refresh flow.

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
| `ui/src/components/shared/AgencyLink.tsx` | **NEW** — Reusable cross-reference link component |
| `ui/src/components/hierarchy/HierarchyTree.tsx` | **NEW** — Expandable tree panel |
| `ui/src/components/hierarchy/HierarchyRefreshPanel.tsx` | **NEW** — Admin refresh controls |
| `ui/src/components/hierarchy/OrgStatsCards.tsx` | **NEW** — Statistics display cards/charts |
| `ui/src/hooks/useHierarchy.ts` | **NEW** — TanStack Query hooks |
| `ui/src/api/hierarchy.ts` | **NEW** — Axios API client functions |
| `ui/src/types/api.ts` | Add hierarchy DTOs |
| `ui/src/routes.tsx` | Add `/hierarchy` and `/hierarchy/:fhOrgId` routes |
| `ui/src/components/layout/Sidebar.tsx` | Add "Federal Hierarchy" nav item under Research |
| `ui/src/pages/OpportunityDetailPage.tsx` | Wrap department/sub-tier/office with `AgencyLink` |
| `ui/src/pages/OpportunitySearchPage.tsx` | Wrap department column with `AgencyLink` |
| `ui/src/pages/AwardDetailPage.tsx` | Wrap agency/office names with `AgencyLink` |
| `api/tests/` | **NEW** — xUnit tests for hierarchy service/controller |

---

## Out of Scope

- **Database normalization** (adding FK columns from opportunity/award to federal_organization) — That's Phase 200.
- **FPDS agency code mapping table** — Deferred to Phase 200 where a proper crosswalk can be built.
- **Org-level notifications/alerts** — Future enhancement (e.g., "notify me when this office posts new opportunities").
- **Historical hierarchy tracking** — The current table tracks current state only; point-in-time hierarchy snapshots are out of scope.
- **Hierarchy data editing** — This phase is read-only + refresh from SAM.gov. No manual org creation/editing.
- **Sub-office (Level 4+) support** — SAM.gov hierarchy has three levels only.
