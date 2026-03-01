-- tables/60_prospecting.sql
-- Sales pipeline / prospecting tables (4 tables)

USE fed_contracts;

CREATE TABLE IF NOT EXISTS app_user (
    user_id              INT AUTO_INCREMENT PRIMARY KEY,
    username             VARCHAR(50) NOT NULL UNIQUE,
    display_name         VARCHAR(100) NOT NULL,
    email                VARCHAR(200),
    role                 VARCHAR(20) DEFAULT 'USER',
    is_active            CHAR(1) DEFAULT 'Y',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prospect (
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
    UNIQUE KEY uk_prospect_notice (notice_id),
    CONSTRAINT fk_prospect_opp FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_prospect_user FOREIGN KEY (assigned_to) REFERENCES app_user(user_id),
    INDEX idx_prospect_status (status),
    INDEX idx_prospect_user (assigned_to),
    INDEX idx_prospect_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prospect_note (
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

CREATE TABLE IF NOT EXISTS prospect_team_member (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id          INT NOT NULL,
    uei_sam              VARCHAR(12) NOT NULL,
    role                 VARCHAR(50),
    notes                TEXT,
    CONSTRAINT fk_ptm_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    INDEX idx_ptm_entity (uei_sam)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS saved_search (
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
