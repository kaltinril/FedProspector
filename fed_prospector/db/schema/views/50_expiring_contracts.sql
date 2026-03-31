-- views/50_expiring_contracts.sql
-- Contracts expiring within 18 months, with incumbent health signals
-- Phase 127: USASpending UNION with FPDS-preferred deduplication
-- Optimized: joins after dedup, no exclusion, no burn rate calc in SQL

USE fed_contracts;

CREATE OR REPLACE VIEW v_expiring_contracts AS
WITH combined AS (
    -- FPDS contracts (priority source)
    SELECT
        fc.contract_id AS piid,
        'FPDS' AS source,
        1 AS source_priority,
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
        fc.solicitation_number
    FROM fpds_contract fc
    WHERE fc.modification_number = '0'
      AND fc.ultimate_completion_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH)

    UNION ALL

    -- USASpending contracts (secondary source)
    SELECT
        ua.piid,
        'USASpending' AS source,
        2 AS source_priority,
        ua.award_description AS description,
        ua.naics_code,
        ua.type_of_set_aside AS set_aside_type,
        ua.recipient_uei AS vendor_uei,
        ua.recipient_name AS vendor_name,
        ua.awarding_agency_name AS agency_name,
        ua.awarding_sub_agency_name AS contracting_office_name,
        ua.base_and_all_options_value AS base_and_all_options,
        ua.total_obligation AS dollars_obligated,
        ua.end_date AS ultimate_completion_date,
        ua.start_date AS date_signed,
        ua.solicitation_identifier AS solicitation_number
    FROM usaspending_award ua
    WHERE ua.award_type IN ('DELIVERY ORDER','PURCHASE ORDER','BPA CALL','DEFINITIVE CONTRACT','DO','DCA','PO','BPA')
      AND ua.end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH)
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
    r.contracting_office_name,
    r.base_and_all_options,
    r.dollars_obligated,
    r.ultimate_completion_date,
    r.date_signed,
    r.solicitation_number,
    e.registration_status,
    e.registration_expiration_date
FROM ranked r
LEFT JOIN entity e ON e.uei_sam = r.vendor_uei
WHERE r.rn = 1;
