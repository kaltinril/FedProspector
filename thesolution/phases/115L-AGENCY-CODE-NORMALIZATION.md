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

**Key discovery:** The opportunity API already sends agency codes in `fullParentPathCode` (e.g., `019.1900.19M553`). We already parse this field and save the last segment as `contracting_office_id`, but discard the first segment (CGAC code `019`) and second segment (sub-tier code `1900`). The fix for opportunities is to save all three segments during the existing parse — no resolver needed. We also store the raw JSON from API loads, so existing records can be backfilled by re-parsing the stored JSON without re-downloading.

---

## Current State

### Existing Agency Columns by Table

| Table | Has Code | Has Name | Notes |
|-------|----------|----------|-------|
| `federal_organization` | `cgac VARCHAR(10)`, `agency_code VARCHAR(20)` | `fh_org_name VARCHAR(500)` | Authoritative source, ~2K rows |
| `fpds_contract` | `agency_id VARCHAR(10)`, `funding_agency_id VARCHAR(10)` | `agency_name VARCHAR(200)`, `funding_agency_name VARCHAR(200)` | Already has codes from FPDS feed |
| `opportunity` | `contracting_office_id VARCHAR(20)` only (last segment of `fullParentPathCode`) | `department_name VARCHAR(200)` | **Has office code but missing CGAC (1st segment) and sub-tier code (2nd segment) — both already in `fullParentPathCode` but discarded during parse** |
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
| `opportunity` | `department_cgac VARCHAR(10)`, `sub_tier_code VARCHAR(20)` | **Already in API data** — parse from `fullParentPathCode` segments 1 and 2 (currently discarded) |
| `usaspending_award` | `awarding_agency_cgac VARCHAR(10)`, `funding_agency_cgac VARCHAR(10)` | `awarding_agency_name` / `funding_agency_name` — need resolver lookup |

CGAC codes are 3-character strings (e.g., "019" for State Dept). Using VARCHAR(10) to match `federal_organization.cgac` column type.

Index each new column for fast joins.

**Not adding columns to:**
- `fpds_contract` -- already has `agency_id` and `funding_agency_id` from the FPDS data feed
- `sam_subaward` -- already has `prime_agency_id` from the subaward data feed

### Opportunity: Data Already Available

The SAM.gov opportunity API returns `fullParentPathCode` (e.g., `019.1900.19M553`):
- Segment 1: **CGAC code** (`019`) — the department identifier we need
- Segment 2: **Sub-tier code** (`1900`) — the sub-agency identifier
- Segment 3: **Office code** (`19M553`) — already saved as `contracting_office_id`

Current code in `opportunity_loader.py` (line 424-426) parses this field but only saves the last segment. Fix: save all three segments. No resolver needed for opportunities.

**Backfill:** We store raw JSON from API loads. Existing records can be backfilled by re-parsing the stored JSON to extract segments 1 and 2 — no re-download needed.

### DDL

```sql
-- opportunity: add department CGAC and sub-tier code
ALTER TABLE opportunity
    ADD COLUMN department_cgac VARCHAR(10) DEFAULT NULL AFTER department_name,
    ADD COLUMN sub_tier_code VARCHAR(20) DEFAULT NULL AFTER sub_tier,
    ADD INDEX idx_opp_dept_cgac (department_cgac);

-- usaspending_award: add awarding and funding agency codes
ALTER TABLE usaspending_award
    ADD COLUMN awarding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER awarding_sub_agency_name,
    ADD COLUMN funding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER funding_agency_name,
    ADD INDEX idx_usa_awarding_cgac (awarding_agency_cgac),
    ADD INDEX idx_usa_funding_cgac (funding_agency_cgac);
```

**Note:** The `usaspending_award` ALTER TABLE will take significant time on 28.7M rows. Plan for off-hours execution. The `opportunity` ALTER is fast (~200K rows).

---

## Feature 3: ETL Integration -- Normalize on Load

Modify each loader's post-load step to resolve agency codes via UPDATE ... JOIN:

| Loader | How |
|--------|-----|
| `opportunity_loader.py` | **Parse during load** — extract segments 1 and 2 from `fullParentPathCode` alongside existing segment 3 parse. No post-load UPDATE needed. |
| `usaspending_loader.py` | After bulk LOAD DATA INFILE, UPDATE to populate `awarding_agency_cgac` and `funding_agency_cgac` using resolver |

