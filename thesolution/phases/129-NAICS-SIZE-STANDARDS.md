# Phase 129: NAICS Code Intelligence & SBA Size Standards

**Status:** PLANNED
**Priority:** High — NAICS size standards are the single most important eligibility gate for small business set-aside contracts. Without this, pWin calculations can't determine if the user is even eligible to bid.
**Dependencies:** None (reference tables already exist from Phase 10)

---

## Problem

We have NAICS codes and SBA size standards loaded as flat reference data, but the system doesn't *understand* them. Specifically:

1. **No hierarchy awareness** — We store `parent_code` but never traverse it. Users can't browse "show me all IT services" (Sector 54 → Subsector 541 → ...).
2. **No automatic eligibility check** — The org stores `size_standard_met` as a manual Y/N toggle. Nobody computes whether the org's revenue/headcount actually qualifies.
3. **No "outsized" warnings** — If a company's revenue grows past a NAICS threshold, the system doesn't flag it. This is a critical business risk: bidding on a set-aside you're no longer eligible for can result in decertification or False Claims Act liability.
4. **No NAICS-to-opportunity matching** — pWin doesn't factor in whether the org is small for that opportunity's NAICS code.
5. **Stale data** — Size standards update periodically (last: March 2023). No mechanism to refresh from SBA.
6. **No sector/category browsing** — Users must know their 6-digit code. They can't explore the hierarchy to discover related codes.

---

## NAICS Code Structure (Background)

NAICS uses a **2-through-6-digit hierarchy** with five levels:

| Digits | Level | Example |
|--------|-------|---------|
| 2 | **Sector** | 54 — Professional, Scientific, and Technical Services |
| 3 | **Subsector** | 541 — Professional, Scientific, and Technical Services |
| 4 | **Industry Group** | 5413 — Architectural, Engineering, and Related Services |
| 5 | **NAICS Industry** | 54133 — Engineering Services |
| 6 | **National Industry** | 541330 — Engineering Services |

There are **20 sectors** spanning the entire economy. The 6-digit level is where SBA assigns size standards.

### SBA Size Standard Types

Each 6-digit NAICS code has ONE size standard, measured in one of two ways:

| Type | Metric | Calculation Window | Common Thresholds |
|------|--------|--------------------|-------------------|
| **Revenue (M)** | Annual receipts in millions | Average of last 5 fiscal years | $2.25M, $8M, $16.5M, $25.5M, $30M, $41.5M, $47M |
| **Employee (E)** | Number of employees | Average of last 24 months (all pay periods) | 100, 250, 500, 750, 1,000, 1,250, 1,500 |

### The "Outsized" Problem

Size determination is **per-NAICS-code, per-contract**:

- A company can be "small" under NAICS 541511 ($34M threshold) but "other than small" under NAICS 541330 ($25.5M threshold) — same company, different eligibility.
- The **contracting officer** assigns the NAICS code to the solicitation. The bidder must be small under **that specific code**.
- When a company's revenue/headcount exceeds the threshold, they are **"other than small"** for that code. Bidding on small business set-asides when outsized = False Claims Act risk.
- Affiliate revenues/employees **must be included** (SBA "power to control" rules apply).

### Size Standard Exceptions (Footnotes)

Some NAICS codes have footnoted exceptions with different thresholds for subcategories:

| NAICS | Base Standard | Exception | Exception Standard |
|-------|--------------|-----------|-------------------|
| 541330 | $25.5M | Military/Aerospace Equipment | $47.0M |
| 541330 | $25.5M | National Energy Policy Act | $47.0M |
| 541330 | $25.5M | Marine Engineering | Separate standard |
| 324110 | 1,500 employees | — | OR 200,000 barrels/day capacity |

These are already modeled in `ref_naics_footnote` but not surfaced in the UI or used in calculations.

---

## What We Have Today

### Database Tables (from Phase 10)

| Table | Purpose | Status |
|-------|---------|--------|
| `ref_naics_code` | Master NAICS hierarchy (2022 + 2017 codes) | Loaded, ~2,100 rows |
| `ref_sba_size_standard` | Size thresholds per 6-digit code | Loaded, ~1,100 rows |
| `ref_naics_footnote` | Exception/footnote text | Loaded |
| `entity_naics` | Vendor's claimed NAICS codes from SAM.gov | Populated via entity loader |
| `organization_naics` | User org's NAICS codes (manual entry) | UI exists in setup wizard |
| `opportunity.naics_code` | NAICS assigned to each opportunity | Populated via opportunity loader |

