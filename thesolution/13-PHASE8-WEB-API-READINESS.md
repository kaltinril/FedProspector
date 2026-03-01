# Phase 8: Web/API Readiness -- Gap Analysis

**Status**: PLANNING
**Purpose**: Document what the MySQL schema needs and what the C# API layer must implement to support a capture management web application for WOSB/8(a) federal contract bidding.
**Architecture**: Python (ETL/data gathering) -> MySQL (shared database) -> C# API (web backend) -> Frontend (TBD)

---

## 1. Current Schema Inventory

### Reference Tables (11 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `ref_naics_code` | 10 | NAICS industry classification lookup -- links opportunities and entities to industries |
| `ref_sba_size_standard` | 8 | SBA small business size thresholds by NAICS -- determines eligibility for set-aside contracts |
| `ref_naics_footnote` | 3 | Supplemental footnotes for NAICS size standards |
| `ref_psc_code` | 15 | Product/Service Code lookup -- categorizes what is being procured |
| `ref_country_code` | 8 | Country code crosswalk (2-letter, 3-letter, numeric) |
| `ref_state_code` | 3 | US state and territory codes |
| `ref_fips_county` | 3 | FIPS county codes for geographic analysis |
| `ref_business_type` | 6 | Business type codes (socioeconomic categories, small business designations) |
| `ref_entity_structure` | 2 | Entity legal structure codes (LLC, Corp, etc.) |
| `ref_set_aside_type` | 4 | Set-aside type codes (WOSB, 8(a), HUBZone, etc.) |
| `ref_sba_type` | 3 | SBA certification program codes |

### Entity Tables (10 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `stg_entity_raw` | 8 | Staging table for raw SAM.gov entity JSON -- ETL internal |
| `entity` | 35 | Core contractor profile -- registration status, NAICS, CAGE code, legal name |
| `entity_address` | 11 | Physical and mailing addresses for contractors |
| `entity_naics` | 6 | NAICS codes registered by each contractor -- used for capability matching |
| `entity_psc` | 3 | PSC codes registered by each contractor |
| `entity_business_type` | 3 | Business type designations (WOSB, 8(a), SDVOSB, etc.) per entity |
| `entity_sba_certification` | 6 | SBA program certifications with entry/exit dates |
| `entity_poc` | 14 | Points of contact (government, electronic, past performance) |
| `entity_disaster_response` | 8 | Disaster response geographic registrations |
| `entity_history` | 7 | Change log for entity field updates (field-level audit) |

### Opportunity Tables (2 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `opportunity` | 33 | Core contract opportunity data -- title, deadline, set-aside, NAICS, award info |
| `opportunity_history` | 7 | Change log for opportunity field updates |

### Federal/Awards Tables (5 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `federal_organization` | 16 | Federal agency hierarchy -- maps agency codes to org names and parent orgs |
| `fpds_contract` | 37 | Historical contract awards -- incumbent vendor, dollar amounts, number of offers |
| `gsa_labor_rate` | 18 | GSA CALC+ labor rate benchmarks -- pricing intelligence |
| `sam_exclusion` | 19 | Debarred/excluded contractors -- compliance check before teaming |
| `sam_subaward` | 22 | Subcontract data -- prime-sub relationships for teaming partner identification |

### ETL Tables (4 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `etl_load_log` | 14 | Load run history -- data freshness monitoring |
| `etl_load_error` | 7 | Per-record error log for ETL troubleshooting |
| `etl_data_quality_rule` | 9 | Configurable data quality validation rules |
| `etl_rate_limit` | 6 | API call quota tracking (SAM.gov daily limits) |

### Prospecting Tables (5 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `app_user` | 8 | Application users -- assignment targets for prospects |
| `prospect` | 19 | Sales pipeline records -- status, priority, scoring, win probability |
| `prospect_note` | 6 | Capture notes and status change audit trail |
| `prospect_team_member` | 5 | Teaming partner assignments per prospect (external entities) |
| `saved_search` | 11 | Saved opportunity search filters with notification support |

### USASpending Tables (2 tables)

