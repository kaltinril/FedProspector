-- migrations/133b_linked_entity_view_aggregation.sql
-- Phase 133 (Tasks 2, 3, 4): Linked Entity Aggregation Fixes.
--
-- The three onboarding/size-standard views built in Phase 115F
-- (115f_onboarding_past_performance.sql) only ever looked at the org's OWN
-- row. They ignored the linked entities recorded in `organization_entity`
-- (sister subsidiaries, JV partners, etc.). This migration rebuilds the three
-- views so they aggregate across the org PLUS its active linked UEIs.
--
-- The "active linked UEIs" set for every view below is:
--     SELECT uei_sam FROM organization_entity
--      WHERE organization_id = <org> AND is_active = 'Y'
-- (all active relationships count; per-link / per-purpose overrides are
-- deferred per the Phase 133 plan). The org's own data is always included via
-- its own `organization_naics` / `organization_past_performance` rows, so the
-- org needs no `SELF` row in `organization_entity` to be counted.
--
-- Views rebuilt:
--   Task 2 - v_portfolio_gap_analysis      (NAICS + past-perf across linked UEIs)
--   Task 3 - v_certification_expiration_alert (SAM.gov certs across linked UEIs)
--   Task 4 - v_sba_size_standard_monitor    (NAICS across linked UEIs; built on
--            top of the already-corrected 'M'/'E' size_type definition from the
--            133a hotfix -- 'R' is NOT reintroduced)
--
-- Performance note (CLAUDE.md): past-performance counts in Task 2 come from
-- `usaspending_award` (the authoritative award source), NOT `fpds_contract`.
-- Soft-deleted award rows (deleted_at IS NOT NULL) are excluded.
--
-- IDEMPOTENT: every statement is CREATE OR REPLACE VIEW; safe to re-run.
--
-- SUPERSEDES the 133a hotfix for v_sba_size_standard_monitor (Task 4 below is
-- the corrected 'M'/'E' definition WITH linked-entity NAICS aggregation layered
-- on). Applying this file makes 133a redundant for that view.
--
-- APPLY (per CLAUDE.md rule 9 -- must reach BOTH dev and prod; back up first per
-- the Phase 134 runbook). Run from this dev box via E:\mysql\bin:
--   Prod:
--     & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133b_linked_entity_view_aggregation.sql"
--   Dev (localhost):
--     & "E:\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133b_linked_entity_view_aggregation.sql"
-- ============================================================

USE fed_contracts;

-- ============================================================
-- Task 3: v_certification_expiration_alert
-- Upcoming certification expirations within 90 days.
-- Sources: organization_certification (manual entries) +
-- entity_sba_certification (SAM.gov) matched via UEI -- now matched against
-- the org's own UEI AND every active linked UEI in organization_entity.
-- ============================================================

CREATE OR REPLACE VIEW v_certification_expiration_alert AS
-- Organization-level certifications (manual)
SELECT
    oc.organization_id,
    oc.certification_type,
    oc.expiration_date,
    DATEDIFF(oc.expiration_date, NOW())              AS days_until_expiration,
    CASE
        WHEN DATEDIFF(oc.expiration_date, NOW()) <= 30 THEN 'URGENT'
        WHEN DATEDIFF(oc.expiration_date, NOW()) <= 60 THEN 'WARNING'
        ELSE 'NOTICE'
    END                                               AS alert_level,
    'MANUAL'                                          AS source
FROM organization_certification oc
WHERE oc.expiration_date IS NOT NULL
  AND oc.expiration_date >= CURDATE()
  AND oc.expiration_date <= DATE_ADD(CURDATE(), INTERVAL 90 DAY)
  AND oc.is_active = 'Y'

UNION ALL

-- SAM.gov SBA certifications matched via UEI.
-- org_uei unions the org's own uei_sam with every active linked UEI so certs
-- attached to a sister subsidiary / JV partner surface under the org.
SELECT
    org_uei.organization_id,
    esc.sba_type_code                                 AS certification_type,
    esc.certification_exit_date                       AS expiration_date,
    DATEDIFF(esc.certification_exit_date, NOW())      AS days_until_expiration,
    CASE
        WHEN DATEDIFF(esc.certification_exit_date, NOW()) <= 30 THEN 'URGENT'
        WHEN DATEDIFF(esc.certification_exit_date, NOW()) <= 60 THEN 'WARNING'
        ELSE 'NOTICE'
    END                                               AS alert_level,
    'SAM_GOV'                                         AS source
FROM (
    -- org's own UEI
    SELECT o.organization_id, o.uei_sam
    FROM organization o
    WHERE o.uei_sam IS NOT NULL
    UNION
    -- active linked UEIs
    SELECT oe.organization_id, oe.uei_sam
    FROM organization_entity oe
    WHERE oe.is_active = 'Y'
      AND oe.uei_sam IS NOT NULL
) org_uei
INNER JOIN entity_sba_certification esc ON esc.uei_sam = org_uei.uei_sam
WHERE esc.certification_exit_date IS NOT NULL
  AND esc.certification_exit_date >= CURDATE()
  AND esc.certification_exit_date <= DATE_ADD(CURDATE(), INTERVAL 90 DAY);

-- ============================================================
-- Task 4: v_sba_size_standard_monitor
-- Compare organization revenue/employees against SBA size standards for the
-- org's registered NAICS codes PLUS NAICS registered on active linked entities.
-- Only rows where usage >= 80% of threshold are returned.
-- size_type: 'M' = revenue (millions), 'E' = employees
-- (built on the 133a 'M'/'E' correction -- 'R' is NOT reintroduced).
-- NOTE: revenue/employee figures remain the ORG's own
-- (organization.annual_revenue / organization.employee_count). The affiliation
-- size ROLL-UP that sums affiliate financials is Task 6 (separate work); this
-- task only broadens the NAICS set the monitor watches.
-- ============================================================

