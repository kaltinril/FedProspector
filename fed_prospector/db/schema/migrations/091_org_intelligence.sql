-- Migration 091: Organization Intelligence & Auto-Prospects (Phase 91)
-- Creates organization_entity table, adds prospect.source, adds saved_search auto-prospect columns.

-- 1. organization_entity table
CREATE TABLE IF NOT EXISTS organization_entity (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    uei_sam         VARCHAR(12) NOT NULL,
    relationship    VARCHAR(20) NOT NULL,
    is_active       CHAR(1) NOT NULL DEFAULT 'Y',
    added_by        INT NULL,
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_entity (organization_id, uei_sam, relationship),
    CONSTRAINT fk_oe_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    CONSTRAINT fk_oe_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam),
    CONSTRAINT fk_oe_user FOREIGN KEY (added_by) REFERENCES app_user(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. prospect.source column (idempotent via procedure)
DROP PROCEDURE IF EXISTS _add_prospect_source;
DELIMITER //
CREATE PROCEDURE _add_prospect_source()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'prospect' AND COLUMN_NAME = 'source'
    ) THEN
        ALTER TABLE prospect ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'MANUAL' AFTER organization_id;
    END IF;
END //
DELIMITER ;
CALL _add_prospect_source();
DROP PROCEDURE _add_prospect_source;

-- 3. saved_search auto-prospect columns (idempotent via procedure)
DROP PROCEDURE IF EXISTS _add_ss_auto_cols;
DELIMITER //
CREATE PROCEDURE _add_ss_auto_cols()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'saved_search' AND COLUMN_NAME = 'auto_prospect_enabled'
    ) THEN
        ALTER TABLE saved_search
            ADD COLUMN auto_prospect_enabled CHAR(1) NOT NULL DEFAULT 'N',
            ADD COLUMN min_pwin_score DECIMAL(5,2) NULL DEFAULT 30.0,
            ADD COLUMN auto_assign_to INT NULL,
            ADD COLUMN last_auto_run_at DATETIME NULL,
            ADD COLUMN last_auto_created INT NULL DEFAULT 0;
    END IF;
END //
DELIMITER ;
CALL _add_ss_auto_cols();
DROP PROCEDURE _add_ss_auto_cols;

-- 4. FK for saved_search.auto_assign_to (idempotent)
SET @fk_exists = (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_NAME = 'fk_ss_auto_user' AND TABLE_NAME = 'saved_search' AND TABLE_SCHEMA = 'fed_contracts');
SET @sql = IF(@fk_exists = 0,
    'ALTER TABLE saved_search ADD CONSTRAINT fk_ss_auto_user FOREIGN KEY (auto_assign_to) REFERENCES app_user(user_id)',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
