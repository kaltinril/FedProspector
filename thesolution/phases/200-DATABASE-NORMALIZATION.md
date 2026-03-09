# Phase 200: Database Schema Normalization

**Status**: PLANNED
**Priority**: Medium
**Dependencies**: None (can run independently of feature phases)
**Impact**: All ETL loaders, all views, C# EF Core DbContext, UI queries

---

## Objective

Reduce data bloat, eliminate redundancy, and normalize the database schema. The current 42-table design has grown organically with significant denormalization — entity names, agency names, code descriptions, and location data are duplicated across many tables instead of using FK relationships to existing reference and master tables.

---

## Pre-Phase: Data Profiling (REQUIRED before any schema changes)

Before making any normalization changes, run column-level statistics on every table to understand actual data distributions, NULL rates, cardinality, and value consistency. This prevents breaking assumptions about data that looks normalized but isn't.

### Profiling checklist

- [ ] **Row counts** per table (understand scale)
- [ ] **NULL rate** per column (which "required" fields are actually sparse?)
- [ ] **Distinct value counts** per column (cardinality — identifies lookup candidates)
- [ ] **Min/max/avg length** for VARCHAR columns (right-size column types)
- [ ] **Value frequency distributions** for code columns (do values match reference tables?)
- [ ] **Orphan check**: Values in data tables that don't exist in corresponding ref_* tables
- [ ] **Cross-table consistency**: Does `fpds_contract.vendor_name` match `entity.legal_business_name` for the same UEI? How often do they diverge?
- [ ] **UEI format audit**: Are UEIs consistently 12 chars? Any 11-char or padded variants?
- [ ] **Agency name consistency**: Do `awarding_agency_name` values in usaspending match `fh_org_name` in federal_organization?
- [ ] **Storage impact estimate**: Calculate bytes saved per normalization change × row count

### Profiling deliverable

A Python script (`fed_prospector/db/profile_schema.py`) that generates a report covering all the above, outputting to CSV and/or console summary. This script becomes a reusable tool for future schema work.

---

## Normalization Opportunities

### 1. Denormalized Entity/Vendor Names (HIGH — 20+ columns, 6 tables)

**Problem**: Entity names are stored as raw strings in every table that references a vendor/recipient/contractor, even though the `entity` master table (keyed on `uei_sam`) already holds canonical names.

| Table | Redundant Columns | Should Reference |
|-------|-------------------|-----------------|
| `fpds_contract` | `vendor_name`, `vendor_duns` | `entity` via `vendor_uei` |
| `usaspending_award` | `recipient_name`, `recipient_parent_name`, `recipient_parent_uei` | `entity` via `recipient_uei` |
| `opportunity` | `awardee_name`, `awardee_cage_code`, `awardee_city`, `awardee_state` | `entity` via `awardee_uei` |
| `sam_subaward` | `prime_name`, `sub_name` | `entity` via `prime_uei`, `sub_uei` |
| `sam_exclusion` | `entity_name`, `cage_code` | `entity` via `uei` |
| `gsa_labor_rate` | `contractor_name` | `entity` (needs UEI column added) |

**Solution**: Keep UEI columns as FKs, drop name/address columns. Create views to reconstruct the denormalized shape for backward compatibility.

**Consideration**: Some entities in FPDS/USASpending may not exist in our `entity` table (we only load entities we care about from SAM.gov). Need a strategy for "unknown" entities — either load them on demand or keep a lightweight `entity_stub` table.

### 2. Denormalized Agency/Organization Names (HIGH — 15+ columns, 5 tables)

**Problem**: Agency names stored as raw strings everywhere. The `federal_organization` table already has the full hierarchy with `fh_org_id`, `agency_code`, and `parent_org_id`.

| Table | Redundant Columns | Should Reference |
|-------|-------------------|-----------------|
| `opportunity` | `department_name`, `sub_tier`, `office`, `full_parent_path_name`, `full_parent_path_code` | `federal_organization` via `fh_org_id` (need 1-3 FK columns) |
| `fpds_contract` | `agency_name`, `contracting_office_name`, `funding_agency_name`, `funding_subtier_name` | `federal_organization` via `agency_id` → `fh_org_id` mapping |
| `usaspending_award` | `awarding_agency_name`, `awarding_sub_agency_name`, `funding_agency_name` | `federal_organization` via new FK columns |
| `sam_subaward` | `prime_agency_name` | `federal_organization` via `prime_agency_id` |
| `sam_exclusion` | `excluding_agency_name` | `federal_organization` via `excluding_agency_code` |

