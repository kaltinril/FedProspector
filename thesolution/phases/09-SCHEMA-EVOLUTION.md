# Phase 9: Schema Evolution

**Status**: PLANNING
**Dependencies**: Phase 8 (Gap Analysis) complete
**Deliverable**: SQL migration scripts `fed_prospector/db/schema/tables/80_raw_staging.sql` (staging) + `fed_prospector/db/schema/tables/90_web_api.sql` (production) + updated `build-database` CLI
**Repository**: `pbdc` (this repo -- these are MySQL schema changes)

---

## Overview

Execute the Tier 1 database changes identified in Phase 8's gap analysis. Add 14 new tables (8 production + 6 raw staging) and ~15 new columns to 4 existing tables to support the C# API backend and raw data replay. All changes are additive -- the Python ETL pipeline is unaffected.

**Result**: 40 tables -> 54 tables + 4 views

---

## 9.1 Raw Staging Tables (6)

The entity pipeline already stores raw API responses in `stg_entity_raw` (see `tables/20_entity.sql`) before normalizing into production tables. This section extends that pattern to the remaining 6 data sources, enabling:

- **Re-processing/replay** without re-fetching from APIs
- **Capturing fields we don't yet normalize** (e.g., `pointOfContact` arrays, nested sub-objects)
- **Historical audit trail** of what each API returned and when
- **Schema evolution safety** -- rebuild production tables from raw data if column definitions change

All 6 tables follow the same structure: an auto-increment PK, a `load_id` (links to `etl_load_log`), a natural key for the source record, the full `raw_json` (MySQL JSON type), a `raw_record_hash` (SHA-256 for change detection), a `processed` flag, and an optional `error_message`.

**Deliverable file**: `fed_prospector/db/schema/tables/80_raw_staging.sql` (separate from production DDL in `tables/90_web_api.sql`)

- [ ] Create all 6 raw staging tables

