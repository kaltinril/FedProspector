-- migrations/123_data_load_request_retry_after.sql
-- Phase 123 backfill: add data_load_request.retry_after + idx_dlr_status_retry.
--
-- The retry_after column (vendor-API 429 deferral) and its (status, retry_after)
-- index shipped in tables/55_data_load_request.sql for Phase 123, but no
-- migration was written at the time. Environments created before that change
-- (e.g. local/dev DBs) are missing both, while prod already has them. This
-- migration reconciles those lagging environments.
--
-- Idempotent via information_schema guards; a no-op where already present.

USE fed_contracts;

DROP PROCEDURE IF EXISTS _add_dlr_retry_after;
DELIMITER //
CREATE PROCEDURE _add_dlr_retry_after()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'data_load_request'
          AND COLUMN_NAME = 'retry_after'
    ) THEN
        ALTER TABLE data_load_request
            ADD COLUMN retry_after DATETIME NULL
            COMMENT 'UTC. Set when vendor API returned 429; poller defers until this time. NULL otherwise.'
            AFTER result_summary;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = 'fed_contracts' AND TABLE_NAME = 'data_load_request'
          AND INDEX_NAME = 'idx_dlr_status_retry'
    ) THEN
        ALTER TABLE data_load_request
            ADD INDEX idx_dlr_status_retry (status, retry_after);
    END IF;
END //
DELIMITER ;
CALL _add_dlr_retry_after();
DROP PROCEDURE _add_dlr_retry_after;
