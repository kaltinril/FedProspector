-- Phase 115F: Onboarding & Past Performance Enhancements
-- Date: 2026-04-02
-- Creates 1 table (organization_psc)
-- and 5 views (profile completeness, certification expiration alerts,
-- SBA size standard monitor, past performance relevance, portfolio gap analysis).

USE fed_contracts;

-- ============================================================
-- Table: organization_psc
-- PSC codes associated with an organization's capabilities.
-- ============================================================

CREATE TABLE IF NOT EXISTS organization_psc (
    organization_psc_id  INT AUTO_INCREMENT PRIMARY KEY,
    organization_id      INT NOT NULL,
    psc_code             VARCHAR(10) NOT NULL,
    added_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_psc (organization_id, psc_code),
    INDEX idx_orgpsc_org (organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- View 1: v_org_profile_completeness
-- Per-organization profile completeness score with
-- recommendations for missing fields.
-- ============================================================

CREATE OR REPLACE VIEW v_org_profile_completeness AS
SELECT
    o.organization_id,
    o.name                                           AS organization_name,
    -- Individual field checks
    (o.uei_sam IS NOT NULL)                          AS has_uei,
    (o.cage_code IS NOT NULL)                        AS has_cage_code,
    (COALESCE(naics_cnt.cnt, 0) > 0)                  AS has_naics,
    (COALESCE(psc_cnt.cnt, 0) > 0)                   AS has_psc,
    (COALESCE(cert_cnt.cnt, 0) > 0)                  AS has_certifications,
    (COALESCE(pp_cnt.cnt, 0) > 0)                    AS has_past_performance,
    (o.city IS NOT NULL AND o.state_code IS NOT NULL) AS has_address,
    (o.entity_structure IS NOT NULL)                  AS has_business_type,
    (o.annual_revenue IS NOT NULL
     OR o.employee_count IS NOT NULL)                AS has_size_standard,
    -- Completeness percentage (9 fields total)
    ROUND(
        (
            (o.uei_sam IS NOT NULL)
          + (o.cage_code IS NOT NULL)
          + (COALESCE(naics_cnt.cnt, 0) > 0)
          + (COALESCE(psc_cnt.cnt, 0) > 0)
          + (COALESCE(cert_cnt.cnt, 0) > 0)
          + (COALESCE(pp_cnt.cnt, 0) > 0)
          + (o.city IS NOT NULL AND o.state_code IS NOT NULL)
          + (o.entity_structure IS NOT NULL)
          + (o.annual_revenue IS NOT NULL OR o.employee_count IS NOT NULL)
        ) / 9.0 * 100
    , 1)                                              AS completeness_pct,
    -- Recommendation text listing missing fields
    NULLIF(CONCAT_WS(', ',
        IF(o.uei_sam IS NULL,          'UEI',             NULL),
        IF(o.cage_code IS NULL,        'CAGE Code',       NULL),
        IF(COALESCE(naics_cnt.cnt, 0) = 0, 'NAICS Codes',     NULL),
        IF(COALESCE(psc_cnt.cnt, 0) = 0,  'PSC Codes',       NULL),
        IF(COALESCE(cert_cnt.cnt, 0) = 0, 'Certifications',  NULL),
        IF(COALESCE(pp_cnt.cnt, 0) = 0,   'Past Performance', NULL),
        IF(o.city IS NULL
           OR o.state_code IS NULL,    'Address',         NULL),
        IF(o.entity_structure IS NULL, 'Business Type',   NULL),
        IF(o.annual_revenue IS NULL
           AND o.employee_count IS NULL, 'Size Standard', NULL)
    ), '')                                             AS missing_fields
FROM organization o
LEFT JOIN (
    SELECT organization_id, COUNT(*) AS cnt
    FROM organization_naics
    GROUP BY organization_id
) naics_cnt ON o.organization_id = naics_cnt.organization_id
LEFT JOIN (
    SELECT organization_id, COUNT(*) AS cnt
    FROM organization_psc
    GROUP BY organization_id
) psc_cnt ON o.organization_id = psc_cnt.organization_id
LEFT JOIN (
    SELECT organization_id, COUNT(*) AS cnt
    FROM organization_certification
    GROUP BY organization_id
) cert_cnt ON o.organization_id = cert_cnt.organization_id
LEFT JOIN (
    SELECT organization_id, COUNT(*) AS cnt
    FROM organization_past_performance
    GROUP BY organization_id
) pp_cnt ON o.organization_id = pp_cnt.organization_id;

-- ============================================================
-- View 2: v_certification_expiration_alert
-- Upcoming certification expirations within 90 days.
-- Sources from organization_certification (manual entries)
-- and entity_sba_certification (SAM.gov data via UEI match).
-- ============================================================

CREATE OR REPLACE VIEW v_certification_expiration_alert AS
-- Organization-level certifications
SELECT
    oc.organization_id,
    oc.certification_type,
    oc.expiration_date,
    DATEDIFF(oc.expiration_date, NOW())              AS days_until_expiration,
    CASE
        WHEN DATEDIFF(oc.expiration_date, NOW()) <= 30 THEN 'URGENT'
        WHEN DATEDIFF(oc.expiration_date, NOW()) <= 60 THEN 'WARNING'
        ELSE 'NOTICE'
    END                                               AS alert_level,
    'MANUAL'                                          AS source
FROM organization_certification oc
WHERE oc.expiration_date IS NOT NULL
  AND oc.expiration_date >= CURDATE()
  AND oc.expiration_date <= DATE_ADD(CURDATE(), INTERVAL 90 DAY)
  AND oc.is_active = 'Y'

UNION ALL

-- SAM.gov SBA certifications matched via UEI
SELECT
    o.organization_id,
    esc.sba_type_code                                 AS certification_type,
    esc.certification_exit_date                       AS expiration_date,
    DATEDIFF(esc.certification_exit_date, NOW())      AS days_until_expiration,
    CASE
        WHEN DATEDIFF(esc.certification_exit_date, NOW()) <= 30 THEN 'URGENT'
        WHEN DATEDIFF(esc.certification_exit_date, NOW()) <= 60 THEN 'WARNING'
        ELSE 'NOTICE'
    END                                               AS alert_level,
    'SAM_GOV'                                         AS source
FROM entity_sba_certification esc
INNER JOIN organization o ON o.uei_sam = esc.uei_sam
WHERE esc.certification_exit_date IS NOT NULL
  AND esc.certification_exit_date >= CURDATE()
  AND esc.certification_exit_date <= DATE_ADD(CURDATE(), INTERVAL 90 DAY);

-- ============================================================
-- View 3: v_sba_size_standard_monitor
-- Compare organization revenue/employees against SBA size
-- standards for their registered NAICS codes.
-- Only rows where usage >= 80% of threshold are returned.
-- size_type: 'R' = revenue (millions), 'E' = employees
-- ============================================================

CREATE OR REPLACE VIEW v_sba_size_standard_monitor AS
SELECT
    o.organization_id,
    o.name                                            AS organization_name,
    orn.naics_code,
    ss.size_type                                      AS size_standard_type,
    ss.size_standard                                  AS threshold,
    CASE ss.size_type
        WHEN 'R' THEN o.annual_revenue / 1000000.0   -- convert to millions for comparison
        WHEN 'E' THEN o.employee_count
    END                                               AS current_value,
    CASE ss.size_type
        WHEN 'R' THEN ROUND((o.annual_revenue / 1000000.0) / ss.size_standard * 100, 1)
        WHEN 'E' THEN ROUND(o.employee_count / ss.size_standard * 100, 1)
    END                                               AS pct_of_threshold
FROM organization o
INNER JOIN organization_naics orn ON o.organization_id = orn.organization_id
INNER JOIN ref_sba_size_standard ss ON orn.naics_code = ss.naics_code
WHERE ss.size_standard > 0
  AND (
      (ss.size_type = 'R' AND o.annual_revenue IS NOT NULL
       AND (o.annual_revenue / 1000000.0) / ss.size_standard >= 0.80)
      OR
      (ss.size_type = 'E' AND o.employee_count IS NOT NULL
       AND o.employee_count / ss.size_standard >= 0.80)
  );

-- ============================================================
-- View 4: v_past_performance_relevance
-- For each organization's past performance record, score
-- relevance against active opportunities. Produces one row
-- per (past_performance, opportunity) pair with relevance
-- signals.
-- ============================================================

CREATE OR REPLACE VIEW v_past_performance_relevance AS
SELECT
    pp.organization_id,
    pp.id                                             AS past_performance_id,
    pp.contract_number,
    pp.agency_name                                    AS pp_agency,
    pp.naics_code                                     AS pp_naics,
    pp.contract_value                                 AS pp_value,
    opp.notice_id,
    opp.title                                         AS opportunity_title,
    opp.department_name                               AS opp_agency,
    opp.naics_code                                    AS opp_naics,
    opp.estimated_contract_value                      AS opp_value,
    -- Relevance signals
    (pp.naics_code IS NOT NULL
     AND opp.naics_code IS NOT NULL
     AND pp.naics_code = opp.naics_code)              AS naics_match,
    (pp.agency_name IS NOT NULL
     AND opp.department_name IS NOT NULL
     AND pp.agency_name = opp.department_name)        AS agency_match,
    -- Value similarity: 1 when equal, decreasing as ratio diverges (0 if either is null/zero)
    CASE
        WHEN pp.contract_value IS NULL OR pp.contract_value = 0
             OR opp.estimated_contract_value IS NULL OR opp.estimated_contract_value = 0
        THEN NULL
        WHEN pp.contract_value <= opp.estimated_contract_value
        THEN ROUND(pp.contract_value / opp.estimated_contract_value, 2)
        ELSE ROUND(opp.estimated_contract_value / pp.contract_value, 2)
    END                                               AS value_similarity,
    -- Recency: years since period_end (lower is better)
    CASE
        WHEN pp.period_end IS NOT NULL
        THEN ROUND(DATEDIFF(CURDATE(), pp.period_end) / 365.25, 1)
        ELSE NULL
    END                                               AS years_since_completion,
    -- Composite relevance score (0-100 scale)
    ROUND(
        (
            (pp.naics_code IS NOT NULL AND opp.naics_code IS NOT NULL AND pp.naics_code = opp.naics_code) * 35
          + (pp.agency_name IS NOT NULL AND opp.department_name IS NOT NULL AND pp.agency_name = opp.department_name) * 25
          + COALESCE(
                CASE
                    WHEN pp.contract_value IS NULL OR pp.contract_value = 0
                         OR opp.estimated_contract_value IS NULL OR opp.estimated_contract_value = 0
                    THEN 0
                    WHEN pp.contract_value <= opp.estimated_contract_value
                    THEN pp.contract_value / opp.estimated_contract_value
                    ELSE opp.estimated_contract_value / pp.contract_value
                END, 0) * 20
          + CASE
                WHEN pp.period_end IS NULL THEN 0
                WHEN DATEDIFF(CURDATE(), pp.period_end) / 365.25 <= 3 THEN 20
                WHEN DATEDIFF(CURDATE(), pp.period_end) / 365.25 <= 5 THEN 10
                ELSE 0
            END
        )
    , 1)                                              AS relevance_score
FROM organization_past_performance pp
INNER JOIN opportunity opp
    ON opp.active = 'Y'
    AND (
        -- Direct NAICS match: PP record's own NAICS matches the opportunity
        (pp.naics_code IS NOT NULL AND opp.naics_code = pp.naics_code)
        OR
        -- Org NAICS match: any of the org's registered NAICS codes matches the opportunity
        EXISTS (
            SELECT 1 FROM organization_naics orn
            WHERE orn.organization_id = pp.organization_id
              AND orn.naics_code = opp.naics_code
        )
    )
;

-- ============================================================
-- View 5: v_portfolio_gap_analysis
-- Per organization + NAICS code: compare opportunity volume
-- (active opps matching the org's NAICS codes) against past
-- performance count to identify gaps and strengths.
-- ============================================================

CREATE OR REPLACE VIEW v_portfolio_gap_analysis AS
SELECT
    orn.organization_id,
    orn.naics_code,
    COALESCE(opp_counts.opportunity_count, 0)         AS opportunity_count,
    COALESCE(pp_counts.past_performance_count, 0)     AS past_performance_count,
    CASE
        WHEN COALESCE(pp_counts.past_performance_count, 0) = 0
             AND COALESCE(opp_counts.opportunity_count, 0) > 0
        THEN 'NO_EXPERIENCE'
        WHEN COALESCE(pp_counts.past_performance_count, 0) > 0
             AND COALESCE(opp_counts.opportunity_count, 0) = 0
        THEN 'LOW_OPPORTUNITY'
        WHEN COALESCE(pp_counts.past_performance_count, 0) > 0
             AND COALESCE(opp_counts.opportunity_count, 0) > 0
        THEN 'STRONG_MATCH'
        ELSE 'NO_DATA'
    END                                               AS gap_type
FROM organization_naics orn
LEFT JOIN (
    SELECT naics_code, COUNT(*) AS opportunity_count
    FROM opportunity
    WHERE active = 'Y'
    GROUP BY naics_code
) opp_counts ON orn.naics_code = opp_counts.naics_code
LEFT JOIN (
    SELECT organization_id, naics_code, COUNT(*) AS past_performance_count
    FROM organization_past_performance
    WHERE naics_code IS NOT NULL
    GROUP BY organization_id, naics_code
) pp_counts ON orn.organization_id = pp_counts.organization_id
              AND orn.naics_code = pp_counts.naics_code;
