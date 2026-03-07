-- Phase 44.6: Schema Drift Remediation
-- Applied: 2026-03-07
-- Fixes findings 1-4 from schema drift audit (Phase 44.5)
--
-- Finding 1a/1b (missing tables) already resolved - tables exist.
-- This migration addresses findings 2, 3, and 4.

USE fed_contracts;

-- ============================================================================
-- Finding 2: Missing indexes (4 indexes)
-- These indexes exist in DDL but were never applied to the live database.
-- ============================================================================

-- 2a: fpds_contract - index on ultimate_completion_date for expiring-contract queries
ALTER TABLE `fpds_contract` ADD INDEX `idx_fpds_ultimate_completion` (`ultimate_completion_date`);

-- 2b: fpds_contract - prefix index on idv_piid for IDV lookups
ALTER TABLE `fpds_contract` ADD INDEX `idx_fpds_idv_piid` (`idv_piid`(50));

-- 2c: sam_exclusion - unique key for deduplication during loads
ALTER TABLE `sam_exclusion` ADD UNIQUE INDEX `uk_excl_key` (`uei`, `exclusion_type`, `activation_date`);

-- 2d: usaspending_award - index on last_modified_date for incremental loads
ALTER TABLE `usaspending_award` ADD INDEX `idx_usa_modified` (`last_modified_date`);

-- ============================================================================
-- Finding 3: Column type mismatches
-- Live DB types differ from DDL definitions.
-- ============================================================================

-- 3a: opportunity_poc.notice_id is VARCHAR(50) but DDL says VARCHAR(100)
--     Must match opportunity.notice_id which is VARCHAR(100)
--     Need to drop/re-add FK because MySQL won't allow column resize with FK
ALTER TABLE `opportunity_poc` DROP FOREIGN KEY `fk_oppoc_opportunity`;
ALTER TABLE `opportunity_poc` MODIFY COLUMN `notice_id` VARCHAR(100) NOT NULL;
ALTER TABLE `opportunity_poc` ADD CONSTRAINT `fk_oppoc_opportunity` FOREIGN KEY (`notice_id`) REFERENCES `opportunity`(`notice_id`);

-- 3b: usaspending_award.record_hash is VARCHAR(64) but DDL says CHAR(64)
--     All other record_hash columns use CHAR(64) for fixed-length SHA-256
ALTER TABLE `usaspending_award` MODIFY COLUMN `record_hash` CHAR(64);

-- ============================================================================
-- Finding 4: prospect.uk_prospect_notice wrong scope (CRITICAL)
-- Index is on (notice_id) only, but DDL specifies (organization_id, notice_id).
-- Without organization_id, multi-tenant isolation is broken - one org adding
-- a prospect blocks all other orgs from adding the same notice_id.
-- ============================================================================

-- Add a plain index on notice_id first so the FK fk_prospect_opp can use it
-- (MySQL requires an index starting with the FK column)
ALTER TABLE `prospect` ADD INDEX `idx_prospect_notice_id` (`notice_id`);

-- Now we can safely drop the incorrect single-column unique key
ALTER TABLE `prospect` DROP INDEX `uk_prospect_notice`;

-- Re-create with correct multi-tenant scope
ALTER TABLE `prospect` ADD UNIQUE INDEX `uk_prospect_notice` (`organization_id`, `notice_id`);
