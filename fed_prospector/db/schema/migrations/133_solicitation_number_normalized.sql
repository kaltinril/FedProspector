-- migrations/133_solicitation_number_normalized.sql
-- Phase 132: Federal Identifier Dash Normalization.
--
-- Adds a SEPARATE normalized column alongside the original solicitation_number
-- on both `opportunity` and `fpds_contract`. The original column is preserved
-- verbatim (display value); the normalized column is the dashless/uppercased
-- canonical form used for matching and cross-reference (exact match).
--
-- Canonical rule (identical in SQL, Python, C#):
--   trim -> uppercase -> remove dashes
--   SQL: UPPER(REPLACE(TRIM(solicitation_number), '-', ''))
--   NULL/empty source -> NULL normalized.
--
-- Idempotent via information_schema guards; safe to re-run. The backfill only
-- touches rows where the normalized column is still NULL but the source has a
-- value, so re-running does not rewrite already-populated rows.
--
-- NOTE: the normalized column is DERIVED data. It is intentionally NOT part of
-- the SHA-256 change-detection hash inputs in the loaders, so existing rows do
-- not spuriously flip to "changed" on the next load.

USE fed_contracts;

DROP PROCEDURE IF EXISTS _add_solicitation_number_normalized;
DELIMITER //
CREATE PROCEDURE _add_solicitation_number_normalized()
BEGIN
    -- opportunity column (matches solicitation_number VARCHAR(100))
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'opportunity'
          AND COLUMN_NAME = 'solicitation_number_normalized'
    ) THEN
        ALTER TABLE opportunity
            ADD COLUMN solicitation_number_normalized VARCHAR(100) NULL
            COMMENT 'Phase 132: dashless/uppercased canonical form for matching; original preserved for display'
            AFTER solicitation_number;
    END IF;

    -- opportunity index
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'opportunity'
          AND INDEX_NAME = 'idx_opp_sol_norm'
    ) THEN
        ALTER TABLE opportunity
            ADD INDEX idx_opp_sol_norm (solicitation_number_normalized);
    END IF;

    -- fpds_contract column (matches solicitation_number VARCHAR(200))
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'fpds_contract'
          AND COLUMN_NAME = 'solicitation_number_normalized'
    ) THEN
        ALTER TABLE fpds_contract
            ADD COLUMN solicitation_number_normalized VARCHAR(200) NULL
            COMMENT 'Phase 132: dashless/uppercased canonical form for matching; original preserved for display'
            AFTER solicitation_number;
    END IF;

    -- fpds_contract index
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'fpds_contract'
          AND INDEX_NAME = 'idx_fpds_solicitation_norm'
    ) THEN
        ALTER TABLE fpds_contract
            ADD INDEX idx_fpds_solicitation_norm (solicitation_number_normalized);
    END IF;
END //
DELIMITER ;
CALL _add_solicitation_number_normalized();
DROP PROCEDURE _add_solicitation_number_normalized;

-- Backfill: populate the normalized column from the existing original value.
-- Re-run-safe: only rows not yet populated are touched.
UPDATE opportunity
   SET solicitation_number_normalized = UPPER(REPLACE(TRIM(solicitation_number), '-', ''))
 WHERE solicitation_number IS NOT NULL
   AND solicitation_number <> ''
   AND solicitation_number_normalized IS NULL;

UPDATE fpds_contract
   SET solicitation_number_normalized = UPPER(REPLACE(TRIM(solicitation_number), '-', ''))
 WHERE solicitation_number IS NOT NULL
   AND solicitation_number <> ''
   AND solicitation_number_normalized IS NULL;
