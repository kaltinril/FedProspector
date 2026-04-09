-- Competition summary pre-computed from usaspending_award (28.7M rows).
-- Refreshed after each usaspending load for sub-millisecond scoring lookups.
-- Source: Phase 115I, updated Phase 115L (CGAC-based agency dimension)

CREATE TABLE IF NOT EXISTS usaspending_award_summary (
    naics_code        VARCHAR(11)    NOT NULL,
    agency_cgac       VARCHAR(10)    NOT NULL,
    agency_name       VARCHAR(255)   NOT NULL DEFAULT '',
    vendor_count      INT            NOT NULL DEFAULT 0,
    contract_count    INT            NOT NULL DEFAULT 0,
    total_value       DECIMAL(18,2)  NOT NULL DEFAULT 0.00,
    computed_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (naics_code, agency_cgac)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- =============================================================================
-- Migration: Phase 115L — Switch to CGAC-based agency dimension
-- Run against existing databases that already have the summary table.
-- =============================================================================
-- ALTER TABLE usaspending_award_summary ADD COLUMN agency_cgac VARCHAR(10) NOT NULL DEFAULT '' AFTER naics_code;
-- ALTER TABLE usaspending_award_summary DROP PRIMARY KEY, ADD PRIMARY KEY (naics_code, agency_cgac);
