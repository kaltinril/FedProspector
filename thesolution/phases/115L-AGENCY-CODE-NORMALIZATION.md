# Phase 115L: Agency Code Normalization

**Status:** PLANNED
**Priority:** HIGH -- cross-cutting data quality issue affecting pricing, scoring, market intel, and competitor analysis
**Dependencies:** federal_organization table (already loaded via hierarchy)

---

## Summary

Agency names are stored as free-text strings that differ across data sources:
- SAM.gov opportunities: "STATE, DEPARTMENT OF"
- USASpending awards: "Department of State"
- FPDS contracts: "DEPARTMENT OF STATE"
- Subawards: "STATE, DEPARTMENT OF"

This means cross-table queries (e.g., "find USASpending awards for this opportunity's agency") fail on text matching. Currently affects IGCE estimator, Price-to-Win, and any query that joins opportunity to award data.

**Solution: Normalize on write.** During ETL load, after downloading but before hashing/upserting, look up each record's agency name in `federal_organization` and resolve it to a CGAC code (or org_id). Store the code alongside the text name. All downstream queries match on code, not text.

---

## Current State

### Existing Agency Columns by Table

| Table | Has Code | Has Name | Notes |
|-------|----------|----------|-------|
| `federal_organization` | `cgac VARCHAR(10)`, `agency_code VARCHAR(20)` | `fh_org_name VARCHAR(500)` | Authoritative source, ~2K rows |
| `fpds_contract` | `agency_id VARCHAR(10)`, `funding_agency_id VARCHAR(10)` | `agency_name VARCHAR(200)`, `funding_agency_name VARCHAR(200)` | Already has codes from FPDS feed |
| `opportunity` | -- none -- | `department_name VARCHAR(200)` | **Missing code column** |
| `usaspending_award` | -- none -- | `awarding_agency_name VARCHAR(200)`, `awarding_sub_agency_name VARCHAR(200)`, `funding_agency_name VARCHAR(200)` | **Missing code columns** |
| `sam_subaward` | `prime_agency_id VARCHAR(10)` | `prime_agency_name VARCHAR(200)` | Already has code from subaward feed |

**Key finding:** `fpds_contract` and `sam_subaward` already carry agency codes from their source feeds. The main gaps are `opportunity` and `usaspending_award`.

---

## Feature 1: Agency Resolution Utility

New Python utility `fed_prospector/etl/agency_resolver.py`:

- Loads `federal_organization` into memory (small table, ~2K rows)
- Builds lookup indexes:
  - `fh_org_name` -> `cgac` (direct match)
  - Normalized variants: "X, DEPARTMENT OF" <-> "Department of X", all-caps, common abbreviations
  - `agency_code` -> `cgac` (for code-based lookups)
- Methods:
  - `resolve_agency(name: str) -> str | None` -- returns CGAC code for a given agency name
  - `resolve_bulk(names: list[str]) -> dict[str, str | None]` -- batch resolution
- Handles common patterns:
  - Case-insensitive matching
  - "STATE, DEPARTMENT OF" -> "DEPARTMENT OF STATE" -> cgac "019"
  - "DEPT OF" <-> "DEPARTMENT OF" abbreviation expansion
  - Leading/trailing whitespace, double spaces
- Fuzzy fallback for near-matches with confidence threshold (>90% similarity)
- Caches resolved names for performance during batch processing
- Logs unresolved agencies for review

---

## Feature 2: Add CGAC Code Columns

New columns on tables that lack agency codes (ALTER TABLE, not recreate):

| Table | New Column(s) | Source for Resolution |
|-------|--------------|----------------------|
| `opportunity` | `department_cgac VARCHAR(10)` | `department_name` |
| `usaspending_award` | `awarding_agency_cgac VARCHAR(10)`, `funding_agency_cgac VARCHAR(10)` | `awarding_agency_name`, `funding_agency_name` |

CGAC codes are 3-character strings (e.g., "019" for State Dept). Using VARCHAR(10) to match `federal_organization.cgac` column type.

Index each new column for fast joins.

**Not adding columns to:**
- `fpds_contract` -- already has `agency_id` and `funding_agency_id` from the FPDS data feed
- `sam_subaward` -- already has `prime_agency_id` from the subaward data feed

### DDL

