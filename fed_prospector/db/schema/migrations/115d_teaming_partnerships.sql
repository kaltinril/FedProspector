-- Phase 115D: Teaming & Partnership Intelligence — views only
-- Date: 2026-04-02
-- Creates 5 views for partner capability matching, risk assessment,
-- mentor-protege identification, prime-sub relationships, and teaming networks.

USE fed_contracts;

-- ============================================================
-- View 1: v_partner_capability_match
-- Gap-based teaming partner matchmaker.
-- For each active entity, aggregates capabilities across 6 dimensions:
-- NAICS codes, PSC codes, certifications, agencies worked with,
-- past performance NAICS, and geographic presence.
-- Sources: entity, entity_naics, entity_psc, entity_sba_certification,
--          entity_address, fpds_contract.
-- ============================================================

CREATE OR REPLACE VIEW v_partner_capability_match AS
WITH contract_agg AS (
    SELECT
        fc.vendor_uei,
        COUNT(*)                                                           AS contract_count,
        SUM(fc.dollars_obligated)                                          AS total_contract_value,
        GROUP_CONCAT(DISTINCT fc.agency_name ORDER BY fc.agency_name SEPARATOR ', ')
                                                                           AS agencies_worked_with,
        GROUP_CONCAT(DISTINCT fc.naics_code ORDER BY fc.naics_code SEPARATOR ', ')
                                                                           AS performance_naics_codes
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.vendor_uei IS NOT NULL
    GROUP BY fc.vendor_uei
)
SELECT
    e.uei_sam,
    e.legal_business_name,
    ea.state_or_province                                                   AS state,
    -- NAICS codes registered in SAM
    GROUP_CONCAT(DISTINCT en.naics_code ORDER BY en.naics_code SEPARATOR ', ')
                                                                           AS naics_codes,
    -- PSC codes registered in SAM
    GROUP_CONCAT(DISTINCT ep.psc_code ORDER BY ep.psc_code SEPARATOR ', ')
                                                                           AS psc_codes,
    -- Active SBA certifications
    GROUP_CONCAT(DISTINCT esc.sba_type_code ORDER BY esc.sba_type_code SEPARATOR ', ')
                                                                           AS certifications,
    -- Contract history aggregates
    COALESCE(ca.agencies_worked_with, '')                                   AS agencies_worked_with,
    COALESCE(ca.performance_naics_codes, '')                                AS performance_naics_codes,
    COALESCE(ca.contract_count, 0)                                         AS contract_count,
    COALESCE(ca.total_contract_value, 0)                                   AS total_contract_value
FROM entity e
LEFT JOIN entity_address ea
    ON ea.uei_sam = e.uei_sam AND ea.address_type = 'PHYSICAL'
LEFT JOIN entity_naics en
    ON en.uei_sam = e.uei_sam
LEFT JOIN entity_psc ep
    ON ep.uei_sam = e.uei_sam
LEFT JOIN entity_sba_certification esc
    ON esc.uei_sam = e.uei_sam
    AND (esc.certification_exit_date IS NULL OR esc.certification_exit_date > CURDATE())
LEFT JOIN contract_agg ca
    ON ca.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY
    e.uei_sam, e.legal_business_name, ea.state_or_province,
    ca.agencies_worked_with, ca.performance_naics_codes,
    ca.contract_count, ca.total_contract_value;


-- ============================================================
-- View 2: v_partner_risk_assessment
-- Toxic partner / due diligence screening per entity (UEI).
-- Aggregates risk signals: exclusions, terminations for cause,
-- spending trajectory, customer concentration, certifications,
-- contract volume, and years in business.
-- Sources: entity, sam_exclusion, fpds_contract,
--          entity_sba_certification.
-- ============================================================

