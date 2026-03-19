-- views/05_opportunity_latest.sql
-- v_opportunity_latest: One row per solicitation — the latest biddable notice.
-- Used as a shared dedup foundation for list pages and target views.
-- Non-biddable types (Award Notice, Justification, etc.) are excluded.
-- Dedup by solicitation_number with ROW_NUMBER() for deterministic tiebreaking.

USE fed_contracts;

CREATE OR REPLACE VIEW v_opportunity_latest AS
SELECT * FROM (
    SELECT o.*,
           ROW_NUMBER() OVER (
               PARTITION BY COALESCE(NULLIF(o.solicitation_number, ''), o.notice_id)
               ORDER BY o.posted_date DESC, o.notice_id DESC
           ) AS rn
    FROM opportunity o
    WHERE o.active <> 'N'
      AND o.type NOT IN ('Award Notice', 'Justification', 'Sale of Surplus Property', 'Consolidate/(Substantially) Bundle')
) ranked
WHERE ranked.rn = 1;
