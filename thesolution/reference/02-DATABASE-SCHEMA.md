# MySQL Database Schema Design

## Overview

Database name: `fed_contracts`
Engine: InnoDB (all tables)
Charset: utf8mb4
Collation: utf8mb4_unicode_ci

Tables are organized into nine groups:
1. **Reference/Lookup Tables** (`ref_*`) - Loaded once, updated infrequently
2. **Entity Tables** (`entity*`) - SAM.gov entity/contractor data
3. **Opportunity Tables** (`opportunity*`) - Contract opportunities
4. **Federal Data Tables** (`federal_*`, `fpds_*`, `gsa_*`, `usaspending_*`) - Hierarchy, awards, rates
5. **ETL / Operational Tables** (`etl_*`, `data_load_request`) - Load tracking, health, quality
6. **Prospecting / Sales Pipeline Tables** (`prospect*`, `app_user`, `saved_search`, `organization*`) - Pipeline, users, orgs
7. **Key Views** - Pre-built analytical and search views
8. **Raw Staging Tables** (`stg_*_raw`) - API response preservation for replay/rebuild
9. **Web API Tables** (`app_session`, `proposal*`, `activity_log`, `notification`, `contracting_officer`, `opportunity_poc`, `organization_*`) - Authentication, proposals, audit, org profile

---

## 1. Reference/Lookup Tables

### ref_naics_code
NAICS classification codes (2-6 digit hierarchy) with level metadata. Sources: `2-6 digit_2022_Codes.csv`, `6-digit_2017_Codes.csv`