### API Endpoints (existing)

| Endpoint | What It Does |
|----------|-------------|
| `GET /reference/naics?q=` | Search NAICS codes by code or description |
| `GET /reference/naics/{code}` | Get NAICS detail + size standard |
| `GET /org/naics` | Get org's NAICS codes |
| `PUT /org/naics` | Set org's NAICS codes |

### Gaps

- `organization_naics.size_standard_met` is a manual toggle — never computed
- No endpoint for hierarchy browsing (sector → subsector → ...)
- No endpoint for size standard eligibility check
- No NAICS factor in pWin
- No "outsized" warning in opportunity views
- No SBA data refresh mechanism
- Footnotes loaded but never displayed

---

## Implementation Plan

### Task 1: NAICS & SBA Size Standards Research Reference Document

Conduct comprehensive research on NAICS codes, SBA size standards, and the "outsized" concept. Produce a reference document at `thesolution/reference/NAICS-SIZE-STANDARDS-REFERENCE.md` covering:

**NAICS structure:**
- Full hierarchy (2-6 digit levels), all 20 sectors with codes and names
- How codes are assigned, revised (2017 → 2022 → 2027 cycle), and retired
- Concordance between revisions (merged, split, renamed codes)
- Relationship to PSC codes (no official crosswalk, empirically derived)

**SBA size standards:**
- How size standards work (revenue-based vs employee-based)
- Calculation windows (5-year avg receipts, 24-month avg employees)
- Complete list of common thresholds and which industries use them
- How affiliates factor in (SBA "power to control" rules)
- Footnotes and exceptions (e.g., NAICS 541330 military/aerospace exception)
- How often standards are updated and where to find the official table

**The "outsized" problem:**
- Per-NAICS, per-contract determination
- What happens when a company exceeds the threshold
- False Claims Act and decertification risks
- Near-threshold strategies and recertification timing

**Data sources for programmatic access:**
- SBA NAICS JSON API (`api.sba.gov`)
- SBA Open Data Portal
- Census Bureau NAICS structure files
- Concordance downloads
- Any available APIs for real-time size determination

**Federal contracting implications:**
- Set-aside eligibility rules (FAR Part 19)
- How contracting officers choose NAICS codes for solicitations
- Impact on pWin for small vs large businesses
- Socioeconomic subcategory layering (WOSB, 8(a), HUBZone, SDVOSB)

**Output:** `thesolution/reference/NAICS-SIZE-STANDARDS-REFERENCE.md`

This document becomes the authoritative reference for all subsequent tasks in this phase.

### Task 2: NAICS Hierarchy API

Add hierarchy-aware endpoints to browse NAICS codes as a tree.

**Endpoints:**

```
GET /api/v1/reference/naics/sectors
  → Returns all 20 sectors (2-digit codes) with child counts

GET /api/v1/reference/naics/{code}/children
  → Returns direct children of any NAICS code
  → Example: /naics/54/children → [541, 542, ...]
  → Include size standard info when at 6-digit level

GET /api/v1/reference/naics/{code}/ancestors
  → Returns full ancestry chain from sector down to the code
  → Example: /naics/541330/ancestors → [54, 541, 5413, 54133, 541330]
```

**Files to modify:**
- `api/src/FedProspector.Api/Controllers/ReferenceController.cs` — new actions
- `api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs` — new queries
- `api/src/FedProspector.Core/DTOs/` — new DTOs for hierarchy responses

### Task 3: Size Standard Eligibility Engine

Compute whether the organization meets the SBA size standard for a given NAICS code automatically.

**Schema change — `organization` table additions:**

```sql
ALTER TABLE organization
  ADD COLUMN annual_revenue DECIMAL(15,2) NULL COMMENT 'Average annual receipts (5-yr avg) in dollars',
  ADD COLUMN employee_count INT NULL COMMENT 'Average employees (24-month avg)';
```

Note: `NaicsStepData` in the UI already collects `employeeCount`, `annualRevenue`, and `fiscalYearEndMonth` — but these aren't persisted to the database today.

**New service method:**

```csharp
// Given org revenue/employees + a NAICS code, return eligibility
SizeEligibilityResult CheckSizeEligibility(int orgId, string naicsCode)
{
    // 1. Look up size standard for naicsCode
    // 2. Get org's revenue and employee count
    // 3. Compare based on size_type (M or E)
    // 4. Return: eligible (bool), threshold, actual, headroom%, outsized warning
}
```

