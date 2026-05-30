-- Phase 126: AI Contradiction Detection
-- Adds the 'ai_contradiction' extraction_method ENUM value to the three intel
-- tables that declare it, and adds a contradictions JSON column to
-- opportunity_attachment_summary to store detected contradictions.
--
-- Idempotent: ENUM MODIFYs are naturally idempotent (re-running with the same
-- definition is a no-op), and the column-add is guarded via information_schema.

-- 1. Extend extraction_method ENUM on document_intel_summary
ALTER TABLE document_intel_summary
    MODIFY COLUMN extraction_method
        ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword','ai_contradiction') NOT NULL;

-- 2. Extend extraction_method ENUM on document_intel_evidence
ALTER TABLE document_intel_evidence
    MODIFY COLUMN extraction_method
        ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword','ai_contradiction') NOT NULL;

-- 3. Extend extraction_method ENUM on opportunity_attachment_summary
ALTER TABLE opportunity_attachment_summary
    MODIFY COLUMN extraction_method
        ENUM('keyword','heuristic','ai_haiku','ai_sonnet','description_keyword','ai_contradiction') NOT NULL;

-- 4. Add contradictions JSON column to opportunity_attachment_summary (idempotent)
DROP PROCEDURE IF EXISTS _add_oas_contradictions;
DELIMITER //
CREATE PROCEDURE _add_oas_contradictions()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'fed_contracts'
          AND TABLE_NAME = 'opportunity_attachment_summary'
          AND COLUMN_NAME = 'contradictions'
    ) THEN
        ALTER TABLE opportunity_attachment_summary
            ADD COLUMN contradictions JSON NULL AFTER citation_offsets;
    END IF;
END //
DELIMITER ;
CALL _add_oas_contradictions();
DROP PROCEDURE _add_oas_contradictions;