**Solution**: Add `fh_org_id` INT FK columns (awarding, funding, contracting office as needed). Drop name strings. Create views for backward compatibility.

**Consideration**: `federal_organization` needs a reliable mapping from CGAC codes, FPDS agency codes, and subtier codes to `fh_org_id`. May need an `agency_code_xref` mapping table since different data sources use different code formats.

### 3. Code+Description Pairs (MEDIUM — 10+ instances)

**Problem**: Tables store both a code and its human-readable description, when the description is already available in a reference table.

| Table | Code Column | Redundant Description Column | Reference Table |
|-------|------------|------------------------------|-----------------|
| `opportunity` | `set_aside_code` | `set_aside_description` | `ref_set_aside_type` |
| `usaspending_award` | `naics_code` | `naics_description` | `ref_naics_code` |
| `usaspending_award` | `type_of_set_aside` | `type_of_set_aside_description` | `ref_set_aside_type` |
| `entity_sba_certification` | `sba_type_code` | `sba_type_desc` | `ref_sba_type` |
| `fpds_contract` | `far1102_exception_code` | `far1102_exception_name` | *needs new ref table* |

**Solution**: Drop description columns, JOIN to reference tables in views/queries. Create missing reference tables first.

### 4. Location Data Inconsistency (MEDIUM — 35+ columns, 8 tables)

**Problem**: Place of performance (PoP) fields repeated across tables with inconsistent types and no FK enforcement.

| Table | Location Columns | Type Inconsistencies |
|-------|-----------------|---------------------|
| `opportunity` | `pop_state`(6), `pop_country`(3), `pop_zip`(10), `pop_city`(100) | — |
| `fpds_contract` | `pop_state`(6), `pop_country`(3), `pop_zip`(10) | Missing `pop_city` |
| `usaspending_award` | `pop_state`(6), `pop_country`(3), `pop_zip`(10), `pop_city`(100) | — |
| `sam_subaward` | `pop_state`(**100**), `pop_country`(3), `pop_zip`(10) | State is VARCHAR(100) vs 6 elsewhere |
| `entity_address` | `state_or_province`(**55**), `country_code`(3), `zip_code`(**50**) | Different naming, oversized types |
| `entity_disaster_response` | `state_code`(10), `state_name`(60), `county_code`(5), `county_name`(100) | Stores both code AND name |
| `organization` | `state_code`(2), `country_code`(3), `zip_code`(10) | — |

**Solution options**:
- **Option A** (minimal): Standardize column names/types, add FK constraints to ref_state_code and ref_country_code. Keep PoP columns inline since they're cheap and heavily queried.
- **Option B** (full normalization): Create a `location` table, FK from all tables. Adds JOINs to every query.
- **Recommendation**: Option A — PoP is 3-4 small columns, the JOIN cost isn't worth it. Just standardize and add FKs.

### 5. Missing Reference Tables (LOW-MEDIUM — 9 tables needed)

These string columns have low cardinality and should be lookup tables:

| New Reference Table | Source Columns | Tables Affected |
|--------------------|---------------|-----------------|
| `ref_award_type` | `award_type` | `usaspending_award` |
| `ref_far1102_exception` | `far1102_exception_code`, `far1102_exception_name` | `fpds_contract` |
| `ref_contract_type` | `type_of_contract_pricing` | `fpds_contract` |
| `ref_extent_competed` | `extent_competed` | `fpds_contract` |
| `ref_exclusion_type` | `exclusion_type`, `exclusion_program`, `termination_type` | `sam_exclusion` |
| `ref_prospect_outcome` | `outcome` | `prospect` |
| `ref_business_size` | `business_size` | `gsa_labor_rate` |
| `ref_security_clearance` | `security_clearance` | `gsa_labor_rate` |
| `ref_gsa_schedule` | `schedule` | `gsa_labor_rate` |

### 6. Missing FK Constraints (HIGH — 25+ locations)

Even without removing denormalized columns, adding FK constraints improves data integrity:

