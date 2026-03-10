-- views/ref_psc_code_latest.sql
-- Deduplicated PSC codes: latest version of each code by start_date.
-- Eliminates the need for correlated subqueries with ORDER BY / LIMIT 1.

USE fed_contracts;

CREATE OR REPLACE VIEW ref_psc_code_latest AS
SELECT rc.psc_code, rc.psc_name
FROM ref_psc_code rc
INNER JOIN (
    SELECT psc_code, MAX(start_date) AS max_start_date
    FROM ref_psc_code
    GROUP BY psc_code
) latest ON rc.psc_code = latest.psc_code AND rc.start_date = latest.max_start_date;
