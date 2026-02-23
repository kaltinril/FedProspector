-- 01_reference_tables.sql
-- Reference/lookup tables (9 tables)
-- Loaded once from CSV files, updated infrequently

USE fed_contracts;

CREATE TABLE IF NOT EXISTS ref_naics_code (
    naics_code       VARCHAR(11) NOT NULL,
    description      VARCHAR(500) NOT NULL,
    year_version     VARCHAR(4),
    is_active        CHAR(1) DEFAULT 'Y',
    footnote_id      VARCHAR(5),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (naics_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_sba_size_standard (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    naics_code       VARCHAR(11) NOT NULL,
    industry_description VARCHAR(500),
    size_standard    DECIMAL(13,2),
    size_type        CHAR(1),
    footnote_id      VARCHAR(5),
    effective_date   DATE,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_naics (naics_code),
    CONSTRAINT fk_size_naics FOREIGN KEY (naics_code) REFERENCES ref_naics_code(naics_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_naics_footnote (
    footnote_id      VARCHAR(5) NOT NULL,
    section          VARCHAR(5) NOT NULL,
    description      TEXT NOT NULL,
    PRIMARY KEY (footnote_id, section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_psc_code (
    psc_code             VARCHAR(10) NOT NULL,
    psc_name             VARCHAR(200),
    start_date           DATE,
    end_date             DATE,
    full_description     TEXT,
    psc_includes         TEXT,
    psc_excludes         TEXT,
    psc_notes            TEXT,
    parent_psc_code      VARCHAR(200),
    category_type        CHAR(1),
    level1_category_code VARCHAR(10),
    level1_category      VARCHAR(100),
    level2_category_code VARCHAR(10),
    level2_category      VARCHAR(100),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (psc_code, start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_country_code (
    country_name    VARCHAR(100) NOT NULL,
    two_code        VARCHAR(2) NOT NULL,
    three_code      VARCHAR(3) NOT NULL,
    numeric_code    VARCHAR(4),
    independent     VARCHAR(3),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (three_code),
    INDEX idx_two_code (two_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_state_code (
    state_code      VARCHAR(2) NOT NULL,
    state_name      VARCHAR(60) NOT NULL,
    country_code    VARCHAR(3) DEFAULT 'USA',
    PRIMARY KEY (state_code, country_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_fips_county (
    fips_code       VARCHAR(5) NOT NULL,
    county_name     VARCHAR(100),
    state_name      VARCHAR(60),
    PRIMARY KEY (fips_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_business_type (
    business_type_code  VARCHAR(4) NOT NULL,
    description         VARCHAR(200) NOT NULL,
    classification      VARCHAR(50),
    PRIMARY KEY (business_type_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_entity_structure (
    structure_code  VARCHAR(2) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    PRIMARY KEY (structure_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ref_set_aside_type (
    set_aside_code  VARCHAR(10) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    is_small_business CHAR(1) DEFAULT 'Y',
    PRIMARY KEY (set_aside_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