| FK Source | FK Target | Count of Missing |
|-----------|-----------|-----------------|
| `*.naics_code` | `ref_naics_code` | 8+ tables |
| `*.psc_code` | `ref_psc_code` | 4+ tables |
| `*.set_aside_*` | `ref_set_aside_type` | 4+ tables |
| `*.country_code` / `pop_country` | `ref_country_code` | 12+ columns |
| `*.state_code` / `pop_state` | `ref_state_code` | 12+ columns |
| `*.vendor_uei` / `recipient_uei` | `entity` | 5+ tables |
| `federal_organization.parent_org_id` | `federal_organization` (self) | 1 |

**Note**: Hard FKs on ETL tables may slow bulk loads. Consider: (a) add FKs but disable during LOAD DATA INFILE batches, or (b) use soft FKs (documented, validated in ETL code, not enforced by DB engine).

### 7. Oversized Column Types (LOW)

| Table | Column | Current Type | Suggested Type |
|-------|--------|-------------|---------------|
| `ref_psc_code` | `parent_psc_code` | VARCHAR(200) | VARCHAR(10) |
| `entity_address` | `zip_code` | VARCHAR(50) | VARCHAR(10) |
| `sam_subaward` | `pop_state` | VARCHAR(100) | VARCHAR(6) |
| `sam_subaward` | `prime_name`, `sub_name` | VARCHAR(500) | VARCHAR(200) |
| `sam_exclusion` | `entity_name` | VARCHAR(500) | VARCHAR(200) |

### 8. Table Decomposition Candidates (MEDIUM-HIGH)

Some of the larger tables are doing too much — they contain logically separate groups of columns that should be broken into related child tables, similar to how `entity` was properly decomposed into `entity` + `entity_address` + `entity_naics` + etc.

#### `usaspending_award` — prime candidate for decomposition

Current: ~27 columns in a single flat table. Logical groupings:

| Proposed Table | Columns to Extract | Rationale |
|---------------|-------------------|-----------|
| `usaspending_award` (slimmed) | `generated_unique_award_id`, `piid`, `fain`, `uri`, `award_type`, `total_obligation`, `base_and_all_options_value`, `start_date`, `end_date`, `fiscal_year`, `solicitation_identifier` | Core award identity and financials |
| `usaspending_award_recipient` | `recipient_uei` (FK→entity), `recipient_parent_uei` (FK→entity) | Recipient info — or just FK to entity directly on parent table |
| `usaspending_award_agency` | `awarding_fh_org_id` (FK→federal_organization), `awarding_sub_fh_org_id`, `funding_fh_org_id` | Agency relationships — replaces 3 name strings with 3 FK ints |
| `usaspending_award_classification` | `naics_code` (FK), `psc_code` (FK), `type_of_set_aside` (FK) | Classification codes — or keep inline if always 1:1 |
| `usaspending_award_location` | `pop_state`, `pop_country`, `pop_zip`, `pop_city` | Place of performance — or keep inline (see Location discussion) |

#### `fpds_contract` — similar decomposition opportunity

Current: ~40+ columns. Logical groupings:

| Proposed Table | Columns to Extract | Rationale |
|---------------|-------------------|-----------|
| `fpds_contract` (slimmed) | Core contract identity: `contract_id`, `modification_number`, `piid`, `idv_piid`, dates, amounts | Contract core |
| `fpds_contract_vendor` | `vendor_uei` (FK→entity) | Replaces vendor_name, vendor_duns with single FK |
| `fpds_contract_agency` | `awarding_fh_org_id`, `contracting_office_fh_org_id`, `funding_fh_org_id`, `funding_subtier_fh_org_id` | Replaces 8 string columns with 4 FK ints |
| `fpds_contract_classification` | `naics_code`, `psc_code`, `set_aside_type`, `type_of_contract_pricing`, `extent_competed` | Classification/competition codes |

#### `opportunity` — moderate decomposition

Current: ~50+ columns. Key extraction candidates:

| Proposed Table | Columns to Extract | Rationale |
|---------------|-------------------|-----------|
| `opportunity_agency` | `department_fh_org_id`, `subtier_fh_org_id`, `office_fh_org_id` | Replaces 3 name strings + 2 path strings |
| `opportunity_award` | `awardee_uei` (FK→entity), `award_date`, `award_number`, `award_amount` | Award info only populated post-award |

#### `sam_exclusion` — person vs entity split

Current table mixes individual person exclusions (first_name, middle_name, last_name) with entity exclusions (entity_name, uei). These are fundamentally different record types sharing one table. Consider:

