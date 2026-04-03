-- Phase 115G: UX & Review Insights
-- Date: 2026-04-02
-- Creates 5 views:
--   v_similar_opportunity        - "More Like This" opportunity matching
--   v_cross_source_validation    - Cross-source data consistency checks
--   v_data_freshness             - Per-source load freshness and record counts
--   v_data_completeness          - Per-table field completeness metrics
--   v_prospect_competitor_summary - Inline competitor data for pipeline cards

USE fed_contracts;

-- ============================================================
-- View 1: v_similar_opportunity
-- "More Like This" discovery: find active opportunities that
-- share NAICS code, agency, or set-aside type with a given
-- opportunity. Filter via WHERE source_notice_id = '...'
-- ============================================================

CREATE OR REPLACE VIEW v_similar_opportunity AS
SELECT
    src.notice_id                                     AS source_notice_id,
    m.notice_id                                       AS match_notice_id,
    m.title                                           AS match_title,
    m.department_name                                 AS match_agency,
    m.naics_code                                      AS match_naics,
    m.set_aside_code                                  AS match_set_aside,
    COALESCE(m.estimated_contract_value, m.award_amount) AS match_value,
    m.posted_date                                     AS match_posted_date,
    m.response_deadline                               AS match_response_deadline,
    -- Similarity factors: which dimensions matched
    CONCAT_WS(', ',
        IF(src.naics_code IS NOT NULL
           AND src.naics_code = m.naics_code,         'NAICS', NULL),
        IF(src.department_name IS NOT NULL
           AND src.department_name = m.department_name, 'AGENCY', NULL),
        IF(src.set_aside_code IS NOT NULL
           AND src.set_aside_code != ''
           AND src.set_aside_code = m.set_aside_code, 'SET_ASIDE', NULL),
        IF(src.classification_code IS NOT NULL
           AND src.classification_code = m.classification_code, 'PSC', NULL)
    )                                                 AS similarity_factors,
    -- Similarity score (0-100): NAICS=40, Agency=25, Set-aside=20, PSC=15
    (
        (src.naics_code IS NOT NULL AND src.naics_code = m.naics_code) * 40
      + (src.department_name IS NOT NULL AND src.department_name = m.department_name) * 25
      + (src.set_aside_code IS NOT NULL AND src.set_aside_code != ''
         AND src.set_aside_code = m.set_aside_code) * 20
      + (src.classification_code IS NOT NULL AND src.classification_code = m.classification_code) * 15
    )                                                 AS similarity_score
FROM opportunity src
INNER JOIN opportunity m
    ON m.notice_id != src.notice_id
    AND m.active = 'Y'
    AND (
        (src.naics_code IS NOT NULL AND src.naics_code = m.naics_code)
        OR (src.department_name IS NOT NULL AND src.department_name = m.department_name)
        OR (src.set_aside_code IS NOT NULL AND src.set_aside_code != ''
            AND src.set_aside_code = m.set_aside_code)
    );

-- ============================================================
-- View 2: v_cross_source_validation
-- Cross-source data consistency checks. Each row is one check
-- comparing counts or overlap across data sources.
-- ============================================================

CREATE OR REPLACE VIEW v_cross_source_validation AS

