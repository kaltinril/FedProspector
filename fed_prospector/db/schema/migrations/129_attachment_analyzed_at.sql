-- Phase 129: Add keyword_analyzed_at and ai_analyzed_at to attachment_document
-- These timestamps track when keyword extraction or AI analysis last ran on a document,
-- replacing the previous approach of checking document_intel_summary for existing rows.

ALTER TABLE attachment_document
    ADD COLUMN keyword_analyzed_at DATETIME DEFAULT NULL AFTER extraction_retry_count,
    ADD COLUMN ai_analyzed_at      DATETIME DEFAULT NULL AFTER keyword_analyzed_at;