```sql
CREATE TABLE ref_naics_code (
    naics_code       VARCHAR(11) NOT NULL,
    description      VARCHAR(500) NOT NULL,
    code_level       TINYINT,                -- 1=Sector, 2=Subsector, 3=Industry Group, 4=NAICS Industry, 5=National Industry
    level_name       VARCHAR(30),            -- Human-readable level name
    parent_code      VARCHAR(11),            -- Parent NAICS code (left(code, len-1))
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
ISO country codes with SAM.gov territory enrichment. Source: `country_codes_combined.csv`, `GG-Updated-Country-and-State-Lists - Countries.csv`

```sql
CREATE TABLE ref_country_code (
    country_name        VARCHAR(100) NOT NULL,
    two_code            VARCHAR(2) NOT NULL,
    three_code          VARCHAR(3) NOT NULL,
    numeric_code        VARCHAR(4),
    independent         VARCHAR(3),
    is_iso_standard     CHAR(1) DEFAULT 'Y',
    sam_gov_recognized  CHAR(1) DEFAULT 'Y',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
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
Business type classification codes with category and socioeconomic flags. Source: `OLD_RESOURCES/BusTypes.csv`

```sql
CREATE TABLE ref_business_type (
    business_type_code         VARCHAR(4) NOT NULL,
    description                VARCHAR(200) NOT NULL,
    classification             VARCHAR(50),
    category                   VARCHAR(50),             -- Woman-Owned, Veteran, Government, etc.
    is_socioeconomic           CHAR(1) DEFAULT 'N',
    is_small_business_related  CHAR(1) DEFAULT 'N',
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
Set-aside type codes for filtering opportunities. Source: `set_aside_types.csv` (23 entries)

```sql
CREATE TABLE ref_set_aside_type (
    set_aside_code  VARCHAR(10) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    is_small_business CHAR(1) DEFAULT 'Y',
    category        VARCHAR(50),             -- WOSB, 8(a), HUBZone, SDVOSB, Veteran, General Small Business, etc.
    PRIMARY KEY (set_aside_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### ref_sba_type
SBA certification type codes for entity SBA certifications lookup.

```sql
CREATE TABLE ref_sba_type (
    sba_type_code   VARCHAR(10) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    program_name    VARCHAR(100),            -- 8(a), HUBZone
    PRIMARY KEY (sba_type_code)
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

### opportunity_relationship
Manual linking of related opportunities (RFI to RFP, presolicitation to solicitation, etc.).

```sql
CREATE TABLE opportunity_relationship (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    parent_notice_id     VARCHAR(100) NOT NULL,
    child_notice_id      VARCHAR(100) NOT NULL,
    relationship_type    VARCHAR(30) NOT NULL,  -- 'RFI_TO_RFP', 'PRESOL_TO_SOL', 'SOL_TO_AWARD'
    created_by           INT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes                TEXT,
    UNIQUE KEY uq_opp_rel (parent_notice_id, child_notice_id),
    INDEX idx_opp_rel_parent (parent_notice_id),
    INDEX idx_opp_rel_child (child_notice_id),
    CONSTRAINT fk_opp_rel_parent FOREIGN KEY (parent_notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_opp_rel_child FOREIGN KEY (child_notice_id) REFERENCES opportunity(notice_id)
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
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    PRIMARY KEY (fh_org_id),
    INDEX idx_fh_parent (parent_org_id),
    INDEX idx_fh_agency (agency_code),
    INDEX idx_fh_type (fh_org_type),
    INDEX idx_fh_status (status),
    INDEX idx_fh_cgac (cgac),
    INDEX idx_fh_hash (record_hash)
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

### sam_exclusion
SAM.gov debarred/suspended entity records for due diligence.

```sql
CREATE TABLE sam_exclusion (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    uei                  VARCHAR(12),
    cage_code            VARCHAR(10),
    entity_name          VARCHAR(500),
    first_name           VARCHAR(100),
    middle_name          VARCHAR(100),
    last_name            VARCHAR(100),
    suffix               VARCHAR(20),
    prefix               VARCHAR(20),
    exclusion_type       VARCHAR(50),
    exclusion_program    VARCHAR(50),
    excluding_agency_code VARCHAR(10),
    excluding_agency_name VARCHAR(200),
    activation_date      DATE,
    termination_date     DATE,
    additional_comments  TEXT,
    record_hash          CHAR(64),
    first_loaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id         INT,
    INDEX idx_excl_uei (uei),
    INDEX idx_excl_entity_name (entity_name),
    INDEX idx_excl_activation (activation_date),
    INDEX idx_excl_type (exclusion_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### sam_subaward
SAM.gov subaward/subcontract data for teaming partner analysis.

```sql
CREATE TABLE sam_subaward (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    prime_piid              VARCHAR(50),           -- Prime contract number
    prime_agency_id         VARCHAR(10),
    prime_agency_name       VARCHAR(200),
    prime_uei               VARCHAR(12),
    prime_name              VARCHAR(500),
    sub_uei                 VARCHAR(12),
    sub_name                VARCHAR(500),
    sub_amount              DECIMAL(15,2),
    sub_date                DATE,
    sub_description         TEXT,
    naics_code              VARCHAR(6),
    psc_code                VARCHAR(10),
    sub_business_type       VARCHAR(50),           -- Small business designation codes
    pop_state               VARCHAR(6),
    pop_country             VARCHAR(3),
    pop_zip                 VARCHAR(10),
    recovery_model_q1       VARCHAR(3),            -- Y/N recovery act
    recovery_model_q2       VARCHAR(3),
    record_hash             CHAR(64),
    first_loaded_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id            INT,
    INDEX idx_sub_prime_uei (prime_uei),
    INDEX idx_sub_sub_uei (sub_uei),
    INDEX idx_sub_naics (naics_code),
    INDEX idx_sub_prime_piid (prime_piid),
    INDEX idx_sub_date (sub_date),
    INDEX idx_sub_hash (record_hash)
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

### usaspending_load_checkpoint
Tracks per-file progress during bulk USASpending CSV loads for resumability.

```sql
CREATE TABLE IF NOT EXISTS usaspending_load_checkpoint (
    checkpoint_id INT AUTO_INCREMENT PRIMARY KEY,
    load_id INT NOT NULL,
    fiscal_year INT NOT NULL,
    csv_file_name VARCHAR(255) NOT NULL,
    status ENUM('IN_PROGRESS', 'COMPLETE', 'FAILED') NOT NULL DEFAULT 'IN_PROGRESS',
    rows_loaded INT DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    CONSTRAINT fk_uslc_load FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id),
    UNIQUE KEY uk_uslc_load_file (load_id, csv_file_name)
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

### etl_health_snapshot
Periodic health check results capturing overall ETL system status (used by `/health` endpoint).

```sql
CREATE TABLE IF NOT EXISTS etl_health_snapshot (
    snapshot_id          INT AUTO_INCREMENT PRIMARY KEY,
    checked_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    overall_status       VARCHAR(20) NOT NULL,
    results_json         JSON NOT NULL,
    alert_count          INT NOT NULL DEFAULT 0,
    INDEX idx_health_checked (checked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### data_load_request
Queue for on-demand data load requests (e.g., lookup a specific PIID or UEI from the UI).

```sql
CREATE TABLE IF NOT EXISTS data_load_request (
    request_id       INT AUTO_INCREMENT PRIMARY KEY,
    request_type     VARCHAR(30) NOT NULL,
    lookup_key       VARCHAR(200) NOT NULL,
    lookup_key_type  VARCHAR(20) NOT NULL DEFAULT 'PIID',
    status           VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    requested_by     INT,
    requested_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at     DATETIME,
    result_message   TEXT,
    INDEX idx_dlr_status (status),
    INDEX idx_dlr_type (request_type)
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

### organization
Multi-tenant organization (company) that owns users and prospects.

```sql
CREATE TABLE IF NOT EXISTS organization (
    organization_id      INT AUTO_INCREMENT PRIMARY KEY,
    name                 VARCHAR(200) NOT NULL,
    slug                 VARCHAR(100) NOT NULL UNIQUE,
    is_active            CHAR(1) NOT NULL DEFAULT 'Y',
    max_users            INT NOT NULL DEFAULT 10,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 7. Key Views

### v_target_opportunities
Active WOSB/8(a) opportunities with enriched reference data.

```sql
CREATE OR REPLACE VIEW v_target_opportunities AS
SELECT
    o.notice_id, o.title, o.solicitation_number,
    o.department_name, o.office, o.posted_date, o.response_deadline,
    DATEDIFF(o.response_deadline, NOW()) AS days_until_due,
    o.set_aside_code, o.set_aside_description,
    sa.category AS set_aside_category,
    o.naics_code, n.description AS naics_description,
    n.level_name AS naics_level, sector.description AS naics_sector,
    ss.size_standard, ss.size_type,
    o.award_amount, o.pop_state, o.pop_city, o.description, o.link,
    p.prospect_id, p.status AS prospect_status,
    p.priority AS prospect_priority, u.display_name AS assigned_to
FROM opportunity o
LEFT JOIN ref_naics_code n ON n.naics_code = o.naics_code
LEFT JOIN ref_naics_code sector ON sector.naics_code = LEFT(o.naics_code, 2) AND sector.code_level = 1
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
LEFT JOIN ref_set_aside_type sa ON sa.set_aside_code = o.set_aside_code
LEFT JOIN prospect p ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE o.active = 'Y'
  AND o.set_aside_code IN ('WOSB', 'EDWOSB', 'WOSBSS', 'EDWOSBSS', 'SBA', '8A', '8AN')
  AND o.response_deadline > NOW();
```

### v_competitor_analysis
Entity competitive intelligence with enriched reference data and FPDS award history.

```sql
CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam, e.legal_business_name, e.primary_naics,
    n.description AS naics_description, sector.description AS naics_sector,
    es.description AS entity_structure,
    GROUP_CONCAT(DISTINCT CONCAT(ebt.business_type_code, ':', COALESCE(rbt.description, ''))
        ORDER BY ebt.business_type_code SEPARATOR '; ') AS business_types,
    GROUP_CONCAT(DISTINCT rbt.category ORDER BY rbt.category SEPARATOR ', ') AS business_type_categories,
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(rst.description, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ') AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN ref_naics_code n ON n.naics_code = e.primary_naics
LEFT JOIN ref_naics_code sector ON sector.naics_code = LEFT(e.primary_naics, 2) AND sector.code_level = 1
LEFT JOIN ref_entity_structure es ON es.structure_code = e.entity_structure_code
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN ref_business_type rbt ON rbt.business_type_code = ebt.business_type_code
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN ref_sba_type rst ON rst.sba_type_code = esc.sba_type_code
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics,
         n.description, sector.description, es.description;
```

### v_entity_search
Flattened entity view with business types, SBA certs, and address info for search/filtering. Source: `01_search_views.sql`.

### v_active_exclusions
Currently active SAM exclusion records with entity join. Source: `01_search_views.sql`.

### v_base_awards
FPDS + USASpending award data unified into a single base view. Source: `01_search_views.sql`.

### v_procurement_intelligence
Market analytics: agency spending, NAICS trends, set-aside distribution. Source: `30_procurement_intelligence.sql`.

### v_incumbent_profile
Incumbent contractor profiles with award history, recompete windows. Source: `40_incumbent_profile.sql`.

### v_expiring_contracts
Contracts nearing expiration for recompete prospecting. Source: `50_expiring_contracts.sql`.

### ref_psc_code_latest
Deduplicated PSC codes showing only the most recent version per code. Source: `ref_psc_code_latest.sql`.

---

## 8. Raw Staging Tables

These tables store the complete JSON response from each API source before normalization into production tables, enabling replay/rebuild without re-fetching. Pattern matches existing `stg_entity_raw` in the Entity tables section.

### stg_opportunity_raw
Raw opportunity API responses for replay/audit.

```sql
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
```

### stg_fpds_award_raw
Raw FPDS/SAM contract award API responses for replay/audit.

```sql
CREATE TABLE IF NOT EXISTS stg_fpds_award_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    contract_id        VARCHAR(50) NOT NULL,
    modification_number VARCHAR(10),
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_fpds_load (load_id),
    INDEX idx_stg_fpds_contract (contract_id),
    INDEX idx_stg_fpds_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### stg_usaspending_raw
Raw USASpending API responses for replay/audit.

```sql
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
```

### stg_exclusion_raw
Raw SAM exclusion API responses for replay/audit.

```sql
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
```

### stg_fedhier_raw
Raw Federal Hierarchy API responses for replay/audit.

```sql
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
```

### stg_subaward_raw
Raw SAM subaward API responses for replay/audit.

```sql
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
```

---

## 9. Web API Tables

Production tables supporting the C# ASP.NET Core Web API: authentication, proposals, audit trails, notifications, contracting officer contacts, and organization profile data.

### app_session
User authentication sessions for JWT/token management.

```sql
CREATE TABLE IF NOT EXISTS app_session (
    session_id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    token_hash           CHAR(64) NOT NULL,
    issued_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at           DATETIME NOT NULL,
    revoked_at           DATETIME,
    ip_address           VARCHAR(45),
    user_agent           VARCHAR(500),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    UNIQUE INDEX idx_session_token (token_hash),
    INDEX idx_session_user (user_id),
    INDEX idx_session_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### contracting_officer
Normalized contracting officer contacts. Auto-populated from SAM.gov Opportunity API `pointOfContact` array.

```sql
CREATE TABLE IF NOT EXISTS contracting_officer (
    officer_id           INT AUTO_INCREMENT PRIMARY KEY,
    full_name            VARCHAR(200) NOT NULL,
    email                VARCHAR(200),
    phone                VARCHAR(50),
    fax                  VARCHAR(50),
    department_name      VARCHAR(200),
    office_name          VARCHAR(200),
    officer_type         VARCHAR(50),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_co_email (email),
    INDEX idx_co_name (full_name(50))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### opportunity_poc
Junction table linking opportunities to their points of contact.

```sql
CREATE TABLE IF NOT EXISTS opportunity_poc (
    poc_id               INT AUTO_INCREMENT PRIMARY KEY,
    notice_id            VARCHAR(50) NOT NULL,
    officer_id           INT NOT NULL,
    poc_type             VARCHAR(20) NOT NULL DEFAULT 'PRIMARY',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_oppoc_opportunity FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_oppoc_officer FOREIGN KEY (officer_id) REFERENCES contracting_officer(officer_id),
    UNIQUE INDEX idx_oppoc_unique (notice_id, officer_id, poc_type),
    INDEX idx_oppoc_officer (officer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### proposal
Proposal lifecycle tracking, 1:1 with prospect.

```sql
CREATE TABLE IF NOT EXISTS proposal (
    proposal_id          INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id          INT NOT NULL,
    proposal_number      VARCHAR(50),
    submission_deadline  DATETIME,
    submitted_at         DATETIME,
    proposal_status      VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    estimated_value      DECIMAL(15,2),
    win_probability_pct  DECIMAL(5,2),
    lessons_learned      TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_proposal_prospect (prospect_id),
    CONSTRAINT fk_proposal_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    INDEX idx_proposal_status (proposal_status),
    INDEX idx_proposal_deadline (submission_deadline)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### proposal_document
File attachment metadata for proposal documents.

```sql
CREATE TABLE IF NOT EXISTS proposal_document (
    document_id          INT AUTO_INCREMENT PRIMARY KEY,
    proposal_id          INT NOT NULL,
    document_type        VARCHAR(50) NOT NULL,
    file_name            VARCHAR(255) NOT NULL,
    file_path            VARCHAR(500) NOT NULL,
    file_size_bytes      BIGINT,
    uploaded_by          INT,
    uploaded_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes                TEXT,
    CONSTRAINT fk_pdoc_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id) ON DELETE CASCADE,
    CONSTRAINT fk_pdoc_uploader FOREIGN KEY (uploaded_by) REFERENCES app_user(user_id) ON DELETE SET NULL,
    INDEX idx_pdoc_proposal (proposal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### proposal_milestone
Bid timeline tracking with planned vs actual dates.

```sql
CREATE TABLE IF NOT EXISTS proposal_milestone (
    milestone_id         INT AUTO_INCREMENT PRIMARY KEY,
    proposal_id          INT NOT NULL,
    milestone_name       VARCHAR(100) NOT NULL,
    due_date             DATE,
    completed_date       DATE,
    assigned_to          INT,
    status               VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    notes                TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pm_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id) ON DELETE CASCADE,
    CONSTRAINT fk_pm_assigned FOREIGN KEY (assigned_to) REFERENCES app_user(user_id) ON DELETE SET NULL,
    INDEX idx_pm_proposal (proposal_id),
    INDEX idx_pm_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### activity_log
Audit trail for all user actions in the web app.

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    activity_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT,
    action               VARCHAR(50) NOT NULL,
    entity_type          VARCHAR(50) NOT NULL,
    entity_id            VARCHAR(100),
    details              JSON,
    ip_address           VARCHAR(45),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_actlog_user FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    INDEX idx_activity_target (entity_type, entity_id),
    INDEX idx_activity_user_date (user_id, created_at),
    INDEX idx_activity_date (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### notification
In-app notification/alert queue.

```sql
CREATE TABLE IF NOT EXISTS notification (
    notification_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    notification_type    VARCHAR(50) NOT NULL,
    title                VARCHAR(200) NOT NULL,
    message              TEXT,
    entity_type          VARCHAR(50),
    entity_id            VARCHAR(100),
    is_read              CHAR(1) NOT NULL DEFAULT 'N',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at              DATETIME,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_notif_user_read (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### organization_invite
Pending email invitations to join an organization.

```sql
CREATE TABLE IF NOT EXISTS organization_invite (
    invite_id            INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    email                VARCHAR(255) NOT NULL,
    invite_code          VARCHAR(64) NOT NULL UNIQUE,
    org_role             VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by           INT NOT NULL,
    expires_at           DATETIME NOT NULL,
    accepted_at          DATETIME,
    CONSTRAINT fk_oi_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_oi_email (email),
    INDEX idx_oi_code (invite_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### organization_certification
Certifications held by an organization (WOSB, 8(a), HUBZone, etc.).

```sql
CREATE TABLE IF NOT EXISTS organization_certification (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    certification_type   VARCHAR(50) NOT NULL,
    certifying_agency    VARCHAR(100),
    certification_number VARCHAR(100),
    expiration_date      DATE,
    CONSTRAINT fk_oc_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_oc_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### organization_naics
NAICS codes an organization is registered/qualified under.

```sql
CREATE TABLE IF NOT EXISTS organization_naics (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    naics_code           VARCHAR(11) NOT NULL,
    is_primary           VARCHAR(1) NOT NULL,
    size_standard_met    VARCHAR(1) NOT NULL,
    CONSTRAINT fk_on_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_on_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### organization_past_performance
Past performance records for an organization (used in pWin/qualification scoring).

```sql
CREATE TABLE IF NOT EXISTS organization_past_performance (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    contract_number      VARCHAR(50),
    agency_name          VARCHAR(200),
    description          TEXT,
    contract_value       DECIMAL(15,2),
    start_date           DATE,
    end_date             DATE,
    CONSTRAINT fk_opp_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_opp_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## Table Count Summary

| Group | Tables | Purpose |
|-------|--------|---------|
| Reference (`ref_*`) | 11 | Lookup/classification data (NAICS, PSC, SBA, FIPS, set-aside, business types) |
| Entity | 10 | SAM.gov contractor data (includes stg_entity_raw) |
| Opportunity | 3 | Contract opportunities, history, relationships |
| Federal | 8 | Hierarchy, awards, rates, exclusions, subawards, spending (includes usaspending_load_checkpoint) |
| ETL | 6 | Load tracking, errors, quality rules, rate limits, health snapshots, data load requests |
| Prospecting | 6 | Sales pipeline, users, saved searches, organization |
| Raw Staging | 6 | API response preservation for replay/rebuild (stg_opportunity_raw, stg_fpds_award_raw, stg_usaspending_raw, stg_exclusion_raw, stg_fedhier_raw, stg_subaward_raw) |
| Web API | 12 | Auth, proposals, audit, notifications, contacts, org invites/certs/NAICS/past performance |
| **Total** | **62** | |
| **Views** | **9** | v_target_opportunities, v_competitor_analysis, v_entity_search, v_active_exclusions, v_base_awards, v_procurement_intelligence, v_incumbent_profile, v_expiring_contracts, ref_psc_code_latest |
