-- views/30_procurement_intelligence.sql
-- Procurement intelligence view - opportunity + award history + spending + incumbent

USE fed_contracts;

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
    fc.source_selection_code,
    fc.contract_bundling_code,
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
