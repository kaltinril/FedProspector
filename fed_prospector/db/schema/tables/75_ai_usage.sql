-- tables/75_ai_usage.sql
-- AI API usage tracking (Phase 110E)

USE fed_contracts;

CREATE TABLE IF NOT EXISTS ai_usage_log (
    usage_id          INT AUTO_INCREMENT PRIMARY KEY,
    notice_id         VARCHAR(100) NOT NULL,
    attachment_id     INT,
    model             VARCHAR(50) NOT NULL,
    input_tokens      INT NOT NULL,
    output_tokens     INT NOT NULL,
    cache_read_tokens INT DEFAULT 0,
    cache_write_tokens INT DEFAULT 0,
    cost_usd          DECIMAL(10,6) NOT NULL,
    requested_by      INT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notice (notice_id),
    INDEX idx_created (created_at),
    INDEX idx_requested_by (requested_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
