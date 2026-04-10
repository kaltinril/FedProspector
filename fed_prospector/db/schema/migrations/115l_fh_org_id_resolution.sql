-- Migration: Phase 115L Item 5 — fh_org_id resolution
-- Adds fh_org_id column to 3 tables and creates agency_name_alias seed data.

-- Step 1: Add columns (IF NOT EXISTS not supported for ADD COLUMN;
-- check with INFORMATION_SCHEMA before running)

-- ALTER TABLE opportunity ADD COLUMN fh_org_id INT DEFAULT NULL;
-- ALTER TABLE opportunity ADD INDEX idx_opp_fh_org (fh_org_id);
-- ALTER TABLE fpds_contract ADD COLUMN fh_org_id INT DEFAULT NULL;
-- ALTER TABLE fpds_contract ADD INDEX idx_fpds_fh_org (fh_org_id);
-- ALTER TABLE usaspending_award ADD COLUMN fh_org_id INT DEFAULT NULL, ALGORITHM=INSTANT;

-- Step 2: Create agency_name_alias table
CREATE TABLE IF NOT EXISTS agency_name_alias (
    source_name VARCHAR(255) NOT NULL,
    fh_org_id   INT NOT NULL,
    PRIMARY KEY (source_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Step 3: Seed alias data (47 USASpending sub-agency name variants)
INSERT INTO agency_name_alias (source_name, fh_org_id) VALUES
-- Defense agencies (Sub-Tier under DoD, CGAC 097)
('Defense Advanced Research Projects Agency', 300000412),
('Defense Commissary Agency', 300000418),
('Defense Contract Management Agency', 300000407),
('Defense Counterintelligence and Security Agency', 300000417),
('Defense Finance and Accounting Service', 300000419),
('Defense Health Agency', 300000422),
('Defense Information Systems Agency', 300000413),
('Defense Media Activity', 300000425),
('Defense Microelectronics Activity', 300000408),
('Defense Threat Reduction Agency', 300000406),
('Missile Defense Agency', 300000429),
('U.S. Special Operations Command', 300000430),
('Washington Headquarters Services', 300000427),
('Uniformed Services University of the Health Sciences', 100011697),
('Department of Defense Education Activity', 300000426),
-- Military departments (Sub-Tier)
('Department of the Air Force', 300000251),
('Department of the Army', 300000201),
('Department of the Navy', 300000188),
-- DOJ (CGAC 015)
('Bureau of Alcohol, Tobacco, Firearms and Explosives Acquisition and Property Management Division', 100500176),
('Federal Prison Industries / Unicor', 300000176),
-- Interior (CGAC 014)
('Bureau of Indian Affairs and Bureau of Indian Education', 300000500),
('U.S. Geological Survey', 100045744),
-- Commerce (CGAC 013)
('Department of Commerce', 100035122),
('U.S. Census Bureau', 100109750),
('U.S. Patent and Trademark Office', 100182899),
-- DOT (CGAC 069)
('Immediate Office of the Secretary of Transportation', 100042830),
('Saint Lawrence Seaway Development Corporation', 100159874),
-- HHS (CGAC 075)
('Office of the Assistant Secretary for Administration', 100081982),
('Office of the Assistant Secretary for Financial Resources', 300000295),
('Office of Assistant Secretary for Preparedness and Response', 100004570),
-- DHS (CGAC 070)
('U. S. Coast Guard', 100012855),
-- HUD (CGAC 086)
('Department of Housing and Urban Development', 300000313),
-- State (CGAC 019)
('Department of State', 100012062),
-- Education (CGAC 091)
('Department of Education', 100001616),
-- Energy (CGAC 089)
('Department of Energy', 100011980),
-- Veterans Affairs (CGAC 036)
('Department of Veterans Affairs', 100006568),
-- Independent agencies
('Administrative Conference of the U.S.', 300000368),
('Council of the Inspectors General on Integrity and Efficiency', 300000364),
('Export-Import Bank of the United States', 300000310),
('Institute of Museum and Library Services', 300000248),
('John F. Kennedy Center for the Performing Arts', 300000211),
('Morris K. Udall and Stewart L. Udall Foundation', 300000385),
('U.S. Agency for Global Media', 300000395),
('U.S. International Development Finance Corporation', 500049427),
('United States Chemical Safety Board', 300000394),
('Office of the Administrator', 100038044),
('Under Secretary for Farm and Foreign Agricultural Services', 100006809)
ON DUPLICATE KEY UPDATE fh_org_id = VALUES(fh_org_id);

-- Step 4: Run backfill via CLI
-- python main.py maintain normalize-fh-orgs --table opportunity
-- python main.py maintain normalize-fh-orgs --table fpds
-- python main.py maintain normalize-fh-orgs --table usaspending
