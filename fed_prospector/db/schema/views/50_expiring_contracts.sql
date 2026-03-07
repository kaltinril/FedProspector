-- views/50_expiring_contracts.sql
-- Contracts expiring within 18 months, with incumbent health signals and burn rate

USE fed_contracts;

CREATE OR REPLACE VIEW v_expiring_contracts AS
SELECT
    fc.contract_id AS piid,
    fc.modification_number,
    fc.description,
    fc.naics_code,
    fc.set_aside_type,
    fc.vendor_uei,
    fc.vendor_name,
    fc.agency_name,
    fc.contracting_office_name,
    fc.base_and_all_options,
    fc.dollars_obligated,
    fc.ultimate_completion_date,
    fc.date_signed,
    fc.solicitation_number,
    -- Incumbent health signals
    e.registration_status,
    e.registration_expiration_date,
    CASE WHEN ex.id IS NOT NULL THEN 1 ELSE 0 END AS is_excluded,
    ex.exclusion_type,
    -- Burn rate calculations
    TIMESTAMPDIFF(MONTH, fc.date_signed, fc.ultimate_completion_date) AS total_months,
    TIMESTAMPDIFF(MONTH, fc.date_signed, NOW()) AS elapsed_months,
    CASE
        WHEN TIMESTAMPDIFF(MONTH, fc.date_signed, NOW()) > 0
        THEN fc.dollars_obligated / TIMESTAMPDIFF(MONTH, fc.date_signed, NOW())
        ELSE NULL
    END AS monthly_burn_rate,
    CASE
        WHEN fc.base_and_all_options > 0
        THEN ROUND(fc.dollars_obligated / fc.base_and_all_options * 100, 1)
        ELSE NULL
    END AS percent_spent,
    -- Months remaining
    TIMESTAMPDIFF(MONTH, NOW(), fc.ultimate_completion_date) AS months_remaining
FROM fpds_contract fc
LEFT JOIN entity e ON e.uei_sam = fc.vendor_uei
LEFT JOIN sam_exclusion ex ON ex.uei = fc.vendor_uei AND ex.termination_date IS NULL
WHERE fc.modification_number = '0'
  AND fc.ultimate_completion_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH);
