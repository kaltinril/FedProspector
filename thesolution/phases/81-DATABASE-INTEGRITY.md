# Phase 81: Database Integrity & Schema Fixes

**Status**: PLANNED
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

## Migration Strategy
1. Create migration file `fed_prospector/db/schema/migrations/phase81_integrity.sql`
2. Run in transaction: ADD FKs → ADD indexes → ALTER column types
3. Verify no orphaned records before adding FKs: `SELECT ... LEFT JOIN ... WHERE parent.id IS NULL`
4. Update DDL source files to include new constraints
5. Update EF Core models in C# project

## Verification
1. All FK constraints pass: `SELECT * FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_TYPE='FOREIGN KEY' AND TABLE_SCHEMA='fed_contracts'`
2. No orphaned records in history tables
3. UEI fields all VARCHAR(12)
4. Collation uniform: `SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='fed_contracts'`
5. EF Core model properties match DDL columns
6. All existing tests pass (Python pytest + C# xUnit)