CREATE OR REPLACE VIEW v_partner_risk_assessment AS
WITH exclusion_agg AS (
    SELECT
        se.uei,
        COUNT(*)                                                           AS exclusion_count,
        MAX(CASE WHEN se.termination_date IS NULL
                   OR se.termination_date > CURDATE()
             THEN 1 ELSE 0 END)                                           AS current_exclusion_flag
    FROM sam_exclusion se
    WHERE se.uei IS NOT NULL
    GROUP BY se.uei
),
termination_agg AS (
    SELECT
        fc.vendor_uei,
        SUM(CASE WHEN fc.reason_for_modification LIKE '%Terminate%Cause%'
                   OR fc.reason_for_modification LIKE '%Termination%Cause%'
             THEN 1 ELSE 0 END)                                           AS termination_for_cause_count
    FROM fpds_contract fc
    WHERE fc.vendor_uei IS NOT NULL
    GROUP BY fc.vendor_uei
),
-- Spending trajectory: compare recent 2 years vs prior 2 years
spending_trend AS (
    SELECT
        fc.vendor_uei,
        SUM(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR)
             THEN fc.dollars_obligated ELSE 0 END)                         AS recent_2yr_value,
        SUM(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 4 YEAR)
                  AND fc.date_signed <  DATE_SUB(CURDATE(), INTERVAL 2 YEAR)
             THEN fc.dollars_obligated ELSE 0 END)                         AS prior_2yr_value
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.vendor_uei IS NOT NULL
      AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 4 YEAR)
    GROUP BY fc.vendor_uei
),
-- Customer concentration: % of contracts from top agency
agency_concentration AS (
    SELECT
        fc.vendor_uei,
        fc.agency_name,
        COUNT(*)                                                           AS agency_contracts,
        SUM(COUNT(*)) OVER (PARTITION BY fc.vendor_uei)                    AS total_contracts,
        ROW_NUMBER() OVER (PARTITION BY fc.vendor_uei ORDER BY COUNT(*) DESC) AS rn
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.vendor_uei IS NOT NULL
    GROUP BY fc.vendor_uei, fc.agency_name
),
top_agency AS (
    SELECT
        vendor_uei,
        agency_name                                                        AS top_agency_name,
        ROUND(agency_contracts / NULLIF(total_contracts, 0) * 100, 1)      AS top_agency_pct
    FROM agency_concentration
    WHERE rn = 1
),
cert_count AS (
    SELECT
        esc.uei_sam,
        COUNT(*)                                                           AS certification_count
    FROM entity_sba_certification esc
    WHERE esc.certification_exit_date IS NULL
       OR esc.certification_exit_date > CURDATE()
    GROUP BY esc.uei_sam
),
contract_total AS (
    SELECT
        fc.vendor_uei,
        SUM(fc.dollars_obligated)                                          AS total_contract_value
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.vendor_uei IS NOT NULL
    GROUP BY fc.vendor_uei
)
SELECT
    e.uei_sam,
    e.legal_business_name,
    -- Exclusion risk
    COALESCE(ex.current_exclusion_flag, 0)                                 AS current_exclusion_flag,
    COALESCE(ex.exclusion_count, 0)                                        AS exclusion_count,
    -- Termination for cause
    COALESCE(ta.termination_for_cause_count, 0)                            AS termination_for_cause_count,
    -- Spending trajectory (positive = growing, negative = shrinking)
    CASE
        WHEN COALESCE(st.prior_2yr_value, 0) = 0 AND COALESCE(st.recent_2yr_value, 0) = 0
            THEN 'NO_DATA'
        WHEN COALESCE(st.prior_2yr_value, 0) = 0
            THEN 'NEW'
        WHEN st.recent_2yr_value >= st.prior_2yr_value
            THEN 'GROWING'
        ELSE 'DECLINING'
    END                                                                    AS spending_trajectory,
    COALESCE(st.recent_2yr_value, 0)                                       AS recent_2yr_value,
    COALESCE(st.prior_2yr_value, 0)                                        AS prior_2yr_value,
    -- Customer concentration
    COALESCE(tga.top_agency_name, '')                                      AS top_agency_name,
    COALESCE(tga.top_agency_pct, 0)                                        AS customer_concentration_pct,
    -- Certifications
    COALESCE(cc.certification_count, 0)                                    AS certification_count,
    -- Contract volume
    COALESCE(ct.total_contract_value, 0)                                   AS total_contract_value,
    -- Years in business
    ROUND(DATEDIFF(CURDATE(), e.initial_registration_date) / 365.25, 1)    AS years_in_business
FROM entity e
LEFT JOIN exclusion_agg ex        ON ex.uei = e.uei_sam
LEFT JOIN termination_agg ta      ON ta.vendor_uei = e.uei_sam
LEFT JOIN spending_trend st       ON st.vendor_uei = e.uei_sam
LEFT JOIN top_agency tga          ON tga.vendor_uei = e.uei_sam
LEFT JOIN cert_count cc           ON cc.uei_sam = e.uei_sam
LEFT JOIN contract_total ct       ON ct.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A';


