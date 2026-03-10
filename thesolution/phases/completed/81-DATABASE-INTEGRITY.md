# Phase 81: Database Integrity & Schema Fixes

**Status**: COMPLETE
**Priority**: HIGH
**Depends on**: None
**Overlaps**: Phase 200 (Database Normalization) addresses larger structural changes. Phase 81 covers correctness issues that should be fixed independently.

## Overview
Comprehensive review identified missing foreign key constraints, type mismatches on key fields, collation inconsistency, and schema drift between Python DDL and EF Core models. These issues risk data integrity and query correctness.

## Issues

### CRITICAL — Missing Foreign Key Constraints

#### 81-1: entity.primary_naics → ref_naics_code
- **File**: `fed_prospector/db/schema/tables/20_entity.sql` line 45
- **Issue**: No FK constraint. Allows orphaned NAICS codes.
- **Fix**: `ALTER TABLE entity ADD CONSTRAINT fk_entity_naics_primary FOREIGN KEY (primary_naics) REFERENCES ref_naics_code(naics_code);`

#### 81-2: entity.entity_structure_code → ref_entity_structure
- **File**: `fed_prospector/db/schema/tables/20_entity.sql` line 39
- **Issue**: No FK constraint. Views (v_competitor_analysis) assume valid codes.
- **Fix**: `ALTER TABLE entity ADD CONSTRAINT fk_entity_structure FOREIGN KEY (entity_structure_code) REFERENCES ref_entity_structure(structure_code);`

#### 81-3: entity_history.uei_sam and entity_history.load_id — No FKs
- **File**: `fed_prospector/db/schema/tables/20_entity.sql` lines 165, 170
- **Issue**: History records can reference non-existent entities or loads.
- **Fix**: Add FKs with ON DELETE CASCADE. Add `INDEX idx_eh_load (load_id)`.

#### 81-4: opportunity_history.notice_id and opportunity_history.load_id — No FKs
- **File**: `fed_prospector/db/schema/tables/30_opportunity.sql` lines 67, 72
- **Issue**: Orphaned history records possible.
- **Fix**: Add FKs with ON DELETE CASCADE. Add `INDEX idx_oh_load (load_id)`.

#### 81-5: prospect_team_member.uei_sam → entity — No FK
- **File**: `fed_prospector/db/schema/tables/60_prospecting.sql` line 117
- **Issue**: Team members can reference non-existent entities.
- **Fix**: Add FK with ON DELETE SET NULL.

#### 81-6: data_load_request.requested_by and load_id — No FKs
- **File**: `fed_prospector/db/schema/tables/55_data_load_request.sql` lines 12, 16
- **Issue**: Orphaned load requests possible.
- **Fix**: Add FKs with ON DELETE SET NULL.

---

### HIGH

#### 81-7: UEI VARCHAR Length Inconsistency
- **Files**:
  - `20_entity.sql:8` — VARCHAR(12)
  - `30_opportunity.sql:29` (incumbent_uei) — VARCHAR(13)
  - `60_prospecting.sql:19` (organization.uei_sam) — VARCHAR(13)
- **Issue**: Type mismatch for JOINs. SAM UEIs are exactly 12 characters.
- **Fix**: Standardize all UEI fields to VARCHAR(12). Verify no data exceeds 12 chars before altering.

#### 81-8: Collation Inconsistency in usaspending_load_checkpoint
- **File**: `fed_prospector/db/schema/tables/70_usaspending.sql` line 108
- **Issue**: Uses `utf8mb4_0900_ai_ci` while all other tables use `utf8mb4_unicode_ci`.
- **Fix**: `ALTER TABLE usaspending_load_checkpoint CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`

#### 81-9: Missing EF Core Model Properties (Schema Drift)
- **Files**:
  - `Entity.cs` missing `eft_indicator` (DDL: `20_entity.sql` line 52)
  - `FpdsContract.cs` missing `funding_subtier_code` and `funding_subtier_name` (DDL: `40_federal.sql` lines 43-44)
- **Issue**: ETL-loaded data inaccessible via API. Silent data loss on reads.
- **Fix**: Add properties with `[Column(...)]` attributes to C# models.

#### 81-10: Soft-Delete Strategy Inconsistency
- **File**: `fed_prospector/db/schema/tables/70_usaspending.sql` line 59
- **Issue**: Only usaspending_award uses `deleted_at DATETIME NULL`. Other tables use `is_active` flags or hard deletes.
- **Fix**: Document the strategy. Add comment to DDL explaining why this table differs.

---

### MEDIUM

#### 81-11: Missing Indexes on History Table FK Columns
- **Files**: `20_entity.sql`, `30_opportunity.sql`
- **Issue**: If FKs added (81-3, 81-4), corresponding indexes needed for DELETE cascade performance.
- **Fix**: Add indexes when adding FKs.

#### 81-12: VARCHAR Length Efficiency
- **Files**: Multiple schema files
- **Issue**: Some VARCHAR lengths excessive (solicitation_number VARCHAR(100), typically 20-50 chars). Minor storage waste.
- **Fix**: Review and right-size based on actual data distribution. Low priority.

