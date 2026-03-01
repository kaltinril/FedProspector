-- Phase 9.3: ALTER existing tables for web API support
-- Run: /d/mysql/bin/mysql.exe -u fed_app -pfed_app_2026 fed_contracts < fed_prospector/db/schema/migrations/phase9_alter_tables.sql
-- All changes are additive (new nullable columns or columns with defaults). Existing data is preserved.

USE fed_contracts;

-- ============================================================
-- 1. app_user -- Add authentication and security columns
-- ============================================================
ALTER TABLE app_user
    ADD COLUMN password_hash VARCHAR(255) AFTER email,
    ADD COLUMN last_login_at DATETIME AFTER role,
    ADD COLUMN is_admin CHAR(1) NOT NULL DEFAULT 'N' AFTER is_active,
    ADD COLUMN mfa_enabled CHAR(1) NOT NULL DEFAULT 'N' AFTER is_admin,
    ADD COLUMN failed_login_attempts INT NOT NULL DEFAULT 0 AFTER mfa_enabled,
    ADD COLUMN locked_until DATETIME AFTER failed_login_attempts;

-- ============================================================
-- 2. opportunity -- Add capture-relevant enrichment fields
-- ============================================================
ALTER TABLE opportunity
    ADD COLUMN period_of_performance_start DATE AFTER pop_city,
    ADD COLUMN period_of_performance_end DATE AFTER period_of_performance_start,
    ADD COLUMN security_clearance_required CHAR(1) AFTER period_of_performance_end,
    ADD COLUMN incumbent_uei VARCHAR(13) AFTER security_clearance_required,
    ADD COLUMN incumbent_name VARCHAR(200) AFTER incumbent_uei,
    ADD COLUMN contract_vehicle_type VARCHAR(50) AFTER incumbent_name,
    ADD COLUMN estimated_contract_value DECIMAL(15,2) AFTER contract_vehicle_type;

-- ============================================================
-- 3. prospect -- Add capture management fields
-- ============================================================
ALTER TABLE prospect
    ADD COLUMN capture_manager_id INT AFTER assigned_to,
    ADD COLUMN proposal_status VARCHAR(20) AFTER status,
    ADD COLUMN contract_award_id VARCHAR(50) AFTER outcome_notes,
    ADD COLUMN estimated_gross_margin_pct DECIMAL(5,2) AFTER estimated_proposal_cost,
    ADD CONSTRAINT fk_prospect_capture_mgr FOREIGN KEY (capture_manager_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    ADD INDEX idx_prospect_capture_mgr (capture_manager_id);

-- ============================================================
-- 4. prospect_team_member -- Make uei_sam nullable, add internal staff tracking
-- ============================================================
ALTER TABLE prospect_team_member
    MODIFY COLUMN uei_sam VARCHAR(12) NULL,
    ADD COLUMN app_user_id INT AFTER uei_sam,
    ADD COLUMN proposed_hourly_rate DECIMAL(10,2) AFTER notes,
    ADD COLUMN commitment_pct DECIMAL(5,2) AFTER proposed_hourly_rate,
    ADD CONSTRAINT fk_team_app_user FOREIGN KEY (app_user_id) REFERENCES app_user(user_id) ON DELETE SET NULL,
    ADD INDEX idx_ptm_app_user (app_user_id);
