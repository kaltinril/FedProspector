-- Teaming partner capability summary, pre-computed from v_partner_capability_match.
-- The view does a 6-way LEFT JOIN + GROUP_CONCAT aggregate over the whole
-- entity table (>90s in prod) and its NAICS filter (LIKE '%code%' over a
-- GROUP_CONCAT) cannot push down, so MySQL materializes the full aggregate
-- before filtering.  This table is refreshed during the daily load
-- (`refresh partner-capability`) so the Teaming Partner Search and Gap
-- Analysis tabs read pre-aggregated rows instead of scanning the view.
-- Source: Phase 138 (performance).
--
-- Mirrors the output columns of v_partner_capability_match that
-- TeamingService consumes (Partner Search + Gap Analysis).

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

-- Child table makes the NAICS filter indexable: instead of a substring match
-- against the naics_codes GROUP_CONCAT, the service joins on a single
-- (naics_code) lookup.  One row per (uei_sam, naics_code) sourced from
-- entity_naics for active entities (the same NAICS dimension the view's
-- naics_codes column aggregates).  No FKs per project convention.
CREATE TABLE IF NOT EXISTS partner_capability_naics (
    uei_sam      VARCHAR(12)  NOT NULL,
    naics_code   VARCHAR(11)  NOT NULL,
    PRIMARY KEY (uei_sam, naics_code),
    INDEX idx_pcn_naics (naics_code),
    INDEX idx_pcn_uei (uei_sam)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