```sql
-- ============================================================
-- Raw staging tables: preserve full API responses for replay
-- Pattern matches existing stg_entity_raw table
-- ============================================================

CREATE TABLE IF NOT EXISTS stg_opportunity_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    notice_id          VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_opp_load (load_id),
    INDEX idx_stg_opp_notice (notice_id),
    INDEX idx_stg_opp_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_fpds_award_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    contract_id        VARCHAR(50) NOT NULL,
    modification_number VARCHAR(10),
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_fpds_load (load_id),
    INDEX idx_stg_fpds_contract (contract_id),
    INDEX idx_stg_fpds_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_usaspending_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    award_id           VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_usa_load (load_id),
    INDEX idx_stg_usa_award (award_id),
    INDEX idx_stg_usa_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_exclusion_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    record_id          VARCHAR(100) NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_excl_load (load_id),
    INDEX idx_stg_excl_record (record_id),
    INDEX idx_stg_excl_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_fedhier_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    fh_org_id          INT NOT NULL,
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_fh_load (load_id),
    INDEX idx_stg_fh_org (fh_org_id),
    INDEX idx_stg_fh_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stg_subaward_raw (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    load_id            INT NOT NULL,
    prime_piid         VARCHAR(50) NOT NULL,
    sub_uei            VARCHAR(12),
    raw_json           JSON NOT NULL,
    raw_record_hash    CHAR(64) NOT NULL,
    processed          CHAR(1) NOT NULL DEFAULT 'N',
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stg_sub_load (load_id),
    INDEX idx_stg_sub_piid (prime_piid),
    INDEX idx_stg_sub_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

> **Replay capability**: To rebuild production tables from raw data, query `stg_*_raw WHERE processed = 'Y'` and re-run the normalize step. The `raw_record_hash` (SHA-256) enables change detection without re-processing unchanged records.

> **Python loader modifications**: Each of the 6 loaders (`opportunity_loader.py`, `awards_loader.py`, `usaspending_loader.py`, `exclusions_loader.py`, `fedhier_loader.py`, `subaward_loader.py`) needs a one-line change: insert the raw JSON into the staging table before calling the normalize function. This matches the existing pattern in `bulk_loader.py` for entities.

> **Storage note**: Raw JSON for ~500K entities is ~2-3GB. Opportunity and award volumes are smaller. The staging tables use MySQL's native JSON type for efficient storage and querying.

---

## 9.2 New Tables (8)

### Table: `app_session`

Purpose: User authentication sessions for JWT/token management.

- [ ] Create table `app_session`

```sql
CREATE TABLE IF NOT EXISTS app_session (
    session_id           VARCHAR(64) NOT NULL,
    user_id              INT NOT NULL,
    token_hash           VARCHAR(255) NOT NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at           DATETIME NOT NULL,
    ip_address           VARCHAR(45),
    user_agent           VARCHAR(500),
    is_active            CHAR(1) NOT NULL DEFAULT 'Y',
    PRIMARY KEY (session_id),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_session_user (user_id),
    INDEX idx_session_active (is_active, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_session_user` (user lookup), `idx_session_active` (active session expiry queries).

---

### Table: `proposal`

Purpose: Proposal lifecycle tracking, 1:1 with prospect.

- [ ] Create table `proposal`

```sql
CREATE TABLE IF NOT EXISTS proposal (
    proposal_id          INT AUTO_INCREMENT,
    prospect_id          INT NOT NULL,
    status               ENUM('DRAFT','IN_REVIEW','SUBMITTED','UNDER_EVALUATION','AWARDED','NOT_AWARDED')
                             NOT NULL DEFAULT 'DRAFT',
    proposal_owner_id    INT NOT NULL,
    due_date             DATE,
    submitted_date       DATE,
    internal_cost_estimate DECIMAL(15,2),
    proposed_price       DECIMAL(15,2),
    estimated_gross_margin_pct DECIMAL(5,2),
    document_count       INT NOT NULL DEFAULT 0,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (proposal_id),
    UNIQUE KEY uk_proposal_prospect (prospect_id),
    CONSTRAINT fk_proposal_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    CONSTRAINT fk_proposal_owner FOREIGN KEY (proposal_owner_id) REFERENCES app_user(user_id),
    INDEX idx_proposal_status (status),
    INDEX idx_proposal_due (due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `uk_proposal_prospect` (unique -- enforces 1:1), `idx_proposal_status`, `idx_proposal_due`.

---

### Table: `proposal_document`

Purpose: File attachment metadata for proposal documents.

- [ ] Create table `proposal_document`

```sql
CREATE TABLE IF NOT EXISTS proposal_document (
    document_id          INT AUTO_INCREMENT,
    proposal_id          INT NOT NULL,
    filename             VARCHAR(255) NOT NULL,
    file_path            VARCHAR(500) NOT NULL,
    file_size_bytes      BIGINT,
    file_type            ENUM('RFQ','RESPONSE','EXHIBIT','PAST_PERFORMANCE','PRICING','OTHER')
                             NOT NULL DEFAULT 'OTHER',
    uploaded_by          INT NOT NULL,
    uploaded_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description          TEXT,
    PRIMARY KEY (document_id),
    CONSTRAINT fk_pdoc_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id),
    CONSTRAINT fk_pdoc_uploader FOREIGN KEY (uploaded_by) REFERENCES app_user(user_id),
    INDEX idx_propdoc_proposal (proposal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_propdoc_proposal` (lookup documents by proposal).

---

### Table: `proposal_milestone`

Purpose: Bid timeline tracking with planned vs actual dates.

- [ ] Create table `proposal_milestone`

```sql
CREATE TABLE IF NOT EXISTS proposal_milestone (
    milestone_id         INT AUTO_INCREMENT,
    proposal_id          INT NOT NULL,
    milestone_name       VARCHAR(100) NOT NULL,
    planned_date         DATE,
    actual_date          DATE,
    owner_id             INT,
    status               ENUM('PENDING','IN_PROGRESS','COMPLETED','SKIPPED')
                             NOT NULL DEFAULT 'PENDING',
    notes                TEXT,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (milestone_id),
    CONSTRAINT fk_pm_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id),
    CONSTRAINT fk_pm_owner FOREIGN KEY (owner_id) REFERENCES app_user(user_id),
    INDEX idx_milestone_proposal (proposal_id),
    INDEX idx_milestone_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_milestone_proposal` (lookup milestones by proposal), `idx_milestone_status`.

---

### Table: `activity_log`

Purpose: Audit trail for all user actions in the web app.

- [ ] Create table `activity_log`

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    log_id               BIGINT AUTO_INCREMENT,
    user_id              INT,
    action_type          VARCHAR(50) NOT NULL,
    target_table         VARCHAR(50),
    target_record_id     VARCHAR(100),
    old_value            TEXT,
    new_value            TEXT,
    ip_address           VARCHAR(45),
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    CONSTRAINT fk_actlog_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_activity_target (target_table, target_record_id),
    INDEX idx_activity_user_date (user_id, created_at),
    INDEX idx_activity_date (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_activity_target` (find changes to a specific record), `idx_activity_user_date` (user activity history), `idx_activity_date` (chronological queries and archival).

---

### Table: `notification`

Purpose: In-app notification/alert queue.

- [ ] Create table `notification`

```sql
CREATE TABLE IF NOT EXISTS notification (
    notification_id      BIGINT AUTO_INCREMENT,
    user_id              INT NOT NULL,
    notification_type    VARCHAR(50) NOT NULL,
    title                VARCHAR(200) NOT NULL,
    message              TEXT,
    related_table        VARCHAR(50),
    related_record_id    VARCHAR(100),
    is_read              CHAR(1) NOT NULL DEFAULT 'N',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at              DATETIME,
    PRIMARY KEY (notification_id),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_notif_user_read (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_notif_user_read` (unread notifications per user, ordered by date).

---

### Table: `contracting_officer`

Purpose: Normalized contracting officer contacts. Auto-populated from SAM.gov Opportunity API `pointOfContact` array. Also editable via manual entry during capture management (Phase 12).

- [ ] Create table `contracting_officer`

```sql
-- Normalized contracting officer contacts
-- Auto-populated from SAM.gov Opportunity API pointOfContact array
-- Also editable via manual entry during capture management (Phase 12)
CREATE TABLE IF NOT EXISTS contracting_officer (
    co_id                  INT AUTO_INCREMENT PRIMARY KEY,
    first_name             VARCHAR(100),
    last_name              VARCHAR(100) NOT NULL,
    email                  VARCHAR(200),
    phone                  VARCHAR(30),
    fax                    VARCHAR(30),
    title                  VARCHAR(100),
    contracting_office_id  VARCHAR(20),
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_co_name (last_name, first_name),
    INDEX idx_co_email (email),
    INDEX idx_co_office (contracting_office_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_co_name` (name lookup), `idx_co_email` (email lookup/dedup), `idx_co_office` (office affiliation queries).

> **Deduplication strategy**: The ETL pipeline matches on `email` (case-insensitive) when available. If no email, match on `fullName` + `contracting_office_id`. Existing CO records are reused; new ones are created only when no match is found. The C# API (Phase 12) uses the same matching logic for manual entry.

---

### Table: `opportunity_poc`

Purpose: Junction table linking opportunities to their points of contact. An opportunity can have multiple contacts (primary, secondary, etc.) as returned by the SAM.gov Opportunity API `pointOfContact` array.

- [ ] Create table `opportunity_poc`

```sql
-- Links opportunities to their points of contact
-- An opportunity can have multiple contacts (primary, secondary, etc.)
CREATE TABLE IF NOT EXISTS opportunity_poc (
    opportunity_poc_id     INT AUTO_INCREMENT PRIMARY KEY,
    notice_id              VARCHAR(100) NOT NULL,
    co_id                  INT NOT NULL,
    contact_type           VARCHAR(20) NOT NULL DEFAULT 'primary',
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_oppoc_opportunity FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
    CONSTRAINT fk_oppoc_co FOREIGN KEY (co_id) REFERENCES contracting_officer(co_id),
    UNIQUE INDEX idx_oppoc_unique (notice_id, co_id),
    INDEX idx_oppoc_co (co_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Indexes beyond PK: `idx_oppoc_unique` (prevents duplicate pairings), `idx_oppoc_co` (reverse lookup -- find all opportunities for a given CO).

---

## 9.3 ALTER Existing Tables

### `app_user` -- Add authentication fields

- [ ] ALTER TABLE `app_user` to add authentication and security columns

```sql
ALTER TABLE app_user
    ADD COLUMN password_hash VARCHAR(255) AFTER email,
    ADD COLUMN last_login_at DATETIME AFTER role,
    ADD COLUMN is_admin CHAR(1) NOT NULL DEFAULT 'N' AFTER is_active,
    ADD COLUMN mfa_enabled CHAR(1) NOT NULL DEFAULT 'N' AFTER is_admin,
    ADD COLUMN failed_login_attempts INT NOT NULL DEFAULT 0 AFTER mfa_enabled,
    ADD COLUMN locked_until DATETIME AFTER failed_login_attempts;
```

Note: `password_hash` is nullable because existing CLI-created users don't have passwords. The C# API will require it for new registrations. All other new columns have safe defaults (`FALSE`, `0`, `NULL`), so existing rows remain valid.

> **Password migration**: Existing `app_user` rows created by the Python CLI do not have hashed passwords. The strategy for migrating CLI users to web app login (admin-set passwords, first-login tokens, or separate user pools) is deferred to Phase 13.

---

### `opportunity` -- Add capture-relevant fields

- [ ] ALTER TABLE `opportunity` to add capture decision fields

```sql
ALTER TABLE opportunity
    ADD COLUMN period_of_performance_start DATE AFTER pop_city,
    ADD COLUMN period_of_performance_end DATE AFTER period_of_performance_start,
    ADD COLUMN security_clearance_required ENUM('NONE','CONFIDENTIAL','SECRET','TOP_SECRET','TS_SCI','UNKNOWN')
        DEFAULT 'UNKNOWN' AFTER period_of_performance_end,
    ADD COLUMN incumbent_uei VARCHAR(12) AFTER security_clearance_required,
    ADD COLUMN incumbent_name VARCHAR(500) AFTER incumbent_uei,
    ADD COLUMN contract_vehicle_type ENUM('OPEN_MARKET','GWAC','IDIQ','BPA','FSS','OTHER')
        AFTER incumbent_name,
    ADD COLUMN estimated_contract_value DECIMAL(15,2) AFTER contract_vehicle_type;
```

Note: All nullable -- populated manually or by future ETL enrichment. `security_clearance_required` defaults to `'UNKNOWN'`. `incumbent_uei` is an informal FK (not enforced) since the incumbent may not be in our entity table. Contracting officer contacts are linked via the `opportunity_poc` junction table (many-to-many).

---

### `prospect` -- Add capture management fields

- [ ] ALTER TABLE `prospect` to add capture lifecycle columns

```sql
ALTER TABLE prospect
    ADD COLUMN capture_manager_id INT AFTER assigned_to,
    ADD COLUMN proposal_status VARCHAR(20) AFTER status,
    ADD COLUMN contract_award_id VARCHAR(100) AFTER outcome_notes,
    ADD COLUMN estimated_gross_margin_pct DECIMAL(5,2) AFTER estimated_proposal_cost,
    ADD CONSTRAINT fk_prospect_capture_mgr FOREIGN KEY (capture_manager_id) REFERENCES app_user(user_id);
```

Note: `proposal_status` mirrors `proposal.status` for quick filtering without join. `contract_award_id` links to `fpds_contract.contract_id` after a win (informal FK -- not enforced because contract data may not be loaded yet).

---

### `prospect_team_member` -- Add internal staff tracking

- [ ] ALTER TABLE `prospect_team_member` to add internal user and rate columns

```sql
ALTER TABLE prospect_team_member
    MODIFY COLUMN uei_sam VARCHAR(12) NULL,
    ADD COLUMN app_user_id INT AFTER uei_sam,
    ADD COLUMN proposed_hourly_rate DECIMAL(10,2) AFTER notes,
    ADD COLUMN commitment_pct DECIMAL(5,2) AFTER proposed_hourly_rate,
    ADD CONSTRAINT fk_team_app_user FOREIGN KEY (app_user_id) REFERENCES app_user(user_id);
```

Note: A team member is either an external entity (`uei_sam`) OR an internal staff member (`app_user_id`). Both are nullable -- exactly one should be set. The existing `uei_sam NOT NULL` constraint will need to be relaxed to allow internal-only team members.

---

## 9.4 Update build-database CLI

- [ ] Add `tables/80_raw_staging.sql` to the schema `tables/` subfolder (before `tables/90_web_api.sql`)
- [ ] Add `tables/90_web_api.sql` to the schema `tables/` subfolder
- [ ] Ensure table creation order respects foreign key dependencies (staging tables first, then ALTER existing tables, then new production tables in dependency order)
- [ ] Test: `python main.py build-database` creates all 54 tables without errors

---

## 9.5 Update load-lookups (if applicable)

- [ ] No new reference data needed for Tier 1 tables
- [ ] Verify existing reference data is unaffected

---

## Acceptance Criteria

1. [ ] All 14 new tables (8 production + 6 staging) created successfully in MySQL
2. [ ] All 4 ALTER TABLE statements execute without errors on existing data
3. [ ] `python main.py build-database` creates all 54 tables + 4 views
4. [ ] `python main.py status` reflects 54 tables
5. [ ] All existing CLI commands still work (ETL unaffected)
6. [ ] Existing data in `app_user`, `opportunity`, `prospect`, `prospect_team_member` preserved
7. [ ] Foreign key relationships are correct (test with sample INSERT)

---

## Schema Ownership Transition Note

Phase 9 is the **last phase where Python DDL exclusively manages ALL tables**. After Phase 9 completes:

- The 5 application tables (`app_user`, `prospect`, `prospect_note`, `prospect_team_member`, `saved_search`) plus all new Phase 9 app tables (`app_session`, `proposal`, `proposal_document`, `proposal_milestone`, `activity_log`, `notification`) transition to **C# EF Core migration ownership** in Phase 10.
- Python DDL continues to own all ETL/data tables, reference tables, and staging tables.
- See [10-API-FOUNDATION.md](10-API-FOUNDATION.md) "Schema Ownership" section for the full split and rules.

---

## Migration Notes

- **Backwards compatible**: All new columns are nullable or have defaults
- **No data migration needed**: New columns start empty, populated by C# API
- **Python ETL unaffected**: Loaders don't write to new columns or tables
- **Rollback**: DROP TABLE for new tables, ALTER TABLE DROP COLUMN for new columns

### Migration Order

1. **Create all 6 raw staging tables first** (`tables/80_raw_staging.sql`) -- these have NO foreign keys and can be created in any order, so they are the safest starting point
2. **ALTER `app_user`** -- auth fields are needed before `app_session` can reference the updated table
3. **Create `contracting_officer`** -- must exist before `opportunity_poc` can reference it
4. **ALTER remaining existing tables** -- `opportunity`, `prospect`, `prospect_team_member`
5. **Create `opportunity_poc`** -- depends on `opportunity` and `contracting_officer`
6. **Create remaining Tier 1 tables in dependency order**:
   - `app_session` (depends on `app_user`)
   - `proposal` (depends on `prospect` and `app_user`)
   - `proposal_document` (depends on `proposal` and `app_user`)
   - `proposal_milestone` (depends on `proposal` and `app_user`)
   - `activity_log` (depends on `app_user`)
   - `notification` (depends on `app_user`)
7. **Verify** -- run `build-database` and `status` commands to confirm 54 tables
