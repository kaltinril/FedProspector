-- migrations/133c_fix_mentor_protege_candidate_cardinality.sql
-- Phase 133 (Task 5): Fix v_mentor_protege_candidate row explosion.
--
-- THE BUG:
--   v_mentor_protege_candidate (defined in 115d_teaming_partnerships.sql) runs
--   but `SELECT *` returns ~5.49M rows, which makes GET /api/v1/teaming/mentor-
--   protege time out / exhaust memory and the UI shows "Failed to load
--   mentor-protege pairs".
--
--   Root cause is an unbounded cross-product in the final SELECT. Each protege
--   (a certified small business) is joined to its `entity_naics` rows and then
--   to the `mentor` CTE on `m.naics_code = pen.naics_code`. The `mentor` CTE is
--   every active entity with >= $1M obligated in a NAICS over the last 5 years,
--   grouped per (vendor_uei, naics_code) -- a very large set. For a popular
--   NAICS (e.g. 541512), a single protege pairs with THOUSANDS of mentors; over
--   all proteges x their NAICS x all mentors sharing each NAICS the result blows
--   up to millions of rows. There is no per-protege bound on mentor candidates.
--
-- THE FIX:
--   Bound the candidate set: within each (protege, shared NAICS) keep only the
--   top 10 mentors ranked by mentor_total_value (the highest-value, most
--   relevant mentors). Implemented by wrapping the protege x mentor join in a
--   ROW_NUMBER() window partitioned by (protege_uei, shared_naics) ordered by
--   mentor_total_value DESC and filtering rn <= 10. This caps total rows to
--   roughly (#proteges x #NAICS-per-protege x 10) -- a sane candidate list --
--   instead of a full cross-product.
--
--   OUTPUT COLUMNS ARE UNCHANGED (same 12 columns, same names/order/types):
--   protege_uei, protege_name, protege_certifications, protege_naics,
--   protege_contract_count, protege_total_value, mentor_uei, mentor_name,
--   shared_naics, mentor_contract_count, mentor_total_value, mentor_agencies.
--   Only the row cardinality changes; the C# mapping (MentorProtegeCandidateView
--   / TeamingService.GetMentorProtegeCandidatesAsync) is unaffected.
--
-- IDEMPOTENT: CREATE OR REPLACE VIEW; safe to re-run.
--
-- APPLY (per CLAUDE.md rule 9 -- BOTH dev and prod; back up first per the
-- Phase 134 runbook). Run from this dev box via E:\mysql\bin:
--   Prod:
--     & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133c_fix_mentor_protege_candidate_cardinality.sql"
--   Dev (localhost):
--     & "E:\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133c_fix_mentor_protege_candidate_cardinality.sql"
-- ============================================================

USE fed_contracts;

-- ============================================================
-- View: v_mentor_protege_candidate
-- Identifies potential mentor-protege pairings.
-- Protege: certified small business (8(a), WOSB, HUBZone, SDVOSB)
--   with smaller contract portfolios.
-- Mentor: larger vendors in overlapping NAICS codes (capped to the top 10 by
--   value per protege+NAICS to keep the candidate set bounded).
-- Sources: entity, entity_sba_certification, entity_naics, fpds_contract.
-- ============================================================

CREATE OR REPLACE VIEW v_mentor_protege_candidate AS
WITH protege AS (
    SELECT
        e.uei_sam,
        e.legal_business_name,
        GROUP_CONCAT(DISTINCT esc.sba_type_code ORDER BY esc.sba_type_code SEPARATOR ', ')
                                                                           AS certifications,
        GROUP_CONCAT(DISTINCT en.naics_code ORDER BY en.naics_code SEPARATOR ', ')
                                                                           AS naics_codes
    FROM entity e
    INNER JOIN entity_sba_certification esc
        ON esc.uei_sam = e.uei_sam
        AND esc.sba_type_code IN ('A4', 'A6', 'XX', '27', 'A2')
        AND (esc.certification_exit_date IS NULL OR esc.certification_exit_date > CURDATE())
    LEFT JOIN entity_naics en
        ON en.uei_sam = e.uei_sam
    WHERE e.registration_status = 'A'
    GROUP BY e.uei_sam, e.legal_business_name
),
protege_volume AS (
    SELECT
        p.uei_sam,
        COALESCE(SUM(fc.dollars_obligated), 0)                             AS protege_total_value,
        COUNT(fc.contract_id)                                              AS protege_contract_count
    FROM protege p
    LEFT JOIN fpds_contract fc
        ON fc.vendor_uei = p.uei_sam AND fc.modification_number = '0'
    GROUP BY p.uei_sam
),
mentor AS (
    SELECT
        fc.vendor_uei                                                      AS uei_sam,
        e.legal_business_name,
        fc.naics_code,
        COUNT(*)                                                           AS mentor_contract_count,
        SUM(fc.dollars_obligated)                                          AS mentor_total_value,
        GROUP_CONCAT(DISTINCT fc.agency_name ORDER BY fc.agency_name SEPARATOR ', ')
                                                                           AS mentor_agencies
    FROM fpds_contract fc
    INNER JOIN entity e ON e.uei_sam = fc.vendor_uei
    WHERE fc.modification_number = '0'
      AND fc.vendor_uei IS NOT NULL
      AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
    GROUP BY fc.vendor_uei, e.legal_business_name, fc.naics_code
    HAVING SUM(fc.dollars_obligated) >= 1000000
),
-- Bound the cross-product: rank mentors within each (protege, shared NAICS) by
-- value and keep only the top 10. Without this cap a single popular NAICS pairs
-- one protege with thousands of mentors, blowing the view up to ~5.49M rows.
ranked AS (
    SELECT
        p.uei_sam                                                          AS protege_uei,
        p.legal_business_name                                              AS protege_name,
        p.certifications                                                   AS protege_certifications,
        p.naics_codes                                                      AS protege_naics,
        pv.protege_contract_count,
        pv.protege_total_value,
        m.uei_sam                                                          AS mentor_uei,
        m.legal_business_name                                              AS mentor_name,
        m.naics_code                                                       AS shared_naics,
        m.mentor_contract_count,
        m.mentor_total_value,
        m.mentor_agencies,
        ROW_NUMBER() OVER (
            PARTITION BY p.uei_sam, m.naics_code
            ORDER BY m.mentor_total_value DESC, m.uei_sam
        )                                                                  AS mentor_rank
    FROM protege p
    INNER JOIN protege_volume pv
        ON pv.uei_sam = p.uei_sam
    INNER JOIN entity_naics pen
        ON pen.uei_sam = p.uei_sam
    INNER JOIN mentor m
        ON m.naics_code = pen.naics_code
        AND m.uei_sam != p.uei_sam
    WHERE pv.protege_total_value < 10000000
)
SELECT
    protege_uei,
    protege_name,
    protege_certifications,
    protege_naics,
    protege_contract_count,
    protege_total_value,
    mentor_uei,
    mentor_name,
    shared_naics,
    mentor_contract_count,
    mentor_total_value,
    mentor_agencies
FROM ranked
WHERE mentor_rank <= 10;
