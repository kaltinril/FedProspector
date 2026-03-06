-- views/01_search_views.sql
-- Base search views for entity, exclusion, and award queries

USE fed_contracts;

CREATE OR REPLACE VIEW v_entity_search AS
SELECT
    e.uei_sam, e.legal_business_name, e.dba_name, e.cage_code,
    e.primary_naics, e.registration_status, e.entity_structure_code,
    e.registration_expiration_date, e.last_update_date, e.entity_url,
    e.exclusion_status_flag, e.uei_duns,
    e.state_of_incorporation, e.country_of_incorporation,
    e.initial_registration_date, e.activation_date,
    ea.state_or_province AS pop_state,
    ea.congressional_district AS pop_congressional_district,
    ea.city AS pop_city
FROM entity e
LEFT JOIN entity_address ea ON e.uei_sam = ea.uei_sam
    AND ea.address_type = 'PHYSICAL';

CREATE OR REPLACE VIEW v_active_exclusions AS
SELECT *
FROM sam_exclusion
WHERE termination_date IS NULL
   OR termination_date > CURDATE();

CREATE OR REPLACE VIEW v_base_awards AS
SELECT *
FROM fpds_contract
WHERE modification_number = '0';