| Table | Columns | Capture Management Role |
|-------|---------|------------------------|
| `usaspending_award` | 32 | Award summaries from USASpending.gov -- incumbent data, obligation totals |
| `usaspending_transaction` | 10 | Transaction-level spending -- monthly burn rate calculation |

### Views (2 views)

| View | Capture Management Role |
|------|------------------------|
| `v_target_opportunities` | Pre-filtered WOSB/8(a) opportunities with NAICS descriptions, size standards, and prospect status -- the primary "what should we bid on" view |
| `v_competitor_analysis` | Aggregated contractor profiles with business types, SBA certs, past contract history -- competitive intelligence |

**Totals**: 39 tables + 2 views

---

## 2. What Works Today for Capture Management

| Capture Management Question | Current Answer | Source |
|----------------------------|----------------|--------|
| Find opportunities to bid on | `v_target_opportunities` view filters for WOSB/EDWOSB/8(a) set-asides with future deadlines. Key columns: `notice_id`, `title`, `solicitation_number`, `department_name`, `office`, `posted_date`, `response_deadline`, `days_until_due`, `set_aside_code`, `set_aside_description`, `set_aside_category`, `naics_code`, `naics_description`, `naics_sector`, `size_standard`, `size_type`, `award_amount`, `pop_state`, `pop_city`, `prospect_status`, `prospect_priority`, `assigned_to` | `07_views.sql` |
| Incumbent contractor | `fpds_contract.vendor_uei` + `fpds_contract.vendor_name` joined to `entity` for full profile; also `usaspending_award.recipient_uei` + `recipient_name` for USASpending data | `04_federal_tables.sql`, `08_usaspending_tables.sql` |
| Number of bidders | `fpds_contract.number_of_offers` (INT) -- how many vendors submitted offers on the original award | `04_federal_tables.sql` |
| Burn rate | `usaspending_transaction` aggregated by month using `DATE_FORMAT(action_date, '%Y-%m')` with `SUM(federal_action_obligation)` -- see Section 9 for full SQL | `usaspending_loader.py` |
| Competitor profile | `v_competitor_analysis` view aggregates entity data with business types, SBA certifications, past contract count, total obligated amount, most recent award date | `07_views.sql` |
| Exclusion/debarment check | `sam_exclusion` table by `uei` -- look up any contractor UEI to check for active exclusions | `04_federal_tables.sql` |
| Teaming partners | `sam_subaward` grouped by `prime_uei` with `COUNT(*)`, `SUM(sub_amount)`, `COUNT(DISTINCT sub_uei)` -- see Section 9 for full SQL | `subaward_loader.py` |
| Prospect tracking | `prospect` table with status flow: NEW -> REVIEWING -> PURSUING -> BID_SUBMITTED -> WON/LOST. Includes priority, estimated value, win probability | `06_prospecting_tables.sql` |
| Go/No-Go scoring | `prospect.go_no_go_score` on 0-40 scale. Four criteria: set-aside favorability (0-10), time remaining (0-10), NAICS match (0-10), award value bracket (0-10) | `prospect_manager.py` |

---

## 3. Missing Tables -- Tier 1 (MVP)

### `app_session`

User authentication sessions for the C# API backend.

