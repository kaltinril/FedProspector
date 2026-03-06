# Phase 30: Search & Discovery

**Status**: COMPLETE
**Dependencies**: Phase 20 (UI Foundation), Phase 14.5 (Multi-Tenancy)
**Deliverable**: Opportunity, award, and entity search pages with filtering, sorting, and pagination
**Repository**: `ui/src/pages/`

---

## Overview

Build the core search experience — the primary way users find contracts to bid on. This phase delivers three search pages (opportunities, awards, entities) plus a teaming partner search. Each page has a filter bar, sortable data grid, and click-through to detail views (built in Phase 40).

**User workflow this enables:**
> "Show me all WOSB set-aside opportunities in NAICS 621111 (medical staffing) with deadlines in the next 60 days."

---

## Pages

### Opportunity Search (`/opportunities`)
The primary discovery page. Users search for active solicitations and RFIs.

**Filters:**
- NAICS code (autocomplete with description)
- Set-aside type (WOSB, 8(a), HUBZone, SDVOSB, etc.)
- Keyword (searches title + description)
- Department / Agency
- State (place of performance)
- Days out (deadline within N days)
- Open only toggle (default: on)

#### Additional Opportunity Filters (Competitive Parity)

These filters match what competing products (GovWin IQ, etc.) offer:

- **Notice/Contract Type**: Solicitation, Pre-solicitation, Sources Sought, RFI, Special Notice, Award Notice. Dropdown multi-select from `opportunity.type` field.
- **Re-compete Status**: New requirement vs. re-compete. Derived from linked prior awards — if `fpds_contract` exists for same solicitation number or same NAICS+agency, flag as "Likely Re-compete". Display as toggle filter: "All" / "New Only" / "Re-competes Only".
- **Full Socioeconomic Set-Aside**: All 23 set-aside types from `ref_set_aside_type` (not just WOSB/8(a)). Includes HUBZone, SDVOSB, 8(a) Sole Source, Total Small Business, etc. Checkbox group or multi-select dropdown.
- **Security Clearance**: "Clearance Required" flag if opportunity description/title contains clearance keywords (Secret, Top Secret, TS/SCI, Public Trust). Binary toggle filter. Note: SAM.gov API does not provide a structured clearance field — this is a keyword-derived indicator.
- **Size Standard Eligibility**: Filter by NAICS size standard threshold. "Show only opportunities where my company's revenue/employee count qualifies as small." Requires user profile to store company size info (future enhancement — for now, filter by NAICS size standard range).

**Grid columns:**
- Title (link to detail)
- Solicitation #
- Department
- Office (sub-agency)
- Set-Aside (color-coded chip)
- NAICS
- Posted Date
- Response Deadline (with "X days" countdown, red when < 7 days)
- Award Ceiling / Base+Options (currency)
  > Displays `BaseAndAllOptions` from search DTO. Phase 14.5 adds `EstimatedContractValue` field; display whichever is available, preferring the solicitation estimate.
- POP State
- Prospect Status (if already tracked — chip or empty)

> **Column visibility configurable by user.** Default shows: Title, Solicitation#, Department, Set-Aside, NAICS, Response Deadline, Award Ceiling / Base+Options, POP State. Office, Posted Date, and Prospect Status are available as togglable columns.

**Actions:**
- Click row → Opportunity Detail (Phase 40)
- "Track" button → Create prospect (Phase 50)
- Export to CSV (via `GET /api/v1/opportunities/export` -- server-side, accepts same filters)

### Target Opportunity Search (`/opportunities/targets`)
Pre-filtered view showing opportunities most relevant to the user's company profile.

**Grid columns:** Same as opportunity search + relevance score

### Award Search (`/awards`)
Historical contract award search for competitive intelligence.

**Filters:**
- Solicitation number
- NAICS code
- Agency
- Vendor UEI or name
- Set-aside type
- Award value range (min/max)
- Date range (signed date)

**Grid columns:**
- Contract ID (link to detail)
- Vendor Name
- Agency
- NAICS
- Set-Aside
- Date Signed
- Total Value (currency)
- Contract Type

### Entity Search (`/entities`)
Find companies — competitors, teaming partners, or incumbents.

