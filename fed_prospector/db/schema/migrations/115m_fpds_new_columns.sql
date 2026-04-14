-- Phase 115M: Add socioeconomic + source selection columns to fpds_contract

ALTER TABLE fpds_contract
    ADD COLUMN source_selection_code VARCHAR(10) DEFAULT NULL COMMENT 'LPTA vs Best Value vs sealed bid — sourceSelectionProcess.code',
    ADD COLUMN contract_bundling_code VARCHAR(10) DEFAULT NULL COMMENT 'Whether contract was bundled — contractBundling.code',
    ADD COLUMN awardee_socioeconomic JSON DEFAULT NULL COMMENT 'Awardee cert flags: sba8a, wosb, edwosb, sdvosb, hubzone, etc.';

ALTER TABLE fpds_contract
    ADD COLUMN is_wosb_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.wosb') = CAST('true' AS JSON)) STORED,
    ADD COLUMN is_8a_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.sba8a') = CAST('true' AS JSON)) STORED,
    ADD INDEX idx_fpds_wosb (is_wosb_awardee),
    ADD INDEX idx_fpds_8a (is_8a_awardee);