| Proposed Table | Purpose |
|---------------|---------|
| `sam_exclusion` (base) | Common fields: exclusion_type, program, dates, agency |
| `sam_exclusion_entity` | Entity-specific: uei (FK→entity), cage_code |
| `sam_exclusion_individual` | Person-specific: first_name, middle_name, last_name, prefix, suffix |

**Decomposition decision rule**: Break a table up when (a) column groups have different NULL patterns (e.g., award columns NULL until post-award), (b) column groups represent logically different entities, or (c) column groups would benefit from independent indexing. Do NOT decompose if it's always 1:1 and the JOIN cost outweighs the clarity gain — profiling data will inform this.

### 9. Dual Source of Truth Issues (LOW)

| Issue | Tables | Resolution |
|-------|--------|-----------|
| `entity.primary_naics` vs `entity_naics.is_primary='Y'` | entity, entity_naics | Drop `primary_naics` from entity, derive from child table |
| `prospect.proposal_status` vs `proposal.proposal_status` | prospect, proposal | Drop from prospect, always query proposal |

---

## Existing Infrastructure (What's Already Good)

These are strengths to build on, not replace:

- **11 reference tables** — well-designed, indexed, cover NAICS, PSC, SBA types, set-asides, business types, entity structures, countries, states, FIPS counties
- **Entity decomposition** — `entity` + 7 child tables (address, naics, psc, business_type, sba_cert, poc, disaster_response)
- **5 database views** — `v_target_opportunities`, `v_competitor_analysis`, `v_procurement_intelligence`, `v_incumbent_profile`, `v_expiring_contracts`
- **SHA-256 change detection** — all loaders use hash-based change detection
- **History tables** — `entity_history`, `opportunity_history` for audit trails
- **ETL infrastructure** — `etl_load_log`, `etl_load_error`, staging tables, load checkpoints

---

## Critical Architecture Decision: ETL Pipeline Strategy

Normalizing the schema fundamentally changes how data flows from vendor APIs into final tables. Today, loaders dump flat API responses almost directly into flat tables. With normalization, a single API response row may need to be split across 3-5 tables (core + recipient + agency + classification + location). This requires deciding on a pipeline architecture.

### Option A: Python Does All the Splitting (recommended)

The Python ETL loaders become smarter — they parse each API response, resolve FKs (look up `fh_org_id` for agency names, verify UEI exists in `entity`, etc.), and INSERT into the correct normalized tables directly.

```
Vendor API → stg_*_raw (JSON) → Python loader splits → final normalized tables
```

**Pros**: Single pipeline, no intermediate tables to maintain, Python already has the logic for staging → target. Keeps the "source of truth" logic in one place.
**Cons**: Loaders become more complex. FK resolution requires lookups during load (cached in memory). Bulk LOAD DATA INFILE harder to use when rows fan out to multiple tables.

**Mitigation**: Build a shared `NormalizationMixin` (similar to existing `StagingMixin`) that handles FK resolution with in-memory caches of reference tables. Each loader calls `resolve_agency(name) → fh_org_id`, `resolve_entity(uei) → verified bool`, etc.

### Option B: Intermediate Staging Tables

Keep current flat loaders writing to staging/intermediate tables, then use SQL transforms (stored procedures or Python-driven SQL) to split into normalized tables.

```
Vendor API → stg_*_raw (JSON) → flat intermediate tables → SQL transforms → final normalized tables
```

**Pros**: Loaders stay simple. SQL transforms are declarative and auditable. Can re-run transforms without re-fetching from APIs.
**Cons**: Three layers of tables (staging, intermediate, final) = more storage, more DDL to maintain, more points of failure. Essentially doubles the table count.

### Option C: Hybrid — Flat Source Tables + Normalized Final Tables

Keep current tables as-is (rename to `src_*`), treat them as the "source layer." Build normalized final tables alongside. Views or materialized queries bridge the gap.

```
Vendor API → src_usaspending_award (flat, as-is) → Python/SQL normalizer → award + award_agency + award_classification
```

**Pros**: Zero risk to existing loaders initially. Can normalize incrementally. Source tables serve as audit trail of what the API actually returned.
**Cons**: Doubles storage. Two copies of every record. Need a sync/refresh process. "Which table is the truth?" confusion.

### Recommendation

**Option A (Python splits)** is the cleanest long-term design. The loaders are already sophisticated (staging tables, change detection, hash-based upserts) — adding FK resolution is incremental complexity, not a rewrite. The key enabler is a `NormalizationMixin` that caches reference table lookups in memory at load start.

