-- views/20_competitor_analysis.sql
-- Competitor analysis view - entity profiles with business types and past performance

USE fed_contracts;

CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.primary_naics,
    n.description AS naics_description,
    sector.description AS naics_sector,
    es.description AS entity_structure,
    GROUP_CONCAT(DISTINCT CONCAT(ebt.business_type_code, ':', COALESCE(rbt.description, ''))
        ORDER BY ebt.business_type_code SEPARATOR '; ') AS business_types,
    GROUP_CONCAT(DISTINCT rbt.category ORDER BY rbt.category SEPARATOR ', ') AS business_type_categories,
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(rst.description, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ') AS sba_certifications,
    COALESCE(MAX(fc_agg.past_contracts), 0) AS past_contracts,
    MAX(fc_agg.total_obligated) AS total_obligated,
    MAX(fc_agg.most_recent_award) AS most_recent_award
FROM entity e
LEFT JOIN ref_naics_code n ON n.naics_code = e.primary_naics
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(e.primary_naics, 2)
    AND sector.code_level = 1
LEFT JOIN ref_entity_structure es ON es.structure_code = e.entity_structure_code
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN ref_business_type rbt ON rbt.business_type_code = ebt.business_type_code
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN ref_sba_type rst ON rst.sba_type_code = esc.sba_type_code
LEFT JOIN (
    SELECT vendor_uei,
           COUNT(*) AS past_contracts,
           SUM(dollars_obligated) AS total_obligated,
           MAX(date_signed) AS most_recent_award
    FROM fpds_contract
    GROUP BY vendor_uei
) fc_agg ON fc_agg.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics,
         n.description, sector.description, es.description;
