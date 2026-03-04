-- tables/60_prospecting.sql
-- Sales pipeline / prospecting tables (5 tables) + organization (multi-tenancy)

USE fed_contracts;

CREATE TABLE IF NOT EXISTS organization (
    organization_id      INT AUTO_INCREMENT PRIMARY KEY,
    name                 VARCHAR(200) NOT NULL,
    slug                 VARCHAR(100) NOT NULL UNIQUE,
    is_active            CHAR(1) NOT NULL DEFAULT 'Y',
    max_users            INT NOT NULL DEFAULT 10,
    subscription_tier    VARCHAR(50) DEFAULT 'trial',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS app_user (
    user_id              INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    username             VARCHAR(50) NOT NULL UNIQUE,
    display_name         VARCHAR(100) NOT NULL,
    email                VARCHAR(200),
    password_hash        VARCHAR(255),
    role                 VARCHAR(20) DEFAULT 'USER',
    last_login_at        DATETIME,
    is_active            CHAR(1) DEFAULT 'Y',
    is_admin             CHAR(1) NOT NULL DEFAULT 'N',
    mfa_enabled          CHAR(1) NOT NULL DEFAULT 'N',
    org_role             VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by           INT,
    invite_accepted_at   DATETIME,
    is_system_admin      TINYINT(1) NOT NULL DEFAULT 0,
    force_password_change CHAR(1) NOT NULL DEFAULT 'N',
    failed_login_attempts INT NOT NULL DEFAULT 0,
    locked_until         DATETIME,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    CONSTRAINT fk_user_invited_by FOREIGN KEY (invited_by) REFERENCES app_user(user_id),
    INDEX idx_user_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prospect (
    prospect_id          INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    notice_id            VARCHAR(100) NOT NULL,
    assigned_to          INT,
    capture_manager_id   INT,
    status               VARCHAR(30) NOT NULL DEFAULT 'NEW',
    proposal_status      VARCHAR(20),
    priority             VARCHAR(10) DEFAULT 'MEDIUM',
    decision_date        DATE,
    bid_submitted_date   DATE,
    estimated_value      DECIMAL(15,2),
    estimated_effort_hours DECIMAL(10,2),
    win_probability      DECIMAL(5,2),
    go_no_go_score       DECIMAL(5,2),
    teaming_required     CHAR(1) DEFAULT 'N',
    estimated_proposal_cost DECIMAL(10,2),
    estimated_gross_margin_pct DECIMAL(5,2),
    proposal_due_days    INT,
    outcome              VARCHAR(20),
    outcome_date         DATE,
    outcome_notes        TEXT,
    contract_award_id    VARCHAR(50),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_prospect_notice (organization_id, notice_id),
    CONSTRAINT fk_prospect_opp FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_prospect_user FOREIGN KEY (assigned_to) REFERENCES app_user(user_id),
    CONSTRAINT fk_prospect_capture_mgr FOREIGN KEY (capture_manager_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_prospect_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_prospect_status (status),
    INDEX idx_prospect_user (assigned_to),
    INDEX idx_prospect_priority (priority),
    INDEX idx_prospect_capture_mgr (capture_manager_id),
    INDEX idx_prospect_org (organization_id)
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
    uei_sam              VARCHAR(12),
    app_user_id          INT,
    role                 VARCHAR(50),
    notes                TEXT,
    proposed_hourly_rate DECIMAL(10,2),
    commitment_pct       DECIMAL(5,2),
    CONSTRAINT fk_ptm_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    CONSTRAINT fk_team_app_user FOREIGN KEY (app_user_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    INDEX idx_ptm_entity (uei_sam),
    INDEX idx_ptm_app_user (app_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS saved_search (
    search_id            INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
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
    CONSTRAINT fk_ss_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    CONSTRAINT fk_ss_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_ss_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