**Filters:**
- Company name (fuzzy search)
- UEI
- NAICS code
- State
- Business type
- SBA certification (WOSB, 8(a), HUBZone, etc.)
- Registration status

**Grid columns:**
- Legal Business Name (link to detail)
- DBA Name
- UEI
- Primary NAICS
- Registration Status (chip)
- Entity URL (requires `EntityUrl` field added to `EntitySearchDto` in Phase 14.5)

### Teaming Partner Search (`/subawards/teaming`)
Find potential teaming partners based on subaward history.

**Filters:**
- Primary contractor UEI
- NAICS code
- Minimum subaward count (maps to `TeamingPartnerSearchRequest.MinSubawards`)

**Grid columns** (matches `TeamingPartnerDto` — prime contractor aggregation):
- Prime Contractor Name (link to entity detail)
- Prime UEI
- Subaward Count
- Total Sub Amount
- Unique Subs
- NAICS Codes

---

## Tasks

### 30.1 Opportunity Search Page
- [ ] Build opportunity search page with filter bar
- [ ] NAICS autocomplete component (search-as-you-type from reference data)
- [ ] Set-aside dropdown with color-coded options
- [ ] Wire to `GET /api/v1/opportunities` with TanStack Query
- [ ] Paginated MUI X Data Grid with server-side sorting
- [ ] Response deadline countdown (days until due, red when urgent)
- [ ] "Track as Prospect" quick action button per row
- [ ] CSV export button
- [ ] URL query params sync (shareable/bookmarkable searches)

### 30.2 Target Opportunity Page
- [ ] Build target opportunity page (separate tab or route)
- [ ] Wire to `GET /api/v1/opportunities/targets`
- [ ] Highlight relevance indicators

### 30.3 Award Search Page
- [ ] Build award search page with filter bar
- [ ] Wire to `GET /api/v1/awards`
- [ ] Date range picker for award date filtering
- [ ] Currency range inputs for value filtering
- [ ] Paginated grid with server-side sorting

### 30.4 Entity Search Page
- [ ] Build entity search page with filter bar
- [ ] SBA certification filter (multi-select chips)
- [ ] Wire to `GET /api/v1/entities`
- [ ] Registration status color-coded chips
- [ ] Paginated grid

### 30.5 Teaming Partner Search
- [ ] Build teaming partner search page
- [ ] Wire to `GET /api/v1/subawards/teaming-partners`
- [ ] Link company names to entity detail pages

### 30.6 Shared Search Infrastructure
- [ ] Reusable filter bar component (consistent across all search pages)
- [ ] URL ↔ filter state sync (React Router search params)
- [ ] Saved filter presets (local storage)

### 30.7 Empty and Error States
- [ ] "No results" empty state with filter suggestions for each search page (e.g., broaden NAICS, remove set-aside filter)
- [ ] Loading skeletons for all grids (match column layout per page)
- [ ] Stale/invalid URL param handling: validate filters on load, toast notification if invalid params are stripped
- [ ] Graceful error states for API failures (retry button, error message)

### 30.X Save Search Integration

**Purpose**: Let users save their current search filters for quick re-use. Phase 60 extends saved searches with notifications and auto-run.

**Implementation**:
- "Save Search" button in the search results toolbar (next to export button)
- Opens modal: search name (required), description (optional)
- Calls `POST /api/v1/saved-searches` (already exists from Phase 11) with current URL filter params as `filter_criteria`
- Success toast: "Search saved. Manage saved searches in Dashboard (Phase 60)."
- Saved searches appear in sidebar under "Saved Searches" section (read-only list, click to re-run)

**API**: Uses existing endpoint. No new backend work needed.

**Phase 60 extends**: Adds notification toggle, auto-run scheduling, and dashboard card for saved search management.

---

## Verification
- [ ] Each search page loads data from the live API
- [ ] Filters narrow results correctly
- [ ] Pagination works (page forward/back, page size selector)
- [ ] Sorting works on all columns
- [ ] URL updates with filter state (copy URL → paste → same results)
- [ ] Grid performance acceptable with 100+ rows
- [ ] Teaming partner grid correctly displays prime contractor data (not sub-awardee)
