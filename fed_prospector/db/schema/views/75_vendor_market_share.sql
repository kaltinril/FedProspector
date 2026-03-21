-- views/75_vendor_market_share.sql
-- Vendor market share by NAICS code from FPDS base awards

USE fed_contracts;

CREATE OR REPLACE VIEW v_vendor_market_share AS
SELECT
    naics_code,
    MAX(vendor_name) AS vendor_name,
    vendor_uei,
    COUNT(*) AS award_count,
    SUM(base_and_all_options) AS total_value,
    AVG(base_and_all_options) AS average_value,
    MAX(date_signed) AS last_award_date
FROM fpds_contract
WHERE vendor_uei IS NOT NULL
  AND vendor_uei != ''
  AND modification_number = '0'
GROUP BY naics_code, vendor_uei;
