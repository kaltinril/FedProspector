-- migrations/133b_affiliation_size_rollup_columns.sql
-- Phase 133 Task 6: SBA Affiliation Size Roll-Up (13 CFR 121.103).
--
-- Adds four nullable columns to organization_entity to support affiliation-aware
-- size determination. organization_entity is EF Core-owned; this raw-SQL migration
-- mirrors the EF migration (AddAffiliationSizeRollupColumns) so prod can be ALTERed
-- by hand. Keep this file, the EF migration, and the DDL
-- (fed_prospector/db/schema/tables/90_web_api.sql) in sync.
--
--   affiliate_annual_revenue  DECIMAL(18,2) NULL  -- owner-entered affiliate receipts (raw USD); NULL = gap
--   affiliate_employee_count  INT NULL            -- owner-entered affiliate headcount;     NULL = gap
--   mpa_approved              CHAR(1) NOT NULL DEFAULT 'N'  -- 'Y' = approved mentor-protégé JV (mentor's size excluded)
--   mpa_effective_date        DATE NULL           -- effective date of the approved MPA (optional)
--
-- Affiliate financials are entered manually via the OrgEntitiesTab link form;
-- SAM.gov entity_* tables carry no revenue/headcount. The org's OWN figures stay
-- on organization.annual_revenue / organization.employee_count.
--
-- IDEMPOTENT: guarded by information_schema.COLUMNS checks inside a stored proc
-- (MySQL lacks ADD COLUMN IF NOT EXISTS). Safe to re-run -- already-present columns
-- are skipped. Same pattern as 133_solicitation_number_normalized.sql.
--
-- APPLY (per CLAUDE.md rule 9 -- must reach BOTH dev and prod; back up first per
-- the Phase 134 runbook). Run from this dev box via E:\mysql\bin:
--   Prod:
--     & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133b_affiliation_size_rollup_columns.sql"
--   Dev (localhost):
--     & "E:\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133b_affiliation_size_rollup_columns.sql"
-- ============================================================

USE fed_contracts;

DROP PROCEDURE IF EXISTS _add_affiliation_size_rollup_columns;
DELIMITER //
CREATE PROCEDURE _add_affiliation_size_rollup_columns()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'organization_entity'
          AND COLUMN_NAME = 'affiliate_annual_revenue'
    ) THEN
        ALTER TABLE organization_entity
            ADD COLUMN affiliate_annual_revenue DECIMAL(18,2) NULL
            COMMENT 'Phase 133 Task 6: owner-entered affiliate annual receipts (raw USD); NULL = gap'
            AFTER notes;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'organization_entity'
          AND COLUMN_NAME = 'affiliate_employee_count'
    ) THEN
        ALTER TABLE organization_entity
            ADD COLUMN affiliate_employee_count INT NULL
            COMMENT 'Phase 133 Task 6: owner-entered affiliate employee count; NULL = gap'
            AFTER affiliate_annual_revenue;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'organization_entity'
          AND COLUMN_NAME = 'mpa_approved'
    ) THEN
        ALTER TABLE organization_entity
            ADD COLUMN mpa_approved CHAR(1) NOT NULL DEFAULT 'N'
            COMMENT 'Phase 133 Task 6: Y = approved mentor-protege JV (mentor size excluded from roll-up)'
            AFTER affiliate_employee_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'organization_entity'
          AND COLUMN_NAME = 'mpa_effective_date'
    ) THEN
        ALTER TABLE organization_entity
            ADD COLUMN mpa_effective_date DATE NULL
            COMMENT 'Phase 133 Task 6: effective date of the approved mentor-protege agreement (optional)'
            AFTER mpa_approved;
    END IF;
END //
DELIMITER ;
CALL _add_affiliation_size_rollup_columns();
DROP PROCEDURE _add_affiliation_size_rollup_columns;
