-- ============================================================
-- 86_v_price_to_win.sql — Price-to-win comparable awards view (Phase 115B)
-- ============================================================

CREATE OR REPLACE VIEW v_price_to_win_comparable AS
SELECT
    fc.naics_code,
    fc.agency_name                AS contracting_agency_name,
    fc.set_aside_type             AS type_of_set_aside,
    fc.type_of_contract_pricing,
    fc.base_and_all_options       AS base_and_all_options_value,
    fc.dollars_obligated,
    fc.number_of_offers,
    DATEDIFF(COALESCE(fc.ultimate_completion_date, fc.completion_date), fc.effective_date) AS period_of_performance_days,
    fc.contract_id,
    fc.vendor_name,
    fc.date_signed
FROM fpds_contract fc
WHERE fc.modification_number = '0'
  AND fc.base_and_all_options > 0
  AND fc.date_signed >= DATE_SUB(CURDATE(), INTERVAL 10 YEAR);