-- ============================================================
-- View 3: v_mentor_protege_candidate
-- Identifies potential mentor-protege pairings.
-- Protege: certified small business (8(a), WOSB, HUBZone, SDVOSB)
--   with smaller contract portfolios.
-- Mentor: larger vendors in overlapping NAICS codes.
-- Sources: entity, entity_sba_certification, entity_naics,
--          fpds_contract.
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
        AND esc.sba_type_code IN ('8A', 'WOSB', 'EDWOSB', 'HUBZONE', 'SDVOSB')
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
)
SELECT
    p.uei_sam                                                              AS protege_uei,
    p.legal_business_name                                                  AS protege_name,
    p.certifications                                                       AS protege_certifications,
    p.naics_codes                                                          AS protege_naics,
    pv.protege_contract_count,
    pv.protege_total_value,
    m.uei_sam                                                              AS mentor_uei,
    m.legal_business_name                                                  AS mentor_name,
    m.naics_code                                                           AS shared_naics,
    m.mentor_contract_count,
    m.mentor_total_value,
    m.mentor_agencies
FROM protege p
INNER JOIN protege_volume pv
    ON pv.uei_sam = p.uei_sam
INNER JOIN entity_naics pen
    ON pen.uei_sam = p.uei_sam
INNER JOIN mentor m
    ON m.naics_code = pen.naics_code
    AND m.uei_sam != p.uei_sam
WHERE pv.protege_total_value < 10000000;


-- ============================================================
-- View 4: v_prime_sub_relationship
-- Existing prime-subcontractor relationships from subaward data.
-- Per prime-sub pair: award counts, total value, NAICS and
-- agencies worked together.
-- Source: sam_subaward.
-- ============================================================

CREATE OR REPLACE VIEW v_prime_sub_relationship AS
SELECT
    sa.prime_uei,
    sa.prime_name,
    sa.sub_uei,
    sa.sub_name,
    COUNT(*)                                                               AS subaward_count,
    SUM(sa.sub_amount)                                                     AS total_subaward_value,
    ROUND(AVG(sa.sub_amount), 2)                                           AS avg_subaward_value,
    MIN(sa.sub_date)                                                       AS first_subaward_date,
    MAX(sa.sub_date)                                                       AS last_subaward_date,
    GROUP_CONCAT(DISTINCT sa.naics_code ORDER BY sa.naics_code SEPARATOR ', ')
                                                                           AS naics_codes_together,
    GROUP_CONCAT(DISTINCT sa.prime_agency_name ORDER BY sa.prime_agency_name SEPARATOR ', ')
                                                                           AS agencies_together
FROM sam_subaward sa
WHERE sa.prime_uei IS NOT NULL
  AND sa.sub_uei IS NOT NULL
GROUP BY sa.prime_uei, sa.prime_name, sa.sub_uei, sa.sub_name;


-- ============================================================
-- View 5: v_teaming_network
-- Aggregated teaming network per vendor: who they've subbed to,
-- who they've used as subs, frequency, and total value.
-- Useful for social graph / network visualization.
-- Source: sam_subaward.
-- ============================================================

CREATE OR REPLACE VIEW v_teaming_network AS
WITH as_sub AS (
    SELECT
        sa.sub_uei                                                         AS vendor_uei,
        sa.sub_name                                                        AS vendor_name,
        'SUB_TO'                                                           AS relationship_direction,
        sa.prime_uei                                                       AS partner_uei,
        sa.prime_name                                                      AS partner_name,
        COUNT(*)                                                           AS award_count,
        SUM(sa.sub_amount)                                                 AS total_value
    FROM sam_subaward sa
    WHERE sa.sub_uei IS NOT NULL
      AND sa.prime_uei IS NOT NULL
    GROUP BY sa.sub_uei, sa.sub_name, sa.prime_uei, sa.prime_name
),
as_prime AS (
    SELECT
        sa.prime_uei                                                       AS vendor_uei,
        sa.prime_name                                                      AS vendor_name,
        'PRIME_OF'                                                         AS relationship_direction,
        sa.sub_uei                                                         AS partner_uei,
        sa.sub_name                                                        AS partner_name,
        COUNT(*)                                                           AS award_count,
        SUM(sa.sub_amount)                                                 AS total_value
    FROM sam_subaward sa
    WHERE sa.prime_uei IS NOT NULL
      AND sa.sub_uei IS NOT NULL
    GROUP BY sa.prime_uei, sa.prime_name, sa.sub_uei, sa.sub_name
)
SELECT * FROM as_sub
UNION ALL
SELECT * FROM as_prime;