#### 81-13: prospect_note.note_text TEXT NOT NULL
- **File**: `fed_prospector/db/schema/tables/60_prospecting.sql` line 106
- **Issue**: TEXT with NOT NULL is unusual. Consider VARCHAR(5000) NOT NULL or allow NULL.
- **Fix**: Change to `MEDIUMTEXT NOT NULL` or validate in application layer.

#### 81-14: SAM Awards number_of_offers No Type Validation
- **Files**: `40_federal.sql` line 63 (INT), `awards_loader.py` line 361
- **Issue**: Loader assigns raw API value without int parsing. If API returns string, MySQL silently truncates.
- **Fix**: Add `int()` conversion in awards_loader with error handling.

---

### LOW

#### 81-15: Missing NOT NULL on Business Logic Columns
- **Files**: Various (proposal_status, base_type)
- **Issue**: NULL allowed where business logic assumes a value. Views may produce unexpected NULLs.
- **Fix**: Add NOT NULL DEFAULT where appropriate after reviewing data.

#### 81-16: CHAR(1) vs VARCHAR(1) for Boolean Flags
- **Files**: `10_reference.sql` line 14 (CHAR), `90_web_api.sql` line 161 (VARCHAR)
- **Issue**: Inconsistent storage for Y/N flags.
- **Fix**: Standardize on CHAR(1) or TINYINT(1).

#### 81-17: Prospect CreatedAt/UpdatedAt Nullable in EF Model
- **File**: `api/src/FedProspector.Core/Models/Prospect.cs` lines 71-73
- **Issue**: Both `DateTime?` but schema defines NOT NULL with DEFAULT CURRENT_TIMESTAMP.
- **Fix**: Change to `DateTime` (non-nullable) in C# model.

---

## Review Decisions

A thorough pre-implementation review was conducted analyzing ETL loader patterns, existing FK constraint handling, and schema drift accuracy before any changes were made.

### FK Constraints — INTENTIONALLY SKIPPED

All FK creation items (81-1 through 81-6, 81-11) are **intentionally skipped**. Rationale:

1. **ETL loaders use TRUNCATE + LOAD DATA INFILE**: The BulkLoader (bulk_loader.py) TRUNCATEs entity and child tables during full loads with `SET FOREIGN_KEY_CHECKS = 0`. Adding FKs would not provide runtime protection during the primary data path.

2. **History table CASCADE would destroy audit data**: Items 81-3 and 81-4 proposed `ON DELETE CASCADE` on entity_history and opportunity_history. These are append-only audit tables — cascading deletes would silently erase change history when parent records are replaced during bulk loads.

3. **Reference table TRUNCATE is unprotected**: reference_loader.py TRUNCATEs ref_entity_structure (line 646) without FK_CHECKS wrapper. Adding an FK from entity.entity_structure_code would require modifying every reference loader TRUNCATE pattern.

4. **Load order is currently arbitrary**: CLI load commands run independently. Adding cross-table FKs would introduce hard ordering dependencies that the current batch system doesn't enforce.

5. **Risk/reward unfavorable**: The 29 existing FKs protect web API tables (prospects, proposals, sessions) where referential integrity matters for user-facing operations. ETL data tables are bulk-loaded from authoritative government sources — orphan prevention is better handled at the ETL validation layer.

### Items SKIPPED as invalid or low-value

| Item | Decision | Reason |
|------|----------|--------|
| 81-7: UEI VARCHAR(13→12) | SKIP | All real data is exactly 12 chars. VARCHAR(13) causes zero JOIN issues. No actual risk. |
| 81-8: Collation inconsistency | SKIP — FALSE ALARM | Live database already uses `utf8mb4_0900_ai_ci` uniformly across all 63 tables. The plan was outdated. Applying the "fix" would introduce a mismatch. |
| 81-12: VARCHAR length efficiency | SKIP | Negligible storage impact, high risk of breaking ETL if lengths are too tight. |
| 81-13: prospect_note TEXT NOT NULL | SKIP | TEXT NOT NULL is valid MySQL. No issue. |
| 81-15: Missing NOT NULL | SKIP | Government API data has many legitimately NULL fields. Adding NOT NULL risks rejecting valid records. |
| 81-16: CHAR(1) vs VARCHAR(1) | SKIP | Cosmetic. No functional impact. |

### Items IMPLEMENTED

| Item | What | Status |
|------|------|--------|
| 81-9 | Add missing EF Core model properties (eft_indicator, funding_subtier_code/name) + DTOs | DONE |
| 81-10 | Document soft-delete strategy in usaspending DDL | DONE |
| 81-14 | Add int() conversion for number_of_offers in awards_loader | DONE |
| 81-17 | Fix Prospect.cs CreatedAt/UpdatedAt to non-nullable DateTime | DONE |

## Migration Strategy

Scope reduced after pre-implementation review. No database migration needed — changes are limited to:
1. C# EF Core model property additions (no schema change, columns already exist)
2. Python ETL validation improvement (code-only)
3. Documentation updates (DDL comments)

## Verification
1. C# API project builds successfully with new model properties
2. Python pytest suite passes with awards_loader change
3. No new EF Core migration needed (columns already exist in DB)
4. DTOs expose new fields in API responses
