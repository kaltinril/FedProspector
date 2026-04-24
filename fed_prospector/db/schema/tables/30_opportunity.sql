-- tables/30_opportunity.sql
-- Opportunity tables (3 tables) - Contract opportunities from SAM.gov

USE fed_contracts;

CREATE TABLE IF NOT EXISTS opportunity (
    notice_id            VARCHAR(100) NOT NULL,
    title                VARCHAR(500),
    solicitation_number  VARCHAR(100),
    department_name      VARCHAR(200),
    department_cgac      VARCHAR(10),
    sub_tier             VARCHAR(200),
    sub_tier_code        VARCHAR(20),
    office               VARCHAR(200),
    posted_date          DATE,
    response_deadline    DATETIME,
    archive_date         DATE,
    type                 VARCHAR(50),
    base_type            VARCHAR(50),
    set_aside_code       VARCHAR(20),
    set_aside_description VARCHAR(200),
    classification_code  VARCHAR(10),
    naics_code           VARCHAR(6),
    pop_state            VARCHAR(6),       -- ISO 3166-2 subdivision: US='VA', foreign='IN-MH'
    pop_zip              VARCHAR(20),      -- Military APO/FPO zips can be 17+ chars
    pop_country          VARCHAR(3),
    pop_city             VARCHAR(100),
    period_of_performance_start DATE,      -- Reserved: not in public Opportunities API v2 response
    period_of_performance_end DATE,        -- Reserved: not in public Opportunities API v2 response
    security_clearance_required CHAR(1),   -- Reserved: not in public Opportunities API v2 response
    incumbent_uei        VARCHAR(13),      -- Reserved: not in public Opportunities API v2 response
    incumbent_name       VARCHAR(200),     -- Reserved: not in public Opportunities API v2 response
    contract_vehicle_type VARCHAR(50),     -- Reserved: not in public Opportunities API v2 response
    pricing_structure     VARCHAR(50),     -- Reserved: not in public Opportunities API v2 response
    place_of_performance_detail VARCHAR(200), -- Reserved: not in public Opportunities API v2 response
    estimated_contract_value DECIMAL(15,2), -- Reserved: not in public Opportunities API v2 response
    active               CHAR(1) DEFAULT 'Y',
    award_number         VARCHAR(500),
    award_date           DATE,
    award_amount         DECIMAL(15,2),
    awardee_uei          VARCHAR(13),
    awardee_name         VARCHAR(500),
    awardee_cage_code    VARCHAR(10),
    awardee_city         VARCHAR(100),
    awardee_state        VARCHAR(50),
    awardee_zip          VARCHAR(20),      -- Military APO/FPO zips can be 17+ chars
    full_parent_path_name VARCHAR(500),
    full_parent_path_code VARCHAR(200),
    description_url      VARCHAR(500),      -- URL to fetch description text via SAM.gov API
    description_text     LONGTEXT,          -- Cached description fetched from description_url
    description_fetch_failures INT NOT NULL DEFAULT 0,  -- Count of consecutive 404/gone failures; stops retry at 3
    link                 VARCHAR(500),
    resource_links       JSON,
    contracting_office_id VARCHAR(20),
    fh_org_id            INT DEFAULT NULL,
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
    INDEX idx_opp_sol (solicitation_number),
    KEY idx_opp_department (department_name),
    INDEX idx_opp_dept_cgac (department_cgac),
    INDEX idx_opp_fh_org (fh_org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opportunity_history (
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

CREATE TABLE IF NOT EXISTS opportunity_relationship (
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

-- =============================================================================
-- Migration: Phase 44.3 Batch 1 (Items 1.2, 1.3) — Awardee location + full parent path
-- Run against existing databases that already have the opportunity table.
-- =============================================================================
-- ALTER TABLE opportunity ADD COLUMN awardee_cage_code VARCHAR(10) AFTER awardee_name;
-- ALTER TABLE opportunity ADD COLUMN awardee_city VARCHAR(100) AFTER awardee_cage_code;
-- ALTER TABLE opportunity ADD COLUMN awardee_state VARCHAR(50) AFTER awardee_city;
-- ALTER TABLE opportunity ADD COLUMN awardee_zip VARCHAR(10) AFTER awardee_state;
-- ALTER TABLE opportunity ADD COLUMN full_parent_path_name VARCHAR(500) AFTER awardee_zip;
-- ALTER TABLE opportunity ADD COLUMN full_parent_path_code VARCHAR(200) AFTER full_parent_path_name;

-- =============================================================================
-- Migration: Phase 44.3 Item 3.5 — Description text caching
-- Run against existing databases that already have the opportunity table.
-- =============================================================================
-- ALTER TABLE opportunity ADD COLUMN description_text LONGTEXT AFTER description_url;

-- =============================================================================
-- Migration: Phase 115L — Agency code normalization
-- Run against existing databases that already have the opportunity table.
-- =============================================================================
-- ALTER TABLE opportunity ADD COLUMN department_cgac VARCHAR(10) DEFAULT NULL AFTER department_name;
-- ALTER TABLE opportunity ADD COLUMN sub_tier_code VARCHAR(20) DEFAULT NULL AFTER sub_tier;
-- ALTER TABLE opportunity ADD INDEX idx_opp_dept_cgac (department_cgac);
-- ALTER TABLE opportunity ADD COLUMN fh_org_id INT DEFAULT NULL;
-- ALTER TABLE opportunity ADD INDEX idx_opp_fh_org (fh_org_id);

-- =============================================================================
-- Migration: Phase 116 — Description fetch failure tracking
-- Run against existing databases that already have the opportunity table.
-- =============================================================================
-- ALTER TABLE opportunity ADD COLUMN description_fetch_failures INT NOT NULL DEFAULT 0 AFTER description_text;
