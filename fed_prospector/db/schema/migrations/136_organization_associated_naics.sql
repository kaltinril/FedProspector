-- migrations/136_organization_associated_naics.sql
-- Phase 136 Unit G: Associated NAICS (manual, user-prioritized list beyond the org's
-- registered organization_naics + linked-entity codes).
--
-- Creates the EF-Core-owned app table organization_associated_naics. This raw-SQL
-- migration mirrors the EF migration (AddOrganizationAssociatedNaics) so prod can be
-- created by hand. Keep this file, the EF migration, the snapshot, and the DDL
-- (fed_prospector/db/schema/tables/90_web_api.sql) in sync.
--
--   organization_id INT NOT NULL          -- references organization logically (NO FK, project convention)
--   naics_code      VARCHAR(11) NOT NULL  -- the 6-digit associated NAICS code
--   note            TEXT NULL             -- optional free-text note on why it's relevant
--   created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
--   UNIQUE KEY (organization_id, naics_code) -- dedup per org
--
-- NO foreign key to organization (project convention — see CLAUDE.md / feedback_no_fk_coupling).
--
-- IDEMPOTENT: CREATE TABLE IF NOT EXISTS. Safe to re-run.
--
-- APPLY STATUS: NOT YET APPLIED (dev or prod). Apply by hand to BOTH dev (127.0.0.1)
-- and prod (192.168.0.137), backing up first per the Phase 134 runbook.
-- Run from this dev box via E:\mysql\bin:
--   Prod:
--     & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 136_organization_associated_naics.sql"
--   Dev (localhost):
--     & "E:\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 136_organization_associated_naics.sql"
-- ============================================================

USE fed_contracts;

CREATE TABLE IF NOT EXISTS organization_associated_naics (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    naics_code           VARCHAR(11) NOT NULL,
    note                 TEXT NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_assoc_naics (organization_id, naics_code),
    INDEX idx_org_assoc_naics_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
