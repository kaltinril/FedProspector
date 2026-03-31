-- ============================================================
-- 36_attachment.sql — Attachment tables (normalized 6-table model)
-- Phase 110ZZZ: Attachment deduplication
--
-- Six tables:
--   1. sam_attachment         — per-file download data (one row per unique resource GUID)
--   2. attachment_document    — per-document content data (1:1 with sam_attachment for now)
--   3. opportunity_attachment — many-to-many mapping (lean join table, composite PK)
--   4. document_intel_summary — per-document intel conclusions
--   5. document_intel_evidence — citations/evidence for document-level intel
--   6. opportunity_attachment_summary — per-opportunity rollup
-- ============================================================

CREATE TABLE IF NOT EXISTS sam_attachment (
    attachment_id          INT AUTO_INCREMENT PRIMARY KEY,
    resource_guid          CHAR(32) NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    filename               VARCHAR(500),
    file_size_bytes        BIGINT,
    file_path              VARCHAR(500),
    download_status        ENUM('pending','downloaded','failed','skipped') DEFAULT 'pending',
    content_hash           CHAR(64),
    downloaded_at          DATETIME,
    download_retry_count   INT NOT NULL DEFAULT 0,
    skip_reason            VARCHAR(100),
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_resource_guid (resource_guid),
    INDEX idx_status (download_status),
    INDEX idx_content_hash (content_hash),
    INDEX idx_url (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS attachment_document (
    document_id            INT AUTO_INCREMENT PRIMARY KEY,
    attachment_id          INT NOT NULL,
    filename               VARCHAR(500),
    content_type           VARCHAR(100),
    extracted_text         LONGTEXT,
    page_count             INT,
    is_scanned             TINYINT DEFAULT 0,
    ocr_quality            ENUM('good','fair','poor'),
    extraction_status      ENUM('pending','extracted','failed','unsupported') DEFAULT 'pending',
    text_hash              CHAR(64),
    extracted_at           DATETIME,
    extraction_retry_count INT DEFAULT 0,
    keyword_analyzed_at    DATETIME     DEFAULT NULL,
    ai_analyzed_at         DATETIME     DEFAULT NULL,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_attachment (attachment_id),
    INDEX idx_status (extraction_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opportunity_attachment (
    notice_id              VARCHAR(100) NOT NULL,
    attachment_id          INT NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notice_id, attachment_id),
    INDEX idx_attachment (attachment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_intel_summary (
    intel_id               INT AUTO_INCREMENT PRIMARY KEY,
    document_id            INT NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword') NOT NULL,
    source_text_hash       CHAR(64),
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  TEXT,
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (document_id, extraction_method),
    INDEX idx_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_intel_evidence (
    evidence_id            INT AUTO_INCREMENT PRIMARY KEY,
    intel_id               INT NOT NULL,
    field_name             VARCHAR(50) NOT NULL,
    document_id            INT,
    source_filename        VARCHAR(500),
    page_number            INT,
    char_offset_start      INT,
    char_offset_end        INT,
    matched_text           VARCHAR(500),
    surrounding_context    TEXT,
    pattern_name           VARCHAR(100),
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword') NOT NULL,
    confidence             ENUM('high','medium','low') NOT NULL,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_intel (intel_id),
    INDEX idx_document (document_id),
    INDEX idx_field (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Phase 128: Federal Identifier Extraction
CREATE TABLE IF NOT EXISTS document_identifier_ref (
    ref_id              INT AUTO_INCREMENT PRIMARY KEY,
    document_id         INT NOT NULL,
    identifier_type     VARCHAR(30) NOT NULL,
    identifier_value    VARCHAR(200) NOT NULL,
    raw_text            VARCHAR(500),
    context             TEXT,
    char_offset_start   INT,
    char_offset_end     INT,
    confidence          ENUM('high','medium','low') DEFAULT 'medium',
    matched_table       VARCHAR(50),
    matched_column      VARCHAR(50),
    matched_id          VARCHAR(200),
    last_load_id        INT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_docid_ref (document_id, identifier_type),
    INDEX idx_identifier (identifier_type, identifier_value),
    INDEX idx_matched (matched_table, matched_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opportunity_attachment_summary (
    summary_id             INT AUTO_INCREMENT PRIMARY KEY,
    notice_id              VARCHAR(100) NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword') NOT NULL,
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  TEXT,
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    source_text_hash       CHAR(64),
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (notice_id, extraction_method),
    INDEX idx_notice (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
