-- 07_views.sql
-- Key views (2 views)

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
    o.naics_code,
    n.description AS naics_description,
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
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
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
    GROUP_CONCAT(DISTINCT ebt.business_type_code) AS business_types,
    GROUP_CONCAT(DISTINCT esc.sba_type_code) AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics;
