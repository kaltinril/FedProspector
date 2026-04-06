-- Phase 115B: Pricing Intelligence — schema migration
-- Date: 2026-04-01
-- Creates pricing intelligence tables and views.
-- Indexes: only UNIQUE keys (for upsert) + one JOIN index on labor_category_mapping.

USE fed_contracts;

-- ============================================================
-- Tables: Labor category normalization
-- ============================================================

CREATE TABLE IF NOT EXISTS canonical_labor_category (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    canonical_name       VARCHAR(200) NOT NULL,
    category_group       VARCHAR(100) NOT NULL,
    onet_code            VARCHAR(20),
    description          LONGTEXT,
    created_at           DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uk_canonical_name (canonical_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS labor_category_mapping (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    raw_labor_category   VARCHAR(200) NOT NULL,
    canonical_id         INT,
    match_method         VARCHAR(20) NOT NULL COMMENT 'EXACT, FUZZY, PATTERN, MANUAL, UNMAPPED',
    confidence           DECIMAL(5,2) COMMENT 'Match confidence 0-100',
    reviewed             TINYINT(1) NOT NULL DEFAULT 0,
    created_at           DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uk_raw_labor (raw_labor_category),
    INDEX idx_lcm_canonical (canonical_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS labor_rate_summary (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    canonical_id         INT NOT NULL,
    category_group       VARCHAR(100) NOT NULL,
    worksite             VARCHAR(100),
    education_level      VARCHAR(50),
    rate_count           INT NOT NULL,
    min_rate             DECIMAL(10,2),
    avg_rate             DECIMAL(10,2),
    max_rate             DECIMAL(10,2),
    p25_rate             DECIMAL(10,2),
    median_rate          DECIMAL(10,2),
    p75_rate             DECIMAL(10,2),
    refreshed_at         DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uk_summary (canonical_id, category_group, worksite, education_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Table: BLS cost index data
-- ============================================================

CREATE TABLE IF NOT EXISTS bls_cost_index (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    series_id            VARCHAR(50) NOT NULL,
    series_name          VARCHAR(200),
    year                 INT NOT NULL,
    period               VARCHAR(5) NOT NULL COMMENT 'M01-M12 or Q01-Q04',
    value                DECIMAL(12,4) NOT NULL,
    footnotes            LONGTEXT,
    first_loaded_at      DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    last_loaded_at       DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    last_load_id         INT,
    UNIQUE KEY uk_bls_series_period (series_id, year, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Views: Pricing intelligence
-- ============================================================

CREATE OR REPLACE VIEW v_labor_rate_heatmap AS
SELECT
    clc.canonical_name,
    clc.category_group,
    glr.worksite,
    glr.education_level,
    glr.schedule,
    COUNT(*)             AS rate_count,
    MIN(glr.current_price) AS min_rate,
    AVG(glr.current_price) AS avg_rate,
    MAX(glr.current_price) AS max_rate
FROM gsa_labor_rate glr
JOIN labor_category_mapping lcm ON lcm.raw_labor_category = glr.labor_category
    AND lcm.source = 'GSA_CALC'
JOIN canonical_labor_category clc ON clc.id = lcm.canonical_id
WHERE glr.current_price > 0
GROUP BY clc.canonical_name, clc.category_group, glr.worksite, glr.education_level, glr.schedule;

CREATE OR REPLACE VIEW v_price_to_win_comparable AS
SELECT
    fc.naics_code,
    fc.agency_name                AS contracting_agency_name,
    fc.set_aside_type             AS type_of_set_aside,
    fc.type_of_contract_pricing,
    fc.base_and_all_options       AS base_and_all_options_value,
    fc.dollars_obligated,
    fc.number_of_offers,
    DATEDIFF(COALESCE(fc.ultimate_completion_date, fc.completion_date), fc.effective_date) AS period_of_performance_days,
    fc.contract_id,
    fc.vendor_name,
    fc.date_signed
FROM fpds_contract fc
WHERE fc.modification_number = '0'
  AND fc.base_and_all_options > 0
  AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 10 YEAR);

CREATE OR REPLACE VIEW v_sub_cost_benchmark AS
SELECT
    sa.naics_code,
    sa.prime_agency_name,
    sa.sub_business_type,
    COUNT(*)               AS sub_count,
    SUM(sa.sub_amount)     AS total_sub_value,
    AVG(sa.sub_amount)     AS avg_sub_value,
    MIN(sa.sub_amount)     AS min_sub_value,
    MAX(sa.sub_amount)     AS max_sub_value
FROM sam_subaward sa
WHERE sa.sub_amount > 0
GROUP BY sa.naics_code, sa.prime_agency_name, sa.sub_business_type;
