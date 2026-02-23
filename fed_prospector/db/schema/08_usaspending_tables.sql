-- 08_usaspending_tables.sql
-- USASpending.gov award data (1 table) - Incumbent and award history

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
    naics_code               VARCHAR(6),
    naics_description        VARCHAR(500),
    psc_code                 VARCHAR(10),

    -- Set-aside
    type_of_set_aside        VARCHAR(50),
    type_of_set_aside_description VARCHAR(200),

    -- Place of Performance
    pop_state                VARCHAR(2),
    pop_country              VARCHAR(3),
    pop_zip                  VARCHAR(10),
    pop_city                 VARCHAR(100),

    -- Solicitation link
    solicitation_identifier  VARCHAR(50),

    -- ETL metadata
    record_hash              VARCHAR(64),
    last_load_id             INT,
    first_loaded_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_usa_naics (naics_code),
    INDEX idx_usa_recipient (recipient_uei),
    INDEX idx_usa_agency (awarding_agency_name(50)),
    INDEX idx_usa_setaside (type_of_set_aside),
    INDEX idx_usa_dates (start_date, end_date),
    INDEX idx_usa_solicitation (solicitation_identifier),
    INDEX idx_usa_piid (piid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
