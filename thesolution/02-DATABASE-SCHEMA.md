# MySQL Database Schema Design

## Overview

Database name: `fed_contracts`
Engine: InnoDB (all tables)
Charset: utf8mb4
Collation: utf8mb4_unicode_ci

Tables are organized into five groups:
1. **Reference/Lookup Tables** (`ref_*`) - Loaded once, updated infrequently
2. **Entity Tables** (`entity*`) - SAM.gov entity/contractor data
3. **Opportunity Tables** (`opportunity*`) - Contract opportunities
4. **Federal Data Tables** (`federal_*`, `fpds_*`, `gsa_*`) - Hierarchy, awards, rates
5. **Operational Tables** (`etl_*`, `app_*`, `prospect*`, `saved_*`) - ETL tracking, prospecting, users

---

## 1. Reference/Lookup Tables

### ref_naics_code
NAICS classification codes (2-6 digit hierarchy). Sources: `2-6 digit_2022_Codes.csv`, `6-digit_2017_Codes.csv`

```sql
CREATE TABLE ref_naics_code (
    naics_code       VARCHAR(11) NOT NULL,
    description      VARCHAR(500) NOT NULL,
    year_version     VARCHAR(4),
    is_active        CHAR(1) DEFAULT 'Y',
    footnote_id      VARCHAR(5),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (naics_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_sba_size_standard
SBA small business size thresholds by NAICS. Source: `naics_size_standards.csv`, `Table of Size Standards March 2023`

```sql
CREATE TABLE ref_sba_size_standard (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    naics_code       VARCHAR(11) NOT NULL,
    industry_description VARCHAR(500),
    size_standard    DECIMAL(13,2),
    size_type        CHAR(1),              -- 'M' = millions revenue, 'E' = employees
    footnote_id      VARCHAR(5),
    effective_date   DATE,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_naics (naics_code),
    CONSTRAINT fk_size_naics FOREIGN KEY (naics_code) REFERENCES ref_naics_code(naics_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_naics_footnote
Specialized rules for specific NAICS size standards. Source: `footnotes.csv`

```sql
CREATE TABLE ref_naics_footnote (
    footnote_id      VARCHAR(5) NOT NULL,
    section          VARCHAR(5) NOT NULL,
    description      TEXT NOT NULL,
    PRIMARY KEY (footnote_id, section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_psc_code
Product/Service Codes with category hierarchy. Source: `PSC April 2022 - PSC for 042022.csv`

```sql
CREATE TABLE ref_psc_code (
    psc_code             VARCHAR(10) NOT NULL,
    psc_name             VARCHAR(200),
    start_date           DATE,
    end_date             DATE,
    full_description     TEXT,
    psc_includes         TEXT,
    psc_excludes         TEXT,
    psc_notes            TEXT,
    parent_psc_code      VARCHAR(200),
    category_type        CHAR(1),              -- 'S' = Service, 'P' = Product
    level1_category_code VARCHAR(10),
    level1_category      VARCHAR(100),
    level2_category_code VARCHAR(10),
    level2_category      VARCHAR(100),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (psc_code, start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_country_code
ISO country codes. Source: `country_codes_combined.csv`, `three letter country codes.csv`

```sql
CREATE TABLE ref_country_code (
    country_name    VARCHAR(100) NOT NULL,
    two_code        VARCHAR(2) NOT NULL,
    three_code      VARCHAR(3) NOT NULL,
    numeric_code    VARCHAR(4),
    independent     VARCHAR(3),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (three_code),
    INDEX idx_two_code (two_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_state_code
US state and territory codes. Source: `GG-Updated-Country-and-State-Lists - States.csv`

```sql
CREATE TABLE ref_state_code (
    state_code      VARCHAR(2) NOT NULL,
    state_name      VARCHAR(60) NOT NULL,
    country_code    VARCHAR(3) DEFAULT 'USA',
    PRIMARY KEY (state_code, country_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_fips_county
FIPS county codes. Source: `FIPS COUNTY CODES.csv`

```sql
CREATE TABLE ref_fips_county (
    fips_code       VARCHAR(5) NOT NULL,
    county_name     VARCHAR(100),
    state_name      VARCHAR(60),
    PRIMARY KEY (fips_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_business_type
Business type classification codes. Source: `OLD_RESOURCES/BusTypes.csv`

```sql
CREATE TABLE ref_business_type (
    business_type_code  VARCHAR(4) NOT NULL,
    description         VARCHAR(200) NOT NULL,
    classification      VARCHAR(50),
    PRIMARY KEY (business_type_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_entity_structure
Entity legal structure codes (from SAM.gov API responses)

```sql
CREATE TABLE ref_entity_structure (
    structure_code  VARCHAR(2) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    PRIMARY KEY (structure_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_set_aside_type
Set-aside type codes for filtering opportunities

```sql
CREATE TABLE ref_set_aside_type (
    set_aside_code  VARCHAR(10) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    is_small_business CHAR(1) DEFAULT 'Y',
    PRIMARY KEY (set_aside_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 2. Entity Tables (SAM.gov Data)

### stg_entity_raw
Staging table for raw entity data before normalization. Preserves original data for audit.

```sql
CREATE TABLE stg_entity_raw (
    load_id              INT NOT NULL,
    uei_sam              VARCHAR(12) NOT NULL,
    raw_json             JSON,                   -- Full JSON record from API/extract
    raw_record_hash      CHAR(64),               -- SHA-256 for change detection
    processed            CHAR(1) DEFAULT 'N',
    processed_at         DATETIME,
    error_message        TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_uei (uei_sam),
    INDEX idx_stg_load (load_id),
    INDEX idx_stg_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### entity
Core entity record. One row per UEI SAM.

```sql
CREATE TABLE entity (
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
```

### entity_address
Physical and mailing addresses. Two rows per entity max.

```sql
CREATE TABLE entity_address (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    address_type         VARCHAR(10) NOT NULL,    -- 'PHYSICAL' or 'MAILING'
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
```

### entity_naics
NAICS codes assigned to an entity. Many-to-many.

```sql
CREATE TABLE entity_naics (
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
```

### entity_psc
PSC codes assigned to an entity. Many-to-many.

```sql
CREATE TABLE entity_psc (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    psc_code             VARCHAR(10) NOT NULL,
    UNIQUE KEY uk_entity_psc (uei_sam, psc_code),
    CONSTRAINT fk_ep_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_ep_psc (psc_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### entity_business_type
Business type codes for an entity. Many-to-many.

```sql
CREATE TABLE entity_business_type (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei_sam              VARCHAR(12) NOT NULL,
    business_type_code   VARCHAR(4) NOT NULL,
    UNIQUE KEY uk_entity_bt (uei_sam, business_type_code),
    CONSTRAINT fk_ebt_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_ebt_code (business_type_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### entity_sba_certification
SBA program certifications with effective dates. Critical for WOSB/8(a) filtering.

```sql
CREATE TABLE entity_sba_certification (
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
```

### entity_poc
Points of contact. 6 types per entity (govt business, electronic business, past performance + alternates).

```sql
CREATE TABLE entity_poc (
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
```

### entity_disaster_response
Geographic areas served for disaster relief.

```sql
CREATE TABLE entity_disaster_response (
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
```

### entity_history
Field-level change tracking between loads.

```sql
CREATE TABLE entity_history (
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
```

---

## 3. Opportunity Tables

### opportunity
Contract opportunities from SAM.gov Opportunities API.

```sql
CREATE TABLE opportunity (
    notice_id            VARCHAR(100) NOT NULL,
    title                VARCHAR(500),
    solicitation_number  VARCHAR(100),
    department_name      VARCHAR(200),
    sub_tier             VARCHAR(200),
    office               VARCHAR(200),
    posted_date          DATE,
    response_deadline    DATETIME,
    archive_date         DATE,
    type                 VARCHAR(50),
    base_type            VARCHAR(50),
    set_aside_code       VARCHAR(20),
    set_aside_description VARCHAR(200),
    classification_code  VARCHAR(10),            -- PSC code
    naics_code           VARCHAR(6),
    pop_state            VARCHAR(6),              -- ISO 3166-2 subdivision codes (e.g., IN-MH)
    pop_zip              VARCHAR(10),
    pop_country          VARCHAR(3),
    pop_city             VARCHAR(100),
    active               CHAR(1) DEFAULT 'Y',
    award_number         VARCHAR(50),
    award_date           DATE,
    award_amount         DECIMAL(15,2),
    awardee_uei          VARCHAR(12),
    awardee_name         VARCHAR(200),
    description          TEXT,
    link                 VARCHAR(500),
    resource_links       JSON,
    contracting_office_id VARCHAR(20),
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    PRIMARY KEY (notice_id),
    INDEX idx_opp_naics (naics_code),
    INDEX idx_opp_set_aside (set_aside_code),
    INDEX idx_opp_posted (posted_date),
    INDEX idx_opp_response (response_deadline),
    INDEX idx_opp_type (type),
    INDEX idx_opp_active (active),
    INDEX idx_opp_sol (solicitation_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### opportunity_history
Change tracking for opportunities.

```sql
CREATE TABLE opportunity_history (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    notice_id            VARCHAR(100) NOT NULL,
    field_name           VARCHAR(100) NOT NULL,
    old_value            TEXT,
    new_value            TEXT,
    changed_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    load_id              INT NOT NULL,
    INDEX idx_oh_notice (notice_id),
    INDEX idx_oh_date (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 4. Federal Data Tables

### federal_organization
Government org hierarchy from Federal Hierarchy API.

```sql
CREATE TABLE federal_organization (
    fh_org_id            INT NOT NULL,
    fh_org_name          VARCHAR(500),
    fh_org_type          VARCHAR(50),
    description          TEXT,
    status               VARCHAR(20),
    agency_code          VARCHAR(20),
    oldfpds_office_code  VARCHAR(20),
    cgac                 VARCHAR(10),
    parent_org_id        INT,
    level                INT,
    created_date         DATE,
    last_modified_date   DATE,
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (fh_org_id),
    INDEX idx_fh_parent (parent_org_id),
    INDEX idx_fh_agency (agency_code),
    INDEX idx_fh_type (fh_org_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### fpds_contract
Historical contract awards from FPDS and SAM.gov Contract Awards API.

```sql
CREATE TABLE fpds_contract (
    contract_id          VARCHAR(50) NOT NULL,
    idv_piid             VARCHAR(50),
    modification_number  VARCHAR(10) NOT NULL DEFAULT '0',
    transaction_number   VARCHAR(10),
    agency_id            VARCHAR(10),
    agency_name          VARCHAR(200),
    contracting_office_id VARCHAR(20),
    contracting_office_name VARCHAR(200),
    funding_agency_id    VARCHAR(10),
    funding_agency_name  VARCHAR(200),
    vendor_uei           VARCHAR(12),
    vendor_name          VARCHAR(200),
    vendor_duns          VARCHAR(9),
    date_signed          DATE,
    effective_date       DATE,
    completion_date      DATE,
    last_modified_date   DATE,
    dollars_obligated    DECIMAL(15,2),
    base_and_all_options DECIMAL(15,2),
    naics_code           VARCHAR(6),
    psc_code             VARCHAR(10),
    set_aside_type       VARCHAR(20),
    type_of_contract     VARCHAR(10),
    description          TEXT,
    pop_state            VARCHAR(6),              -- ISO 3166-2 subdivision codes (e.g., IN-MH)
    pop_country          VARCHAR(3),
    pop_zip              VARCHAR(10),
    extent_competed      VARCHAR(10),
    number_of_offers     INT,
    far1102_exception_code   VARCHAR(2),          -- FAR 1.102 exception (Phase 5A)
    far1102_exception_name   VARCHAR(100),
    reason_for_modification  VARCHAR(100),
    solicitation_date        DATE,
    ultimate_completion_date DATE,
    type_of_contract_pricing VARCHAR(10),
    co_bus_size_determination VARCHAR(50),
    record_hash              CHAR(64),            -- SHA-256 change detection
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    PRIMARY KEY (contract_id, modification_number),
    INDEX idx_fpds_vendor (vendor_uei),
    INDEX idx_fpds_naics (naics_code),
    INDEX idx_fpds_agency (agency_id),
    INDEX idx_fpds_date (date_signed),
    INDEX idx_fpds_setaside (set_aside_type),
    INDEX idx_fpds_completion (completion_date),
    INDEX idx_fpds_hash (record_hash),
    INDEX idx_fpds_far1102 (far1102_exception_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### gsa_labor_rate
GSA CALC+ labor rates for pricing intelligence.

```sql
CREATE TABLE gsa_labor_rate (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    labor_category       VARCHAR(200),
    education_level      VARCHAR(50),
    min_years_experience INT,
    hourly_rate_year1    DECIMAL(10,2),
    current_price        DECIMAL(10,2),
    next_year_price      DECIMAL(10,2),
    second_year_price    DECIMAL(10,2),
    schedule             VARCHAR(200),
    contractor_name      VARCHAR(200),
    sin                  VARCHAR(500),
    business_size        VARCHAR(10),
    security_clearance   VARCHAR(50),
    worksite             VARCHAR(100),
    contract_start       DATE,
    contract_end         DATE,
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_load_id         INT,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_labor_category (labor_category),
    INDEX idx_labor_schedule (schedule),
    INDEX idx_labor_size (business_size)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### usaspending_award
USASpending.gov award data for incumbent and spending analysis.

```sql
CREATE TABLE usaspending_award (
    generated_unique_award_id VARCHAR(100) PRIMARY KEY,
    piid                     VARCHAR(50),
    fain                     VARCHAR(30),
    uri                      VARCHAR(70),
    award_type               VARCHAR(50),
    award_description        TEXT,
    recipient_name           VARCHAR(200),
    recipient_uei            VARCHAR(12),
    recipient_parent_name    VARCHAR(200),
    recipient_parent_uei     VARCHAR(12),
    total_obligation         DECIMAL(15,2),
    base_and_all_options_value DECIMAL(15,2),
    start_date               DATE,
    end_date                 DATE,
    last_modified_date       DATE,
    awarding_agency_name     VARCHAR(200),
    awarding_sub_agency_name VARCHAR(200),
    funding_agency_name      VARCHAR(200),
    naics_code               VARCHAR(6),
    naics_description        VARCHAR(500),
    psc_code                 VARCHAR(10),
    type_of_set_aside        VARCHAR(50),
    type_of_set_aside_description VARCHAR(200),
    pop_state                VARCHAR(6),  -- ISO 3166-2 subdivision codes (e.g., IN-MH)
    pop_country              VARCHAR(3),
    pop_zip                  VARCHAR(10),
    pop_city                 VARCHAR(100),
    solicitation_identifier  VARCHAR(50),
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
```

### usaspending_transaction
Transaction-level spending detail for burn rate analysis. FK to usaspending_award.

```sql
CREATE TABLE usaspending_transaction (
    id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
    award_id                    VARCHAR(100) NOT NULL,
    action_date                 DATE NOT NULL,
    modification_number         VARCHAR(20),
    action_type                 VARCHAR(5),
    action_type_description     VARCHAR(100),
    federal_action_obligation   DECIMAL(15,2),
    description                 TEXT,
    first_loaded_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_load_id                INT,
    INDEX idx_ut_award (award_id),
    INDEX idx_ut_date (action_date),
    CONSTRAINT fk_ut_award FOREIGN KEY (award_id)
        REFERENCES usaspending_award(generated_unique_award_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 5. ETL / Operational Tables

### etl_load_log
Tracks every data load operation.

```sql
CREATE TABLE etl_load_log (
    load_id              INT AUTO_INCREMENT PRIMARY KEY,
    source_system        VARCHAR(50) NOT NULL,
    load_type            VARCHAR(20) NOT NULL,    -- 'FULL', 'INCREMENTAL', 'DAILY'
    status               VARCHAR(20) NOT NULL,    -- 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
    started_at           DATETIME NOT NULL,
    completed_at         DATETIME,
    records_read         INT DEFAULT 0,
    records_inserted     INT DEFAULT 0,
    records_updated      INT DEFAULT 0,
    records_unchanged    INT DEFAULT 0,
    records_errored      INT DEFAULT 0,
    error_message        TEXT,
    parameters           JSON,
    source_file          VARCHAR(500),
    INDEX idx_etl_source (source_system),
    INDEX idx_etl_date (started_at),
    INDEX idx_etl_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### etl_load_error
Individual record-level errors during loads.

```sql
CREATE TABLE etl_load_error (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    load_id              INT NOT NULL,
    record_identifier    VARCHAR(100),
    error_type           VARCHAR(50),
    error_message        TEXT,
    raw_data             TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_err_load (load_id),
    CONSTRAINT fk_err_load FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### etl_data_quality_rule
Configurable data cleanup rules applied during loading.

```sql
CREATE TABLE etl_data_quality_rule (
    rule_id              INT AUTO_INCREMENT PRIMARY KEY,
    rule_name            VARCHAR(100) NOT NULL,
    description          TEXT,
    target_table         VARCHAR(100),
    target_column        VARCHAR(100),
    rule_type            VARCHAR(20),             -- 'TRUNCATE', 'REPLACE', 'DEFAULT', 'STRIP', 'VALIDATE'
    rule_definition      JSON,
    is_active            CHAR(1) DEFAULT 'Y',
    priority             INT DEFAULT 100
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### etl_rate_limit
Tracks API usage per source per day.

```sql
CREATE TABLE etl_rate_limit (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    source_system        VARCHAR(50) NOT NULL,
    request_date         DATE NOT NULL,
    requests_made        INT DEFAULT 0,
    max_requests         INT NOT NULL,
    last_request_at      DATETIME,
    UNIQUE KEY uk_rate_limit (source_system, request_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 6. Prospecting / Sales Pipeline Tables

### app_user
Team members who work prospects.

```sql
CREATE TABLE app_user (
    user_id              INT AUTO_INCREMENT PRIMARY KEY,
    username             VARCHAR(50) NOT NULL UNIQUE,
    display_name         VARCHAR(100) NOT NULL,
    email                VARCHAR(200),
    role                 VARCHAR(20) DEFAULT 'USER',
    is_active            CHAR(1) DEFAULT 'Y',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### prospect
Links an opportunity to a team member for tracking through the pipeline.

```sql
CREATE TABLE prospect (
    prospect_id          INT AUTO_INCREMENT PRIMARY KEY,
    notice_id            VARCHAR(100) NOT NULL,
    assigned_to          INT,
    status               VARCHAR(30) NOT NULL DEFAULT 'NEW',
    priority             VARCHAR(10) DEFAULT 'MEDIUM',
    decision_date        DATE,
    bid_submitted_date   DATE,
    estimated_value      DECIMAL(15,2),
    estimated_effort_hours DECIMAL(10,2),
    win_probability      DECIMAL(5,2),
    go_no_go_score       DECIMAL(5,2),
    teaming_required     CHAR(1) DEFAULT 'N',
    estimated_proposal_cost DECIMAL(10,2),
    proposal_due_days    INT,
    outcome              VARCHAR(20),
    outcome_date         DATE,
    outcome_notes        TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_prospect_opp FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_prospect_user FOREIGN KEY (assigned_to) REFERENCES app_user(user_id),
    INDEX idx_prospect_status (status),
    INDEX idx_prospect_user (assigned_to),
    INDEX idx_prospect_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Prospect Status Values**: `NEW`, `REVIEWING`, `PURSUING`, `BID_SUBMITTED`, `WON`, `LOST`, `DECLINED`, `NO_BID`

### prospect_note
Activity log and comments on prospects.

```sql
CREATE TABLE prospect_note (
    note_id              INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id          INT NOT NULL,
    user_id              INT NOT NULL,
    note_type            VARCHAR(30) DEFAULT 'COMMENT',
    note_text            TEXT NOT NULL,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_note_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    CONSTRAINT fk_note_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_note_prospect (prospect_id),
    INDEX idx_note_date (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Note Types**: `COMMENT`, `STATUS_CHANGE`, `ASSIGNMENT`, `DECISION`, `REVIEW`, `MEETING`

### prospect_team_member
Partners or JV entities teaming on a prospect.

```sql
CREATE TABLE prospect_team_member (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id          INT NOT NULL,
    uei_sam              VARCHAR(12) NOT NULL,
    role                 VARCHAR(50),             -- 'PRIME', 'SUB', 'MENTOR', 'JV_PARTNER'
    notes                TEXT,
    CONSTRAINT fk_ptm_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    INDEX idx_ptm_entity (uei_sam)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### saved_search
Reusable opportunity filters for ongoing monitoring.

```sql
CREATE TABLE saved_search (
    search_id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    search_name          VARCHAR(100) NOT NULL,
    description          TEXT,
    filter_criteria      JSON NOT NULL,
    notification_enabled CHAR(1) DEFAULT 'N',
    is_active            CHAR(1) DEFAULT 'Y',
    last_run_at          DATETIME,
    last_new_results     INT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ss_user FOREIGN KEY (user_id) REFERENCES app_user(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Example filter_criteria JSON**:
```json
{
    "set_aside_codes": ["WOSB", "EDWOSB", "8A", "8AN"],
    "naics_codes": ["541511", "541512", "541519"],
    "min_award_amount": 50000,
    "max_award_amount": 5000000,
    "states": ["WI", "IL", "MN"],
    "types": ["o", "k", "p"]
}
```

---

## 7. Key Views

### v_target_opportunities
Active WOSB/8(a) opportunities with enriched data.

```sql
CREATE OR REPLACE VIEW v_target_opportunities AS
SELECT
    o.notice_id,
    o.title,
    o.solicitation_number,
    o.department_name,
    o.office,
    o.posted_date,
    o.response_deadline,
    DATEDIFF(o.response_deadline, NOW()) AS days_until_due,
    o.set_aside_code,
    o.set_aside_description,
    o.naics_code,
    n.description AS naics_description,
    ss.size_standard,
    ss.size_type,
    o.award_amount,
    o.pop_state,
    o.pop_city,
    o.description,
    o.link,
    p.prospect_id,
    p.status AS prospect_status,
    p.priority AS prospect_priority,
    u.display_name AS assigned_to
FROM opportunity o
LEFT JOIN ref_naics_code n ON n.naics_code = o.naics_code
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
LEFT JOIN prospect p ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE o.active = 'Y'
  AND o.set_aside_code IN ('WOSB', 'EDWOSB', 'WOSBSS', 'EDWOSBSS', 'SBA', '8A', '8AN')
  AND o.response_deadline > NOW();
```

### v_competitor_analysis
Entity competitive intelligence using FPDS award history.

```sql
CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.primary_naics,
    GROUP_CONCAT(DISTINCT ebt.business_type_code) AS business_types,
    GROUP_CONCAT(DISTINCT esc.sba_type_code) AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics;
```

---

## Table Count Summary

| Group | Tables | Purpose |
|-------|--------|---------|
| Reference (`ref_*`) | 10 | Lookup/classification data (includes ref_entity_structure) |
| Entity | 10 | SAM.gov contractor data |
| Opportunity | 2 | Contract opportunities |
| Federal | 5 | Hierarchy, awards, rates, spending (includes usaspending_award + usaspending_transaction) |
| ETL | 4 | Load tracking and quality |
| Prospecting | 5 | Sales pipeline (includes saved_search) |
| **Total** | **36** | |
| **Views** | **2** | |
