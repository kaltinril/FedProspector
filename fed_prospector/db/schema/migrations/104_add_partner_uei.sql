-- Phase 104: Add partner_uei column to organization_entity
-- UEI used for JV partnership filings (awards may be filed under this UEI)
ALTER TABLE organization_entity ADD COLUMN partner_uei VARCHAR(13) NULL AFTER uei_sam;
