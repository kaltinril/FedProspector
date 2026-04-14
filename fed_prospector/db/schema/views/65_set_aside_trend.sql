-- views/65_set_aside_trend.sql
-- NAICS-level set-aside trend aggregation: yearly contract counts and values by set-aside type
-- Supports Phase 109 (Set-Aside Shift Analysis) trend charts

USE fed_contracts;

CREATE OR REPLACE VIEW v_set_aside_trend AS
SELECT
    fc.naics_code,
    -- Federal fiscal year: Oct-Sep (month >= 10 belongs to next fiscal year)
    CASE
        WHEN MONTH(fc.date_signed) >= 10 THEN YEAR(fc.date_signed) + 1
        ELSE YEAR(fc.date_signed)
    END AS fiscal_year,
    fc.set_aside_type,
    COALESCE(ref.category, fc.set_aside_type) AS set_aside_category,
    COUNT(*) AS contract_count,
    SUM(fc.base_and_all_options) AS total_value,
    AVG(fc.base_and_all_options) AS avg_value,
    SUM(CASE WHEN JSON_EXTRACT(fc.awardee_socioeconomic, '$.wosb') = CAST('true' AS JSON) THEN 1 ELSE 0 END) AS wosb_awardee_count,
    SUM(CASE WHEN JSON_EXTRACT(fc.awardee_socioeconomic, '$.sba8a') = CAST('true' AS JSON) THEN 1 ELSE 0 END) AS sba8a_awardee_count
FROM fpds_contract fc
LEFT JOIN ref_set_aside_type ref ON fc.set_aside_type = ref.set_aside_code
WHERE fc.modification_number = '0'
  AND fc.date_signed IS NOT NULL
  AND fc.naics_code IS NOT NULL
  AND CASE
        WHEN MONTH(fc.date_signed) >= 10 THEN YEAR(fc.date_signed) + 1
        ELSE YEAR(fc.date_signed)
      END >= YEAR(CURDATE()) - 6
GROUP BY
    fc.naics_code,
    fiscal_year,
    fc.set_aside_type,
    set_aside_category;
