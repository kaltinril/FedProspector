# Phase 115L: Agency Code Normalization

**Status:** IN PROGRESS — Code complete. ALTER TABLE pending (run when MySQL is available).
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

After codes are populated, downstream queries can use code-based joins instead of text matching.

**Validated scope (smaller than initially estimated):**
- **PricingService.cs** — Already avoids agency matching by design (line 972 comment: "agency name formats differ between opportunity and USASpending"). Uses NAICS as primary filter. **No changes needed** — but the new CGAC codes enable future agency-aware pricing queries.
- **MarketIntelService.cs** — Already uses `AgencyId` extracted from `FullParentPathCode` via `ExtractAgencyCode()` (line 434). **No changes needed for FPDS queries**, but opportunity→usaspending joins now possible via `department_cgac = awarding_agency_cgac`.
- **Views** — Display agency names for UI but don't perform cross-table agency matching. **No changes needed.**

**Primary value:** Enables new cross-table queries that were previously impossible:
```sql
-- Find USASpending awards for an opportunity's agency (NEW — not possible before)
SELECT ua.*
FROM opportunity o
JOIN usaspending_award ua ON o.department_cgac = ua.awarding_agency_cgac
WHERE o.notice_id = ?;

-- Join FPDS contracts to opportunities via agency (NEW — previously required text matching)
SELECT fc.*
FROM opportunity o
JOIN fpds_contract fc ON o.department_cgac = fc.agency_id
WHERE o.notice_id = ?;
```

These joins will be consumed by future features (e.g., agency-filtered IGCE, award history by department). No existing C# services or views require immediate updates.

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
| Downstream query updates | Small -- no existing services need changes (validated: PricingService avoids agency matching, MarketIntelService already uses AgencyId codes) |
| Unresolved agency report | Small -- query + CLI command |

---

## Data Impact

- Adds 1 new nullable VARCHAR(10) column to `opportunity`
- Adds 2 new nullable VARCHAR(10) columns to `usaspending_award`
- Enables exact-match cross-table queries instead of LIKE text matching
- All pricing, scoring, and market intel queries become faster and more accurate
- No changes to `fpds_contract` or `sam_subaward` (already have codes)

---

## Post-Backfill Cleanup (Evaluated 2026-04-09)

### Backfill Results

| Table | Populated | Unresolved | Rate |
|-------|-----------|------------|------|
| opportunity | 56,392 | 1 (no department_name) | 99.998% |
| usaspending_award (awarding) | 28,755,675 | 8,385 (5 names) | 99.97% |
| usaspending_award (funding) | 28,716,745 | 41,972 (9 names) | 99.85% |

Resolver stats: 57 exact, 6 variant, 4 fuzzy matches out of 72 distinct awarding names.

Top unresolved names (niche agencies not in federal_organization):
- U.S. Agency for Global Media (5,983 rows)
- Corps of Engineers - Civil Works (33,255 funding rows)
- U.S. International Development Finance Corporation (1,337 rows)
- Export-Import Bank of the United States (973 rows)

---

### 1. Performance — HIGH PRIORITY: Cross-Table Joins Producing Wrong Results

Three services are doing text-based agency matching that **silently fails** due to name format differences between SAM.gov and USASpending:

| Service | Line | What's Broken | Impact |
|---------|------|---------------|--------|
| `AutoProspectService.cs` | 275 | `o.DepartmentName == contract.FundingAgencyName` | Recompete detection misses matches where agency names differ across sources |
| `RecommendedOpportunityService.cs` | 164, 203, 405 | `competitionLookup` keyed on `AgencyName`, looked up by `DepartmentName` | Opportunity scoring ignores agency-level competition data when names don't match |
| `etl_utils.py` | 239-248 | `usaspending_award_summary` built with `GROUP BY awarding_agency_name` | Summary table uses text names as dimension key — lookups from opportunity side fail |

**Fix required:**
1. Change `usaspending_award_summary` schema: add `agency_cgac` column, change PK to `(naics_code, agency_cgac)`, keep `agency_name` for display
2. Change `etl_utils.py` summary refresh to `GROUP BY awarding_agency_cgac`
3. Change `AutoProspectService.cs:275` to compare CGAC codes
4. Change `RecommendedOpportunityService.cs` competition lookup to key on CGAC codes
5. Change `PWinService.cs:313-321,488-493` from `Contains()` string matching to CGAC comparison

**Additional medium-priority fixes:**
- `FederalHierarchyService.cs:315` — match opportunities to org hierarchy by CGAC instead of name list

