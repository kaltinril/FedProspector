-- Migration 015: Add usaspending_load_checkpoint table
-- Applied: 2026-03-08
-- Adds checkpoint/resume tracking for USASpending bulk CSV loads

USE fed_contracts;

CREATE TABLE IF NOT EXISTS usaspending_load_checkpoint (
    checkpoint_id INT AUTO_INCREMENT PRIMARY KEY,
    load_id INT NOT NULL,
    fiscal_year INT NOT NULL,
    csv_file_name VARCHAR(255) NOT NULL,
    status ENUM('IN_PROGRESS', 'COMPLETE', 'FAILED') NOT NULL DEFAULT 'IN_PROGRESS',
    completed_batches INT NOT NULL DEFAULT 0,
    total_rows_loaded INT NOT NULL DEFAULT 0,
    archive_hash VARCHAR(130) NULL COMMENT 'SHA-256 hash (first 1MB) + file size for FY dedup',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    UNIQUE KEY uq_load_csv (load_id, csv_file_name),
    KEY idx_fy_hash (fiscal_year, archive_hash),
    CONSTRAINT fk_checkpoint_load FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
