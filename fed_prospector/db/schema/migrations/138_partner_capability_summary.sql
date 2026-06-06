-- Phase 138: Materialize v_partner_capability_match into a daily-refreshed summary
-- Date: 2026-06-05
--
-- v_partner_capability_match (>90s, broken in prod) backs the Teaming Partner
-- Search and Gap Analysis tabs.  Its NAICS filter (LIKE '%code%' over a
-- GROUP_CONCAT) cannot push down, forcing a full materialization of the 6-way
-- aggregate before filtering.  This migration creates a pre-computed summary
-- table (refreshed during the daily load via `refresh partner-capability`) plus
-- a child NAICS table so the NAICS filter is an indexed join instead of a
-- substring scan.
--
-- *** MANUAL APPLY REQUIRED ***
-- Apply BY HAND to prod (192.168.0.137 / DESKTOP-D58HJ5B, db fed_contracts).
-- NOT yet applied to any database.  Idempotent (CREATE TABLE IF NOT EXISTS) —
-- safe to re-run.  After applying, run `python main.py refresh partner-capability`
-- once to populate (the daily job will keep it fresh thereafter).
--   & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> \
--       fed_contracts -e "source 138_partner_capability_summary.sql"

USE fed_contracts;

-- Pre-aggregated capability rows (one per active entity), mirroring the
-- v_partner_capability_match output columns consumed by TeamingService.
CREATE TABLE IF NOT EXISTS partner_capability_match (
    uei_sam                 VARCHAR(12)    NOT NULL,
    legal_business_name     VARCHAR(255)   NULL,
    state                   VARCHAR(100)   NULL,
    naics_codes             TEXT           NULL,
    psc_codes               TEXT           NULL,
    certifications          TEXT           NULL,
    agencies_worked_with    TEXT           NULL,
    performance_naics_codes TEXT           NULL,
    contract_count          INT            NOT NULL DEFAULT 0,
    total_contract_value    DECIMAL(18,2)  NOT NULL DEFAULT 0.00,
    computed_at             DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (uei_sam),
    INDEX idx_pcm_contract_count (contract_count),
    INDEX idx_pcm_total_value (total_contract_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Indexable NAICS dimension: one row per (uei_sam, naics_code) so the
-- Partner Search / Gap Analysis NAICS filter is a single-key lookup join
-- rather than a GROUP_CONCAT substring match.  No FKs per project convention.
CREATE TABLE IF NOT EXISTS partner_capability_naics (
    uei_sam      VARCHAR(12)  NOT NULL,
    naics_code   VARCHAR(11)  NOT NULL,
    PRIMARY KEY (uei_sam, naics_code),
    INDEX idx_pcn_naics (naics_code),
    INDEX idx_pcn_uei (uei_sam)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
