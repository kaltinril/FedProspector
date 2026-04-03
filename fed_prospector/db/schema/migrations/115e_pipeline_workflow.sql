-- Phase 115E: Pipeline & Workflow Enhancements
-- Date: 2026-04-02
-- Creates 2 tables (milestone tracking, status history)
-- and 4 views (funnel analytics, calendar, stale detection, revenue forecast).

USE fed_contracts;

-- ============================================================
-- Table 1: prospect_milestone
-- Reverse-timeline milestones working backward from response
-- deadline. Each prospect can have N milestones (review gates,
-- draft deadlines, submission dates, etc.).
-- ============================================================

CREATE TABLE IF NOT EXISTS prospect_milestone (
    prospect_milestone_id INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id           INT NOT NULL,
    milestone_name        VARCHAR(100) NOT NULL,
    target_date           DATE NOT NULL,
    completed_date        DATE NULL,
    is_completed          TINYINT(1) NOT NULL DEFAULT 0,
    sort_order            INT NOT NULL DEFAULT 0,
    notes                 TEXT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_pm_prospect (prospect_id),
    INDEX idx_pm_target   (target_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Table 2: prospect_status_history
-- Tracks every status transition on a prospect for funnel
-- analysis, conversion-rate calculation, and time-in-stage
-- metrics.
-- ============================================================

CREATE TABLE IF NOT EXISTS prospect_status_history (
    history_id              INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id             INT NOT NULL,
    old_status              VARCHAR(30) NULL,
    new_status              VARCHAR(30) NOT NULL,
    changed_by              INT NULL,
    changed_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    time_in_old_status_hours INT NULL,
    INDEX idx_psh_prospect  (prospect_id),
    INDEX idx_psh_new_status (new_status),
    INDEX idx_psh_changed   (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- View 1: v_pipeline_funnel
-- Per-organization pipeline funnel: counts, estimated values,
-- average time-in-stage, win rate, and stage conversion rates.
-- ============================================================

CREATE OR REPLACE VIEW v_pipeline_funnel AS
WITH status_counts AS (
    SELECT
        p.organization_id,
        p.status,
        COUNT(*)                    AS prospect_count,
        SUM(p.estimated_value)      AS total_estimated_value
    FROM prospect p
    GROUP BY p.organization_id, p.status
),
avg_time AS (
    SELECT
        p.organization_id,
        psh.new_status,
        AVG(psh.time_in_old_status_hours) AS avg_hours_in_prior_status
    FROM prospect_status_history psh
    JOIN prospect p ON p.prospect_id = psh.prospect_id
    WHERE psh.time_in_old_status_hours IS NOT NULL
    GROUP BY p.organization_id, psh.new_status
),
outcomes AS (
    SELECT
        organization_id,
        SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END)  AS won_count,
        SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END)  AS lost_count
    FROM prospect
    GROUP BY organization_id
)
SELECT
    sc.organization_id,
    sc.status,
    sc.prospect_count,
    sc.total_estimated_value,
    ROUND(at2.avg_hours_in_prior_status, 1)               AS avg_hours_in_prior_status,
    ROUND(
        CASE WHEN (o.won_count + o.lost_count) > 0
             THEN o.won_count * 100.0 / (o.won_count + o.lost_count)
             ELSE NULL
        END, 1
    )                                                       AS win_rate_pct,
    o.won_count,
    o.lost_count
FROM status_counts sc
LEFT JOIN avg_time at2
       ON at2.organization_id = sc.organization_id
      AND at2.new_status      = sc.status
LEFT JOIN outcomes o
       ON o.organization_id   = sc.organization_id;

-- ============================================================
-- View 2: v_pipeline_calendar
-- Active prospects with their response deadlines for calendar
-- display.  Joins prospect -> opportunity via notice_id.
-- ============================================================

CREATE OR REPLACE VIEW v_pipeline_calendar AS
SELECT
    p.prospect_id,
    p.organization_id,
    p.notice_id,
    o.title                   AS opportunity_title,
    o.response_deadline,
    o.solicitation_number,
    p.status,
    p.priority,
    p.assigned_to,
    u.display_name            AS assigned_to_name,
    p.estimated_value,
    p.win_probability
FROM prospect p
JOIN opportunity o ON o.notice_id = p.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID');

-- ============================================================
-- View 3: v_stale_prospect
-- Prospects in active statuses that have not been updated in
-- 14+ days. Surfaces forgotten pipeline items.
-- ============================================================

CREATE OR REPLACE VIEW v_stale_prospect AS
SELECT
    p.prospect_id,
    p.organization_id,
    p.notice_id,
    o.title                   AS opportunity_title,
    p.status,
    p.priority,
    DATEDIFF(NOW(), p.updated_at) AS days_since_update,
    p.assigned_to,
    u.display_name            AS assigned_to_name,
    p.estimated_value,
    p.updated_at              AS last_updated_at
FROM prospect p
JOIN opportunity o ON o.notice_id = p.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE p.status IN ('NEW', 'REVIEWING', 'PURSUING')
  AND p.updated_at < DATE_SUB(NOW(), INTERVAL 14 DAY);

-- ============================================================
-- View 4: v_pipeline_revenue_forecast
-- Weighted and unweighted revenue projection per organization
-- per month, based on response_deadline month of linked
-- opportunity.
-- ============================================================

CREATE OR REPLACE VIEW v_pipeline_revenue_forecast AS
SELECT
    p.organization_id,
    DATE_FORMAT(o.response_deadline, '%Y-%m')               AS forecast_month,
    COUNT(*)                                                 AS prospect_count,
    SUM(p.estimated_value)                                   AS total_unweighted_value,
    SUM(p.estimated_value * COALESCE(p.win_probability, 0) / 100)
                                                             AS total_weighted_value,
    AVG(p.win_probability)                                   AS avg_win_probability
FROM prospect p
JOIN opportunity o ON o.notice_id = p.notice_id
WHERE p.status IN ('NEW', 'REVIEWING', 'PURSUING', 'BID_SUBMITTED')
  AND o.response_deadline IS NOT NULL
GROUP BY p.organization_id, DATE_FORMAT(o.response_deadline, '%Y-%m');
