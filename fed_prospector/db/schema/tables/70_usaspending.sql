-- tables/70_usaspending.sql
-- USASpending.gov award data (2 tables) - Award summaries and transaction detail

USE fed_contracts;

CREATE TABLE IF NOT EXISTS usaspending_award (
    generated_unique_award_id VARCHAR(100) PRIMARY KEY,
    piid                     VARCHAR(50),
    fain                     VARCHAR(30),
    uri                      VARCHAR(70),
    award_type               VARCHAR(50),
    award_description        TEXT,

    -- Recipient (incumbent)
    recipient_name           VARCHAR(200),
    recipient_uei            VARCHAR(12),
    recipient_parent_name    VARCHAR(200),
    recipient_parent_uei     VARCHAR(12),

    -- Amounts
    total_obligation         DECIMAL(15,2),
    base_and_all_options_value DECIMAL(15,2),

    -- Dates
    start_date               DATE,
    end_date                 DATE,
    last_modified_date       DATE,

    -- Classification
    awarding_agency_name     VARCHAR(200),
    awarding_sub_agency_name VARCHAR(200),
    funding_agency_name      VARCHAR(200),
    awarding_agency_cgac     VARCHAR(10),
    funding_agency_cgac      VARCHAR(10),
    naics_code               VARCHAR(6),
    naics_description        VARCHAR(500),
    psc_code                 VARCHAR(10),

    -- Set-aside
    type_of_set_aside        VARCHAR(100),
    type_of_set_aside_description VARCHAR(200),

    -- Place of Performance
    pop_state                VARCHAR(6),  -- ISO 3166-2 subdivision codes (e.g., IN-MH)
    pop_country              VARCHAR(3),
    pop_zip                  VARCHAR(10),
    pop_city                 VARCHAR(100),

    -- Solicitation link
    solicitation_identifier  VARCHAR(100),

    -- Bulk load metadata
    fiscal_year              SMALLINT,
    fpds_enriched_at         DATETIME,

    -- Resolved federal hierarchy org
    fh_org_id                INT DEFAULT NULL,

    -- ETL metadata
    record_hash              CHAR(64),
    last_load_id             INT,
    first_loaded_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at               DATETIME NULL,  -- Soft-delete: USASpending awards use deleted_at (not hard delete) to preserve transaction FK references

    INDEX idx_usa_naics (naics_code),
    INDEX idx_usa_recipient (recipient_uei),
    INDEX idx_usa_awarding_cgac (awarding_agency_cgac),
    INDEX idx_usa_funding_cgac (funding_agency_cgac),
    INDEX idx_usa_setaside (type_of_set_aside),
    INDEX idx_usa_dates (start_date, end_date),
    INDEX idx_usa_solicitation (solicitation_identifier),
    INDEX idx_usa_piid (piid),
    INDEX idx_usa_fy (fiscal_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Phase 127: optimize expiring contracts query (end_date range + award_type + naics filter)
CREATE INDEX IF NOT EXISTS idx_usa_end_date_type_naics ON usaspending_award (end_date, award_type, naics_code);

-- Scope post-load resolution (fh_org_id, agency codes) to new rows instead of full-table scan
CREATE INDEX IF NOT EXISTS idx_usa_last_load_id ON usaspending_award (last_load_id);

-- Phase 117A: covering index for refresh_usaspending_award_summary() ROLLUP query
-- Enables index-only scan (no clustered-row access) for the daily summary refresh
CREATE INDEX IF NOT EXISTS idx_usa_summary_cover ON usaspending_award (naics_code, awarding_agency_cgac, recipient_uei, total_obligation);

-- Transaction-level spending detail for burn rate analysis
CREATE TABLE IF NOT EXISTS usaspending_transaction (
    id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
    award_id                    VARCHAR(100) NOT NULL,
    action_date                 DATE NOT NULL,
    modification_number         VARCHAR(25) NOT NULL DEFAULT '',
    action_type                 VARCHAR(5),
    action_type_description     VARCHAR(100),
    federal_action_obligation   DECIMAL(15,2),
    description                 TEXT,
    first_loaded_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_load_id                INT,
    UNIQUE KEY uk_txn_dedup (award_id, modification_number, action_date),
    INDEX idx_ut_award (award_id),
    INDEX idx_ut_date (action_date),
    CONSTRAINT fk_ut_award FOREIGN KEY (award_id)
        REFERENCES usaspending_award(generated_unique_award_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Checkpoint/resume tracking for bulk CSV loads
CREATE TABLE IF NOT EXISTS usaspending_load_checkpoint (
    checkpoint_id INT AUTO_INCREMENT PRIMARY KEY,
    load_id INT NOT NULL,
    fiscal_year INT NOT NULL,
    csv_file_name VARCHAR(255) NOT NULL,
    status ENUM('IN_PROGRESS', 'COMPLETE', 'FAILED') NOT NULL DEFAULT 'IN_PROGRESS',
    completed_batches INT NOT NULL DEFAULT 0,
    total_rows_loaded INT NOT NULL DEFAULT 0,
    archive_hash VARCHAR(130) NULL COMMENT 'SHA-256 hash (first 1MB) + file size for FY dedup',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    UNIQUE KEY uq_load_csv (load_id, csv_file_name),
    KEY idx_fy_hash (fiscal_year, archive_hash),
    CONSTRAINT fk_checkpoint_load FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =============================================================================
-- Migration: Phase 115L — Agency code normalization
-- Run against existing databases that already have the usaspending_award table.
-- NOTE: 28.7M rows — schedule for off-hours.
-- =============================================================================
-- ALTER TABLE usaspending_award ADD COLUMN awarding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER awarding_sub_agency_name;
-- ALTER TABLE usaspending_award ADD COLUMN funding_agency_cgac VARCHAR(10) DEFAULT NULL AFTER funding_agency_name;
-- ALTER TABLE usaspending_award ADD INDEX idx_usa_awarding_cgac (awarding_agency_cgac);
-- ALTER TABLE usaspending_award ADD INDEX idx_usa_funding_cgac (funding_agency_cgac);

-- =============================================================================
-- Migration: Phase 115L — Drop unused indexes
-- Run against existing databases.
-- =============================================================================
-- DROP INDEX idx_usa_agency ON usaspending_award;
-- DROP INDEX idx_usa_recipient_name ON usaspending_award;
-- DROP INDEX idx_usa_modified ON usaspending_award;
-- DROP INDEX idx_usa_enrich ON usaspending_award;

-- =============================================================================
-- Migration: Phase 115L Item 5 — fh_org_id resolution
-- Run against existing databases.
-- NOTE: 28.7M rows — ADD COLUMN is instant (metadata-only) in MySQL 8.0+.
-- =============================================================================
-- ALTER TABLE opportunity ADD COLUMN fh_org_id INT DEFAULT NULL;
-- ALTER TABLE opportunity ADD INDEX idx_opp_fh_org (fh_org_id);
-- ALTER TABLE fpds_contract ADD COLUMN fh_org_id INT DEFAULT NULL;
-- ALTER TABLE fpds_contract ADD INDEX idx_fpds_fh_org (fh_org_id);
-- ALTER TABLE usaspending_award ADD COLUMN fh_org_id INT DEFAULT NULL;
