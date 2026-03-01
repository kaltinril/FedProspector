-- tables/20_entity.sql
-- Entity tables (10 tables) - SAM.gov contractor data

USE fed_contracts;

CREATE TABLE IF NOT EXISTS stg_entity_raw (
    load_id              INT NOT NULL,
    uei_sam              VARCHAR(12) NOT NULL,
    raw_json             JSON,
    raw_record_hash      CHAR(64),
    processed            CHAR(1) DEFAULT 'N',
    processed_at         DATETIME,
    error_message        TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_uei (uei_sam),
    INDEX idx_stg_load (load_id),
    INDEX idx_stg_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity (
    uei_sam              VARCHAR(12) NOT NULL,
    uei_duns             VARCHAR(9),
    cage_code            VARCHAR(5),
    dodaac               VARCHAR(9),
    registration_status  VARCHAR(1),
    purpose_of_registration VARCHAR(2),
    initial_registration_date DATE,
    registration_expiration_date DATE,
    last_update_date     DATE,
    activation_date      DATE,
    legal_business_name  VARCHAR(120) NOT NULL,
    dba_name             VARCHAR(120),
    entity_division      VARCHAR(60),
    entity_division_number VARCHAR(10),
    dnb_open_data_flag   VARCHAR(1),
    entity_start_date    DATE,
    fiscal_year_end_close VARCHAR(4),
    entity_url           VARCHAR(200),
    entity_structure_code VARCHAR(2),
    entity_type_code     VARCHAR(2),
    profit_structure_code VARCHAR(2),
    organization_structure_code VARCHAR(2),
    state_of_incorporation VARCHAR(2),
    country_of_incorporation VARCHAR(3),
    primary_naics        VARCHAR(6),
    credit_card_usage    VARCHAR(1),
    correspondence_flag  VARCHAR(1),
    debt_subject_to_offset VARCHAR(1),
    exclusion_status_flag VARCHAR(1),
    no_public_display_flag VARCHAR(4),
    evs_source           VARCHAR(10),
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    PRIMARY KEY (uei_sam),
    INDEX idx_entity_name (legal_business_name),
    INDEX idx_entity_naics (primary_naics),
    INDEX idx_entity_status (registration_status),
    INDEX idx_entity_updated (last_update_date),
    INDEX idx_entity_cage (cage_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_address (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    address_type         VARCHAR(10) NOT NULL,
    address_line_1       VARCHAR(150),
    address_line_2       VARCHAR(150),
    city                 VARCHAR(40),
    state_or_province    VARCHAR(55),
    zip_code             VARCHAR(50),
    zip_code_plus4       VARCHAR(10),
    country_code         VARCHAR(3),
    congressional_district VARCHAR(10),
    UNIQUE KEY uk_entity_addr (uei_sam, address_type),
    CONSTRAINT fk_addr_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_naics (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    naics_code           VARCHAR(11) NOT NULL,
    is_primary           CHAR(1) DEFAULT 'N',
    sba_small_business   VARCHAR(1),
    naics_exception      VARCHAR(20),
    UNIQUE KEY uk_entity_naics (uei_sam, naics_code),
    CONSTRAINT fk_en_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_en_naics (naics_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_psc (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    psc_code             VARCHAR(10) NOT NULL,
    UNIQUE KEY uk_entity_psc (uei_sam, psc_code),
    CONSTRAINT fk_ep_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_ep_psc (psc_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_business_type (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    business_type_code   VARCHAR(4) NOT NULL,
    UNIQUE KEY uk_entity_bt (uei_sam, business_type_code),
    CONSTRAINT fk_ebt_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_ebt_code (business_type_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_sba_certification (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    sba_type_code        VARCHAR(10),
    sba_type_desc        VARCHAR(200),
    certification_entry_date DATE,
    certification_exit_date  DATE,
    UNIQUE KEY uk_entity_sba (uei_sam, sba_type_code),
    CONSTRAINT fk_esba_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_esba_code (sba_type_code),
    INDEX idx_esba_active (certification_exit_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_poc (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    poc_type             VARCHAR(40) NOT NULL,
    first_name           VARCHAR(65),
    middle_initial       VARCHAR(3),
    last_name            VARCHAR(65),
    title                VARCHAR(50),
    address_line_1       VARCHAR(150),
    address_line_2       VARCHAR(150),
    city                 VARCHAR(40),
    state_or_province    VARCHAR(55),
    zip_code             VARCHAR(50),
    zip_code_plus4       VARCHAR(10),
    country_code         VARCHAR(3),
    UNIQUE KEY uk_entity_poc (uei_sam, poc_type),
    CONSTRAINT fk_poc_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_disaster_response (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    state_code           VARCHAR(10),
    state_name           VARCHAR(60),
    county_code          VARCHAR(5),
    county_name          VARCHAR(100),
    msa_code             VARCHAR(10),
    msa_name             VARCHAR(100),
    CONSTRAINT fk_edr_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entity_history (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    field_name           VARCHAR(100) NOT NULL,
    old_value            TEXT,
    new_value            TEXT,
    changed_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    load_id              INT NOT NULL,
    INDEX idx_eh_uei (uei_sam),
    INDEX idx_eh_date (changed_at),
    INDEX idx_eh_load (load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
