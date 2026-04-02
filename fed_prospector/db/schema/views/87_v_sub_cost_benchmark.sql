-- ============================================================
-- 87_v_sub_cost_benchmark.sql — Subcontract cost benchmark view (Phase 115B)
-- ============================================================

CREATE OR REPLACE VIEW v_sub_cost_benchmark AS
SELECT
    sa.naics_code,
    sa.prime_agency_name,
    sa.sub_business_type,
    COUNT(*)               AS sub_count,
    SUM(sa.sub_amount)     AS total_sub_value,
    AVG(sa.sub_amount)     AS avg_sub_value,
    MIN(sa.sub_amount)     AS min_sub_value,
    MAX(sa.sub_amount)     AS max_sub_value
FROM sam_subaward sa
WHERE sa.sub_amount > 0
GROUP BY sa.naics_code, sa.prime_agency_name, sa.sub_business_type;