CREATE OR REPLACE VIEW v_sba_size_standard_monitor AS
SELECT
    o.organization_id,
    o.name                                            AS organization_name,
    org_naics.naics_code,
    ss.size_type                                      AS size_standard_type,
    ss.size_standard                                  AS threshold,
    CASE ss.size_type
        WHEN 'M' THEN o.annual_revenue / 1000000.0   -- convert to millions for comparison
        WHEN 'E' THEN o.employee_count
    END                                               AS current_value,
    CASE ss.size_type
        WHEN 'M' THEN ROUND((o.annual_revenue / 1000000.0) / ss.size_standard * 100, 1)
        WHEN 'E' THEN ROUND(o.employee_count / ss.size_standard * 100, 1)
    END                                               AS pct_of_threshold
FROM organization o
-- Aggregated NAICS set: org's own organization_naics UNION linked entities'
-- entity_naics (via active organization_entity). DISTINCT (UNION) collapses a
-- NAICS registered on both the org and a linked entity into a single row.
INNER JOIN (
    SELECT orn.organization_id, orn.naics_code
    FROM organization_naics orn
    UNION
    SELECT oe.organization_id, en.naics_code
    FROM organization_entity oe
    INNER JOIN entity_naics en ON en.uei_sam = oe.uei_sam
    WHERE oe.is_active = 'Y'
) org_naics ON org_naics.organization_id = o.organization_id
INNER JOIN ref_sba_size_standard ss ON org_naics.naics_code = ss.naics_code
WHERE ss.size_standard > 0
  AND (
      (ss.size_type = 'M' AND o.annual_revenue IS NOT NULL
       AND (o.annual_revenue / 1000000.0) / ss.size_standard >= 0.80)
      OR
      (ss.size_type = 'E' AND o.employee_count IS NOT NULL
       AND o.employee_count / ss.size_standard >= 0.80)
  );

-- ============================================================
-- Task 2: v_portfolio_gap_analysis
-- Per organization + NAICS code: compare opportunity volume (active opps
-- matching the org's NAICS codes) against past-performance count to identify
-- gaps and strengths.
--
-- NAICS source  = org's organization_naics UNION linked entities' entity_naics
--                 (via active organization_entity).
-- Past-perf cnt = org's organization_past_performance rows
--                 PLUS awards from linked UEIs in usaspending_award
--                 (joined organization_entity.uei_sam = usaspending_award.recipient_uei),
--                 grouped by usaspending_award.naics_code, deleted_at IS NULL.
--                 (usaspending_award per CLAUDE.md -- NOT fpds_contract.)
-- ============================================================

CREATE OR REPLACE VIEW v_portfolio_gap_analysis AS
SELECT
    org_naics.organization_id,
    org_naics.naics_code,
    COALESCE(opp_counts.opportunity_count, 0)         AS opportunity_count,
    COALESCE(pp_counts.past_performance_count, 0)     AS past_performance_count,
    CASE
        WHEN COALESCE(pp_counts.past_performance_count, 0) = 0
             AND COALESCE(opp_counts.opportunity_count, 0) > 0
        THEN 'NO_EXPERIENCE'
        WHEN COALESCE(pp_counts.past_performance_count, 0) > 0
             AND COALESCE(opp_counts.opportunity_count, 0) = 0
        THEN 'LOW_OPPORTUNITY'
        WHEN COALESCE(pp_counts.past_performance_count, 0) > 0
             AND COALESCE(opp_counts.opportunity_count, 0) > 0
        THEN 'STRONG_MATCH'
        ELSE 'NO_DATA'
    END                                               AS gap_type
FROM (
    -- Aggregated NAICS set: org's own organization_naics UNION linked entities'
    -- entity_naics. UNION de-dupes a NAICS shared by org + linked entity.
    SELECT orn.organization_id, orn.naics_code
    FROM organization_naics orn
    UNION
    SELECT oe.organization_id, en.naics_code
    FROM organization_entity oe
    INNER JOIN entity_naics en ON en.uei_sam = oe.uei_sam
    WHERE oe.is_active = 'Y'
) org_naics
LEFT JOIN (
    SELECT naics_code, COUNT(*) AS opportunity_count
    FROM opportunity
    WHERE active = 'Y'
    GROUP BY naics_code
) opp_counts ON org_naics.naics_code = opp_counts.naics_code
LEFT JOIN (
    -- Org's own past performance UNION ALL linked-UEI awards from
    -- usaspending_award, summed per (organization_id, naics_code).
    SELECT organization_id, naics_code, SUM(cnt) AS past_performance_count
    FROM (
        -- Org's manually entered past performance
        SELECT organization_id, naics_code, COUNT(*) AS cnt
        FROM organization_past_performance
        WHERE naics_code IS NOT NULL
        GROUP BY organization_id, naics_code

        UNION ALL

        -- Awards on the org's active linked UEIs (incumbency on a sister
        -- subsidiary / JV partner counts as experience for that NAICS).
        SELECT oe.organization_id, ua.naics_code, COUNT(*) AS cnt
        FROM organization_entity oe
        INNER JOIN usaspending_award ua
            ON ua.recipient_uei = oe.uei_sam
        WHERE oe.is_active = 'Y'
          AND ua.deleted_at IS NULL
          AND ua.naics_code IS NOT NULL
        GROUP BY oe.organization_id, ua.naics_code
    ) pp_union
    GROUP BY organization_id, naics_code
) pp_counts ON org_naics.organization_id = pp_counts.organization_id
              AND org_naics.naics_code = pp_counts.naics_code;
