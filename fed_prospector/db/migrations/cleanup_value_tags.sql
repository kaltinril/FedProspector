-- ============================================================
-- cleanup_value_tags.sql
-- Remove [VALUE] tags from key_requirements JSON arrays
--
-- The AI analyzer was tagging contract dollar values as
-- "[VALUE] $65M" etc. in key_requirements. These are not
-- requirements and should be removed.
--
-- Affects: document_intel_summary, opportunity_attachment_summary
-- Column:  key_requirements (JSON array of strings)
--
-- Safe to re-run: only touches rows containing [VALUE] tags.
-- ============================================================

USE fed_contracts;

-- Preview affected rows (uncomment to check before running)
-- SELECT intel_id, key_requirements
-- FROM document_intel_summary
-- WHERE JSON_SEARCH(key_requirements, 'one', '[VALUE]%') IS NOT NULL;

-- SELECT summary_id, key_requirements
-- FROM opportunity_attachment_summary
-- WHERE JSON_SEARCH(key_requirements, 'one', '[VALUE]%') IS NOT NULL;

-- 1. Clean document_intel_summary
UPDATE document_intel_summary dis
SET dis.key_requirements = (
    SELECT JSON_ARRAYAGG(val)
    FROM JSON_TABLE(dis.key_requirements, '$[*]' COLUMNS (val VARCHAR(500) PATH '$')) jt
    WHERE val NOT LIKE '[VALUE]%'
)
WHERE JSON_SEARCH(dis.key_requirements, 'one', '[VALUE]%') IS NOT NULL;

-- 2. Clean opportunity_attachment_summary
UPDATE opportunity_attachment_summary oas
SET oas.key_requirements = (
    SELECT JSON_ARRAYAGG(val)
    FROM JSON_TABLE(oas.key_requirements, '$[*]' COLUMNS (val VARCHAR(500) PATH '$')) jt
    WHERE val NOT LIKE '[VALUE]%'
)
WHERE JSON_SEARCH(oas.key_requirements, 'one', '[VALUE]%') IS NOT NULL;

-- Note: if ALL entries in a row are [VALUE] tags, JSON_ARRAYAGG returns NULL.
-- That is the correct behavior — an empty result means no key requirements.
