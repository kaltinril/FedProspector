-- 07_views.sql
-- Key views (4 views)

USE fed_contracts;

CREATE OR REPLACE VIEW v_target_opportunities AS
SELECT
    o.notice_id,
    o.title,
    o.solicitation_number,
    o.department_name,
    o.office,
    o.posted_date,
    o.response_deadline,
    DATEDIFF(o.response_deadline, NOW()) AS days_until_due,
    o.set_aside_code,
    o.set_aside_description,
    sa.category AS set_aside_category,
    o.naics_code,
    n.description AS naics_description,
    n.level_name AS naics_level,
    sector.description AS naics_sector,
    ss.size_standard,
    ss.size_type,
    o.award_amount,
    o.pop_state,
    o.pop_city,
    o.description,
    o.link,
    p.prospect_id,
    p.status AS prospect_status,
    p.priority AS prospect_priority,
    u.display_name AS assigned_to
FROM opportunity o
LEFT JOIN ref_naics_code n ON n.naics_code = o.naics_code
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(o.naics_code, 2)
    AND sector.code_level = 1
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
LEFT JOIN ref_set_aside_type sa ON sa.set_aside_code = o.set_aside_code
LEFT JOIN prospect p ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE o.active = 'Y'
  AND o.set_aside_code IN ('WOSB', 'EDWOSB', 'WOSBSS', 'EDWOSBSS', 'SBA', '8A', '8AN')
  AND o.response_deadline > NOW();

CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.primary_naics,
    n.description AS naics_description,
    sector.description AS naics_sector,
    es.description AS entity_structure,
    GROUP_CONCAT(DISTINCT CONCAT(ebt.business_type_code, ':', COALESCE(rbt.description, ''))
        ORDER BY ebt.business_type_code SEPARATOR '; ') AS business_types,
    GROUP_CONCAT(DISTINCT rbt.category ORDER BY rbt.category SEPARATOR ', ') AS business_type_categories,
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(rst.description, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ') AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN ref_naics_code n ON n.naics_code = e.primary_naics
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(e.primary_naics, 2)
    AND sector.code_level = 1
LEFT JOIN ref_entity_structure es ON es.structure_code = e.entity_structure_code
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN ref_business_type rbt ON rbt.business_type_code = ebt.business_type_code
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN ref_sba_type rst ON rst.sba_type_code = esc.sba_type_code
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics,
         n.description, sector.description, es.description;

-- Procurement intelligence: joins opportunity -> fpds_contract -> usaspending_award
-- for a given solicitation. Returns award history, bidder count, burn rate, incumbent.
CREATE OR REPLACE VIEW v_procurement_intelligence AS
SELECT
    -- Opportunity fields
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.type AS opportunity_type,
    o.set_aside_code,
    o.naics_code,
    o.posted_date,
    o.response_deadline,
    o.department_name,
    o.sub_tier,
    o.office,
    o.award_number,
    o.award_amount AS opp_award_amount,
    o.award_date,
    o.link AS sam_gov_link,
    -- FPDS contract fields
    fc.contract_id AS piid,
    fc.vendor_name AS awardee_name,
    fc.vendor_uei AS awardee_uei,
    fc.number_of_offers AS bidder_count,
    fc.extent_competed,
    fc.dollars_obligated,
    fc.base_and_all_options AS contract_ceiling,
    fc.date_signed,
    fc.effective_date,
    fc.completion_date,
    fc.ultimate_completion_date,
    fc.type_of_contract,
    fc.type_of_contract_pricing,
    -- USASpending fields
    ua.total_obligation AS total_spent,
    ua.base_and_all_options_value AS usa_ceiling,
    ua.start_date AS performance_start,
    ua.end_date AS performance_end,
    ua.recipient_name AS incumbent_name,
    ua.recipient_uei AS incumbent_uei,
    -- Computed
    DATEDIFF(COALESCE(fc.ultimate_completion_date, fc.completion_date), fc.effective_date) AS total_performance_days,
    ROUND(ua.total_obligation / GREATEST(TIMESTAMPDIFF(MONTH, ua.start_date, CURDATE()), 1), 2) AS monthly_burn_rate
FROM opportunity o
LEFT JOIN fpds_contract fc
    ON fc.contract_id = o.award_number
    AND fc.modification_number = '0'
LEFT JOIN usaspending_award ua
    ON ua.solicitation_identifier = o.solicitation_number;

-- Incumbent profile: given a UEI, returns entity profile + certifications + past performance.
CREATE OR REPLACE VIEW v_incumbent_profile AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.dba_name,
    e.registration_status,
    e.primary_naics,
    e.entity_url,
    GROUP_CONCAT(DISTINCT sc.sba_type_desc ORDER BY sc.sba_type_code SEPARATOR ', ') AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS total_past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN entity_sba_certification sc
    ON sc.uei_sam = e.uei_sam
    AND (sc.certification_exit_date IS NULL OR sc.certification_exit_date > CURDATE())
LEFT JOIN fpds_contract fc
    ON fc.vendor_uei = e.uei_sam
GROUP BY e.uei_sam, e.legal_business_name, e.dba_name,
         e.registration_status, e.primary_naics, e.entity_url;
