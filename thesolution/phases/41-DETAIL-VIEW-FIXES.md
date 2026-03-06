# Phase 41: Detail View Fixes & Remediation

**Status**: IN PROGRESS
**Dependencies**: Phase 40 (Detail Views)
**Deliverable**: Bug fixes, missing features, and quality improvements from Phase 40 QA review

---

## Overview

Phase 40 QA review (6 parallel agents) found 30+ issues across all detail pages, shared components, and the market-share API endpoint. This phase addresses them by severity.

---

## HIGH Priority (Bugs & Broken Features)

### 41.1 Opportunity Detail -- BurnRateChart hardcoded to empty data
- [x] BurnRateChart in History tab passes `data={[]}` (always shows "No data")
- [x] Fetch burn rate via `getBurnRate(contractId)` when opportunity has related awards
- [x] Wire query with `enabled` flag tied to History tab being active + award existing

### 41.2 Market-Share SQL Bugs (C# AwardService)
- [x] Add `AND modification_number = '0'` filter (currently counts every modification as a separate award, inflating counts/values)
- [x] Change `GROUP BY vendor_uei, vendor_name` to `GROUP BY vendor_uei` with `MAX(vendor_name)` (vendor name variations split one vendor into multiple rows)

### 41.3 Solicitation-to-Opportunity Cross-Link Broken
- [x] Award Detail links to `/opportunities/{solicitationNumber}` but route expects `noticeId` -- these are different fields
- [x] Fix: either add backend lookup-by-solicitation-number, or remove the broken link and show solicitation number as plain text

### 41.4 Entity Detail -- SAM.gov Link Uses Wrong URL
- [x] Header "SAM.gov Profile" link uses `entity.entityUrl` (company website), not SAM.gov
- [x] Fix: construct SAM.gov URL as `https://sam.gov/entity/${uei}` for the header link; keep `entityUrl` in profile tab as "Entity URL"

---

## MEDIUM Priority (Missing Plan Features)

### 41.5 Award Detail -- Missing Subcontractors Tab
- [ ] Add 4th tab: Subcontractors (plan lines 136-147)
- [ ] Show subawards filtered by prime award ID
- [ ] Uses existing `GET /api/v1/subawards` endpoint (may need query param extension for contractId filter)

### 41.6 Award Detail -- Missing "Other Awards by Same Vendor"
- [ ] Vendor Profile tab should show other awards by the same vendor
- [ ] Use existing award search API filtered by `vendorUei`

### 41.7 Opportunity Detail -- Missing DTO Fields
- [x] Add `naicsDescription`, `naicsSector`, `sizeStandard`, `setAsideCategory` to C# `OpportunityDetailDto`
- [x] Add same fields to TypeScript `OpportunityDetail` interface
- [x] Display in Overview tab KeyFactsGrid

### 41.8 Opportunity Detail -- Missing "Save Search Similar" Button
- [ ] Add button to header actions that pre-populates saved search dialog with opportunity's NAICS/set-aside
- [ ] Opens modal: search name (required), calls `POST /api/v1/saved-searches`

### 41.9 Entity Detail -- Missing DBA Name in Header
- [x] Show DBA name alongside legal business name in header (when present)

### 41.10 Entity Detail -- Business Type Codes Need Descriptions
- [x] Raw codes like "2X" are meaningless to users
- [x] Either extend API to return descriptions, or add a client-side lookup map

### 41.11 Entity Detail -- Competitor Analysis Missing NAICS Display
- [x] Show "NAICS codes they compete in" from competitor profile DTO

### 41.12 Opportunity Detail -- Missing Active/Inactive Status Chip
- [x] Add chip using `opp.active` field in header

### 41.13 Award Detail -- Transaction getRowId Duplicate Key Risk
- [x] `getRowId` index param never populated by DataGrid -- use array index or synthetic ID
- [x] Same issue exists for Entity Detail POC table

---

## LOW Priority (Polish & Edge Cases)

### 41.14 BackToSearch -- Unreliable History Guard
- [x] `window.history.length > 1` doesn't reliably detect in-app history
- [x] Consider always using `navigate(searchPath)` as primary behavior

### 41.15 QualificationChecklist -- Accessibility
- [x] Add `titleAccess` to status icons for screen readers

### 41.16 DeadlineCountdown -- Invalid Date Handling
- [x] Add `isValid` check from date-fns for malformed date strings

### 41.17 Award Detail -- Header Missing IdvPiid and Funding Agency
- [x] Show parent contract ID and funding agency (when different) in header summary

### 41.18 Award Detail -- Vendor Link Clickable Without UEI
- [x] Render as plain Typography when `vendorUei` is null

### 41.19 Market-Share Bar Chart
- [ ] Plan calls for horizontal bar chart above the table -- currently table only

### 41.20 CONUS/OCONUS -- APO/FPO Addresses
- [ ] Military addresses (states AA, AE, AP) should be detected separately

### 41.21 Duplicate React Key Risks
- [x] KeyFactsGrid uses `fact.label` as key -- breaks with duplicate labels
- [x] QualificationChecklist uses `item.label` as key
- [ ] Entity NAICS table uses `naicsCode` as key
- [ ] Opportunity resource links use `url` as key
- [ ] Fix: use array index or composite keys

---

## Verification
- [ ] Burn rate chart shows real data on re-compete opportunity detail
- [ ] Market share counts match base awards only (no modification inflation)
- [ ] Solicitation link from award detail reaches correct opportunity (or is gracefully handled)
- [ ] Entity SAM.gov link navigates to sam.gov, not company website
- [ ] Subcontractors tab appears on award detail
- [ ] TypeScript and C# builds pass with zero errors
