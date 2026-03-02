-- Phase 14.5: Multi-tenancy schema changes
-- Run: /d/mysql/bin/mysql.exe -u fed_app -pfed_app_2026 fed_contracts < fed_prospector/db/schema/migrations/phase14_5_multi_tenancy.sql
-- All changes are additive (new tables and new nullable/defaulted columns). Existing data is preserved.

USE fed_contracts;

-- ============================================================
-- 1. organization -- New table for multi-tenancy
-- ============================================================
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

-- ============================================================
-- 2. app_user -- Add multi-tenancy and invite columns
-- ============================================================
ALTER TABLE app_user
    ADD COLUMN organization_id INT NOT NULL AFTER user_id,
    ADD COLUMN org_role VARCHAR(50) NOT NULL DEFAULT 'member' AFTER mfa_enabled,
    ADD COLUMN invited_by INT AFTER org_role,
    ADD COLUMN invite_accepted_at DATETIME AFTER invited_by,
    ADD COLUMN force_password_change CHAR(1) NOT NULL DEFAULT 'N' AFTER invite_accepted_at,
    ADD CONSTRAINT fk_user_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    ADD CONSTRAINT fk_user_invited_by FOREIGN KEY (invited_by) REFERENCES app_user(user_id),
    ADD INDEX idx_user_org (organization_id);

-- ============================================================
-- 3. organization_invite -- New table for org invitations
-- ============================================================
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

-- ============================================================
-- 4. app_session -- Add revoked_reason column
-- ============================================================
ALTER TABLE app_session
    ADD COLUMN revoked_reason VARCHAR(100) AFTER revoked_at;

-- ============================================================
-- 5. prospect -- Add organization_id for multi-tenancy
-- ============================================================
ALTER TABLE prospect
    ADD COLUMN organization_id INT NOT NULL AFTER prospect_id,
    ADD CONSTRAINT fk_prospect_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    ADD INDEX idx_prospect_org (organization_id);

-- ============================================================
-- 6. saved_search -- Add organization_id for multi-tenancy
-- ============================================================
ALTER TABLE saved_search
    ADD COLUMN organization_id INT NOT NULL AFTER search_id,
    ADD CONSTRAINT fk_ss_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    ADD INDEX idx_ss_org (organization_id);

-- ============================================================
-- 7. activity_log -- Add organization_id for multi-tenancy
-- ============================================================
ALTER TABLE activity_log
    ADD COLUMN organization_id INT NOT NULL AFTER activity_id,
    ADD CONSTRAINT fk_actlog_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    ADD INDEX idx_actlog_org (organization_id);

-- ============================================================
-- 8. Seed data -- Default development organization
-- ============================================================
INSERT INTO organization (name, slug, is_active, max_users, subscription_tier)
VALUES ('Dev Organization', 'dev-org', 'Y', 50, 'premium');
