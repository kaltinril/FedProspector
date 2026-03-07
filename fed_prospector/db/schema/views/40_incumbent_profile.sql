-- views/40_incumbent_profile.sql
-- Incumbent profile view - entity + certifications + past performance by UEI

USE fed_contracts;

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
    COALESCE(fc_agg.total_past_contracts, 0) AS total_past_contracts,
    fc_agg.total_obligated,
    fc_agg.most_recent_award
FROM entity e
LEFT JOIN entity_sba_certification sc
    ON sc.uei_sam = e.uei_sam
    AND (sc.certification_exit_date IS NULL OR sc.certification_exit_date > CURDATE())
LEFT JOIN (
    SELECT vendor_uei,
           COUNT(*) AS total_past_contracts,
           SUM(dollars_obligated) AS total_obligated,
           MAX(date_signed) AS most_recent_award
    FROM fpds_contract
    GROUP BY vendor_uei
) fc_agg ON fc_agg.vendor_uei = e.uei_sam
GROUP BY e.uei_sam, e.legal_business_name, e.dba_name,
         e.registration_status, e.primary_naics, e.entity_url,
         fc_agg.total_past_contracts, fc_agg.total_obligated, fc_agg.most_recent_award;
