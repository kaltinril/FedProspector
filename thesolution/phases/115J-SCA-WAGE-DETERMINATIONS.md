# Phase 115J: SCA Wage Determinations

**Status:** PLANNED
**Priority:** HIGH
**Dependencies:** Phase 115B (Pricing Intelligence) — canonical labor categories, market rate heatmap, bid scenario modeler
**Data Source:** SAM.gov Wage Determination API (beta.sam.gov/api) — same API infrastructure as opportunities, free with existing key

---

## Summary

Integrate Department of Labor Service Contract Act (SCA) wage determination data to establish labor rate floors by geographic area. Combined with GSA CALC+ ceiling rates (Phase 115B), this gives users the full pricing range for service contracts.

The SCA requires contractors on federal service contracts to pay employees at least the prevailing wage rates set by DOL for each labor category in each geographic area. DOL publishes these as Wage Determinations (WDs) via SAM.gov. WDs specify minimum hourly rates + fringe benefit requirements by occupation and geographic area, using Directory of Occupations (DO) titles that can be cross-referenced to our canonical labor categories.

**Value proposition:**
- **Pricing floor** — know the minimum you MUST pay before bidding
- **Margin analysis** — compare SCA floor to GSA CALC+ ceiling to see real margin range
- **Geographic intelligence** — SCA rates vary by county; know where labor is cheaper
- **Compliance risk** — flag bids where proposed rates are below SCA minimums

---

## Features

### 1. SCA Data Loader

Python ETL to fetch and store wage determinations from SAM.gov.

- New API client extending `BaseAPIClient` (SAM.gov WD endpoint)
- CLI: `python main.py load sca`
- Change detection via record hash (standard pattern)
- Incremental loads keyed on WD number + revision

### 2. SCA / Canonical Category Mapping

Map DOL occupation titles to our canonical labor categories.

- DOL uses "Directory of Occupations" titles (e.g., "Computer Programmer III")
- Extend the labor_category_mapping approach from 115B
- New mapping table with `source='SCA'` to distinguish from GSA CALC+ mappings
- Confidence scoring for fuzzy matches; human review queue for low-confidence

### 3. Rate Floor/Ceiling Analysis

For a given canonical category + geographic area: show SCA floor, GSA CALC+ ceiling, and spread.

- Integrate into the Market Rate Heatmap (115B Feature 1) as an additional layer
- API: `GET /api/v1/pricing/rate-range?canonicalId=X&state=Y`
- React UI: side-by-side floor/ceiling display with margin percentage

### 4. Bid Compliance Checker

Validate proposed labor rates against SCA minimums before submission.

- Input: proposed labor rates by category + work location
- Output: pass/fail per category, required fringe obligations, total compliance cost
- Integrate into Bid Scenario Modeler (115B Feature 3)
- API: `POST /api/v1/pricing/sca-compliance-check`

### 5. Geographic Rate Map

Show SCA rate variations by area for a given occupation.

- Table or map visualization: rates by state/county
- Useful for deciding where to propose work or base employees
- API: `GET /api/v1/pricing/sca-geographic?occupation=X`

---

## New Tables

| Table | Purpose |
|-------|---------|
| `sca_wage_determination` | WD metadata — WD number, revision, area, effective date, status |
| `sca_wage_rate` | Individual occupation rates per WD — occupation, hourly rate, fringe, health_welfare, vacation, holiday |
| `sca_occupation_mapping` | DOL occupation title -> canonical labor category crosswalk |

---

## Implementation Notes

### Existing Foundation

| Asset | Relevance |
|-------|-----------|
| `gsa_labor_rate` | 230K+ GSA CALC+ rates — the ceiling side of the floor/ceiling range |
| 115B Market Rate Heatmap | UI framework to layer SCA floor data onto |
| 115B Bid Scenario Modeler | Calculator to integrate compliance checking into |
| SAM.gov API client infrastructure | Same base URL and auth; extend for WD endpoint |

### Build Order

1. **Feature 1** (SCA Data Loader) — must come first; all other features depend on having data
2. **Feature 2** (Category Mapping) — needed before floor/ceiling comparison is meaningful
3. **Features 3-5** can be built in parallel once data and mappings exist

### API Key Usage

Uses existing SAM.gov API key (same as opportunity loads). WD API is lower volume than opportunity search — expect hundreds of WDs, not millions of records. Key 2 (1000/day) should be sufficient.