**No changes needed for:**
- User-facing LIKE/Contains search filters (OpportunityService, AwardService, ExpiringContractService, PricingService) — text search is correct UX
- Display-only projections into DTOs — names still needed for UI rendering
- ETL loaders that already populate both name and CGAC columns

---

### 2. Index Cleanup — Drop 4 Unused Indexes (~400-600 MB savings)

Evaluation of all 15 indexes on `usaspending_award` (28.7M rows):

| Index | Columns | Verdict | Evidence |
|-------|---------|---------|----------|
| `idx_usa_agency` | `awarding_agency_name(50)` | **DROP — REPLACED** | Prefix index never helped existing LIKE '%...%' queries. Superseded by `idx_usa_awarding_cgac`. |
| `idx_usa_recipient_name` | `recipient_name(40)` | **DROP — USELESS** | Only consumer uses CONTAINS (mid-string match) which cannot use a prefix index. Vendor lookup uses `entity` table instead. |
| `idx_usa_modified` | `last_modified_date` | **DROP — UNUSED** | Zero WHERE clause usage in entire codebase (Python + C#). Column is write-only metadata. |
| `idx_usa_enrich` | `fpds_enriched_at` | **DROP — UNUSED** | Zero WHERE clause usage. Column is write-only metadata. |

**Borderline:** `idx_usa_fy` (`fiscal_year`) — also zero WHERE usage today, but cheapest index (SMALLINT) and natural future analytics dimension. Keep for now.

**Note:** `usaspending_bulk_loader.py` lines 111-115 drops/recreates indexes during full loads — that code needs updating when indexes are removed.

---

### 3. Auto-Resolve on USASpending Load

Currently new bulk loads insert rows with NULL CGAC codes, requiring manual `maintain normalize-agencies`.

**Best approach — check CSV columns first:**
USASpending's 299-column CSV format likely includes `awarding_agency_code` and `funding_agency_code`. If so, map them directly in `usaspending_bulk_loader.py`:
- Add to `CSV_COLUMN_MAP`: `"awarding_agency_code": "awarding_agency_cgac"`
- Add to `LOAD_COLUMNS`: `"awarding_agency_cgac"`, `"funding_agency_cgac"`
- This is zero-cost — codes arrive via LOAD DATA INFILE, no resolver needed for bulk path

**Fallback — resolver-based post-load step:**
If CSV lacks agency codes, add shared utility to `etl_utils.py`:
- `resolve_usaspending_agency_codes(conn)` — queries distinct NULL names, resolves via AgencyResolver, per-name UPDATEs
- Call after `refresh_usaspending_award_summary()` in both `usaspending_bulk_loader.py` (load_fiscal_year line 285, load_delta line 416) and `usaspending_loader.py` (line 283)
- Performance: <2 seconds on daily loads (~100 distinct names, indexed UPDATEs on NULL rows only)
- AgencyResolver loads ~2K rows into memory — trivial footprint

**API loader always needs resolver** — USASpending search endpoint doesn't return agency codes.

---

### 4. Column Removal — DEFERRED (keep as denormalized display fields)

Evaluated dropping `awarding_agency_name`, `awarding_sub_agency_name`, `funding_agency_name` from `usaspending_award`.

**Verdict: Too much blast radius, low ROI.**

Blocking dependencies:
- **HASH fields** — all 3 columns are in `_AWARD_HASH_FIELDS`. Removing them changes SHA-256 hashes for all 28.7M rows, triggering full re-upsert on next load
- **15+ display references** — C# services project names into DTOs for UI (AwardService, ExpiringContractService, PricingService, etc.). Dropping columns requires JOIN to `federal_organization` everywhere
- **4 query filters** — LIKE searches in AwardService, ExpiringContractService, PricingService still need text columns for user-facing agency name search
- **UI components** — AwardDetailPage.tsx renders funding_agency_name directly
- **Views** — 50_expiring_contracts.sql, competitive intel views SELECT agency names

**Recommendation:** Keep columns as denormalized display-convenience fields. Gradually migrate filters to CGAC codes (items #1 above). Column removal can be revisited after all query filters are CGAC-based and a hash migration strategy is planned.

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
| `fed_prospector/etl/opportunity_loader.py` | Parse segments 1+2 from `fullParentPathCode` during load, add to hash fields + upsert columns |
| `fed_prospector/etl/usaspending_loader.py` | Post-load UPDATE to set `awarding_agency_cgac`, `funding_agency_cgac` |
| `fed_prospector/cli/maintain.py` | Add `normalize-agencies` command |
| `fed_prospector/cli/report.py` | Add `unresolved-agencies` command |
