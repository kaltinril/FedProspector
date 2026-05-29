-- tables/55_data_load_request.sql
-- On-demand data loading request queue (Phase 43)
--
-- Allowed status values (free-form VARCHAR; no CHECK constraint enforced):
--   PENDING         - newly inserted, waiting for poller pickup
--   RUNNING         - in-flight (poller has claimed it)
--   COMPLETED       - finished successfully
--   FAILED          - permanent failure (error_message populated)
--   CANCELLED       - cleared from queue (e.g. --clear-queue on startup)
--   PENDING_RETRY   - deferred due to vendor API rate-limit (429); poller
--                     will reattempt after `retry_after` (UTC). See Phase 123.

USE fed_contracts;

CREATE TABLE IF NOT EXISTS data_load_request (
    request_id       INT AUTO_INCREMENT PRIMARY KEY,
    request_type     VARCHAR(30) NOT NULL,
    lookup_key       VARCHAR(200) NOT NULL,
    lookup_key_type  VARCHAR(20) NOT NULL DEFAULT 'PIID',
    status           VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    requested_by     INT,
    requested_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at       DATETIME,
    completed_at     DATETIME,
    load_id          INT,
    error_message    TEXT,
    result_summary   JSON,
    retry_after      DATETIME NULL COMMENT 'UTC. Set when vendor API returned 429; poller defers until this time. NULL otherwise.',
    INDEX idx_dlr_status (status),
    INDEX idx_dlr_lookup (lookup_key, request_type),
    INDEX idx_dlr_requested (requested_at),
    INDEX idx_dlr_status_retry (status, retry_after)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
