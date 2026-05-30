-- migrations/schema_drift_nullability_remediation.sql
-- Schema drift remediation: enforce NOT NULL on 5 columns whose live DB had
-- drifted to nullable while the DDL (and the loaders' actual behavior) treat
-- them as required.
--
-- Background: `health check-schema` (with nullability detection) found that
-- these 5 columns were NULLABLE in the live DB but NOT NULL in the table DDL.
-- Investigation confirmed every one is always populated by its loader and most
-- are members of a UNIQUE/PRIMARY key, so NOT NULL is the correct, intended
-- definition. On the prod DB (192.168.0.137) all 5 columns contained zero NULL
-- rows at remediation time, so tightening is data-safe.
--
-- Idempotent: re-running an ALTER ... MODIFY ... NOT NULL on a column that is
-- already NOT NULL is a successful no-op. If any environment DOES contain NULL
-- rows in these columns, the matching ALTER will fail loudly — that is correct;
-- there is no sensible value to backfill (e.g. match_method, raw_labor_category),
-- so the data must be investigated rather than silently defaulted.
--
-- Apply to: every environment (prod .137 first; then any local/dev DB created
-- before this migration). Fresh builds from tables/*.sql already create these
-- columns NOT NULL.
--
-- NOTE: ref_state_code.country_code (the 6th column from the same drift report)
-- needed no DB change — it is already NOT NULL via its PRIMARY KEY; only the DDL
-- (tables/10_reference.sql) was updated to declare NOT NULL explicitly.

USE fed_contracts;

ALTER TABLE canonical_labor_category
    MODIFY COLUMN category_group VARCHAR(100) NOT NULL;

ALTER TABLE labor_category_mapping
    MODIFY COLUMN raw_labor_category VARCHAR(200) NOT NULL;

ALTER TABLE labor_category_mapping
    MODIFY COLUMN match_method VARCHAR(20) NOT NULL
    COMMENT 'EXACT, FUZZY, PATTERN, MANUAL, UNMAPPED';

ALTER TABLE labor_rate_summary
    MODIFY COLUMN category_group VARCHAR(100) NOT NULL;

ALTER TABLE bls_cost_index
    MODIFY COLUMN series_id VARCHAR(50) NOT NULL;
