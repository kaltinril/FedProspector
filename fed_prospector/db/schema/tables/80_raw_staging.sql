-- tables/80_raw_staging.sql
-- Raw staging tables (6 tables) - Preserve full API responses for replay/rebuild
--
-- These tables store the complete JSON response from each API source before
-- normalization into production tables. This enables:
--   - Re-processing/replay without re-fetching from APIs
--   - Capturing fields not yet normalized
--   - Historical audit trail of what each API returned and when
--   - Schema evolution safety -- rebuild production tables from raw data
--
-- Pattern matches existing stg_entity_raw in tables/20_entity.sql

USE fed_contracts;

CREATE TABLE IF NOT EXISTS stg_opportunity_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    notice_id          VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_opp_load (load_id),
    INDEX idx_stg_opp_notice (notice_id),
    INDEX idx_stg_opp_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_fpds_award_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    contract_id        VARCHAR(100) NOT NULL,
    modification_number VARCHAR(25),
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_fpds_load (load_id),
    INDEX idx_stg_fpds_contract (contract_id),
    INDEX idx_stg_fpds_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_usaspending_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    award_id           VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_usa_load (load_id),
    INDEX idx_stg_usa_award (award_id),
    INDEX idx_stg_usa_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_exclusion_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    record_id          VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_excl_load (load_id),
    INDEX idx_stg_excl_record (record_id),
    INDEX idx_stg_excl_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_fedhier_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    fh_org_id          INT NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_fh_load (load_id),
    INDEX idx_stg_fh_org (fh_org_id),
    INDEX idx_stg_fh_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_subaward_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    prime_piid         VARCHAR(50) NOT NULL,
    sub_uei            VARCHAR(12),
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_sub_load (load_id),
    INDEX idx_stg_sub_piid (prime_piid),
    INDEX idx_stg_sub_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
