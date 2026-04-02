-- ============================================================
-- 85_v_labor_rate_heatmap.sql — Labor rate heatmap view (Phase 115B)
-- ============================================================

CREATE OR REPLACE VIEW v_labor_rate_heatmap AS
SELECT
    clc.canonical_name,
    clc.category_group,
    glr.worksite,
    glr.education_level,
    glr.schedule,
    COUNT(*)             AS rate_count,
    MIN(glr.current_price) AS min_rate,
    AVG(glr.current_price) AS avg_rate,
    MAX(glr.current_price) AS max_rate
FROM gsa_labor_rate glr
JOIN labor_category_mapping lcm ON lcm.raw_labor_category = glr.labor_category
JOIN canonical_labor_category clc ON clc.id = lcm.canonical_id
WHERE glr.current_price > 0
GROUP BY clc.canonical_name, clc.category_group, glr.worksite, glr.education_level, glr.schedule;
