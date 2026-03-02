# Phase 17: Detail Views & Competitive Intelligence

**Status**: NOT STARTED
**Dependencies**: Phase 16 (Search & Discovery)
**Deliverable**: Detail pages for opportunities, awards, and entities with full intel and analytics
**Repository**: `ui/src/pages/`

---

## Overview

Build the detail pages that answer the user's core questions:
- **Is this new or a re-compete?**
- **Who is the incumbent? Are they good? Are they eligible?**
- **What's the burn rate? How much money has been spent?**
- **How many bidders last time?**
- **Does it require clearance? CONUS or OCONUS?**
- **Does my company qualify?**

These pages are the competitive intelligence engine — the core value proposition over competitors like GovWin IQ.

---

## Pages

### Opportunity Detail (`/opportunities/:noticeId`)

**Layout: Tabbed detail page**

**Header Section (always visible):**
- Title, solicitation number, department/office
- Response deadline with countdown (days/hours, urgent coloring)
- Estimated value (prominent)
- Status chips: Set-aside type, NAICS code, active/inactive
- Action buttons: "Track as Prospect", "Save Search Similar" (pre-populates saved search create dialog with the opportunity's NAICS/set-aside values)

**Tab 1: Overview**
- Description (full text, collapsible if long)
- Key facts grid:
  - Type (solicitation, RFI, sources sought, etc.)
  - Base type (`BaseType`)
  - Classification code (PSC)
  - Set-aside code + description + category
  - NAICS code + description + sector + size standard
  - Place of performance (city, state, ZIP, country → CONUS/OCONUS indicator)
  - Security clearance required (Yes/No + type if known)
  - Period of performance (start → end dates)
  - Data freshness: `FirstLoadedAt` / `LastLoadedAt` (when record was first/last seen in our system)
  - Link to SAM.gov listing
  - Resource links (attachments from SAM.gov)
- **Qualification checklist** (visual pass/fail indicators):
  - Set-aside match (does user's company qualify?)
  - NAICS match
  - Size standard (under threshold?)
  - Clearance (does company have it?)
  - Location (CONUS/OCONUS)

**Tab 2: History & Incumbent Intel**
- **New vs Re-compete indicator** (prominent badge)
- If re-compete:
  - Inline award fields from opportunity record: `AwardNumber`, `AwardDate`, `AwardAmount`, `AwardeeUei`, `AwardeeName`
  - Incumbent name + UEI (link to entity detail, from `AwardeeName`/`AwardeeUei`)
  - Incumbent exclusion check (are they debarred?)
  - Award date and completion date of previous contract
  - Burn rate chart (monthly spend over contract life)
  - Total obligated vs. base-and-all-options (% spent)
  - Number of offers on previous solicitation
  - Related awards list (all historical awards on this solicitation)
- If new:
  - "New solicitation — no incumbent" message
  - Related opportunities (similar NAICS/department)

**Tab 3: Competition**
- Related awards by same NAICS + set-aside (who's winning similar work?)
- Top vendors in this NAICS (see Market Share section below)
- USAspending summary (if linked) — display from `UsaspendingSummaryDto`:
  - `GeneratedUniqueAwardId`, `RecipientName`, `TotalObligation`, `BaseAndAllOptionsValue`, `StartDate`, `EndDate`

#### Market Share: Top Vendors by NAICS (Required)

**Purpose**: Show which companies dominate the opportunity's NAICS code. This is a primary competitive intelligence differentiator — customers pay for this insight.

**Data source**: Aggregate `fpds_contract` records grouped by `vendor_uei` WHERE `naics_code` matches the opportunity's NAICS.

**Display**:
- Horizontal bar chart: Top 10 vendors by total award value
- Table below chart: Vendor name, UEI, award count, total value, average value, most recent award date
- Click vendor name → navigate to Entity Detail page

**API**: New endpoint `GET /api/v1/awards/market-share?naicsCode={code}&limit=10`
- Returns: `[{ vendorName, vendorUei, awardCount, totalValue, averageValue, lastAwardDate }]`
- If fewer than 3 vendors found: show "Insufficient award data for NAICS {code}" with suggestion to broaden search

**Edge cases**:
- If NAICS code has no awards in DB: show "No contract award data available for this NAICS code. Award data coverage depends on ETL load history."
- If vendor UEI not in entity table: show vendor name from award record with "(Not in entity database)" note

**Tab 4: Prospect (if tracked)**
- Prospect status, priority, score
- Link to full prospect detail page
- Quick status update

### Award Detail (`/awards/:contractId`)

**Header Section:**
- Contract ID, solicitation number (linked to opportunity if exists)
- `IdvPiid` (parent contract ID, if applicable)
- Vendor name + UEI (link to entity detail)
- Agency / contracting office
- `FundingAgencyName` (when different from contracting agency — show both)
- Total value (base-and-all-options)
- Date signed → completion date timeline

**Tab 1: Contract Details**
- Key facts grid:
  - Contract type, pricing type
  - NAICS, PSC code
  - Set-aside type
  - Extent competed, number of offers
  - `SolicitationDate`
  - Description
  - Place of performance
  - `CompletionDate` vs `UltimateCompletionDate` (show both when they differ, to indicate extensions)

**Tab 2: Financials & Burn Rate**
- **Burn rate chart** (monthly obligations over time)
- Dollars obligated vs. base-and-all-options (progress bar)
- Monthly spend table (from MonthlySpendDto)
- Transaction history table (modifications, amounts, dates)

**Tab 3: Vendor Profile**
- Vendor summary card (from VendorSummaryDto)
- Link to full entity detail
- Other awards by same vendor

#### Subcontractors Tab

**Purpose**: Show all known subcontractors for this prime contract. Critical for teaming partner intelligence.

**Data source**: `sam_subaward` table WHERE `prime_award_id` matches the award.

**Display**:
- Table: Subcontractor name, UEI, subaward value, description, report date
- Click subcontractor name → navigate to Entity Detail page (if UEI exists in entity table)
- If no subawards found: "No subaward data reported for this contract."

**API**: Uses existing `GET /api/v1/subawards` endpoint filtered by prime award ID.

### Entity Detail (`/entities/:uei`)

**Header Section:**
- Legal business name, DBA name
- UEI
- Registration status chip
- `ExclusionStatusFlag` inline badge (quick visual without switching to exclusion tab)
- Primary NAICS
- Link to SAM.gov entity page

**Tab 1: Company Profile**
- Business types and certifications (WOSB, 8(a), HUBZone, etc.)
- NAICS codes (primary + additional)
- `PscCodes` (Product Service Codes)
- `CageCode`
- Physical address
- Congressional district
- Entity URL
- `RegistrationExpirationDate` with "expiring soon" warning (highlight if within 60 days)
- `PointsOfContact` — **critical for business development**: display POC list with name, title, type, location

**Tab 2: Competitor Analysis**
- Competitor profile data (from CompetitorProfileDto):
  - Total contracts won, total obligation amount
  - Win rate / recent win trend
  - NAICS codes they compete in
  - Average contract size
  - Recent awards table
- **Phase 14.5 DTO changes needed**: `CompetitorProfileDto` currently lacks `WinRate`, `AverageContractSize`, and `RecentAwards` fields. These are added in Phase 14.5 DTO changes. Until then, compute `AverageContractSize` client-side as `TotalObligated / PastContracts`.

**Tab 3: Exclusion Check**
- Exclusion status (prominent green "Clear" or red "EXCLUDED" badge)
- If excluded: exclusion details (type, date, agency, description)
- Last checked date

**Tab 4: Federal Hierarchy**
- Where this entity sits in the federal hierarchy (if government entity)
- Parent/child relationships
- **Note**: Federal hierarchy data displayed only if entity is a government organization. Otherwise show "Not applicable -- commercial entity."

---

## Tasks

### 17.1 Opportunity Detail Page
- [ ] Build tabbed detail page layout
- [ ] Header with deadline countdown, value, action buttons
- [ ] Overview tab: description, key facts grid, resource links
- [ ] CONUS/OCONUS indicator based on POP country/state
- [ ] Security clearance display
- [ ] Qualification checklist component (pass/fail visual indicators)
- [ ] History tab: new vs re-compete detection
- [ ] Incumbent info panel (name, exclusion check, award details)
- [ ] Burn rate chart for previous contract (@mui/x-charts line chart)
- [ ] Number of offers on previous solicitation
- [ ] Competition tab: related awards, top vendors in NAICS
- [ ] Prospect tab: show linked prospect or "Track" CTA
- [ ] Wire to `GET /api/v1/opportunities/{noticeId}`

### 17.2 Award Detail Page
- [ ] Build tabbed detail page layout
- [ ] Contract details tab with key facts
- [ ] Financials tab: burn rate chart, obligation progress bar
- [ ] Monthly spend table
- [ ] Transaction history table
- [ ] Vendor profile summary card
- [ ] Wire to `GET /api/v1/awards/{contractId}` and `GET .../burn-rate`

### 17.3 Entity Detail Page
- [ ] Build tabbed detail page layout
- [ ] Company profile tab: certifications, NAICS, address
- [ ] Competitor analysis tab with win metrics and recent awards
- [ ] Exclusion check tab with prominent status badge
- [ ] Wire to `GET /api/v1/entities/{uei}`, `GET .../competitor-profile`, `GET .../exclusion-check`

### 17.4 Shared Detail Components
- [ ] Tabbed page layout component (consistent across all detail pages)
- [ ] Key facts grid component (label-value pairs in responsive grid)
- [ ] Timeline/countdown component (deadline display)
- [ ] Burn rate chart component (reused in opportunity and award detail)
- [ ] Qualification checklist component (pass/fail visual)
- [ ] "Back to search" navigation with preserved search state

### 17.5 Edge Case Handling
- [ ] Burn rate chart: handle zero transactions gracefully (show "No transaction data available" instead of empty chart)
- [ ] CONUS/OCONUS detection: handle US territories (PR, GU, VI, AS, MP), APO/FPO addresses, and null country values
- [ ] Cross-link integrity: if linked entity/award doesn't exist, show "Data not available" placeholder instead of 404
- [ ] Tab lazy loading: only fetch tab data when tab is activated (TanStack Query `enabled` flag tied to active tab)
- [ ] Registration expiration warning: highlight entities expiring within 60 days
- [ ] Federal hierarchy tab: show "Not applicable -- commercial entity" for non-government entities
- [ ] Handle null `NumberOfOffers` gracefully -- FPDS does not always populate this field. Display "N/A" when null.

---

## Verification
- [ ] Click opportunity in search → detail page loads with all tabs
- [ ] Re-compete opportunities show incumbent info and burn rate
- [ ] New solicitations show appropriate "new" messaging
- [ ] CONUS/OCONUS correctly detected from POP data
- [ ] Award detail shows burn rate chart and transaction history
- [ ] Entity detail shows competitor analysis and exclusion status
- [ ] All cross-links work (opportunity → award → entity → back)
- [ ] Cross-link to missing data shows "Data not available" instead of 404
- [ ] Burn rate chart handles zero transactions gracefully
- [ ] CONUS/OCONUS correctly handles US territories (PR, GU, VI, AS, MP)
- [ ] Entity detail shows POC list, CAGE code, PSC codes, and registration expiration warning
- [ ] Federal hierarchy tab shows conditional message for commercial entities
- [ ] "Save Search Similar" pre-populates saved search dialog with opportunity NAICS/set-aside