**Auto-compute `size_standard_met`:**
- When org revenue/employees are updated, recompute for all org NAICS codes
- Store result in `organization_naics.size_standard_met`
- Trigger re-evaluation on size standard data refresh

**Files to modify:**
- `fed_prospector/db/schema/tables/60_prospecting.sql` — add columns
- Migration SQL file
- `api/src/FedProspector.Core/Models/Organization.cs` — new properties
- `api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs` — eligibility logic
- `api/src/FedProspector.Core/DTOs/` — new result DTOs

### Task 4: Outsized Warning System

Flag opportunities where the user's org exceeds the size standard.

**Opportunity list enrichment:**
- For each opportunity in search results, compare `opportunity.naics_code` against org's revenue/employees
- Add `sizeEligible` (bool) and `sizeHeadroomPct` (decimal) to `OpportunityListDto`
- If outsized: show warning badge in UI

**Opportunity detail enrichment:**
- Show full size standard breakdown: threshold, org actual, headroom, footnotes
- If outsized: prominent warning with explanation of risk

**Near-threshold alerts:**
- If org is within 20% of the size standard threshold, flag as "approaching outsized"
- This lets companies plan ahead before they lose eligibility

**Files to modify:**
- `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` — eligibility annotation
- `api/src/FedProspector.Core/DTOs/Opportunity/` — add eligibility fields
- `ui/src/pages/opportunities/` — warning badges and detail display

### Task 5: pWin Integration

Factor NAICS size standard eligibility into probability-of-win calculations.

**pWin factors to add:**

| Factor | Weight | Logic |
|--------|--------|-------|
| Size-eligible for set-aside | +15-25% | Org is small under the opportunity's NAICS code AND opportunity is a small business set-aside |
| Outsized | -50% or disqualify | Org exceeds size standard for a set-aside opportunity |
| NAICS code match | +5-10% | Org has the opportunity's NAICS code in their profile (demonstrates relevance) |
| Primary NAICS match | +3-5% additional | Opportunity NAICS matches org's primary NAICS (core competency) |
| Near-threshold | -5% | Org is within 20% of outsized — risk factor for multi-year contracts |

**Files to modify:**
- Wherever pWin calculation lives (likely a future phase)
- This task defines the scoring model; implementation integrates when pWin engine exists

### Task 6: NAICS Hierarchy Browser UI

New UI page or panel for exploring NAICS codes as a navigable tree.

**Features:**
- Expandable tree view: Sector → Subsector → Industry Group → Industry → National Industry
- Each 6-digit node shows: size standard, type (revenue/employee), footnotes
- Click a code to see: full description, SBA size standard, org's eligibility, opportunity count using that code
- Search/filter within the tree
- "Add to my profile" action from any node

**Placement:** New tab in Settings/Company Profile, or standalone page under Reference Data.

**Files to create/modify:**
- `ui/src/pages/` — new NAICS browser page/component
- `ui/src/api/reference.ts` — new API calls
- `ui/src/queries/useReference.ts` — new query hooks
- Router registration

### Task 7: SBA Size Standards Data Refresh

Mechanism to update size standards when SBA publishes new thresholds.

**Data sources (in priority order):**

1. **SBA NAICS JSON API**: `https://api.sba.gov/naics/naics.json` — structured JSON with all codes, size standards, and footnotes
2. **SBA Open Data Portal**: `https://data.sba.gov/en/dataset/small-business-size-standards` — downloadable datasets
3. **Census 2022 Structure**: `https://www.census.gov/naics/2022NAICS/2022_NAICS_Structure.xlsx` — code hierarchy

**CLI command:**

```bash
python main.py load naics-refresh [--source sba-api|csv] [--dry-run]
```

**Refresh logic:**
1. Fetch current SBA data
2. Compare against `ref_sba_size_standard` rows
3. Report changes (new codes, changed thresholds, retired codes)
4. Apply updates with `effective_date` tracking
5. Recompute `organization_naics.size_standard_met` for all orgs
6. Log changes to `etl_load_log`

**NAICS revision handling (2022 → 2027):**
- Census provides concordance files mapping old codes to new
- Load concordance as `ref_naics_concordance` table
- When a code is retired, link to successor(s) and flag affected orgs/opportunities

**New table:**

