-- Phase 92: Add unique index to sam_subaward for batch INSERT ON DUPLICATE KEY UPDATE
--
-- Pre-requisite: Verify no duplicate rows exist before running:
--   SELECT prime_piid, sub_uei, sub_date, COUNT(*) c
--   FROM sam_subaward GROUP BY prime_piid, sub_uei, sub_date HAVING c > 1;
--
-- If duplicates exist, deduplicate first:
--   DELETE s1 FROM sam_subaward s1
--   INNER JOIN sam_subaward s2
--   WHERE s1.id > s2.id
--     AND s1.prime_piid <=> s2.prime_piid
--     AND s1.sub_uei <=> s2.sub_uei
--     AND s1.sub_date <=> s2.sub_date;

USE fed_contracts;

ALTER TABLE sam_subaward
    ADD UNIQUE KEY uk_sub_key (prime_piid, sub_uei, sub_date);
