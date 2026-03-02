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
- Action buttons: "Track as Prospect", "Save Search Similar"

**Tab 1: Overview**
- Description (full text, collapsible if long)
- Key facts grid:
  - Type (solicitation, RFI, sources sought, etc.)
  - Set-aside code + description + category
  - NAICS code + description + sector + size standard
  - Place of performance (city, state, ZIP, country → CONUS/OCONUS indicator)
  - Security clearance required (Yes/No + type if known)
  - Period of performance (start → end dates)
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
  - Award number of previous contract
  - Incumbent name + UEI (link to entity detail)
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
- Top vendors in this NAICS (from entity data)
- USAspending summary (if linked)

**Tab 4: Prospect (if tracked)**
- Prospect status, priority, score
- Link to full prospect detail page
- Quick status update

### Award Detail (`/awards/:contractId`)

**Header Section:**
- Contract ID, solicitation number (linked to opportunity if exists)
- Vendor name + UEI (link to entity detail)
- Agency / contracting office
- Total value (base-and-all-options)
- Date signed → completion date timeline

**Tab 1: Contract Details**
- Key facts grid:
  - Contract type, pricing type
  - NAICS, PSC code
  - Set-aside type
  - Extent competed, number of offers
  - Description
  - Place of performance

**Tab 2: Financials & Burn Rate**
- **Burn rate chart** (monthly obligations over time)
- Dollars obligated vs. base-and-all-options (progress bar)
- Monthly spend table (from MonthlySpendDto)
- Transaction history table (modifications, amounts, dates)

**Tab 3: Vendor Profile**
- Vendor summary card (from VendorSummaryDto)
- Link to full entity detail
- Other awards by same vendor

### Entity Detail (`/entities/:uei`)

**Header Section:**
- Legal business name, DBA name
- UEI
- Registration status chip
- Primary NAICS
- Link to SAM.gov entity page

**Tab 1: Company Profile**
- Business types and certifications (WOSB, 8(a), HUBZone, etc.)
- NAICS codes (primary + additional)
- Physical address
- Congressional district
- Entity URL

**Tab 2: Competitor Analysis**
- Competitor profile data (from CompetitorProfileDto):
  - Total contracts won, total obligation amount
  - Win rate / recent win trend
  - NAICS codes they compete in
  - Average contract size
  - Recent awards table

**Tab 3: Exclusion Check**
- Exclusion status (prominent green "Clear" or red "EXCLUDED" badge)
- If excluded: exclusion details (type, date, agency, description)
- Last checked date

**Tab 4: Federal Hierarchy**
- Where this entity sits in the federal hierarchy (if government entity)
- Parent/child relationships

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
- [ ] Burn rate chart for previous contract (Recharts line chart)
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

---

## Verification
- [ ] Click opportunity in search → detail page loads with all tabs
- [ ] Re-compete opportunities show incumbent info and burn rate
- [ ] New solicitations show appropriate "new" messaging
- [ ] CONUS/OCONUS correctly detected from POP data
- [ ] Award detail shows burn rate chart and transaction history
- [ ] Entity detail shows competitor analysis and exclusion status
- [ ] All cross-links work (opportunity → award → entity → back)
