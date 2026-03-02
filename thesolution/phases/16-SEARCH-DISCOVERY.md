# Phase 16: Search & Discovery

**Status**: NOT STARTED
**Dependencies**: Phase 15 (UI Foundation)
**Deliverable**: Opportunity, award, and entity search pages with filtering, sorting, and pagination
**Repository**: `ui/src/pages/`

---

## Overview

Build the core search experience — the primary way users find contracts to bid on. This phase delivers three search pages (opportunities, awards, entities) plus a teaming partner search. Each page has a filter bar, sortable data grid, and click-through to detail views (built in Phase 17).

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

**Grid columns:**
- Title (link to detail)
- Solicitation #
- Department
- Set-Aside (color-coded chip)
- NAICS
- Response Deadline (with "X days" countdown, red when < 7 days)
- Estimated Value (currency)
- POP State
- Prospect Status (if already tracked — chip or empty)

**Actions:**
- Click row → Opportunity Detail (Phase 17)
- "Track" button → Create prospect (Phase 18)
- Export to CSV

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
- Entity URL

### Teaming Partner Search (`/subawards/teaming`)
Find potential teaming partners based on subaward history.

**Filters:**
- Primary contractor UEI
- NAICS code
- Award amount range

**Grid columns:**
- Company Name (link to entity detail)
- UEI
- Primary NAICS
- Total Subaward Value
- Number of Awards

---

## Tasks

### 16.1 Opportunity Search Page
- [ ] Build opportunity search page with filter bar
- [ ] NAICS autocomplete component (search-as-you-type from reference data)
- [ ] Set-aside dropdown with color-coded options
- [ ] Wire to `GET /api/v1/opportunities` with TanStack Query
- [ ] Paginated MUI X Data Grid with server-side sorting
- [ ] Response deadline countdown (days until due, red when urgent)
- [ ] "Track as Prospect" quick action button per row
- [ ] CSV export button
- [ ] URL query params sync (shareable/bookmarkable searches)

### 16.2 Target Opportunity Page
- [ ] Build target opportunity page (separate tab or route)
- [ ] Wire to `GET /api/v1/opportunities/targets`
- [ ] Highlight relevance indicators

### 16.3 Award Search Page
- [ ] Build award search page with filter bar
- [ ] Wire to `GET /api/v1/awards`
- [ ] Date range picker for award date filtering
- [ ] Currency range inputs for value filtering
- [ ] Paginated grid with server-side sorting

### 16.4 Entity Search Page
- [ ] Build entity search page with filter bar
- [ ] SBA certification filter (multi-select chips)
- [ ] Wire to `GET /api/v1/entities`
- [ ] Registration status color-coded chips
- [ ] Paginated grid

### 16.5 Teaming Partner Search
- [ ] Build teaming partner search page
- [ ] Wire to `GET /api/v1/subawards/teaming-partners`
- [ ] Link company names to entity detail pages

### 16.6 Shared Search Infrastructure
- [ ] Reusable filter bar component (consistent across all search pages)
- [ ] URL ↔ filter state sync (React Router search params)
- [ ] Saved filter presets (local storage)
- [ ] "No results" empty state with suggestions
- [ ] Loading skeletons for data grid

---

## Verification
- [ ] Each search page loads data from the live API
- [ ] Filters narrow results correctly
- [ ] Pagination works (page forward/back, page size selector)
- [ ] Sorting works on all columns
- [ ] URL updates with filter state (copy URL → paste → same results)
- [ ] Grid performance acceptable with 100+ rows
