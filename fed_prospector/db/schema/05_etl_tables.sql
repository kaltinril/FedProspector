-- 05_etl_tables.sql
-- ETL operational tables (4 tables) - Load tracking and data quality

USE fed_contracts;

CREATE TABLE IF NOT EXISTS etl_load_log (
    load_id              INT AUTO_INCREMENT PRIMARY KEY,
    source_system        VARCHAR(50) NOT NULL,
    load_type            VARCHAR(20) NOT NULL,
    status               VARCHAR(20) NOT NULL,
    started_at           DATETIME NOT NULL,
    completed_at         DATETIME,
    records_read         INT DEFAULT 0,
    records_inserted     INT DEFAULT 0,
    records_updated      INT DEFAULT 0,
    records_unchanged    INT DEFAULT 0,
    records_errored      INT DEFAULT 0,
    error_message        TEXT,
    parameters           JSON,
    source_file          VARCHAR(500),
    INDEX idx_etl_source (source_system),
    INDEX idx_etl_date (started_at),
    INDEX idx_etl_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS etl_load_error (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    load_id              INT NOT NULL,
    record_identifier    VARCHAR(100),
    error_type           VARCHAR(50),
    error_message        TEXT,
    raw_data             TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_err_load (load_id),
    CONSTRAINT fk_err_load FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS etl_data_quality_rule (
    rule_id              INT AUTO_INCREMENT PRIMARY KEY,
    rule_name            VARCHAR(100) NOT NULL,
    description          TEXT,
    target_table         VARCHAR(100),
    target_column        VARCHAR(100),
    rule_type            VARCHAR(20),
    rule_definition      JSON,
    is_active            CHAR(1) DEFAULT 'Y',
    priority             INT DEFAULT 100
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS etl_rate_limit (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    source_system        VARCHAR(50) NOT NULL,
    request_date         DATE NOT NULL,
    requests_made        INT DEFAULT 0,
    max_requests         INT NOT NULL,
    last_request_at      DATETIME,
    UNIQUE KEY uk_rate_limit (source_system, request_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
