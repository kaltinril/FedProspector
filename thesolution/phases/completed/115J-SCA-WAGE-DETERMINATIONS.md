# Phase 115J: SCA Wage Determinations

**Status:** COMPLETE
**Priority:** HIGH
**Dependencies:** Phase 115B (Pricing Intelligence) — canonical labor categories, market rate heatmap, bid scenario modeler
**Data Source:** SAM.gov undocumented download endpoints (no API key needed):
- WD text: `sam.gov/api/prod/wdol/v1/wd/{WD_NUMBER}/{REVISION}/download` — fixed-width plain text, ~10-30KB each
- County crosswalk: `sam.gov/sites/default/files/2024-11/sca-2015-crosswalk.xlsx` — maps 4,917 counties → 887 unique WD numbers

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

Python ETL to fetch and store wage determinations from SAM.gov download endpoints.

- **NOT a standard JSON API client** — data comes from an undocumented S3-backed download endpoint returning fixed-width plain text
- Download crosswalk XLSX to discover all WD numbers + county mappings
- Iterate over 887 WD numbers, fetch each via download endpoint, probe revisions until 404
- Parse fixed-width text with regex to extract occupation codes, titles, hourly rates, fringe benefits
- No API key needed. No rate limiting observed (S3-backed).
- Change detection via record hash (standard pattern)
- Uses LoadManager for tracking (standard pattern)
- CLI: `python main.py load sca`

### 2. SCA / Canonical Category Mapping

Map DOL occupation titles to our canonical labor categories.

- DOL uses "Directory of Occupations" titles (e.g., "Computer Programmer III")
- Extend existing `labor_category_mapping` table with a `source` column:
  - `ALTER TABLE labor_category_mapping ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'GSA_CALC'`
  - Widen unique key to `(raw_labor_category, source)` to allow same raw title from different sources
- Reuse existing `labor_normalizer.py` 3-pass matching (exact → pattern → fuzzy)
- Confidence scoring for fuzzy matches; human review queue for low-confidence

### 3. Rate Floor/Ceiling Analysis

For a given canonical category + geographic area: show SCA floor, GSA CALC+ ceiling, and spread.

- Endpoint: `GET /api/v1/pricing/rate-range` with `RateRangeRequest` DTO (canonicalId, state, county, areaCode)
- Response includes fringe costs: `scaFloorRate`, `scaFringe`, `scaFullCost` (floor + fringe), `gsaCeilingRate`, `spread`, `spreadPct`
- UI: Toggle on existing RateHeatmapPage, not a separate view

### 4. Bid Compliance Checker

Validate proposed labor rates against SCA minimums before submission.

- Endpoint: `POST /api/v1/pricing/sca-compliance-check` with `ScaComplianceRequest` (state, county, list of line items with canonicalId + proposedRate + includesFringe flag)
- Per-line-item pass/fail results with required fringe obligations and total compliance cost
- UI: Section within existing BidScenarioPage, not a separate page

### 5. SCA Area Rates

Show SCA rate variations by area for a given occupation.

- Endpoint: `GET /api/v1/pricing/sca-area-rates/{canonicalId:int}` (canonicalId, not occupation text)
- UI: New page `ScaGeographicPage.tsx` with sortable DataTable, no map visualization in v1

---

## New Tables

### `sca_wage_determination`

| Column | Type | Notes |
|--------|------|-------|
| id | INT AUTO_INCREMENT PK | |
| wd_number | VARCHAR(20) NOT NULL | e.g., "2015-4281" |
| revision | INT NOT NULL | Revision number, probed until 404 |
| title | VARCHAR(255) | WD title from parsed text |
| area_name | VARCHAR(255) | Geographic area name |
| state_code | CHAR(2) | State abbreviation |
| county_name | VARCHAR(100) | County name (NULL if statewide) |
| is_statewide | TINYINT(1) NOT NULL DEFAULT 0 | 1 if covers entire state |
| effective_date | DATE | |
| expiration_date | DATE | |
| status | VARCHAR(20) | Active, superseded, etc. |
| is_current | TINYINT(1) NOT NULL DEFAULT 1 | 1 for latest revision |
| record_hash | CHAR(64) NOT NULL | SHA-256 change detection |
| first_loaded_at | DATETIME NOT NULL | |
| last_loaded_at | DATETIME NOT NULL | |
| last_load_id | INT NOT NULL | |

**UK:** `(wd_number, revision)`

### `sca_wage_rate`

| Column | Type | Notes |
|--------|------|-------|
| id | INT AUTO_INCREMENT PK | |
| wd_id | INT NOT NULL | References sca_wage_determination.id (no FK constraint) |
| occupation_code | VARCHAR(20) NOT NULL | DOL occupation code |
| occupation_title | VARCHAR(255) NOT NULL | DOL occupation title |
| hourly_rate | DECIMAL(10,2) | Minimum hourly rate |
| fringe_rate | DECIMAL(10,2) | Total fringe rate |
| health_welfare | DECIMAL(10,2) | H&W component |
| vacation | DECIMAL(10,2) | Vacation component |
| holiday | DECIMAL(10,2) | Holiday component |
| record_hash | CHAR(64) NOT NULL | SHA-256 change detection |
| first_loaded_at | DATETIME NOT NULL | |
| last_loaded_at | DATETIME NOT NULL | |
| last_load_id | INT NOT NULL | |

**UK:** `(wd_id, occupation_code)`

### No `sca_occupation_mapping` table

Category mapping uses the existing `labor_category_mapping` table extended with a `source` column (see Feature 2).

---

## Implementation Notes

### Existing Foundation

| Asset | Relevance |
|-------|-----------|
| `gsa_labor_rate` | 230K+ GSA CALC+ rates — the ceiling side of the floor/ceiling range |
| 115B Market Rate Heatmap | UI framework to layer SCA floor data onto |
| 115B Bid Scenario Modeler | Calculator to integrate compliance checking into |
| `labor_normalizer.py` | 3-pass matching logic reused for SCA occupation → canonical mapping |
| `labor_category_mapping` | Extended with `source` column to hold SCA mappings alongside GSA CALC+ |

### Key Engineering Effort

The fixed-width text parser is the main engineering challenge. Each WD download is plain text with occupation codes, titles, and rates in a fixed-width layout that must be parsed with regex. There is no JSON or structured API response — the download endpoint returns raw text files.

### Build Order

1. **Feature 1** (SCA Data Loader) — must come first; all other features depend on having data
2. **Feature 2** (Category Mapping) — needed before floor/ceiling comparison is meaningful
3. **Features 3-5** can be built in parallel once data and mappings exist
