-- tables/42_pricing.sql
-- Pricing intelligence tables (4 tables) - Labor normalization, BLS cost indices

USE fed_contracts;

CREATE TABLE IF NOT EXISTS canonical_labor_category (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    canonical_name       VARCHAR(200) NOT NULL,
    category_group       VARCHAR(50) NOT NULL,
    onet_code            VARCHAR(10),
    description          TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_canonical_name (canonical_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS labor_category_mapping (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    raw_labor_category   VARCHAR(200) NOT NULL,
    canonical_id         INT,
    match_method         VARCHAR(20) NOT NULL COMMENT 'EXACT, FUZZY, PATTERN, MANUAL, UNMAPPED',
    confidence           DECIMAL(5,2) COMMENT 'Match confidence 0-100',
    reviewed             TINYINT(1) DEFAULT 0,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_raw_labor (raw_labor_category),
    INDEX idx_lcm_canonical (canonical_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS labor_rate_summary (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    canonical_id         INT NOT NULL,
    category_group       VARCHAR(50) NOT NULL,
    worksite             VARCHAR(100),
    education_level      VARCHAR(50),
    rate_count           INT NOT NULL,
    min_rate             DECIMAL(10,2),
    avg_rate             DECIMAL(10,2),
    max_rate             DECIMAL(10,2),
    p25_rate             DECIMAL(10,2),
    median_rate          DECIMAL(10,2),
    p75_rate             DECIMAL(10,2),
    refreshed_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_summary (canonical_id, category_group, worksite, education_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bls_cost_index (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    series_id            VARCHAR(30) NOT NULL,
    series_name          VARCHAR(200),
    year                 INT NOT NULL,
    period               VARCHAR(5) NOT NULL COMMENT 'M01-M12 or Q01-Q04',
    value                DECIMAL(12,4) NOT NULL,
    footnotes            VARCHAR(200),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    UNIQUE KEY uk_bls_series_period (series_id, year, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
