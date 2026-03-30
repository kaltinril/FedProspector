-- ============================================================
-- 80_identifier_refs.sql — Identifier cross-reference views (Phase 128)
-- ============================================================

CREATE OR REPLACE VIEW v_opportunity_identifier_refs AS
SELECT
    oa.notice_id,
    dir.identifier_type,
    dir.identifier_value,
    dir.confidence,
    dir.matched_table,
    dir.matched_column,
    dir.matched_id,
    COUNT(*) AS mention_count
FROM document_identifier_ref dir
JOIN attachment_document ad ON ad.document_id = dir.document_id
JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
GROUP BY oa.notice_id, dir.identifier_type, dir.identifier_value,
         dir.confidence, dir.matched_table, dir.matched_column, dir.matched_id;


-- Predecessor contract candidates: for each opportunity, finds PIID-type
-- identifiers extracted from its attachments and joins to fpds_contract
-- to find the actual prior contract.
CREATE OR REPLACE VIEW v_predecessor_candidates AS
SELECT
    oa.notice_id,
    dir.identifier_value    AS predecessor_piid,
    fc.vendor_name          AS predecessor_vendor_name,
    fc.vendor_uei           AS predecessor_vendor_uei,
    fc.base_and_all_options  AS predecessor_award_amount,
    fc.set_aside_type       AS predecessor_set_aside_type,
    fc.naics_code           AS predecessor_naics,
    dir.confidence,
    COUNT(DISTINCT dir.document_id) AS document_mentions
FROM document_identifier_ref dir
JOIN attachment_document ad ON ad.document_id = dir.document_id
JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
JOIN fpds_contract fc ON fc.contract_id = dir.identifier_value
    AND fc.modification_number = '0'
WHERE dir.identifier_type IN ('PIID', 'SOLICITATION')
  AND dir.matched_table = 'fpds_contract'
GROUP BY oa.notice_id, dir.identifier_value,
         fc.vendor_name, fc.vendor_uei,
         fc.base_and_all_options, fc.set_aside_type,
         fc.naics_code, dir.confidence;
