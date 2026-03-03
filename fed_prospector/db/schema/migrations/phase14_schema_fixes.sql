-- Phase 14.14: Database Schema Fixes
-- Date: 2026-03-03
-- Description: Fixes missing indexes, broken multi-tenant unique constraints, DDL sync gaps,
--              and several data integrity issues found during code review and schema audit.
-- Run: /d/mysql/bin/mysql.exe -u fed_app -pfed_app_2026 fed_contracts < fed_prospector/db/schema/migrations/phase14_schema_fixes.sql
-- All statements use IF NOT EXISTS / IF EXISTS where supported, and MODIFY COLUMN is idempotent.

USE fed_contracts;

-- ============================================================
-- Fix 11: ref_psc_code — start_date NOT NULL
-- PRIMARY KEY (psc_code, start_date) with a nullable start_date is semantically
-- undefined in MySQL. Make it explicitly NOT NULL with a safe default.
-- ============================================================
ALTER TABLE ref_psc_code
    MODIFY COLUMN start_date DATE NOT NULL DEFAULT '1970-01-01';

-- ============================================================
-- Fix 3: entity_disaster_response — missing index on uei_sam
-- entity_loader.py runs DELETE FROM entity_disaster_response WHERE uei_sam = %s
-- on every entity update. Without an index this is a full table scan.
-- All other entity child tables already have this index.
-- ============================================================
CREATE INDEX idx_edr_uei ON entity_disaster_response (uei_sam);

-- ============================================================
-- Fix 2: opportunity — add 7 missing Phase 9 columns
-- phase9_alter_tables.sql added these to existing installs but 30_opportunity.sql
-- was never updated, so fresh builds are missing them. ADD COLUMN IF NOT EXISTS
-- makes this idempotent against already-migrated installs.
-- ============================================================
ALTER TABLE opportunity
    ADD COLUMN IF NOT EXISTS period_of_performance_start DATE NULL,
    ADD COLUMN IF NOT EXISTS period_of_performance_end DATE NULL,
    ADD COLUMN IF NOT EXISTS security_clearance_required TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS incumbent_uei VARCHAR(12) NULL,
    ADD COLUMN IF NOT EXISTS incumbent_name VARCHAR(200) NULL,
    ADD COLUMN IF NOT EXISTS contract_vehicle_type VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS estimated_contract_value DECIMAL(15,2) NULL;

-- ============================================================
-- Fix 7: sam_exclusion — add UNIQUE constraint on natural business key
-- Without a unique key, duplicate rows accumulate silently when the loader
-- crashes between delete and re-insert. NULL uei values are treated as
-- distinct by MySQL UNIQUE keys — document this as a known data quality
-- limitation for entity-name-only exclusions.
-- ============================================================
ALTER TABLE sam_exclusion
    ADD UNIQUE KEY uk_excl_key (uei, exclusion_type, activation_date);

-- ============================================================
-- Fix 12: sam_exclusion — fix silently truncated entity_name index
-- entity_name VARCHAR(500) with utf8mb4 (4 bytes/char) exceeds the 767-byte
-- InnoDB prefix limit. MySQL silently truncates to ~191 chars. Replace with
-- an explicit 100-char prefix index to avoid silent false negatives.
-- ============================================================
DROP INDEX idx_excl_entity_name ON sam_exclusion;
CREATE INDEX idx_excl_entity_name ON sam_exclusion (entity_name(100));

-- ============================================================
-- Fix 6: fpds_contract — missing index on idv_piid
-- idv_piid links task orders to their parent IDV contract. Queries finding
-- all task orders under an IDV do full table scans without this index.
-- Use a prefix index since idv_piid is VARCHAR(100).
-- ============================================================
CREATE INDEX idx_fpds_idv_piid ON fpds_contract (idv_piid(50));

-- ============================================================
-- Fix 5: fpds_contract — missing index on ultimate_completion_date
-- Re-compete prediction queries filter by ultimate_completion_date.
-- idx_fpds_completion exists for completion_date but not this column.
-- ============================================================
CREATE INDEX idx_fpds_ultimate_completion ON fpds_contract (ultimate_completion_date);

-- ============================================================
-- Fix 1: prospect — UNIQUE KEY breaks multi-tenancy
-- uk_prospect_notice (notice_id) prevents two orgs from tracking the same
-- notice. Change to scope uniqueness to the organization.
-- ============================================================
ALTER TABLE prospect DROP INDEX uk_prospect_notice;
ALTER TABLE prospect ADD UNIQUE KEY uk_prospect_notice (organization_id, notice_id);

-- ============================================================
-- Fix 8: usaspending_award — record_hash type inconsistency
-- All tables use CHAR(64) for SHA-256 hashes. usaspending_award alone used
-- VARCHAR(64), which has unnecessary length overhead.
-- ============================================================
ALTER TABLE usaspending_award
    MODIFY COLUMN record_hash CHAR(64) NULL;

-- ============================================================
-- Fix 4: usaspending_award — missing index on last_modified_date
-- Incremental loads filter by modification date; without this index those
-- queries perform full table scans. idx_usa_dates covers (start_date, end_date)
-- but not last_modified_date.
-- ============================================================
CREATE INDEX idx_usa_modified ON usaspending_award (last_modified_date);

-- ============================================================
-- Fix 10: usaspending_transaction — modification_number NOT NULL
-- UNIQUE KEY uk_txn_dedup (award_id, modification_number, action_date) includes
-- nullable modification_number. MySQL treats two NULLs as distinct in a UNIQUE
-- KEY, so INSERT IGNORE cannot deduplicate NULL-modification_number rows.
-- Make the column NOT NULL with empty-string default to close this gap.
-- ============================================================
ALTER TABLE usaspending_transaction
    MODIFY COLUMN modification_number VARCHAR(20) NOT NULL DEFAULT '';