### Opportunity Loader: Parse on Load (No Resolver Needed)

The fix is ~3 lines in `opportunity_loader.py` (around line 424):
```python
# Current: only saves last segment
contracting_office_id = code_parts[-1] if code_parts else None

# New: save all three segments  
department_cgac = code_parts[0] if len(code_parts) >= 1 else None
sub_tier_code = code_parts[1] if len(code_parts) >= 2 else None
contracting_office_id = code_parts[-1] if code_parts else None
```

Then include `department_cgac` and `sub_tier_code` in the upsert column list.

### USASpending Loader: Post-Load Resolver

USASpending bulk CSV downloads may include `awarding_agency_code` — check the export columns first. If the code is in the CSV, save it directly during LOAD DATA INFILE (no resolver needed, same as opportunity approach).

If the code is NOT in the CSV, use the two-pass resolver approach:

**Pass 1: Direct match via JOIN**
```sql
UPDATE usaspending_award ua
JOIN federal_organization fo ON UPPER(ua.awarding_agency_name) = UPPER(fo.fh_org_name)
SET ua.awarding_agency_cgac = fo.cgac
WHERE ua.awarding_agency_cgac IS NULL AND fo.fh_org_type = 'Department/Ind. Agency';
```

**Pass 2: Fuzzy/variant match via Python**
For records still NULL after Pass 1, use the `agency_resolver.py` utility to handle name variants. Run as a batched UPDATE with a temporary mapping table built by the resolver.

### No Changes Needed For:
- `fpds_loader.py` -- `agency_id` and `funding_agency_id` already come from the FPDS source data
- `subaward_loader.py` -- `prime_agency_id` already comes from the subaward source data

---

## Feature 4: Backfill Existing Data

One-time migration to populate codes for already-loaded records.

CLI: `python main.py maintain normalize-agencies`

### Opportunity Backfill (two-pass)

**Pass 1: Extract from stored raw JSON (free, fast)**

We store full API responses in `stg_opportunity_raw.raw_json`. The `fullParentPathCode` field is in there — extract segments 1 and 2 without re-downloading:

```sql
UPDATE opportunity o
JOIN stg_opportunity_raw s ON o.notice_id = s.notice_id
SET o.department_cgac = SUBSTRING_INDEX(
        JSON_UNQUOTE(JSON_EXTRACT(s.raw_json, '$.fullParentPathCode')), '.', 1),
    o.sub_tier_code = SUBSTRING_INDEX(
        SUBSTRING_INDEX(JSON_UNQUOTE(JSON_EXTRACT(s.raw_json, '$.fullParentPathCode')), '.', 2), '.', -1)
WHERE o.department_cgac IS NULL;
```

**Pass 2: Re-fetch from SAM.gov API for records missing from staging**

Some opportunities may have been loaded before `stg_opportunity_raw` existed, or staging may have been purged. For any records still NULL after Pass 1:
- Query `SELECT notice_id FROM opportunity WHERE department_cgac IS NULL`
- Batch-fetch from SAM.gov API (uses API key — respect rate limits)
- Extract `fullParentPathCode` from response, update opportunity row
- CLI flag: `python main.py maintain normalize-agencies --refetch-missing`

### USASpending Backfill

Same two-pass approach if `stg_usaspending_raw` exists. Otherwise use the resolver approach:

```sql
CREATE TEMPORARY TABLE tmp_agency_map (
    agency_name VARCHAR(200) PRIMARY KEY,
    cgac VARCHAR(10) NOT NULL
);
-- Python populates tmp_agency_map using agency_resolver.py

UPDATE usaspending_award ua
JOIN tmp_agency_map m ON ua.awarding_agency_name = m.agency_name
SET ua.awarding_agency_cgac = m.cgac
WHERE ua.awarding_agency_cgac IS NULL;

-- Similar for funding_agency_cgac
```

### Statistics

Report after backfill:
- Total rows per table
- Resolved from raw JSON (Pass 1)
- Resolved from API re-fetch (Pass 2)
- Resolved from name mapping (USASpending)
- Still unresolved (with top unresolved names by frequency)

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
