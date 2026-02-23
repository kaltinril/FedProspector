-- 03_opportunity_tables.sql
-- Opportunity tables (2 tables) - Contract opportunities from SAM.gov

USE fed_contracts;

CREATE TABLE IF NOT EXISTS opportunity (
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
    classification_code  VARCHAR(10),
    naics_code           VARCHAR(6),
    pop_state            VARCHAR(2),
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
