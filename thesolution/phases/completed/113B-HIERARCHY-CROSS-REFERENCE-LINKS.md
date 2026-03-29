# Phase 113B: Hierarchy Cross-Reference Links

**Status:** PLANNED
**Priority:** Medium
**Dependencies:** Phase 113 (Federal Hierarchy Browser)

---

## Summary

Add clickable agency/office links throughout the app that navigate to the Federal Hierarchy browser. Anywhere the app shows a department, sub-tier, or office name as plain text, wrap it in an `AgencyLink` component that resolves the name to a hierarchy org and links to its detail page.

## Problem / Current State

After Phase 113 delivers the hierarchy browser, agency and office names throughout the app (opportunity detail, search results, award detail, entity pages) remain plain text. Users see "Department of the Navy" but can't click it to explore what else that department is buying. The hierarchy browser exists but nothing links to it.

## Design

### Cross-Reference Links (App-Wide)

Anywhere the app displays an agency/office name, make it a clickable link:
- **Opportunity Detail Page**: `departmentName`, `subTier`, `office` fields link to matching hierarchy org.
- **Opportunity Search Results**: Department column links.
- **Award Detail Page**: `agencyName`, `contractingOfficeName`, `fundingAgencyName` links.
- **Entity Detail Page**: If agency references exist, link them.
- **Subaward Detail Page**: Agency references link to hierarchy.

### AgencyLink Component

Shared component at `ui/src/components/shared/AgencyLink.tsx`:
- **Props**: `name` (required), `agencyCode?`, `level?` (Department/Sub-Tier/Office hint).
- **Behavior**: Renders the name as a clickable link. On first render, resolves the name to a `fhOrgId` via the lookup API.
- **Resolution strategy**: Exact match on `federal_organization.fh_org_name` preferred. If `agencyCode` is provided, also match on `agency_code`. Falls back to search link (`/hierarchy?keyword={name}`) if no exact match found.
- **Display**: Renders as an inline link (MUI `Link` or `Typography` with link styling). Shows a subtle icon (e.g., `OpenInNew` or `AccountTree`) on hover. Does not disrupt surrounding text layout.
- **Error handling**: If lookup fails or no match, renders as plain text (graceful degradation).

### Org Lookup API

Lightweight endpoint or reuse of existing search:
- The `useOrgLookup(name)` hook calls `/api/v1/hierarchy?keyword={name}&pageSize=1` (or a dedicated `/api/v1/hierarchy/lookup?name={name}` endpoint if needed for performance).
- **Caching**: Use TanStack Query with long `staleTime` (30 min) for org name-to-ID lookups since hierarchy data rarely changes. Batch lookups where possible (e.g., opportunity detail page has 3 names to resolve).

---

## Tasks

### Task 1: AgencyLink Component

- [ ] Create shared `AgencyLink` component at `ui/src/components/shared/AgencyLink.tsx`.
- [ ] Accept props: `name`, optional `agencyCode`, optional `level`.
- [ ] Render name as clickable MUI `Link` navigating to `/hierarchy/{fhOrgId}` when resolved, or `/hierarchy?keyword={name}` as fallback.
- [ ] Show subtle visual indicator that the name is a link (underline on hover, optional icon).
- [ ] Graceful degradation: render as plain text if lookup fails or hierarchy data is unavailable.
- [ ] Update `OpportunityDetailPage`: Wrap `departmentName`, `subTier`, `office` with `AgencyLink`.
- [ ] Update opportunity search page: Make department column render as `AgencyLink`.
- [ ] Update `AwardDetailPage`: Wrap `agencyName`, `contractingOfficeName`, `fundingAgencyName` with `AgencyLink`.
- [ ] Update any other pages displaying agency/office names (entity detail, subaward detail, etc.).

### Task 2: Hooks & API Functions

- [ ] Add `useOrgLookup(name)` hook to `ui/src/hooks/useHierarchy.ts` — lightweight name-to-ID resolution for `AgencyLink`.
- [ ] Add org lookup API function to `ui/src/api/hierarchy.ts`.
- [ ] Add `OrgLookupResult` type to `ui/src/types/api.ts` if needed (may reuse `FederalOrgListItem`).
- [ ] Configure TanStack Query with 30-minute `staleTime` for lookup queries.
- [ ] Consider batch lookup support (resolve multiple names in a single request) if performance warrants it.

### Task 3: Testing

- [ ] Manual test plan:
  - Verify `AgencyLink` renders correctly on Opportunity Detail (department, sub-tier, office).
  - Verify `AgencyLink` renders correctly on Opportunity Search (department column).
  - Verify `AgencyLink` renders correctly on Award Detail (agency, contracting office, funding agency).
  - Verify resolution: clicking a resolved link navigates to the correct hierarchy detail page.
  - Verify fallback: clicking an unresolved link navigates to hierarchy search with the name pre-filled.
  - Verify graceful degradation: if hierarchy API is down, names render as plain text.
  - Verify caching: second render of same name does not trigger a new API call.
- [ ] Unit tests for `AgencyLink` component (render states: loading, resolved, fallback, error).
- [ ] Verify no layout disruption when `AgencyLink` replaces plain text in existing pages.

---

## Code Touchpoints

| File | What to do |
|------|------------|
| `ui/src/components/shared/AgencyLink.tsx` | **NEW** — Reusable cross-reference link component |
| `ui/src/hooks/useHierarchy.ts` | Add `useOrgLookup` hook |
| `ui/src/api/hierarchy.ts` | Add org lookup API function |
| `ui/src/types/api.ts` | Add `OrgLookupResult` type if needed |
| `ui/src/pages/opportunities/OpportunityDetailPage.tsx` | Wrap `departmentName`, `subTier`, `office` with `AgencyLink` |
| `ui/src/pages/opportunities/OpportunitySearchPage.tsx` | Wrap department column with `AgencyLink` |
| `ui/src/pages/awards/AwardDetailPage.tsx` | Wrap `agencyName`, `contractingOfficeName`, `fundingAgencyName` with `AgencyLink` |
| `ui/src/pages/entities/EntityDetailPage.tsx` | Wrap agency references with `AgencyLink` |
| `ui/src/pages/subawards/SubawardDetailPage.tsx` | Wrap agency references with `AgencyLink` |

---

## Out of Scope

- **The hierarchy browser itself** (browse page, detail page, refresh panel) — That's Phase 113.
- **Database normalization** (adding FK columns from opportunity/award to federal_organization) — That's Phase 200.
- **Dedicated lookup endpoint** — Start with reusing the search endpoint; add a dedicated one only if performance requires it.
- **Bidirectional linking** — This phase adds links FROM app pages TO hierarchy. Links from hierarchy detail back to opportunities/awards are already in Phase 113.
