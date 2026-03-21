-- views/70_monthly_spend.sql
-- Monthly spend breakdown by award for burn rate analysis

USE fed_contracts;

CREATE OR REPLACE VIEW v_monthly_spend AS
SELECT
    award_id,
    DATE_FORMAT(action_date, '%Y-%m') AS `year_month`,
    SUM(federal_action_obligation) AS amount,
    COUNT(*) AS transaction_count
FROM usaspending_transaction
WHERE federal_action_obligation IS NOT NULL
GROUP BY award_id, DATE_FORMAT(action_date, '%Y-%m');