-- XSV-001: Entity count: sam_entity vs distinct recipient UEIs in usaspending
SELECT
    'XSV-001'                                         AS check_id,
    'Entity Count: SAM vs USASpending'                AS check_name,
    'sam_entity'                                      AS source_a_name,
    e_cnt.cnt                                         AS source_a_count,
    'usaspending_award (distinct UEI)'                AS source_b_name,
    u_cnt.cnt                                         AS source_b_count,
    ABS(CAST(e_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED)) AS difference,
    CASE WHEN GREATEST(e_cnt.cnt, u_cnt.cnt) = 0 THEN 0
         ELSE ROUND(ABS(CAST(e_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
                    / GREATEST(e_cnt.cnt, u_cnt.cnt) * 100, 1)
    END                                               AS pct_difference,
    CASE
        WHEN GREATEST(e_cnt.cnt, u_cnt.cnt) = 0 THEN 'OK'
        WHEN ABS(CAST(e_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
             / GREATEST(e_cnt.cnt, u_cnt.cnt) > 0.50 THEN 'ERROR'
        WHEN ABS(CAST(e_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
             / GREATEST(e_cnt.cnt, u_cnt.cnt) > 0.20 THEN 'WARNING'
        ELSE 'OK'
    END                                               AS status
FROM
    (SELECT COUNT(*) AS cnt FROM entity) e_cnt,
    (SELECT COUNT(DISTINCT recipient_uei) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) u_cnt

UNION ALL

-- XSV-002: Opportunity count by active status
SELECT
    'XSV-002'                                         AS check_id,
    'Opportunity Count: Active vs Inactive'           AS check_name,
    'opportunity (active=Y)'                          AS source_a_name,
    a_cnt.cnt                                         AS source_a_count,
    'opportunity (active=N)'                          AS source_b_name,
    i_cnt.cnt                                         AS source_b_count,
    ABS(CAST(a_cnt.cnt AS SIGNED) - CAST(i_cnt.cnt AS SIGNED)) AS difference,
    CASE WHEN (a_cnt.cnt + i_cnt.cnt) = 0 THEN 0
         ELSE ROUND(a_cnt.cnt / (a_cnt.cnt + i_cnt.cnt) * 100, 1)
    END                                               AS pct_difference,
    'INFO'                                            AS status
FROM
    (SELECT COUNT(*) AS cnt FROM opportunity WHERE active = 'Y') a_cnt,
    (SELECT COUNT(*) AS cnt FROM opportunity WHERE active != 'Y') i_cnt

UNION ALL

-- XSV-003: Award alignment: fpds_contract vs usaspending_award
SELECT
    'XSV-003'                                         AS check_id,
    'Award Count: FPDS vs USASpending'                AS check_name,
    'fpds_contract (distinct contract_id)'            AS source_a_name,
    f_cnt.cnt                                         AS source_a_count,
    'usaspending_award'                               AS source_b_name,
    u_cnt.cnt                                         AS source_b_count,
    ABS(CAST(f_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED)) AS difference,
    CASE WHEN GREATEST(f_cnt.cnt, u_cnt.cnt) = 0 THEN 0
         ELSE ROUND(ABS(CAST(f_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
                    / GREATEST(f_cnt.cnt, u_cnt.cnt) * 100, 1)
    END                                               AS pct_difference,
    CASE
        WHEN GREATEST(f_cnt.cnt, u_cnt.cnt) = 0 THEN 'OK'
        WHEN ABS(CAST(f_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
             / GREATEST(f_cnt.cnt, u_cnt.cnt) > 0.50 THEN 'ERROR'
        WHEN ABS(CAST(f_cnt.cnt AS SIGNED) - CAST(u_cnt.cnt AS SIGNED))
             / GREATEST(f_cnt.cnt, u_cnt.cnt) > 0.20 THEN 'WARNING'
        ELSE 'OK'
    END                                               AS status
FROM
    (SELECT COUNT(DISTINCT contract_id) AS cnt FROM fpds_contract) f_cnt,
    (SELECT COUNT(*) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) u_cnt

UNION ALL

-- XSV-004: Orphan opportunities - opportunities with awards that have no matching usaspending record
SELECT
    'XSV-004'                                         AS check_id,
    'Orphan Opportunities (awarded, no USASpending match)' AS check_name,
    'opportunity (awarded)'                           AS source_a_name,
    awarded.cnt                                       AS source_a_count,
    'matched in usaspending_award'                    AS source_b_name,
    matched.cnt                                       AS source_b_count,
    (awarded.cnt - matched.cnt)                       AS difference,
    CASE WHEN awarded.cnt = 0 THEN 0
         ELSE ROUND((awarded.cnt - matched.cnt) / awarded.cnt * 100, 1)
    END                                               AS pct_difference,
    CASE
        WHEN awarded.cnt = 0 THEN 'OK'
        WHEN (awarded.cnt - matched.cnt) / awarded.cnt > 0.50 THEN 'WARNING'
        ELSE 'OK'
    END                                               AS status
FROM
    (SELECT COUNT(*) AS cnt FROM opportunity WHERE award_number IS NOT NULL) awarded,
    (SELECT COUNT(DISTINCT o.notice_id) AS cnt
     FROM opportunity o
     INNER JOIN usaspending_award ua
         ON ua.solicitation_identifier = o.solicitation_number
         AND ua.deleted_at IS NULL
     WHERE o.award_number IS NOT NULL
       AND o.solicitation_number IS NOT NULL) matched

UNION ALL

-- XSV-005: Orphan awards - usaspending awards referencing UEIs not in sam_entity
SELECT
    'XSV-005'                                         AS check_id,
    'Orphan Awards (UEI not in SAM entity)'           AS check_name,
    'usaspending_award (distinct UEI)'                AS source_a_name,
    total_uei.cnt                                     AS source_a_count,
    'matched in entity'                               AS source_b_name,
    matched_uei.cnt                                   AS source_b_count,
    (total_uei.cnt - matched_uei.cnt)                 AS difference,
    CASE WHEN total_uei.cnt = 0 THEN 0
         ELSE ROUND((total_uei.cnt - matched_uei.cnt) / total_uei.cnt * 100, 1)
    END                                               AS pct_difference,
    CASE
        WHEN total_uei.cnt = 0 THEN 'OK'
        WHEN (total_uei.cnt - matched_uei.cnt) / total_uei.cnt > 0.50 THEN 'ERROR'
        WHEN (total_uei.cnt - matched_uei.cnt) / total_uei.cnt > 0.20 THEN 'WARNING'
        ELSE 'OK'
    END                                               AS status
FROM
    (SELECT COUNT(DISTINCT recipient_uei) AS cnt
     FROM usaspending_award
     WHERE recipient_uei IS NOT NULL AND deleted_at IS NULL) total_uei,
    (SELECT COUNT(DISTINCT ua.recipient_uei) AS cnt
     FROM usaspending_award ua
     INNER JOIN entity e ON e.uei_sam = ua.recipient_uei
     WHERE ua.recipient_uei IS NOT NULL AND ua.deleted_at IS NULL) matched_uei;

-- ============================================================
-- View 3: v_data_freshness
-- Per data source: last load time, records loaded, and
-- freshness status (FRESH/STALE/CRITICAL).
-- FRESH: loaded within 24h, STALE: 24-72h, CRITICAL: >72h
-- ============================================================

CREATE OR REPLACE VIEW v_data_freshness AS
SELECT
    ll.source_system                                  AS source_name,
    ll.completed_at                                   AS last_load_date,
    ll.records_inserted + ll.records_updated          AS records_loaded,
    ll.status                                         AS last_load_status,
    TIMESTAMPDIFF(HOUR, ll.completed_at, NOW())       AS hours_since_last_load,
    CASE
        WHEN TIMESTAMPDIFF(HOUR, ll.completed_at, NOW()) <= 24  THEN 'FRESH'
        WHEN TIMESTAMPDIFF(HOUR, ll.completed_at, NOW()) <= 72  THEN 'STALE'
        ELSE 'CRITICAL'
    END                                               AS freshness_status,
    tbl.table_rows                                    AS table_row_count,
    tbl.table_name
FROM (
    -- Latest successful load per source
    SELECT source_system, MAX(load_id) AS max_load_id
    FROM etl_load_log
    WHERE status = 'SUCCESS'
    GROUP BY source_system
) latest
INNER JOIN etl_load_log ll ON ll.load_id = latest.max_load_id
LEFT JOIN (
    -- Map source_system to primary table and get row counts
    SELECT
        t.TABLE_NAME                                  AS table_name,
        t.TABLE_ROWS                                  AS table_rows,
        CASE t.TABLE_NAME
            WHEN 'opportunity'        THEN 'SAM_OPPORTUNITY'
            WHEN 'entity'             THEN 'SAM_ENTITY'
            WHEN 'fpds_contract'      THEN 'SAM_AWARDS'
            WHEN 'usaspending_award'  THEN 'USASPENDING_BULK'
            WHEN 'sam_exclusion'      THEN 'SAM_EXCLUSIONS'
            WHEN 'sam_subaward'       THEN 'SAM_SUBAWARD'
            WHEN 'federal_organization' THEN 'SAM_FEDHIER'
            WHEN 'gsa_labor_rate'     THEN 'GSA_CALC'
        END                                           AS source_system
    FROM information_schema.TABLES t
    WHERE t.TABLE_SCHEMA = 'fed_contracts'
      AND t.TABLE_NAME IN (
          'opportunity', 'entity', 'fpds_contract', 'usaspending_award',
          'sam_exclusion', 'sam_subaward', 'federal_organization', 'gsa_labor_rate'
      )
) tbl ON tbl.source_system = ll.source_system;

-- ============================================================
-- View 4: v_data_completeness
-- Per-table field completeness for business-critical columns.
-- Each row = one (table, field) pair with null/non-null counts.
-- ============================================================

CREATE OR REPLACE VIEW v_data_completeness AS

-- opportunity
SELECT
    'opportunity'                                     AS table_name,
    total.cnt                                         AS total_rows,
    'naics_code'                                      AS field_name,
    SUM(o.naics_code IS NOT NULL)                     AS non_null_count,
    SUM(o.naics_code IS NULL)                         AS null_count,
    ROUND(SUM(o.naics_code IS NOT NULL) / total.cnt * 100, 1) AS completeness_pct
FROM opportunity o, (SELECT COUNT(*) AS cnt FROM opportunity) total
GROUP BY total.cnt

UNION ALL
SELECT 'opportunity', total.cnt, 'department_name',
    SUM(o.department_name IS NOT NULL), SUM(o.department_name IS NULL),
    ROUND(SUM(o.department_name IS NOT NULL) / total.cnt * 100, 1)
FROM opportunity o, (SELECT COUNT(*) AS cnt FROM opportunity) total
GROUP BY total.cnt

UNION ALL
SELECT 'opportunity', total.cnt, 'set_aside_code',
    SUM(o.set_aside_code IS NOT NULL), SUM(o.set_aside_code IS NULL),
    ROUND(SUM(o.set_aside_code IS NOT NULL) / total.cnt * 100, 1)
FROM opportunity o, (SELECT COUNT(*) AS cnt FROM opportunity) total
GROUP BY total.cnt

UNION ALL
SELECT 'opportunity', total.cnt, 'response_deadline',
    SUM(o.response_deadline IS NOT NULL), SUM(o.response_deadline IS NULL),
    ROUND(SUM(o.response_deadline IS NOT NULL) / total.cnt * 100, 1)
FROM opportunity o, (SELECT COUNT(*) AS cnt FROM opportunity) total
GROUP BY total.cnt

UNION ALL
SELECT 'opportunity', total.cnt, 'estimated_contract_value',
    SUM(o.estimated_contract_value IS NOT NULL), SUM(o.estimated_contract_value IS NULL),
    ROUND(SUM(o.estimated_contract_value IS NOT NULL) / total.cnt * 100, 1)
FROM opportunity o, (SELECT COUNT(*) AS cnt FROM opportunity) total
GROUP BY total.cnt

UNION ALL

-- entity
SELECT 'entity', total.cnt, 'primary_naics',
    SUM(e.primary_naics IS NOT NULL), SUM(e.primary_naics IS NULL),
    ROUND(SUM(e.primary_naics IS NOT NULL) / total.cnt * 100, 1)
FROM entity e, (SELECT COUNT(*) AS cnt FROM entity) total
GROUP BY total.cnt

UNION ALL
SELECT 'entity', total.cnt, 'registration_status',
    SUM(e.registration_status IS NOT NULL), SUM(e.registration_status IS NULL),
    ROUND(SUM(e.registration_status IS NOT NULL) / total.cnt * 100, 1)
FROM entity e, (SELECT COUNT(*) AS cnt FROM entity) total
GROUP BY total.cnt

UNION ALL
SELECT 'entity', total.cnt, 'cage_code',
    SUM(e.cage_code IS NOT NULL), SUM(e.cage_code IS NULL),
    ROUND(SUM(e.cage_code IS NOT NULL) / total.cnt * 100, 1)
FROM entity e, (SELECT COUNT(*) AS cnt FROM entity) total
GROUP BY total.cnt

UNION ALL

-- fpds_contract
SELECT 'fpds_contract', total.cnt, 'naics_code',
    SUM(f.naics_code IS NOT NULL), SUM(f.naics_code IS NULL),
    ROUND(SUM(f.naics_code IS NOT NULL) / total.cnt * 100, 1)
FROM fpds_contract f, (SELECT COUNT(*) AS cnt FROM fpds_contract) total
GROUP BY total.cnt

UNION ALL
SELECT 'fpds_contract', total.cnt, 'vendor_uei',
    SUM(f.vendor_uei IS NOT NULL), SUM(f.vendor_uei IS NULL),
    ROUND(SUM(f.vendor_uei IS NOT NULL) / total.cnt * 100, 1)
FROM fpds_contract f, (SELECT COUNT(*) AS cnt FROM fpds_contract) total
GROUP BY total.cnt

UNION ALL
SELECT 'fpds_contract', total.cnt, 'dollars_obligated',
    SUM(f.dollars_obligated IS NOT NULL), SUM(f.dollars_obligated IS NULL),
    ROUND(SUM(f.dollars_obligated IS NOT NULL) / total.cnt * 100, 1)
FROM fpds_contract f, (SELECT COUNT(*) AS cnt FROM fpds_contract) total
GROUP BY total.cnt

UNION ALL
SELECT 'fpds_contract', total.cnt, 'date_signed',
    SUM(f.date_signed IS NOT NULL), SUM(f.date_signed IS NULL),
    ROUND(SUM(f.date_signed IS NOT NULL) / total.cnt * 100, 1)
FROM fpds_contract f, (SELECT COUNT(*) AS cnt FROM fpds_contract) total
GROUP BY total.cnt

UNION ALL

-- usaspending_award
SELECT 'usaspending_award', total.cnt, 'naics_code',
    SUM(u.naics_code IS NOT NULL), SUM(u.naics_code IS NULL),
    ROUND(SUM(u.naics_code IS NOT NULL) / total.cnt * 100, 1)
FROM usaspending_award u, (SELECT COUNT(*) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) total
WHERE u.deleted_at IS NULL
GROUP BY total.cnt

UNION ALL
SELECT 'usaspending_award', total.cnt, 'recipient_uei',
    SUM(u.recipient_uei IS NOT NULL), SUM(u.recipient_uei IS NULL),
    ROUND(SUM(u.recipient_uei IS NOT NULL) / total.cnt * 100, 1)
FROM usaspending_award u, (SELECT COUNT(*) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) total
WHERE u.deleted_at IS NULL
GROUP BY total.cnt

UNION ALL
SELECT 'usaspending_award', total.cnt, 'total_obligation',
    SUM(u.total_obligation IS NOT NULL), SUM(u.total_obligation IS NULL),
    ROUND(SUM(u.total_obligation IS NOT NULL) / total.cnt * 100, 1)
FROM usaspending_award u, (SELECT COUNT(*) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) total
WHERE u.deleted_at IS NULL
GROUP BY total.cnt

UNION ALL
SELECT 'usaspending_award', total.cnt, 'awarding_agency_name',
    SUM(u.awarding_agency_name IS NOT NULL), SUM(u.awarding_agency_name IS NULL),
    ROUND(SUM(u.awarding_agency_name IS NOT NULL) / total.cnt * 100, 1)
FROM usaspending_award u, (SELECT COUNT(*) AS cnt FROM usaspending_award WHERE deleted_at IS NULL) total
WHERE u.deleted_at IS NULL
GROUP BY total.cnt;

-- ============================================================
-- View 5: v_prospect_competitor_summary
-- Inline competitor data for pipeline cards. Per prospect:
-- likely incumbent, estimated competitor count, and incumbent
-- contract value. Uses usaspending_award for incumbent
-- detection (authoritative source per project conventions).
-- ============================================================

CREATE OR REPLACE VIEW v_prospect_competitor_summary AS
SELECT
    p.prospect_id,
    p.organization_id,
    p.notice_id,
    opp.title                                         AS opportunity_title,
    opp.naics_code,
    opp.department_name,
    opp.set_aside_code,
    -- Likely incumbent: vendor with most recent award in same NAICS + agency
    inc.recipient_name                                AS likely_incumbent,
    inc.recipient_uei                                 AS incumbent_uei,
    inc.total_obligation                              AS incumbent_contract_value,
    inc.end_date                                      AS incumbent_contract_end,
    -- Estimated competitor count: distinct entities registered in same NAICS
    -- filtered by set-aside SBA certifications when applicable
    COALESCE(comp.competitor_count, 0)                AS estimated_competitor_count
FROM prospect p
INNER JOIN opportunity opp ON opp.notice_id = p.notice_id
-- Subquery: find the most recent award per (NAICS, agency) pair
LEFT JOIN LATERAL (
    SELECT
        ua.recipient_name,
        ua.recipient_uei,
        ua.total_obligation,
        ua.end_date
    FROM usaspending_award ua
    WHERE ua.naics_code = opp.naics_code
      AND ua.awarding_agency_name = opp.department_name
      AND ua.deleted_at IS NULL
      AND ua.recipient_uei IS NOT NULL
    ORDER BY ua.end_date DESC
    LIMIT 1
) inc ON TRUE
-- Subquery: count distinct entities registered for this NAICS
LEFT JOIN LATERAL (
    SELECT COUNT(DISTINCT en.uei_sam) AS competitor_count
    FROM entity_naics en
    INNER JOIN entity e ON e.uei_sam = en.uei_sam
        AND e.registration_status = 'A'
    WHERE en.naics_code = opp.naics_code
) comp ON TRUE;