```sql
CREATE TABLE IF NOT EXISTS app_session (
    session_id           VARCHAR(64) NOT NULL,
    user_id              INT NOT NULL,
    token_hash           VARCHAR(255) NOT NULL,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at           DATETIME NOT NULL,
    ip_address           VARCHAR(45),
    user_agent           VARCHAR(500),
    is_active            CHAR(1) DEFAULT 'Y',
    PRIMARY KEY (session_id),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_session_user (user_id),
    INDEX idx_session_expires (expires_at),
    INDEX idx_session_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### `proposal`

Proposal lifecycle tracking. Links 1:1 with a prospect (one proposal per opportunity pursuit).

```sql
CREATE TABLE IF NOT EXISTS proposal (
    proposal_id          INT AUTO_INCREMENT PRIMARY KEY,
    prospect_id          INT NOT NULL,
    status               ENUM('DRAFT','IN_REVIEW','SUBMITTED','UNDER_EVALUATION','AWARDED','NOT_AWARDED')
                             NOT NULL DEFAULT 'DRAFT',
    proposal_owner_id    INT,
    due_date             DATE,
    submitted_date       DATE,
    internal_cost_estimate DECIMAL(15,2),
    proposed_price       DECIMAL(15,2),
    estimated_gross_margin_pct DECIMAL(5,2),
    document_count       INT DEFAULT 0,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_proposal_prospect (prospect_id),
    CONSTRAINT fk_proposal_prospect FOREIGN KEY (prospect_id) REFERENCES prospect(prospect_id),
    CONSTRAINT fk_proposal_owner FOREIGN KEY (proposal_owner_id) REFERENCES app_user(user_id),
    INDEX idx_proposal_status (status),
    INDEX idx_proposal_due (due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### `proposal_document`

File attachment metadata for proposal responses.

```sql
CREATE TABLE IF NOT EXISTS proposal_document (
    document_id          INT AUTO_INCREMENT PRIMARY KEY,
    proposal_id          INT NOT NULL,
    filename             VARCHAR(255) NOT NULL,
    file_path            VARCHAR(500) NOT NULL,
    file_size_bytes      BIGINT,
    file_type            ENUM('RFQ','RESPONSE','EXHIBIT','PAST_PERFORMANCE','PRICING','OTHER')
                             NOT NULL DEFAULT 'OTHER',
    uploaded_by          INT,
    uploaded_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    description          TEXT,
    CONSTRAINT fk_pdoc_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id),
    CONSTRAINT fk_pdoc_uploader FOREIGN KEY (uploaded_by) REFERENCES app_user(user_id),
    INDEX idx_pdoc_proposal (proposal_id),
    INDEX idx_pdoc_type (file_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### `proposal_milestone`

Bid timeline tracking with planned and actual dates.

```sql
CREATE TABLE IF NOT EXISTS proposal_milestone (
    milestone_id         INT AUTO_INCREMENT PRIMARY KEY,
    proposal_id          INT NOT NULL,
    milestone_name       VARCHAR(100) NOT NULL,
    planned_date         DATE,
    actual_date          DATE,
    owner_id             INT,
    status               ENUM('PENDING','IN_PROGRESS','COMPLETED','SKIPPED')
                             NOT NULL DEFAULT 'PENDING',
    notes                TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pm_proposal FOREIGN KEY (proposal_id) REFERENCES proposal(proposal_id),
    CONSTRAINT fk_pm_owner FOREIGN KEY (owner_id) REFERENCES app_user(user_id),
    INDEX idx_pm_proposal (proposal_id),
    INDEX idx_pm_status (status),
    INDEX idx_pm_planned (planned_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### `activity_log`

Audit trail for all user actions in the web application.

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    log_id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT,
    action_type          VARCHAR(50) NOT NULL,
    target_table         VARCHAR(50),
    target_record_id     VARCHAR(100),
    old_value            TEXT,
    new_value            TEXT,
    ip_address           VARCHAR(45),
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_actlog_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_actlog_target (target_table, target_record_id),
    INDEX idx_actlog_user_date (user_id, created_at),
    INDEX idx_actlog_action (action_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### `notification`

Alert queue for deadline reminders, status changes, and saved search hits.

```sql
CREATE TABLE IF NOT EXISTS notification (
    notification_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    notification_type    VARCHAR(50) NOT NULL,
    title                VARCHAR(200) NOT NULL,
    message              TEXT,
    related_table        VARCHAR(50),
    related_record_id    VARCHAR(100),
    is_read              CHAR(1) NOT NULL DEFAULT 'N',
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at              DATETIME NULL,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES app_user(user_id),
    INDEX idx_notif_user_read (user_id, is_read),
    INDEX idx_notif_type (notification_type),
    INDEX idx_notif_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 4. Missing Columns on Existing Tables

### `app_user` -- add authentication fields

The current `app_user` table only has display/role info. The C# API needs authentication and account security fields.

```sql
ALTER TABLE app_user
    ADD COLUMN password_hash VARCHAR(255) AFTER email,
    ADD COLUMN last_login_at DATETIME AFTER role,
    ADD COLUMN is_admin CHAR(1) NOT NULL DEFAULT 'N' AFTER last_login_at,
    ADD COLUMN mfa_enabled CHAR(1) NOT NULL DEFAULT 'N' AFTER is_admin,
    ADD COLUMN failed_login_attempts INT DEFAULT 0 AFTER mfa_enabled,
    ADD COLUMN locked_until DATETIME NULL AFTER failed_login_attempts;
```

### `opportunity` -- add capture-relevant fields

Fields needed for bid/no-bid decisions that are not currently captured from the SAM.gov API.

```sql
ALTER TABLE opportunity
    ADD COLUMN period_of_performance_start DATE AFTER pop_city,
    ADD COLUMN period_of_performance_end DATE AFTER period_of_performance_start,
    ADD COLUMN security_clearance_required ENUM('NONE','CONFIDENTIAL','SECRET','TOP_SECRET','TS_SCI','UNKNOWN')
        DEFAULT 'UNKNOWN' AFTER period_of_performance_end,
    ADD COLUMN incumbent_uei VARCHAR(12) AFTER security_clearance_required,
    ADD COLUMN incumbent_name VARCHAR(500) AFTER incumbent_uei,
    ADD COLUMN contract_vehicle_type ENUM('OPEN_MARKET','GWAC','IDIQ','BPA','FSS','OTHER')
        NULL AFTER incumbent_name,
    ADD COLUMN estimated_contract_value DECIMAL(15,2) NULL AFTER contract_vehicle_type;
```

### `prospect` -- add capture management fields

Additional fields for the full capture lifecycle.

```sql
ALTER TABLE prospect
    ADD COLUMN capture_manager_id INT AFTER assigned_to,
    ADD COLUMN proposal_status VARCHAR(20) NULL AFTER outcome_notes,
    ADD COLUMN contract_award_id VARCHAR(100) NULL AFTER proposal_status,
    ADD COLUMN estimated_gross_margin_pct DECIMAL(5,2) NULL AFTER contract_award_id,
    ADD CONSTRAINT fk_prospect_capture_mgr FOREIGN KEY (capture_manager_id) REFERENCES app_user(user_id);
```

### `prospect_team_member` -- add internal staff tracking

Currently only tracks external entities (by `uei_sam`). Need to also track internal staff members and their proposed rates.

```sql
ALTER TABLE prospect_team_member
    ADD COLUMN app_user_id INT NULL AFTER uei_sam,
    ADD COLUMN proposed_hourly_rate DECIMAL(10,2) NULL AFTER notes,
    ADD COLUMN commitment_pct DECIMAL(5,2) NULL AFTER proposed_hourly_rate,
    ADD CONSTRAINT fk_ptm_appuser FOREIGN KEY (app_user_id) REFERENCES app_user(user_id);
```

---

## 5. Missing Tables -- Tier 2 (Advanced)

### `proposal_compliance_checklist`

Track compliance with solicitation requirements (Section L/M items).

Key fields: `checklist_id` (PK), `proposal_id` (FK), `requirement` VARCHAR(500), `section_reference` VARCHAR(50), `status` ENUM('PENDING','MET','NOT_MET','NA'), `owner_id` (FK to app_user), `due_date` DATE, `evidence_document_id` (FK to proposal_document), `notes` TEXT, `created_at`.

### `proposal_risk_register`

Identify and track risks for each proposal.

Key fields: `risk_id` (PK), `proposal_id` (FK), `description` TEXT, `likelihood` TINYINT (1-5), `impact` TINYINT (1-5), `risk_score` TINYINT (computed as likelihood * impact), `mitigation_plan` TEXT, `owner_id` (FK to app_user), `status` ENUM('IDENTIFIED','MITIGATING','ACCEPTED','CLOSED'), `created_at`, `updated_at`.

### `bid_financial_estimate`

Line-item cost breakdown for a proposal.

Key fields: `estimate_id` (PK), `proposal_id` (FK), `cost_type` ENUM('LABOR','SUBCONTRACTOR','MATERIALS','TRAVEL','OVERHEAD','PROFIT'), `description` VARCHAR(200), `estimated_amount` DECIMAL(15,2), `basis` VARCHAR(200), `approved_by` (FK to app_user), `approved_at` DATETIME, `created_at`.

### `win_loss_analysis`

Post-decision analysis for continuous improvement.

Key fields: `analysis_id` (PK), `prospect_id` (FK), `winner_uei` VARCHAR(12), `winner_name` VARCHAR(500), `winning_amount` DECIMAL(15,2), `reasons_text` TEXT, `score_differential` DECIMAL(5,2), `lessons_learned` TEXT, `analyzed_by` (FK to app_user), `created_at`.

### `entity_past_performance`

Precomputed competitive intelligence scores per entity.

Key fields: `id` (PK), `uei_sam` VARCHAR(12) (FK to entity), `total_contracts` INT, `total_value` DECIMAL(15,2), `win_rate` DECIMAL(5,2), `avg_contract_size` DECIMAL(15,2), `most_common_naics` VARCHAR(6), `geographic_coverage` TEXT, `last_calculated_at` DATETIME.

---

## 6. Missing Tables -- Tier 3 (Nice-to-Have)

- **Personnel security clearance tracking** -- Track which team members hold active clearances (level, investigation date, expiry)
- **Facility compliance certifications** -- ISO 9001, CMMC level, FedRAMP, facility clearances with expiration dates
- **Contract vehicle master registry** -- GWAC/IDIQ/BPA details (vehicle name, ordering period, ceiling, SINs, eligible agencies)
- **Revenue forecast** -- Pipeline-weighted forecast: prospect estimated value * win probability, grouped by quarter
- **Team capacity/utilization tracking** -- Track billable hours, availability by month, skill matrix for staffing proposals

---

## 7. Data Gaps No API Can Fill

These fields require manual entry, document scraping, or paid third-party data:

1. **Security clearance requirements** -- Not in SAM.gov API structured fields. Buried in solicitation PDF attachments. Must be manually entered after reading the RFQ/RFP, or extracted via PDF parsing.

2. **Evaluation criteria weights** -- Found in RFQ Section M documents, not structured API data. Critical for proposal strategy but only available by reading the solicitation.

3. **Incumbent contractor for an opportunity** -- Must be inferred by joining `fpds_contract` on `solicitation_number` or matching on NAICS + agency + place of performance. No direct link exists in the SAM.gov Opportunities API.

4. **D&B financial data** -- Revenue, employee count, credit rating, years in business. Requires a paid Dun & Bradstreet subscription or SAM.gov entity management API with elevated permissions.

5. **Opportunity description text** -- SAM.gov Opportunities API returns the `description` field as a URL pointing to the full text, not the text content itself (known issue #14 in CLAUDE.md). Requires a separate authenticated fetch to retrieve the actual description HTML/text.

---

## 8. Recommended C# API Endpoints

| Method | Route | Description | Source Table/View | Auth | Notes |
|--------|-------|-------------|-------------------|------|-------|
| `GET` | `/api/opportunities` | Search with filters (set-aside, NAICS, keyword, deadline) | `opportunity` + `ref_naics_code` + `ref_set_aside_type` | Yes | Mirrors Python `search` CLI; support pagination |
| `GET` | `/api/opportunities/{noticeId}` | Single opportunity detail with related awards and prospect | `opportunity` + `fpds_contract` + `prospect` | Yes | Join on `solicitation_number` to find related awards |
| `GET` | `/api/awards` | Search historical awards (solicitation, NAICS, agency, vendor) | `fpds_contract` | Yes | Support multi-field filtering |
| `GET` | `/api/awards/{contractId}` | Single award detail with transactions | `fpds_contract` + `usaspending_transaction` | Yes | `contractId` is composite: `contract_id` + `modification_number` |
| `GET` | `/api/awards/{contractId}/burn-rate` | Monthly spend breakdown | `usaspending_transaction` | Yes | Returns monthly_breakdown array; see Section 9 SQL |
| `GET` | `/api/entities` | Search contractors (name, UEI, NAICS, certification) | `entity` + child tables | Yes | Support LIKE search on name, exact match on UEI |
| `GET` | `/api/entities/{uei}` | Full entity profile with addresses, certs, POCs | `entity` + all child tables | Yes | 6 child table joins; return nested JSON |
| `GET` | `/api/entities/{uei}/competitor-profile` | Aggregated competitive intelligence | `v_competitor_analysis` | Yes | SELECT from view with `WHERE uei_sam = {uei}` |
| `GET` | `/api/entities/{uei}/exclusion-check` | Is this contractor debarred/excluded? | `sam_exclusion` | Yes | Check `WHERE uei = {uei} AND (termination_date IS NULL OR termination_date > NOW())` |
| `GET` | `/api/subawards/teaming-partners` | Find prime-sub relationships by NAICS | `sam_subaward` GROUP BY | Yes | See Section 9 teaming partners SQL |
| `POST` | `/api/prospects` | Create prospect from opportunity | `prospect` | Yes | Validates notice_id exists; sets status=NEW |
| `GET` | `/api/prospects` | List with filters (status, assignee, priority) | `prospect` + `opportunity` | Yes | Mirrors Python `list_prospects`; support `open_only` flag |
| `GET` | `/api/prospects/{id}` | Full detail with notes, team, proposal | `prospect` + children | Yes | Return nested JSON with notes[], team_members[], proposal |
| `PATCH` | `/api/prospects/{id}/status` | Status transition (validates flow) | `prospect` | Yes | Must enforce STATUS_FLOW rules; see Section 9 |
| `POST` | `/api/prospects/{id}/notes` | Add capture note | `prospect_note` | Yes | Validate note_type against allowed list |
| `POST` | `/api/proposals` | Create proposal for prospect | `proposal` | Yes | Enforces 1:1 with prospect via UNIQUE KEY |
| `PATCH` | `/api/proposals/{id}` | Update proposal (pricing, status, dates) | `proposal` | Yes | Update `document_count` when documents added |
| `POST` | `/api/proposals/{id}/documents` | Upload document metadata | `proposal_document` | Yes | File storage handled by C# backend; DB stores metadata only |
| `GET` | `/api/dashboard` | Pipeline stats, deadline alerts, workload | `prospect` + `opportunity` aggregation | Yes | Mirrors Python `get_dashboard_data`; 5 sub-queries |
| `POST` | `/api/auth/login` | Authenticate user | `app_user` + `app_session` | No | Hash password with bcrypt; create session; return token |
| `POST` | `/api/auth/logout` | Invalidate session | `app_session` | Yes | Set `is_active = 'N'` on session record |
| `GET` | `/api/admin/etl-status` | Check last ETL runs and data freshness | `etl_load_log` | Yes (admin) | Show latest load per source_system with age in hours |

---

## 9. Key Business Logic to Replicate in C#

### Prospect Status Flow

From `ProspectManager` in `fed_prospector/etl/prospect_manager.py`:

```
STATUS_FLOW = {
    "NEW":           ["REVIEWING", "DECLINED"],
    "REVIEWING":     ["PURSUING", "DECLINED", "NO_BID"],
    "PURSUING":      ["BID_SUBMITTED", "DECLINED"],
    "BID_SUBMITTED": ["WON", "LOST"],
}

TERMINAL_STATUSES = {"WON", "LOST", "DECLINED", "NO_BID"}
```

Rules:
- A prospect in a terminal status cannot be updated.
- Status transitions must follow the `STATUS_FLOW` map. Any other transition is rejected.
- When status moves to a terminal status, set `outcome = new_status`, `outcome_date = NOW()`.
- When status moves to `BID_SUBMITTED`, set `bid_submitted_date = NOW()`.
- Every status change auto-creates a `prospect_note` with `note_type = 'STATUS_CHANGE'`.

Valid note types: `COMMENT`, `STATUS_CHANGE`, `ASSIGNMENT`, `DECISION`, `REVIEW`, `MEETING`.

Valid team roles: `PRIME`, `SUB`, `MENTOR`, `JV_PARTNER`.

Valid priority levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

### Go/No-Go Scoring (0-40 scale)

From `ProspectManager.calculate_score()`. Four criteria, each scored 0-10:

**1. Set-aside favorability (0-10)**

```python
sa_scores = {
    "WOSB": 10, "EDWOSB": 10, "WOSBSS": 10, "EDWOSBSS": 10,
    "8A": 8, "8AN": 8,
    "SBA": 5, "SBP": 5,
    "HZC": 5, "HZS": 5,
    "SDVOSBC": 5, "SDVOSBS": 5,
}
# Any other code or no code = 0
```

**2. Time remaining (0-10)**

```
> 30 days remaining  = 10 pts
15-30 days           =  7 pts
7-14 days            =  4 pts
< 7 days             =  1 pt
Past deadline        =  0 pts
No deadline known    =  5 pts (neutral)
```

**3. NAICS match (0 or 10)**

Checks if any entity in the database with WOSB business type codes (`2X`, `8W`, `A2`) has the opportunity's NAICS code registered:

```sql
SELECT COUNT(*) AS cnt
FROM entity_naics en
JOIN entity_business_type ebt ON en.uei_sam = ebt.uei_sam
WHERE en.naics_code = %s
  AND ebt.business_type_code IN ('2X', '8W', 'A2')
```

Score: 10 if `cnt > 0`, otherwise 0.

**4. Award value bracket (0-10)**

Uses `award_amount` from opportunity, falling back to `estimated_value` from prospect:

```
>= $1,000,000  = 10 pts
>= $500,000    =  8 pts
>= $100,000    =  6 pts
>= $50,000     =  4 pts
< $50,000      =  2 pts
Unknown value  =  3 pts (neutral-low)
```

Total = sum of all four criteria. Maximum possible = 40. Stored in `prospect.go_no_go_score`.

### Burn Rate Calculation

From `USASpendingLoader.calculate_burn_rate()` in `fed_prospector/etl/usaspending_loader.py`:

```sql
SELECT DATE_FORMAT(action_date, '%Y-%m') AS year_month,
       SUM(federal_action_obligation) AS monthly_total,
       COUNT(*) AS txn_count
FROM usaspending_transaction
WHERE award_id = %s
  AND federal_action_obligation IS NOT NULL
GROUP BY year_month
ORDER BY year_month
```

Calculated fields:
- `total_obligated` = sum of all `monthly_total` values
- `months_elapsed` = inclusive month count from first to last `year_month`
- `monthly_rate` = `total_obligated / months_elapsed`
- `monthly_breakdown` = list of `(year_month, amount)` tuples
- `transaction_count` = sum of all `txn_count` values

### Target Opportunity View

Full SQL from `fed_prospector/db/schema/07_views.sql`:

```sql
CREATE OR REPLACE VIEW v_target_opportunities AS
SELECT
    o.notice_id,
    o.title,
    o.solicitation_number,
    o.department_name,
    o.office,
    o.posted_date,
    o.response_deadline,
    DATEDIFF(o.response_deadline, NOW()) AS days_until_due,
    o.set_aside_code,
    o.set_aside_description,
    sa.category AS set_aside_category,
    o.naics_code,
    n.description AS naics_description,
    n.level_name AS naics_level,
    sector.description AS naics_sector,
    ss.size_standard,
    ss.size_type,
    o.award_amount,
    o.pop_state,
    o.pop_city,
    o.description,
    o.link,
    p.prospect_id,
    p.status AS prospect_status,
    p.priority AS prospect_priority,
    u.display_name AS assigned_to
FROM opportunity o
LEFT JOIN ref_naics_code n ON n.naics_code = o.naics_code
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(o.naics_code, 2)
    AND sector.code_level = 1
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
LEFT JOIN ref_set_aside_type sa ON sa.set_aside_code = o.set_aside_code
LEFT JOIN prospect p ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE o.active = 'Y'
  AND o.set_aside_code IN ('WOSB', 'EDWOSB', 'WOSBSS', 'EDWOSBSS', 'SBA', '8A', '8AN')
  AND o.response_deadline > NOW();
```

The C# API can `SELECT * FROM v_target_opportunities` directly, adding `ORDER BY` and `LIMIT` as needed. No need to replicate the JOIN logic in C#.

### Competitor Analysis View

Full SQL from `fed_prospector/db/schema/07_views.sql`:

```sql
CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.primary_naics,
    n.description AS naics_description,
    sector.description AS naics_sector,
    es.description AS entity_structure,
    GROUP_CONCAT(DISTINCT CONCAT(ebt.business_type_code, ':', COALESCE(rbt.description, ''))
        ORDER BY ebt.business_type_code SEPARATOR '; ') AS business_types,
    GROUP_CONCAT(DISTINCT rbt.category ORDER BY rbt.category SEPARATOR ', ') AS business_type_categories,
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(rst.description, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ') AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN ref_naics_code n ON n.naics_code = e.primary_naics
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(e.primary_naics, 2)
    AND sector.code_level = 1
LEFT JOIN ref_entity_structure es ON es.structure_code = e.entity_structure_code
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN ref_business_type rbt ON rbt.business_type_code = ebt.business_type_code
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN ref_sba_type rst ON rst.sba_type_code = esc.sba_type_code
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics,
         n.description, sector.description, es.description;
```

The C# API can `SELECT * FROM v_competitor_analysis WHERE uei_sam = @uei` for a single entity, or add `LIMIT`/`ORDER BY` for search results.

### Teaming Partners Query

From `SubawardLoader.find_teaming_partners()` in `fed_prospector/etl/subaward_loader.py`:

```sql
SELECT
    s.prime_uei,
    s.prime_name,
    COUNT(*) AS sub_count,
    SUM(s.sub_amount) AS total_sub_amount,
    COUNT(DISTINCT s.sub_uei) AS unique_subs,
    GROUP_CONCAT(DISTINCT s.naics_code ORDER BY s.naics_code SEPARATOR ', ')
        AS naics_codes
FROM sam_subaward s
WHERE s.naics_code = %s    -- optional NAICS filter
GROUP BY s.prime_uei, s.prime_name
HAVING COUNT(*) >= %s      -- min_subawards threshold
ORDER BY sub_count DESC
LIMIT %s
```

### Opportunity Search Query

From the `search` CLI command in `fed_prospector/cli/opportunities.py`:

```sql
SELECT o.title, o.set_aside_code, o.naics_code,
       o.response_deadline, o.posted_date, o.department_name,
       n.description
FROM opportunity o
LEFT JOIN ref_naics_code n ON o.naics_code = n.naics_code
WHERE o.posted_date >= %s                    -- cutoff date
  AND o.set_aside_code = %s                  -- optional
  AND o.naics_code = %s                      -- optional
  AND o.response_deadline > NOW()            -- if open_only
  AND o.active = 'Y'                         -- if open_only
ORDER BY o.response_deadline ASC
LIMIT %s
```

---

## 10. Database Changes Summary

| Metric | Count |
|--------|-------|
| **Current state** | 39 tables + 2 views |
| **Tier 1 new tables** | +6 (`app_session`, `proposal`, `proposal_document`, `proposal_milestone`, `activity_log`, `notification`) |
| **Tier 1 new columns** | ~15 columns across 4 existing tables (`app_user`, `opportunity`, `prospect`, `prospect_team_member`) |
| **After Tier 1** | **45 tables + 2 views** |
| **Tier 2 new tables** | +5 (`proposal_compliance_checklist`, `proposal_risk_register`, `bid_financial_estimate`, `win_loss_analysis`, `entity_past_performance`) |
| **After Tier 2** | **50 tables + 2 views** |
| **Tier 3 new tables** | +5 (clearance tracking, facility certs, vehicle registry, revenue forecast, capacity tracking) |
| **After Tier 3** | **55 tables + 2 views** |

### Migration Order

1. **ALTER existing tables first** -- `app_user` auth fields are needed before `app_session` can reference them.
2. **Create Tier 1 tables** -- `app_session` depends on `app_user`; `proposal` depends on `prospect` and `app_user`; `proposal_document` and `proposal_milestone` depend on `proposal`.
3. **Tier 2 and Tier 3** -- can be added incrementally as the C# API features expand.

### Compatibility Note

All new tables and columns are additive. The Python ETL layer will continue to work unchanged -- it does not touch `app_session`, `proposal`, `activity_log`, or `notification`. The `ALTER TABLE` statements add nullable columns or columns with defaults, so existing Python INSERT/UPDATE statements are unaffected.
