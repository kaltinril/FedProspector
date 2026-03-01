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
