-- Phase 115C: Advanced Competitive Intelligence — views only
-- Date: 2026-04-02
-- Creates 5 views for re-compete identification, agency behavior profiling,
-- competitor dossiers, agency buying patterns, and contracting office profiles.

USE fed_contracts;

-- ============================================================
-- View 1: v_recompete_candidate
-- Contracts likely to be re-competed in 12-18 months.
-- Sources: fpds_contract UNION usaspending_award, deduped by PIID.
-- Excludes completed contracts and micro-purchases (<$10K).
-- ============================================================

CREATE OR REPLACE VIEW v_recompete_candidate AS
WITH combined AS (
    -- FPDS contracts (priority source)
    SELECT
        fc.contract_id                  AS piid,
        'FPDS'                          AS source,
        1                               AS source_priority,
        fc.description,
        fc.naics_code,
        fc.set_aside_type,
        fc.vendor_uei,
        fc.vendor_name,
        fc.agency_name,
        fc.contracting_office_id,
        fc.contracting_office_name,
        fc.base_and_all_options          AS contract_value,
        fc.dollars_obligated,
        fc.ultimate_completion_date      AS current_end_date,
        fc.date_signed,
        fc.solicitation_number,
        fc.type_of_contract_pricing,
        fc.extent_competed
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.base_and_all_options >= 10000
      AND fc.ultimate_completion_date BETWEEN DATE_ADD(CURDATE(), INTERVAL 12 MONTH)
                                          AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH)

    UNION ALL

    -- USASpending contracts (secondary source)
    SELECT
        ua.piid,
        'USASpending'                   AS source,
        2                               AS source_priority,
        ua.award_description            AS description,
        ua.naics_code,
        ua.type_of_set_aside            AS set_aside_type,
        ua.recipient_uei                AS vendor_uei,
        ua.recipient_name               AS vendor_name,
        ua.awarding_agency_name         AS agency_name,
        NULL                            AS contracting_office_id,
        ua.awarding_sub_agency_name     AS contracting_office_name,
        ua.base_and_all_options_value   AS contract_value,
        ua.total_obligation             AS dollars_obligated,
        ua.end_date                     AS current_end_date,
        ua.start_date                   AS date_signed,
        ua.solicitation_identifier      AS solicitation_number,
        NULL                            AS type_of_contract_pricing,
        NULL                            AS extent_competed
    FROM usaspending_award ua
    WHERE ua.award_type IN ('DELIVERY ORDER','PURCHASE ORDER','BPA CALL',
                            'DEFINITIVE CONTRACT','DO','DCA','PO','BPA')
      AND ua.base_and_all_options_value >= 10000
      AND ua.end_date BETWEEN DATE_ADD(CURDATE(), INTERVAL 12 MONTH)
                          AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH)
      AND ua.deleted_at IS NULL
),
ranked AS (
    SELECT
        c.*,
        ROW_NUMBER() OVER (PARTITION BY c.piid ORDER BY c.source_priority ASC) AS rn
    FROM combined c
)
SELECT
    r.piid,
    r.source,
    r.description,
    r.naics_code,
    r.set_aside_type,
    r.vendor_uei,
    r.vendor_name,
    r.agency_name,
    r.contracting_office_id,
    r.contracting_office_name,
    r.contract_value,
    r.dollars_obligated,
    r.current_end_date,
    r.date_signed,
    r.solicitation_number,
    r.type_of_contract_pricing,
    r.extent_competed,
    DATEDIFF(r.current_end_date, CURDATE()) AS days_until_end,
    e.registration_status                   AS incumbent_registration_status,
    e.registration_expiration_date          AS incumbent_reg_expiration
FROM ranked r
LEFT JOIN entity e ON e.uei_sam = r.vendor_uei
WHERE r.rn = 1;


-- ============================================================
-- View 2: v_agency_recompete_pattern
-- 7 behavioral metrics per contracting office.
-- Sources: fpds_contract, opportunity.
-- ============================================================

