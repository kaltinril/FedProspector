-- tables/43_sca_pricing.sql
-- SCA Wage Determination tables (3 tables) - Phase 115J

USE fed_contracts;

CREATE TABLE IF NOT EXISTS sca_wage_determination (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    wd_number            VARCHAR(20) NOT NULL COMMENT 'DOL WD number e.g. 2015-4281',
    revision             INT NOT NULL DEFAULT 0 COMMENT 'Revision number, 0 = original',
    title                VARCHAR(500),
    area_name            VARCHAR(500) NOT NULL COMMENT 'DOL locality description',
    state_code           VARCHAR(2) COMMENT '2-letter state code',
    county_name          VARCHAR(500) COMMENT 'County name(s), comma-separated for multi-county WDs',
    is_statewide         TINYINT(1) NOT NULL DEFAULT 0,
    effective_date       DATE,
    expiration_date      DATE,
    status               VARCHAR(20) COMMENT 'ACTIVE, SUPERSEDED, EXPIRED',
    is_current           TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1 = latest revision of this WD',
    wd_type              VARCHAR(20) DEFAULT 'STANDARD' COMMENT 'STANDARD or NON_STANDARD',
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    UNIQUE KEY uk_wd_rev (wd_number, revision),
    INDEX idx_swd_state (state_code),
    INDEX idx_swd_current (is_current),
    INDEX idx_swd_hash (record_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sca_wage_rate (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    wd_id                INT NOT NULL COMMENT 'Logical FK to sca_wage_determination.id',
    occupation_code      VARCHAR(20) NOT NULL COMMENT 'DOL Directory of Occupations code',
    occupation_title     VARCHAR(200) NOT NULL COMMENT 'DOL occupation title',
    hourly_rate          DECIMAL(10,2) COMMENT 'Minimum hourly wage',
    fringe_rate          DECIMAL(10,2) COMMENT 'Total fringe benefit rate per hour',
    health_welfare       DECIMAL(10,2) COMMENT 'Health & welfare component per hour',
    vacation             DECIMAL(10,2) COMMENT 'Vacation component per hour',
    holiday              DECIMAL(10,2) COMMENT 'Holiday component per hour',
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    UNIQUE KEY uk_rate (wd_id, occupation_code),
    INDEX idx_swr_occupation (occupation_code),
    INDEX idx_swr_hash (record_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_sca_wd_raw (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    load_id              INT NOT NULL,
    wd_number            VARCHAR(20),
    revision             INT,
    raw_text             LONGTEXT,
    raw_record_hash      CHAR(64),
    processed            ENUM('Y', 'E') NULL,
    error_message        TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