```sql
CREATE TABLE ref_naics_concordance (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    old_code        VARCHAR(11) NOT NULL,
    old_year        VARCHAR(4) NOT NULL,
    new_code        VARCHAR(11) NOT NULL,
    new_year        VARCHAR(4) NOT NULL,
    change_type     VARCHAR(20) NOT NULL COMMENT 'merged, split, renamed, unchanged',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_old (old_code),
    INDEX idx_new (new_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Files to modify:**
- `fed_prospector/etl/reference_loader.py` — new `refresh_naics()` and `refresh_size_standards()` methods
- `fed_prospector/cli/` — new CLI subcommand
- `fed_prospector/main.py` — register command
- `fed_prospector/db/schema/tables/10_reference.sql` — concordance table
- Migration SQL

### Task 8: Footnote Display & Exception Handling

Surface footnotes and size standard exceptions in the UI and API.

**API enhancement:**
- `GET /reference/naics/{code}` — include footnote text and any exception subcategories
- New DTO field: `footnotes: [{footnoteId, section, description}]`
- New DTO field: `exceptions: [{description, sizeStandard, sizeType}]` (from footnoted sub-entries)

**UI display:**
- Show footnote icon next to NAICS codes that have exceptions
- Expandable footnote text on hover/click
- If org's work falls under an exception subcategory, allow them to select it (affects size standard used)

**Files to modify:**
- `api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs`
- `api/src/FedProspector.Core/DTOs/`
- `ui/src/pages/setup/NaicsCodesStep.tsx`
- NAICS browser (Task 5)

---

## Cross-Linking Summary

### How NAICS data flows through the system

```
SBA API / CSV files
        │
        ▼
  ref_naics_code ◄────── Census NAICS structure
  ref_sba_size_standard   (hierarchy, descriptions)
  ref_naics_footnote
        │
        ├──► entity_naics ◄──── SAM.gov entity data
        │       (vendor's claimed NAICS codes)
        │
        ├──► organization_naics ◄──── User setup wizard
        │       (org's NAICS codes + eligibility)
        │
        ├──► opportunity.naics_code ◄──── SAM.gov opportunities
        │       (CO-assigned NAICS per solicitation)
        │
        └──► pWin calculation
                (eligibility gate + scoring factor)
```

### Relationships to other features

| Feature | NAICS Interaction |
|---------|-------------------|
| **Opportunity search** | Filter by NAICS code, show eligibility badge |
| **Prospect scoring (pWin)** | Size eligibility = major pWin factor |
| **Entity/vendor lookup** | Show vendor's NAICS codes and whether they're small |
| **Saved searches** | NAICS codes as saved filter criteria |
| **Federal hierarchy** | Agencies procure in specific NAICS codes — show patterns |
| **Awards/USASpending** | Historical awards by NAICS — market sizing |
| **Set-aside analysis** | Which NAICS codes have the most set-aside opportunities? |

---

## Out of Scope

- **SBA certification verification** (8(a), WOSB, HUBZone status) — separate from NAICS size standards
- **Affiliate analysis** — determining which entities are SBA affiliates is a legal question, not a data question
- **Recertification workflows** — annual recertification tracking
- **NAICS code recommendation engine** — "you should add this NAICS code" AI suggestions (Phase 500 candidate)

---

## Success Criteria

1. Comprehensive NAICS reference document in `thesolution/reference/`
2. NAICS hierarchy browsable as a tree in the UI (all 5 levels)
3. Automatic size eligibility computation based on org revenue/employees
4. Outsized warnings displayed on opportunities where org exceeds threshold
5. Footnotes and exceptions visible in NAICS detail views
6. CLI command to refresh size standards from SBA
7. Concordance table ready for NAICS 2027 revision
8. pWin scoring model documented and ready for integration
9. All existing NAICS functionality preserved (search, org setup, entity display)

---

## Estimated Effort

- Task 1 (Research & Reference Doc): 2-3 hours
- Task 2 (Hierarchy API): 2-3 hours
- Task 3 (Eligibility Engine): 3-4 hours
- Task 4 (Outsized Warnings): 2-3 hours
- Task 5 (pWin Integration): 1-2 hours (model definition; implementation depends on pWin engine)
- Task 6 (Hierarchy Browser UI): 4-6 hours
- Task 7 (Data Refresh): 3-4 hours
- Task 8 (Footnotes): 2-3 hours
- **Total: ~19-28 hours**

Can be split into sub-phases (129A, 129B, etc.) if needed.
