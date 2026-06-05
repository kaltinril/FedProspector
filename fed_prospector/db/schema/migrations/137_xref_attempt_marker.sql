-- migrations/137_xref_attempt_marker.sql
-- Phase 137: Cross-reference round-robin fairness marker.
--
-- Adds a `last_xref_attempt_at` timestamp + supporting index to
-- `document_identifier_ref` so the identifier cross-reference matcher can
-- rotate through the unmatched backlog fairly instead of re-grinding the same
-- lowest-ref_id block on every nightly run.
--
-- IMPORTANT: `last_xref_attempt_at` is a FAIRNESS / ROUND-ROBIN ordering marker
-- ONLY. It is NOT a "give up" flag. The matcher selection NEVER filters rows out
-- by this column — it only ORDERs by it (NULL = never attempted = highest
-- priority, then oldest-attempted first). Every row with matched_table IS NULL
-- remains eligible for re-checking forever, on its next rotation and whenever new
-- reference data lands. A match removes a row from the pool only via
-- matched_table being set, never via this marker.
--
-- Idempotent via information_schema guards; safe to re-run. NO backfill: a NULL
-- value is the intended "never attempted" state and sorts first.

USE fed_contracts;

DROP PROCEDURE IF EXISTS _add_xref_attempt_marker;
DELIMITER //
CREATE PROCEDURE _add_xref_attempt_marker()
BEGIN
    -- document_identifier_ref column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'document_identifier_ref'
          AND COLUMN_NAME = 'last_xref_attempt_at'
    ) THEN
        ALTER TABLE document_identifier_ref
            ADD COLUMN last_xref_attempt_at DATETIME NULL
            COMMENT 'Phase 137: round-robin fairness marker for cross-reference ordering; NOT a give-up flag. NULL = never attempted (sorts first). Unmatched rows stay eligible forever.'
            AFTER matched_id;
    END IF;

    -- document_identifier_ref index
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'document_identifier_ref'
          AND INDEX_NAME = 'idx_dir_xref_attempt'
    ) THEN
        ALTER TABLE document_identifier_ref
            ADD INDEX idx_dir_xref_attempt (last_xref_attempt_at);
    END IF;
END //
DELIMITER ;
CALL _add_xref_attempt_marker();
DROP PROCEDURE _add_xref_attempt_marker;
