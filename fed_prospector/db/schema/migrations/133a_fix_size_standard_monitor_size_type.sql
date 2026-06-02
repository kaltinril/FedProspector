-- migrations/133a_fix_size_standard_monitor_size_type.sql
-- HOTFIX (surfaced during Phase 133): v_sba_size_standard_monitor size_type bug.
-- Date: 2026-06-01
--
-- THE BUG:
--   The view v_sba_size_standard_monitor (defined in
--   migrations/115f_onboarding_past_performance.sql) compared size_type = 'R'
--   for the revenue branch. But the loaded reference data in
--   ref_sba_size_standard.size_type is 'M' (revenue, in $millions) and 'E'
--   (employees) -- there is NO 'R'. The source CSV
--   (workdir/converted/local database/data_to_import/naics_size_standards.csv)
--   has 513 'M' rows and 483 'E' rows, and reference_loader.py copies the CSV
--   TYPE column through verbatim. As a result the revenue branch never matched,
--   so EVERY revenue-based ('M') NAICS was silently dropped from the size-
--   standard monitor; only the employee-based ('E') branches worked.
--
-- THE FIX:
--   Change every 'R' to 'M' in the view (CASE branches + WHERE clause). No other
--   logic changes. The employee ('E') branches were already correct.
--
-- IDEMPOTENT: CREATE OR REPLACE VIEW is naturally idempotent -- re-running
-- redefines the view to the same correct definition. Safe to re-run.
--
-- APPLY STATUS (per CLAUDE.md rule 9 -- must reach BOTH dev and prod):
--   PROD (192.168.0.137): APPLIED 2026-06-01, verified -- live view def now uses
--     'M' (0 'R' tokens remain); old 'R' logic returned NULL for revenue NAICS,
--     new 'M' logic computes correctly (functional test, no data modified).
--   DEV (127.0.0.1): PENDING -- local MySQL was not running at apply time. Apply
--     when dev is up so dev does not drift behind prod.
-- Run from this dev box via E:\mysql\bin (back up first per the Phase 134 runbook):
--   Prod:
--     & "E:\mysql\bin\mysql.exe" -h 192.168.0.137 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133a_fix_size_standard_monitor_size_type.sql"
--   Dev (localhost):
--     & "E:\mysql\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u fed_app -p<pw> fed_contracts -e "source 133a_fix_size_standard_monitor_size_type.sql"
-- ============================================================

USE fed_contracts;

-- ============================================================
-- View: v_sba_size_standard_monitor
-- Compare organization revenue/employees against SBA size
-- standards for their registered NAICS codes.
-- Only rows where usage >= 80% of threshold are returned.
-- size_type: 'M' = revenue (millions), 'E' = employees
-- ============================================================

CREATE OR REPLACE VIEW v_sba_size_standard_monitor AS
SELECT
    o.organization_id,
    o.name                                            AS organization_name,
    orn.naics_code,
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
INNER JOIN organization_naics orn ON o.organization_id = orn.organization_id
INNER JOIN ref_sba_size_standard ss ON orn.naics_code = ss.naics_code
WHERE ss.size_standard > 0
  AND (
      (ss.size_type = 'M' AND o.annual_revenue IS NOT NULL
       AND (o.annual_revenue / 1000000.0) / ss.size_standard >= 0.80)
      OR
      (ss.size_type = 'E' AND o.employee_count IS NOT NULL
       AND o.employee_count / ss.size_standard >= 0.80)
  );
