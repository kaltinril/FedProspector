-- tables/90_web_api.sql
-- Web API production tables (9 tables) - Authentication, proposals, audit, notifications, contacts, invites

USE fed_contracts;

CREATE TABLE IF NOT EXISTS app_session (
    session_id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    token_hash           CHAR(64) NOT NULL,
    refresh_token_hash   CHAR(64),
    issued_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at           DATETIME NOT NULL,
    revoked_at           DATETIME,
    revoked_reason       VARCHAR(100),
    ip_address           VARCHAR(45),
    user_agent           VARCHAR(500),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    UNIQUE INDEX idx_session_token (token_hash),
    INDEX idx_session_refresh_token (refresh_token_hash),
    INDEX idx_session_user (user_id),
    INDEX idx_session_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS organization_invite (
    invite_id            INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    email                VARCHAR(255) NOT NULL,
    invite_code          VARCHAR(64) NOT NULL UNIQUE,
    org_role             VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by           INT NOT NULL,
    expires_at           DATETIME NOT NULL,
    accepted_at          DATETIME,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_invite_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    CONSTRAINT fk_invite_user FOREIGN KEY (invited_by) REFERENCES app_user(user_id),
    INDEX idx_invite_org (organization_id),
    INDEX idx_invite_email (email),
    INDEX idx_invite_code (invite_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contracting_officer (
    officer_id           INT AUTO_INCREMENT PRIMARY KEY,
    full_name            VARCHAR(500) NOT NULL,
    email                VARCHAR(200),
    phone                VARCHAR(100),
    fax                  VARCHAR(100),
    title                VARCHAR(200),
    department_name      VARCHAR(200),
    office_name          VARCHAR(200),
    officer_type         VARCHAR(50),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_co_name_email (full_name(100), email(100)),
    INDEX idx_co_email (email),
    INDEX idx_co_name (full_name(50))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opportunity_poc (
    poc_id               INT AUTO_INCREMENT PRIMARY KEY,
    notice_id            VARCHAR(100) NOT NULL,
    officer_id           INT NOT NULL,
    poc_type             VARCHAR(20) NOT NULL DEFAULT 'PRIMARY',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_oppoc_opportunity FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_oppoc_officer FOREIGN KEY (officer_id) REFERENCES contracting_officer(officer_id),
    UNIQUE INDEX idx_oppoc_unique (notice_id, officer_id, poc_type),
    INDEX idx_oppoc_officer (officer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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

CREATE TABLE IF NOT EXISTS activity_log (
    activity_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    user_id              INT,
    action               VARCHAR(50) NOT NULL,
    entity_type          VARCHAR(50) NOT NULL,
    entity_id            VARCHAR(100),
    details              JSON,
    ip_address           VARCHAR(45),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_actlog_user FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_actlog_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    INDEX idx_activity_target (entity_type, entity_id),
    INDEX idx_activity_user_date (user_id, created_at),
    INDEX idx_activity_date (created_at),
    INDEX idx_actlog_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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

-- Company profile child tables (Phase 44.6 — consolidated from EF Core migration)

CREATE TABLE IF NOT EXISTS organization_certification (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    certification_type   VARCHAR(50) NOT NULL,
    certifying_agency    VARCHAR(100),
    certification_number VARCHAR(100),
    expiration_date      DATETIME,
    is_active            VARCHAR(1) NOT NULL,
    source               VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orgcert_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id) ON DELETE CASCADE,
    INDEX idx_orgcert_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS organization_naics (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    naics_code           VARCHAR(11) NOT NULL,
    is_primary           VARCHAR(1) NOT NULL,
    size_standard_met    VARCHAR(1) NOT NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orgnaics_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id) ON DELETE CASCADE,
    INDEX idx_orgnaics_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS organization_past_performance (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    contract_number      VARCHAR(50),
    agency_name          VARCHAR(200),
    description          TEXT,
    naics_code           VARCHAR(11),
    contract_value       DECIMAL(18,2),
    period_start         DATETIME,
    period_end           DATETIME,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orgperf_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id) ON DELETE CASCADE,
    INDEX idx_orgperf_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Organization intelligence (Phase 91 — track entities of interest per org)

CREATE TABLE IF NOT EXISTS organization_entity (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    uei_sam         VARCHAR(12) NOT NULL,
    partner_uei     VARCHAR(13) NULL,      -- UEI used for JV partnership filings
    relationship    VARCHAR(20) NOT NULL,
    is_active       CHAR(1) NOT NULL DEFAULT 'Y',
    added_by        INT NULL,
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_entity (organization_id, uei_sam, relationship),
    CONSTRAINT fk_oe_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    CONSTRAINT fk_oe_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam),
    CONSTRAINT fk_oe_user FOREIGN KEY (added_by) REFERENCES app_user(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- Migration: Phase 44.3 Batch 1 (Item 1.1) — POC data loading
-- Run against existing databases that already have the contracting_officer table.
-- =============================================================================
-- ALTER TABLE contracting_officer ADD COLUMN title VARCHAR(200) AFTER fax;
-- ALTER TABLE contracting_officer ADD UNIQUE INDEX idx_co_name_email (full_name(100), email(100));