CREATE OR REPLACE VIEW v_agency_recompete_pattern AS
WITH office_contracts AS (
    SELECT
        fc.contracting_office_id,
        fc.contracting_office_name,
        fc.agency_name,
        fc.contract_id,
        fc.naics_code,
        fc.vendor_uei,
        fc.set_aside_type,
        fc.extent_competed,
        fc.effective_date,
        fc.ultimate_completion_date,
        fc.completion_date,
        fc.date_signed
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.contracting_office_id IS NOT NULL
      AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 10 YEAR)
),
-- Consecutive contracts on same NAICS+office to detect incumbent retention
consecutive AS (
    SELECT
        oc.contracting_office_id,
        oc.naics_code,
        oc.vendor_uei,
        oc.date_signed,
        LAG(oc.vendor_uei) OVER (
            PARTITION BY oc.contracting_office_id, oc.naics_code
            ORDER BY oc.date_signed
        ) AS prev_vendor_uei,
        LAG(oc.date_signed) OVER (
            PARTITION BY oc.contracting_office_id, oc.naics_code
            ORDER BY oc.date_signed
        ) AS prev_date_signed
    FROM office_contracts oc
),
-- Incumbent retention: % where vendor_uei = prev_vendor_uei on same NAICS+office
retention AS (
    SELECT
        contracting_office_id,
        COUNT(*) AS recompete_count,
        SUM(CASE WHEN vendor_uei = prev_vendor_uei THEN 1 ELSE 0 END) AS incumbent_wins
    FROM consecutive
    WHERE prev_vendor_uei IS NOT NULL
    GROUP BY contracting_office_id
),
-- New entrant: vendors whose first contract at this office is the one being measured
first_at_office AS (
    SELECT
        oc.contracting_office_id,
        oc.vendor_uei,
        MIN(oc.date_signed) AS first_award_date
    FROM office_contracts oc
    GROUP BY oc.contracting_office_id, oc.vendor_uei
),
new_entrant AS (
    SELECT
        fao.contracting_office_id,
        COUNT(*) AS total_vendors,
        SUM(CASE WHEN fao.first_award_date >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR) THEN 1 ELSE 0 END) AS new_entrant_wins
    FROM first_at_office fao
    GROUP BY fao.contracting_office_id
),
-- Bridge/extension: contracts where ultimate_completion_date > completion_date
bridge AS (
    SELECT
        contracting_office_id,
        COUNT(*) AS total_contracts,
        SUM(CASE WHEN ultimate_completion_date > completion_date
                  AND completion_date IS NOT NULL
             THEN 1 ELSE 0 END) AS bridge_count
    FROM office_contracts
    GROUP BY contracting_office_id
),
-- Sole source rate
sole_source AS (
    SELECT
        contracting_office_id,
        COUNT(*) AS total_contracts,
        SUM(CASE WHEN extent_competed IN ('NONCOMP', 'NOT COMPETED', 'NDO') THEN 1 ELSE 0 END) AS sole_source_count
    FROM office_contracts
    GROUP BY contracting_office_id
),
-- Set-aside shift frequency (consecutive contracts same NAICS+office, different set-aside)
sa_shift AS (
    SELECT
        oc.contracting_office_id,
        oc.naics_code,
        oc.set_aside_type,
        LAG(oc.set_aside_type) OVER (
            PARTITION BY oc.contracting_office_id, oc.naics_code
            ORDER BY oc.date_signed
        ) AS prev_set_aside
    FROM office_contracts oc
),
sa_shift_agg AS (
    SELECT
        contracting_office_id,
        COUNT(*) AS sa_pairs,
        SUM(CASE WHEN set_aside_type != prev_set_aside THEN 1 ELSE 0 END) AS sa_shifts
    FROM sa_shift
    WHERE prev_set_aside IS NOT NULL
    GROUP BY contracting_office_id
),
-- NAICS shift frequency (consecutive contracts same office+solicitation_number area, different NAICS)
naics_shift AS (
    SELECT
        oc.contracting_office_id,
        oc.naics_code,
        LAG(oc.naics_code) OVER (
            PARTITION BY oc.contracting_office_id, LEFT(oc.naics_code, 4)
            ORDER BY oc.date_signed
        ) AS prev_naics
    FROM office_contracts oc
),
naics_shift_agg AS (
    SELECT
        contracting_office_id,
        COUNT(*) AS naics_pairs,
        SUM(CASE WHEN naics_code != prev_naics THEN 1 ELSE 0 END) AS naics_shifts
    FROM naics_shift
    WHERE prev_naics IS NOT NULL
    GROUP BY contracting_office_id
),
-- Average solicitation lead time from opportunity table
opp_lead AS (
    SELECT
        o.contracting_office_id,
        AVG(DATEDIFF(o.response_deadline, o.posted_date)) AS avg_lead_days
    FROM opportunity o
    WHERE o.posted_date IS NOT NULL
      AND o.response_deadline IS NOT NULL
      AND o.contracting_office_id IS NOT NULL
    GROUP BY o.contracting_office_id
),
-- Base office list
offices AS (
    SELECT DISTINCT
        contracting_office_id,
        contracting_office_name,
        agency_name
    FROM office_contracts
)
SELECT
    off.contracting_office_id,
    off.contracting_office_name,
    off.agency_name,
    ROUND(COALESCE(ret.incumbent_wins / NULLIF(ret.recompete_count, 0), 0) * 100, 1)
        AS incumbent_retention_rate_pct,
    ROUND(COALESCE(ne.new_entrant_wins / NULLIF(ne.total_vendors, 0), 0) * 100, 1)
        AS new_entrant_win_rate_pct,
    ROUND(COALESCE(sas.sa_shifts / NULLIF(sas.sa_pairs, 0), 0) * 100, 1)
        AS set_aside_shift_frequency_pct,
    ROUND(COALESCE(ol.avg_lead_days, 0), 1)
        AS avg_solicitation_lead_time_days,
    ROUND(COALESCE(br.bridge_count / NULLIF(br.total_contracts, 0), 0) * 100, 1)
        AS bridge_extension_frequency_pct,
    ROUND(COALESCE(ss.sole_source_count / NULLIF(ss.total_contracts, 0), 0) * 100, 1)
        AS sole_source_rate_pct,
    ROUND(COALESCE(ns.naics_shifts / NULLIF(ns.naics_pairs, 0), 0) * 100, 1)
        AS naics_shift_rate_pct,
    COALESCE(br.total_contracts, 0) AS total_contracts_analyzed
