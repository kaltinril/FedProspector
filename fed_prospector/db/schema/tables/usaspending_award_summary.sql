-- Competition summary pre-computed from usaspending_award (28.7M rows).
-- Refreshed after each usaspending load for sub-millisecond scoring lookups.
-- Source: Phase 115I

CREATE TABLE IF NOT EXISTS usaspending_award_summary (
    naics_code        VARCHAR(11)    NOT NULL,
    agency_name       VARCHAR(255)   NOT NULL,
    vendor_count      INT            NOT NULL DEFAULT 0,
    contract_count    INT            NOT NULL DEFAULT 0,
    total_value       DECIMAL(18,2)  NOT NULL DEFAULT 0.00,
    computed_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (naics_code, agency_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