However, **the existing `stg_*_raw` tables already serve as the source/audit layer** — they store raw JSON from every API call. So we already have Option C's audit trail without needing to keep flat intermediate tables. The pipeline becomes:

```
Vendor API → stg_*_raw (raw JSON, audit trail)
           → Python parses + resolves FKs
           → INSERT into normalized final tables (award, award_agency, etc.)
```

If a load goes wrong, we can always re-process from `stg_*_raw` without re-fetching from the API.

### What This Means for Implementation Scope

This is a significant rework of the ETL layer. Each loader needs:

1. **FK resolution cache** — On load start, cache `federal_organization` (name → fh_org_id), `entity` (uei → exists), all ref_* tables (code → validated)
2. **Row fan-out logic** — One API row → multiple INSERT targets (e.g., one usaspending record becomes inserts into `usaspending_award` + agency FK columns + classification FK columns)
3. **Dependency ordering** — Must insert/verify parent records before child records (entity before award that references it)
4. **Error handling for missing FKs** — What if an agency name doesn't match any `federal_organization` entry? Options: skip, insert with NULL FK, create stub record, log to `etl_load_error`
5. **Re-processing capability** — Ability to re-run normalization from `stg_*_raw` if schema changes or FK resolution logic improves

The `StagingMixin` and `ChangeDetector` patterns already handle #3 and #5 partially. The new `NormalizationMixin` handles #1, #2, and #4.

---

## Implementation Strategy

### Sub-phase 200A: Data Profiling Script
- Build `profile_schema.py` — column stats, orphan checks, cross-table consistency
- Generate baseline report before any changes
- Identify data quality issues that would block FK enforcement

### Sub-phase 200B: Reference Table Expansion
- Create 9 new reference tables
- Populate from existing data (SELECT DISTINCT from source columns)
- Add FK constraints from source columns to new ref tables

### Sub-phase 200C: Agency Code Cross-Reference
- Build `agency_code_xref` mapping table (CGAC → fh_org_id, FPDS code → fh_org_id)
- Add `fh_org_id` FK columns to opportunity, fpds_contract, usaspending_award, sam_subaward, sam_exclusion
- Create migration script to populate FKs from existing string values

### Sub-phase 200D: Entity FK Consolidation
- Add/enforce `entity` FKs on fpds_contract, usaspending_award, sam_subaward
- Determine strategy for entities not in our SAM.gov load (stub table vs. nullable FK)
- Create backward-compatible views that reconstruct denormalized shape

### Sub-phase 200E: Column Cleanup
- Drop redundant description columns (after views are in place)
- Drop redundant name columns (after FK views are in place)
- Right-size oversized VARCHAR columns
- Resolve dual source of truth issues

### Sub-phase 200F: ETL Loader Updates
- Update all 7 loaders to write FK IDs instead of denormalized strings
- Update staging → target logic for new schema
- Add pre-insert validation against reference tables

### Sub-phase 200G: View & Query Migration
- Update all 5 existing views for new schema
- Update C# EF Core DbContext entity models
- Update any direct queries in API controllers/services

---

## Downstream Impact

| Component | Changes Required |
|-----------|-----------------|
| `fed_prospector/etl/` | All 7 loaders need column mapping updates |
| `fed_prospector/db/schema/views/` | All 5 views need JOIN updates |
| `fed_prospector/db/schema/tables/` | DDL changes for FK columns, dropped columns |
| `api/src/FedProspector.Infrastructure/Data/` | EF Core DbContext + entity models |
| `api/src/FedProspector.Infrastructure/Services/` | Any services with direct queries |
| `ui/src/types/api.ts` | DTO changes if API response shapes change |
| `fed_prospector/etl/change_detector.py` | Hash field lists need updating |

---

## Risk Mitigation

1. **Backward-compatible views first** — Create views that reconstruct the old denormalized shape before dropping columns. This lets the API layer migrate gradually.
2. **Profile before changing** — The pre-phase data profiling catches orphaned values, format mismatches, and NULLs that would violate new FK constraints.
3. **Soft FKs for ETL tables** — Consider not enforcing hard FKs on tables loaded via LOAD DATA INFILE to preserve bulk load performance. Validate in ETL code instead.
4. **Incremental sub-phases** — Each sub-phase is independently deployable. Can pause after any sub-phase without leaving the schema in a broken state.