FROM offices off
LEFT JOIN retention ret        ON ret.contracting_office_id = off.contracting_office_id
LEFT JOIN new_entrant ne       ON ne.contracting_office_id  = off.contracting_office_id
LEFT JOIN sa_shift_agg sas     ON sas.contracting_office_id = off.contracting_office_id
LEFT JOIN opp_lead ol          ON ol.contracting_office_id  = off.contracting_office_id
LEFT JOIN bridge br            ON br.contracting_office_id  = off.contracting_office_id
LEFT JOIN sole_source ss       ON ss.contracting_office_id  = off.contracting_office_id
LEFT JOIN naics_shift_agg ns   ON ns.contracting_office_id  = off.contracting_office_id;


-- ============================================================
-- View 3: v_competitor_dossier
-- Comprehensive competitor profile per vendor (UEI).
-- Sources: entity, fpds_contract, usaspending_award,
--          entity_naics, entity_sba_certification,
--          entity_business_type, sam_subaward.
-- ============================================================

CREATE OR REPLACE VIEW v_competitor_dossier AS
WITH fpds_agg AS (
    SELECT
        fc.vendor_uei,
        COUNT(*)                                                       AS fpds_contract_count,
        SUM(fc.dollars_obligated)                                      AS fpds_total_obligated,
        SUM(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
                 THEN fc.dollars_obligated ELSE 0 END)                 AS fpds_obligated_3yr,
        SUM(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
                 THEN fc.dollars_obligated ELSE 0 END)                 AS fpds_obligated_5yr,
        COUNT(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
                   THEN 1 END)                                         AS fpds_count_3yr,
        COUNT(CASE WHEN fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
                   THEN 1 END)                                         AS fpds_count_5yr,
        AVG(fc.dollars_obligated)                                      AS fpds_avg_contract_value,
        MAX(fc.date_signed)                                            AS fpds_most_recent_award,
        -- Top 3 NAICS by contract count
        SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT fc.naics_code
            ORDER BY fc.naics_code SEPARATOR ','), ',', 5)             AS fpds_top_naics,
        -- Top agencies
        SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT fc.agency_name
            ORDER BY fc.agency_name SEPARATOR ' | '), ' | ', 5)       AS fpds_top_agencies
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
    GROUP BY fc.vendor_uei
),
usa_agg AS (
    SELECT
        ua.recipient_uei                                               AS vendor_uei,
        COUNT(*)                                                       AS usa_contract_count,
        SUM(ua.total_obligation)                                       AS usa_total_obligated,
        SUM(CASE WHEN ua.start_date >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
                 THEN ua.total_obligation ELSE 0 END)                  AS usa_obligated_3yr,
        SUM(CASE WHEN ua.start_date >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
                 THEN ua.total_obligation ELSE 0 END)                  AS usa_obligated_5yr,
        MAX(ua.start_date)                                             AS usa_most_recent_award,
        SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT ua.awarding_agency_name
            ORDER BY ua.awarding_agency_name SEPARATOR ' | '), ' | ', 5) AS usa_top_agencies
    FROM usaspending_award ua
    WHERE ua.award_type IN ('DELIVERY ORDER','PURCHASE ORDER','BPA CALL',
                            'DEFINITIVE CONTRACT','DO','DCA','PO','BPA')
      AND ua.deleted_at IS NULL
    GROUP BY ua.recipient_uei
),
sub_agg AS (
    SELECT
        sa.sub_uei                                                     AS vendor_uei,
        COUNT(*)                                                       AS sub_count,
        SUM(sa.sub_amount)                                             AS sub_total_value,
        AVG(sa.sub_amount)                                             AS sub_avg_value
    FROM sam_subaward sa
    WHERE sa.sub_amount > 0
    GROUP BY sa.sub_uei
),
prime_sub_agg AS (
    SELECT
        sa.prime_uei                                                   AS vendor_uei,
        COUNT(*)                                                       AS prime_sub_count,
        SUM(sa.sub_amount)                                             AS prime_sub_total_value
    FROM sam_subaward sa
    WHERE sa.sub_amount > 0
    GROUP BY sa.prime_uei
)
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.dba_name,
    e.registration_status,
    e.registration_expiration_date,
    e.primary_naics,
    e.entity_url,
    -- NAICS codes registered in SAM
    GROUP_CONCAT(DISTINCT en.naics_code ORDER BY en.is_primary DESC, en.naics_code SEPARATOR ', ')
        AS registered_naics_codes,
    -- SBA certifications (active only)
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(esc.sba_type_desc, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ')
        AS sba_certifications,
    -- Business types
    GROUP_CONCAT(DISTINCT ebt.business_type_code ORDER BY ebt.business_type_code SEPARATOR ', ')
        AS business_type_codes,
    -- FPDS metrics
    COALESCE(fa.fpds_contract_count, 0)                                AS fpds_contract_count,
    fa.fpds_total_obligated,
    fa.fpds_obligated_3yr,
    fa.fpds_obligated_5yr,
    fa.fpds_count_3yr,
    fa.fpds_count_5yr,
    fa.fpds_avg_contract_value,
    fa.fpds_most_recent_award,
    fa.fpds_top_naics,
    fa.fpds_top_agencies,
    -- USASpending metrics
    COALESCE(uaa.usa_contract_count, 0)                                AS usa_contract_count,
    uaa.usa_total_obligated,
    uaa.usa_obligated_3yr,
    uaa.usa_obligated_5yr,
    uaa.usa_most_recent_award,
    uaa.usa_top_agencies,
    -- Sub-contracting (as sub)
    COALESCE(sa.sub_count, 0)                                          AS sub_contract_count,
    sa.sub_total_value,
    sa.sub_avg_value,
    -- Sub-contracting (as prime)
    COALESCE(psa.prime_sub_count, 0)                                   AS prime_sub_awards_count,
    psa.prime_sub_total_value
FROM entity e
LEFT JOIN entity_naics en
    ON en.uei_sam = e.uei_sam
LEFT JOIN entity_sba_certification esc
    ON esc.uei_sam = e.uei_sam
    AND (esc.certification_exit_date IS NULL OR esc.certification_exit_date > CURDATE())
LEFT JOIN entity_business_type ebt
    ON ebt.uei_sam = e.uei_sam
LEFT JOIN fpds_agg fa
    ON fa.vendor_uei = e.uei_sam
LEFT JOIN usa_agg uaa
    ON uaa.vendor_uei = e.uei_sam
LEFT JOIN sub_agg sa
    ON sa.vendor_uei = e.uei_sam
LEFT JOIN prime_sub_agg psa
    ON psa.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY
    e.uei_sam, e.legal_business_name, e.dba_name,
    e.registration_status, e.registration_expiration_date,
    e.primary_naics, e.entity_url,
    fa.fpds_contract_count, fa.fpds_total_obligated,
    fa.fpds_obligated_3yr, fa.fpds_obligated_5yr,
    fa.fpds_count_3yr, fa.fpds_count_5yr,
    fa.fpds_avg_contract_value, fa.fpds_most_recent_award,
    fa.fpds_top_naics, fa.fpds_top_agencies,
    uaa.usa_contract_count, uaa.usa_total_obligated,
    uaa.usa_obligated_3yr, uaa.usa_obligated_5yr,
    uaa.usa_most_recent_award, uaa.usa_top_agencies,
    sa.sub_count, sa.sub_total_value, sa.sub_avg_value,
    psa.prime_sub_count, psa.prime_sub_total_value;


-- ============================================================
-- View 4: v_agency_buying_pattern
-- Agency procurement behavior profile per awarding agency.
-- Sources: fpds_contract (primary for detailed breakdowns).
-- ============================================================

CREATE OR REPLACE VIEW v_agency_buying_pattern AS
WITH agency_yearly AS (
    SELECT
        fc.agency_id,
        fc.agency_name,
        YEAR(fc.date_signed)                                           AS award_year,
        QUARTER(fc.date_signed)                                        AS award_quarter,
        COUNT(*)                                                       AS contract_count,
        SUM(fc.dollars_obligated)                                      AS total_obligated,
        -- Set-aside breakdown
        SUM(CASE WHEN fc.set_aside_type IN ('SBA','SBP','RSB')        THEN 1 ELSE 0 END) AS small_business_count,
        SUM(CASE WHEN fc.set_aside_type IN ('WOSB','EDWOSB')          THEN 1 ELSE 0 END) AS wosb_count,
        SUM(CASE WHEN fc.set_aside_type IN ('8A','8AN')               THEN 1 ELSE 0 END) AS eight_a_count,
        SUM(CASE WHEN fc.set_aside_type IN ('HZC','HZS')              THEN 1 ELSE 0 END) AS hubzone_count,
        SUM(CASE WHEN fc.set_aside_type IN ('SDVOSBC','SDVOSBS')      THEN 1 ELSE 0 END) AS sdvosb_count,
        SUM(CASE WHEN fc.set_aside_type IS NULL
                   OR fc.set_aside_type IN ('NONE','')                 THEN 1 ELSE 0 END) AS unrestricted_count,
        -- Competition breakdown
        SUM(CASE WHEN fc.extent_competed IN ('FULL','A')               THEN 1 ELSE 0 END) AS full_competition_count,
        SUM(CASE WHEN fc.extent_competed IN ('NONCOMP','NOT COMPETED','NDO')
                                                                       THEN 1 ELSE 0 END) AS sole_source_count,
        SUM(CASE WHEN fc.extent_competed NOT IN ('FULL','A','NONCOMP','NOT COMPETED','NDO')
                  AND fc.extent_competed IS NOT NULL                    THEN 1 ELSE 0 END) AS limited_competition_count,
        -- Contract type distribution
        SUM(CASE WHEN fc.type_of_contract_pricing IN ('FFP','J')       THEN 1 ELSE 0 END) AS ffp_count,
        SUM(CASE WHEN fc.type_of_contract_pricing IN ('TM','T')        THEN 1 ELSE 0 END) AS tm_count,
        SUM(CASE WHEN fc.type_of_contract_pricing IN ('CPFF','CPAF','CPIF','K','L','R','S','U','V','Y')
                                                                       THEN 1 ELSE 0 END) AS cost_plus_count,
        SUM(CASE WHEN fc.type_of_contract_pricing NOT IN ('FFP','J','TM','T','CPFF','CPAF','CPIF','K','L','R','S','U','V','Y')
                  AND fc.type_of_contract_pricing IS NOT NULL           THEN 1 ELSE 0 END) AS other_type_count
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
      AND fc.agency_id IS NOT NULL
    GROUP BY fc.agency_id, fc.agency_name,
             YEAR(fc.date_signed), QUARTER(fc.date_signed)
)
SELECT
    ay.agency_id,
    ay.agency_name,
    ay.award_year,
    ay.award_quarter,
    ay.contract_count,
    ay.total_obligated,
    -- Set-aside utilization percentages
    ROUND(ay.small_business_count / NULLIF(ay.contract_count, 0) * 100, 1)  AS small_business_pct,
    ROUND(ay.wosb_count           / NULLIF(ay.contract_count, 0) * 100, 1)  AS wosb_pct,
    ROUND(ay.eight_a_count        / NULLIF(ay.contract_count, 0) * 100, 1)  AS eight_a_pct,
    ROUND(ay.hubzone_count        / NULLIF(ay.contract_count, 0) * 100, 1)  AS hubzone_pct,
    ROUND(ay.sdvosb_count         / NULLIF(ay.contract_count, 0) * 100, 1)  AS sdvosb_pct,
    ROUND(ay.unrestricted_count   / NULLIF(ay.contract_count, 0) * 100, 1)  AS unrestricted_pct,
    -- Competition percentages
    ROUND(ay.full_competition_count    / NULLIF(ay.contract_count, 0) * 100, 1) AS full_competition_pct,
    ROUND(ay.sole_source_count         / NULLIF(ay.contract_count, 0) * 100, 1) AS sole_source_pct,
    ROUND(ay.limited_competition_count / NULLIF(ay.contract_count, 0) * 100, 1) AS limited_competition_pct,
    -- Contract type percentages
    ROUND(ay.ffp_count        / NULLIF(ay.contract_count, 0) * 100, 1) AS ffp_pct,
    ROUND(ay.tm_count         / NULLIF(ay.contract_count, 0) * 100, 1) AS tm_pct,
    ROUND(ay.cost_plus_count  / NULLIF(ay.contract_count, 0) * 100, 1) AS cost_plus_pct,
    ROUND(ay.other_type_count / NULLIF(ay.contract_count, 0) * 100, 1) AS other_type_pct,
    -- Raw counts for downstream aggregation
    ay.small_business_count,
    ay.wosb_count,
    ay.eight_a_count,
    ay.hubzone_count,
    ay.sdvosb_count,
    ay.unrestricted_count,
    ay.full_competition_count,
    ay.sole_source_count,
    ay.limited_competition_count,
    ay.ffp_count,
    ay.tm_count,
    ay.cost_plus_count,
    ay.other_type_count
FROM agency_yearly ay;


-- ============================================================
-- View 5: v_contracting_office_profile
-- Enhanced office-level procurement profile.
-- Sources: fpds_contract (last 5 years).
-- ============================================================

CREATE OR REPLACE VIEW v_contracting_office_profile AS
WITH office_stats AS (
    SELECT
        fc.contracting_office_id,
        fc.contracting_office_name,
        fc.agency_name,
        COUNT(*)                                                       AS total_awards,
        SUM(fc.dollars_obligated)                                      AS total_obligated,
        ROUND(AVG(fc.dollars_obligated), 2)                            AS avg_award_value,
        MIN(fc.date_signed)                                            AS earliest_award,
        MAX(fc.date_signed)                                            AS latest_award,
        -- Top NAICS (most frequent)
        SUBSTRING_INDEX(GROUP_CONCAT(fc.naics_code
            ORDER BY fc.naics_code SEPARATOR ','), ',', 5)             AS top_naics_codes,
        -- Set-aside preferences
        ROUND(SUM(CASE WHEN fc.set_aside_type IN ('SBA','SBP','RSB')  THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS small_business_pct,
        ROUND(SUM(CASE WHEN fc.set_aside_type IN ('WOSB','EDWOSB')    THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS wosb_pct,
        ROUND(SUM(CASE WHEN fc.set_aside_type IN ('8A','8AN')         THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS eight_a_pct,
        ROUND(SUM(CASE WHEN fc.set_aside_type IN ('HZC','HZS')        THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS hubzone_pct,
        ROUND(SUM(CASE WHEN fc.set_aside_type IN ('SDVOSBC','SDVOSBS') THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS sdvosb_pct,
        ROUND(SUM(CASE WHEN fc.set_aside_type IS NULL
                         OR fc.set_aside_type IN ('NONE','')           THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS unrestricted_pct,
        -- Contract type distribution
        ROUND(SUM(CASE WHEN fc.type_of_contract_pricing IN ('FFP','J') THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS ffp_pct,
        ROUND(SUM(CASE WHEN fc.type_of_contract_pricing IN ('TM','T')  THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS tm_pct,
        ROUND(SUM(CASE WHEN fc.type_of_contract_pricing IN ('CPFF','CPAF','CPIF','K','L','R','S','U','V','Y')
                       THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS cost_plus_pct,
        -- Competition preference
        ROUND(SUM(CASE WHEN fc.extent_competed IN ('FULL','A')         THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS full_competition_pct,
        ROUND(SUM(CASE WHEN fc.extent_competed IN ('NONCOMP','NOT COMPETED','NDO')
                       THEN 1 ELSE 0 END)
              / COUNT(*) * 100, 1)                                     AS sole_source_pct,
        -- Average procurement timeline (posting to award, via opportunity table)
        NULL                                                           AS avg_procurement_days
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 5 YEAR)
      AND fc.contracting_office_id IS NOT NULL
    GROUP BY fc.contracting_office_id, fc.contracting_office_name, fc.agency_name
),
opp_timeline AS (
    SELECT
        o.contracting_office_id,
        ROUND(AVG(DATEDIFF(o.award_date, o.posted_date)), 1) AS avg_procurement_days
    FROM opportunity o
    WHERE o.posted_date IS NOT NULL
      AND o.award_date IS NOT NULL
      AND o.contracting_office_id IS NOT NULL
    GROUP BY o.contracting_office_id
)
SELECT
    os.contracting_office_id,
    os.contracting_office_name,
    os.agency_name,
    os.total_awards,
    os.total_obligated,
    os.avg_award_value,
    os.earliest_award,
    os.latest_award,
    os.top_naics_codes,
    os.small_business_pct,
    os.wosb_pct,
    os.eight_a_pct,
    os.hubzone_pct,
    os.sdvosb_pct,
    os.unrestricted_pct,
    os.ffp_pct,
    os.tm_pct,
    os.cost_plus_pct,
    os.full_competition_pct,
    os.sole_source_pct,
    COALESCE(ot.avg_procurement_days, 0) AS avg_procurement_days
FROM office_stats os
LEFT JOIN opp_timeline ot ON ot.contracting_office_id = os.contracting_office_id;