```sql
-- opportunity: add department code
ALTER TABLE opportunity
    ADD COLUMN department_cgac VARCHAR(10) DEFAULT NULL AFTER department_name,
    ADD INDEX idx_opp_dept_cgac (department_cgac);

-- usaspending_award: add awarding and funding agency codes
ALTER TABLE usaspending_award
    ADD COLUMN awarding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER awarding_sub_agency_name,
    ADD COLUMN funding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER funding_agency_name,
    ADD INDEX idx_usa_awarding_cgac (awarding_agency_cgac),
    ADD INDEX idx_usa_funding_cgac (funding_agency_cgac);
```

**Note:** The `usaspending_award` ALTER TABLE will take significant time on 28.7M rows. Plan for off-hours execution.

---

## Feature 3: ETL Integration -- Normalize on Load

Modify each loader's post-load step to resolve agency codes via UPDATE ... JOIN:

| Loader | How |
|--------|-----|
| `opportunity_loader.py` | After load, UPDATE opportunity o JOIN federal_organization fo to set `department_cgac` |
| `usaspending_loader.py` | After bulk LOAD DATA INFILE, UPDATE to populate `awarding_agency_cgac` and `funding_agency_cgac` |

The UPDATE approach is better than per-row resolution because:
- Works with LOAD DATA INFILE (can't modify data during bulk load)
- Single UPDATE ... JOIN is fast even on millions of rows
- Doesn't change the load pipeline structure

### Resolution Strategy

Direct JOIN on name won't work due to name format differences. Two-pass approach:

**Pass 1: Direct match via JOIN**
```sql
UPDATE opportunity o
JOIN federal_organization fo ON UPPER(o.department_name) = UPPER(fo.fh_org_name)
SET o.department_cgac = fo.cgac
WHERE o.department_cgac IS NULL AND fo.level = 1;
```

**Pass 2: Fuzzy/variant match via Python**
For records still NULL after Pass 1, use the `agency_resolver.py` utility to handle name variants ("STATE, DEPARTMENT OF" -> "DEPARTMENT OF STATE"). Run as a batched UPDATE with a temporary mapping table built by the resolver.

### No Changes Needed For:
- `fpds_loader.py` -- `agency_id` and `funding_agency_id` already come from the FPDS source data
- `subaward_loader.py` -- `prime_agency_id` already comes from the subaward source data

---

## Feature 4: Backfill Existing Data

One-time migration to populate codes for already-loaded records.

CLI: `python main.py maintain normalize-agencies`

Steps:
1. Build name-to-CGAC mapping using `agency_resolver.py`
2. Create temporary mapping table with all resolved name->code pairs
3. UPDATE each target table using JOIN to the mapping table
4. Report statistics: total rows, resolved, unresolved

```sql
-- Example: backfill opportunity
CREATE TEMPORARY TABLE tmp_agency_map (
    agency_name VARCHAR(200) PRIMARY KEY,
    cgac VARCHAR(10) NOT NULL
);
-- Python populates tmp_agency_map using resolver

UPDATE opportunity o
JOIN tmp_agency_map m ON o.department_name = m.agency_name
SET o.department_cgac = m.cgac
WHERE o.department_cgac IS NULL;

-- Similar for usaspending_award awarding/funding
```

---

## Feature 5: Update Downstream Queries

After codes are populated, update queries that currently match on agency text:

| Component | Current (text match) | New (code match) |
|-----------|---------------------|-------------------|
| PricingService.cs | LIKE on `awarding_agency_name` | JOIN on `awarding_agency_cgac` or `agency_id` |
| MarketIntelService.cs | LIKE on agency names | JOIN on CGAC codes |
| v_procurement_intelligence | Text-based agency grouping | Code-based grouping |
| v_price_to_win_comparable | LIKE text matching | Code-based joins |
| Scoring services | Any agency-based text matching | Code-based matching |

Cross-table queries become straightforward:
```sql
-- Find USASpending awards for an opportunity's agency
SELECT ua.*
FROM opportunity o
JOIN usaspending_award ua ON o.department_cgac = ua.awarding_agency_cgac
WHERE o.notice_id = ?;

-- Join FPDS contracts to opportunities via agency
SELECT fc.*
FROM opportunity o
JOIN fpds_contract fc ON o.department_cgac = fc.agency_id
WHERE o.notice_id = ?;
```

---

## Feature 6: Unresolved Agency Report

Track agencies that couldn't be resolved:

CLI: `python main.py report unresolved-agencies`

Output:
- Unmatched agency names with row counts, grouped by source table
- Helps identify gaps in `federal_organization` data or new name patterns
- Sorted by row count descending (fix highest-impact gaps first)

---

## Existing Foundation

| Asset | Relevance |
|-------|-----------|
| `federal_organization` table | ~2K rows with fh_org_name, cgac, agency_code, sub-tier hierarchy |
| `federal_hierarchy` loader | Already loads org data weekly from SAM.gov |
| `fpds_contract.agency_id` | Already normalized -- no work needed |
| `sam_subaward.prime_agency_id` | Already normalized -- no work needed |
| `etl_utils.py` | Shared ETL utilities for post-load processing |

---

## Build Order

1. Agency resolver utility (pure Python, no DB changes)
2. ALTER TABLE to add CGAC columns + indexes on `opportunity` and `usaspending_award`
3. Backfill existing data via `maintain normalize-agencies`
4. Modify `opportunity_loader` and `usaspending_loader` to run post-load normalization
5. Update downstream queries/views in C# services
6. Unresolved agency report

---

## Implementation Estimate

| Item | Effort |
|------|--------|
| `agency_resolver.py` -- lookup utility | Medium -- name variant handling is the core logic |
| ALTER TABLE on `opportunity` | Small -- fast table (~200K rows) |
| ALTER TABLE on `usaspending_award` | Medium -- 28.7M rows, needs off-hours |
| Backfill existing data | Medium -- depends on resolver accuracy |
| Loader integration (2 loaders) | Small -- add post-load UPDATE step |
| Downstream query updates | Medium -- multiple C# services and views |
| Unresolved agency report | Small -- query + CLI command |

---

## Data Impact

- Adds 1 new nullable VARCHAR(10) column to `opportunity`
- Adds 2 new nullable VARCHAR(10) columns to `usaspending_award`
- Enables exact-match cross-table queries instead of LIKE text matching
- All pricing, scoring, and market intel queries become faster and more accurate
- No changes to `fpds_contract` or `sam_subaward` (already have codes)

---

## Risks

- `federal_organization` may not cover all agency names (especially sub-tier offices that use non-standard names)
- The UPDATE ... JOIN approach requires matching names which is the same problem we're solving -- need the fuzzy resolver for edge cases
- ALTER TABLE on `usaspending_award` (28.7M rows) will take significant time and disk space for the index builds
- Some source data may use sub-agency names that don't map cleanly to a top-level CGAC code

---

## Testing

1. Unit test `agency_resolver.py` with known name variants:
   - "STATE, DEPARTMENT OF" -> "019"
   - "Department of State" -> "019"
   - "DEPARTMENT OF STATE" -> "019"
   - Unknown name -> None
2. Verify ALTER TABLE succeeds on both tables
3. Run backfill and check resolution rate (target: >95% of rows resolved)
4. Verify post-load normalization populates codes on newly loaded records
5. Test cross-table JOIN queries using CGAC codes
6. Run unresolved agency report and verify output format

---

## Files Modified

| File | Change |
|------|--------|
| `fed_prospector/etl/agency_resolver.py` | **New** -- agency name to CGAC resolution utility |
| `fed_prospector/db/schema/tables/30_opportunity.sql` | Add `department_cgac` column |
| `fed_prospector/db/schema/tables/70_usaspending.sql` | Add `awarding_agency_cgac`, `funding_agency_cgac` columns |
| `fed_prospector/etl/opportunity_loader.py` | Post-load UPDATE to set `department_cgac` |
| `fed_prospector/etl/usaspending_loader.py` | Post-load UPDATE to set `awarding_agency_cgac`, `funding_agency_cgac` |
| `fed_prospector/cli/maintain.py` | Add `normalize-agencies` command |
| `fed_prospector/cli/report.py` | Add `unresolved-agencies` command |
| `api/src/FedProspector.Infrastructure/Services/PricingService.cs` | Switch to code-based agency joins |
| `api/src/FedProspector.Infrastructure/Services/MarketIntelService.cs` | Switch to code-based agency joins |
| `fed_prospector/db/schema/views/` | Update agency-matching views to use CGAC codes |
