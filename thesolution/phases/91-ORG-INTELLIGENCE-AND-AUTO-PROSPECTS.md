# Phase 91: Organization Intelligence & Auto-Prospects

**Status**: BACKLOG
**Priority**: HIGH
**Depends on**: Phase 90 (Smart Daily Load)
**Estimated scope**: Large (schema + API + ETL + UI)

---

## Purpose

The ONLY purpose of FedProspect is to help organizations easily find and be prepared to bid on federal opportunities — both active solicitations and upcoming re-competes. Today, prospects must be created manually one at a time. An org with 14,000+ loaded opportunities sees only 5 prospects because nobody clicked "Track" on the other 13,995.

This phase makes prospects **appear automatically** based on organizational fit, and gives orgs the tools to define who they are and who they team with so the system can match intelligently.

---

## Problem Statement

### P91-1: Organizations Can't Define Their Business Identity
- An org has a `uei_sam` field but no enforced link to SAM.gov `entity` data
- NAICS codes in `organization_naics` are manually entered — they could be auto-populated from the org's SAM.gov entity record
- No way to link JV or teaming partners to the org
- pWin scoring queries `organization_naics` and `organization_certification` but these may be stale or incomplete vs. the authoritative SAM.gov `entity` record

### P91-2: No Auto-Prospect Generation
- Loading opportunities, awards, entities does NOT create prospect records
- Saved searches notify but don't auto-create prospects
- Expiring contract detection shows data but doesn't create prospects
- Users must manually click "Track as Prospect" on every opportunity they want to pursue
- Result: the Prospects pipeline is always near-empty despite thousands of matching opportunities

### P91-3: `prospect.win_probability` Is Never Written
The column exists but no code path populates it. `PWinService.CalculateAsync()` returns a score but never persists it to the prospect row. This is a bug — fix in C2.

### P91-4: pWin Uses Only a Single UEI
- 4 of 7 pWin factors (`ScoreNaicsExperienceAsync`, `ScoreIncumbentAdvantageAsync`, `ScoreTeamingStrengthAsync`, `ScoreContractValueFitAsync`) query only the org's single `uei_sam`
- JV partner FPDS experience, partner incumbency, and partner teaming history are invisible to scoring
- This directly undermines auto-prospect accuracy for orgs that bid as a team

---

## Architecture Decisions

### AD-1: Schema Ownership — `organization_entity`
The new table is **EF Core-owned** (user-facing application data, not ETL). DDL goes in `90_web_api.sql` alongside other app tables. The `organization_entity` table has a cross-domain FK to the Python-owned `entity.uei_sam` — this is the first such cross-domain FK. Update `check-schema` validation to expect it.

### AD-2: Auto-Prospect Scoring Lives in C# (Not Python)
pWin is calculated by `PWinService.cs` (C#). `RecommendedOpportunityService.cs` already does NAICS+cert matching in C#. **Do not reimplement scoring in Python.** Instead:
- Add a batch endpoint: `POST /api/v1/prospects/auto-generate` that accepts `{organizationId}` and runs matching + pWin internally
- Python post-load hook calls this endpoint via HTTP (same pattern as health checks)
- Requires the C# API to be running during batch jobs — acceptable for a scheduled process

### AD-3: `organization.uei_sam` Stays As-Is
When `organization_entity` is added, `organization.uei_sam` remains as it is. Services that read `org.UeiSam` (PWinService, QualificationService, CompanyProfileService) continue working unchanged. The SELF entity link in `organization_entity` is the authoritative relationship; `org.uei_sam` is updated when a SELF entity is linked.

### AD-4: Dual Scoring — Go/No-Go vs. pWin
Go/No-Go (4 factors, 0-40 scale) is a quick eligibility gate. pWin (7 weighted factors, 0-100%) is deeper win probability. They are complementary, not redundant. `prospect.win_probability` should be populated by pWin on every calculation.

### AD-5: API Route Convention
Existing org endpoints use `api/v1/org/` (no `{id}` in URL — resolved from JWT). New entity-linking endpoints follow the same pattern:
- `GET api/v1/org/entities` — list linked entities
- `POST api/v1/org/entities` — link an entity
- `DELETE api/v1/org/entities/{linkId}` — remove link

Entity search already exists at `GET api/v1/entities` — no new endpoint needed.

---

## Deliverables

### Task Group A: Organization Entity Linking (5 tasks)

**Goal**: Let orgs define which SAM.gov entities they own or partner with, and inherit NAICS/cert data automatically.

#### P91-A1: `organization_entity` Junction Table

**Schema owner**: EF Core. DDL in `90_web_api.sql`.

```sql
CREATE TABLE organization_entity (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    uei_sam         VARCHAR(12) NOT NULL,
    relationship    VARCHAR(20) NOT NULL,
    is_active       CHAR(1) NOT NULL DEFAULT 'Y',
    added_by        INT NULL,
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_entity (organization_id, uei_sam, relationship),
    CONSTRAINT fk_oe_org FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    CONSTRAINT fk_oe_entity FOREIGN KEY (uei_sam) REFERENCES entity(uei_sam),
    CONSTRAINT fk_oe_user FOREIGN KEY (added_by) REFERENCES app_user(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Unique key includes `relationship`** — allows the same entity to be both `JV_PARTNER` and `TEAMING` for different arrangements.

**Relationship types**:
| Type | Meaning | Contributes to Effective NAICS? |
|------|---------|--------------------------------|
| `SELF` | This entity IS the organization | Yes |
| `JV_PARTNER` | Joint venture partner | Yes |
| `TEAMING` | Teaming agreement partner | Yes |

#### P91-A2: Auto-Populate Org Profile from SELF Entity

When an org links a `SELF` entity:
- Copy `organization_naics` from `entity_naics`
- Copy `organization_certification` from `entity_sba_certification`
- Auto-fill org profile fields (legal_name, address, CAGE, etc.) from `entity` record
- Update `organization.uei_sam`

**Refresh button**: A "Refresh from SAM.gov" button re-copies from the SELF entity on demand. No ongoing sync infrastructure needed.

**Orgs without SAM.gov entities**: Entity linking is optional. `organization_naics` (manually entered) is always included in effective NAICS regardless of whether any entities are linked. Auto-prospects work with manual NAICS alone.

#### P91-A3: Entity Search & Link UI
New tab on Organization Settings page:
- Search entities using existing `GET api/v1/entities` endpoint (by UEI, name, CAGE code)
- Preview entity details (NAICS codes, certs, address) before linking
- Select relationship type and confirm
- Show all linked entities with relationship type and status
- Remove/deactivate links

#### P91-A4: Aggregate NAICS Across Linked Entities
Create a C# service method that computes the org's **effective NAICS codes** — the union of:
- `organization_naics` (manually entered — always included)
- `entity_naics` for all active linked entities where relationship contributes to NAICS (SELF, JV_PARTNER, TEAMING)

This aggregate is used by auto-prospect matching, pWin scoring, and the recommended opportunities service.

**Limitation**: pWin scoring accuracy depends on FPDS award data being loaded for these NAICS codes. If a JV partner adds NAICS 236220 but Phase 90 doesn't load awards for that code, pWin factors (Competition Level, Incumbent Advantage, Contract Value Fit) will score neutral (50) for those opportunities. Document this in the UI.

#### P91-A5: API Endpoints for Entity Linking
- `GET api/v1/org/entities` — list linked entities with entity details
- `POST api/v1/org/entities` — link an entity `{ueiSam, relationship, notes}`
- `DELETE api/v1/org/entities/{linkId}` — deactivate link

Entity search: existing `GET api/v1/entities` endpoint — no new work needed.

#### P91-A6: Update pWin to Use Aggregate UEIs
Modify `PWinService.cs` to query all active linked entity UEIs instead of just `org.UeiSam`:

| Factor Method | Current | After P91-A6 |
|--------------|---------|-------------|
| `ScoreNaicsExperienceAsync` | FPDS WHERE `vendor_uei = orgUei` | FPDS WHERE `vendor_uei IN (linked UEIs)` |
| `ScoreIncumbentAdvantageAsync` | `incumbentUei == orgUei` | `incumbentUei IN (SELF + JV_PARTNER UEIs)` |
| `ScoreTeamingStrengthAsync` | Subawards for `orgUei` | Subawards for any linked UEI |
| `ScoreContractValueFitAsync` | FPDS for `orgUei` | FPDS for any linked UEI |

---

### Task Group B: Auto-Prospect Generation (6 tasks)

**Goal**: After each data load, automatically surface matching opportunities as prospects based on organizational profile and scoring.

#### P91-B1: Add `source` Column to Prospect Table

```sql
ALTER TABLE prospect ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'MANUAL'
    AFTER organization_id;
```

Values: `MANUAL`, `AUTO_MATCH`, `AUTO_RECOMPETE`, `AUTO_SAVED_SEARCH`

This enables UI filtering, dashboard differentiation, and notification strategy.

#### P91-B2: Saved Search as Auto-Prospect Driver

Extend `saved_search` with auto-prospect columns:

```sql
ALTER TABLE saved_search
    ADD COLUMN auto_prospect_enabled CHAR(1) NOT NULL DEFAULT 'N',
    ADD COLUMN min_pwin_score DECIMAL(5,2) NULL DEFAULT 30.0,
    ADD COLUMN auto_assign_to INT NULL,
    ADD COLUMN last_auto_run_at DATETIME NULL,
    ADD COLUMN last_auto_created INT NULL DEFAULT 0,
    ADD CONSTRAINT fk_ss_auto_user FOREIGN KEY (auto_assign_to) REFERENCES app_user(user_id);
```

**Why reuse saved searches**: The `saved_search.filter_criteria` JSON already supports `set_aside_codes`, `naics_codes`, `states`, `min_award_amount`, `max_award_amount`, `types`, `days_back`. This is exactly the filtering auto-prospects need. An org doing WOSB IT in Virginia shouldn't get WOSB construction prospects in Alaska.

**Multiple profiles**: An org can have several saved searches with auto-prospect enabled (e.g., one for IT services, one for consulting), each with different filters and pWin thresholds.

Recompete settings (if needed) go as columns on `organization` directly.

**Schema owner**: EF Core-owned.

#### P91-B3: Auto-Prospect Engine (C# API Endpoint)

**Architecture**: Scoring lives in C# (see AD-2). The auto-prospect engine is a C# endpoint, not a Python CLI command.

New endpoint: `POST api/v1/prospects/auto-generate`
- Accepts: `{organizationId}` (admin-only or internal service call)
- Returns: `{evaluated: N, created: N, skipped: N, errors: []}`

Logic:
1. Get org's saved searches where `auto_prospect_enabled = 'Y'`
2. For each saved search, run the filter criteria against `opportunity` table:
   - `response_deadline > NOW()` (still open)
   - Apply all saved search filters (NAICS, set-aside, states, dollar range, etc.)
   - `NOT EXISTS (SELECT 1 FROM prospect WHERE organization_id = X AND notice_id = opp.notice_id)` — dedup
3. **Pre-filter is critical**: This SQL step reduces 14,000+ opportunities to a manageable candidate set before any pWin calculation
4. For each candidate, call `PWinService.CalculateAsync()` (reuses existing code)
5. If pWin >= saved search's `min_pwin_score`:
   - Create prospect with `source = 'AUTO_MATCH'`, `status = 'NEW'`
   - `priority` based on pWin tier (HIGH >= 70, MEDIUM >= 40, LOW < 40)
   - `assigned_to` = saved search's `auto_assign_to` or org default
   - Write `prospect.win_probability` = pWin score
   - Auto-note: "Auto-matched via saved search '{name}': pWin {score}%, NAICS {code}"
   - **Skip individual notifications** — one summary notification at the end (see B6 note below)
6. Update saved search: `last_auto_run_at`, `last_auto_created`
7. Create ONE summary notification: "Auto-prospect run: {N} new prospects from {M} saved searches. Highest pWin: {score}%."

**Notification note (B6)**: Auto-prospect creation skips individual `PROSPECT_ASSIGNED` notifications. The summary notification in step 7 is the only notification. This is logic inside B3, not a separate deliverable.

#### P91-B4: Recompete Detection (V1)

Extend auto-generation for expiring awards. V1 is conservative: only create recompete prospects when a follow-on solicitation already exists.

- Match expiring contract to opportunity by `solicitation_number` or `agency + NAICS` pattern
- If match found: create prospect with `source = 'AUTO_RECOMPETE'`, link to the opportunity's `notice_id`
- If no match: no prospect created (the ExpiringContractsPage already shows these contracts)

Uses `ExpiringContractService` logic (already queries `fpds_contract_record.ultimate_completion_date`).

#### P91-B5: Post-Load Hook Integration

The auto-prospect trigger runs as a scheduler job in `scheduler.py`:
- Add `"auto_prospect"` to `JOBS` dict
- Append to `DAILY_SEQUENCE` after opportunity/award loads
- Job calls `POST api/v1/prospects/auto-generate` for each active org
- Leverages existing batch runner infrastructure (skip-if-fresh, failure tracking, timing)

Also available as standalone: `python main.py prospect auto-generate --all-orgs` (calls the API endpoint)

#### P91-B7: Dashboard Integration (Slim)

- **New "Auto-Matches" card**: Shows count of unreviewed auto-prospects this week, with "Review" button linking to filtered pipeline view
- **Filtered pipeline view**: Prospect pipeline page gets a `source` filter dropdown

Auto-prospect settings (per-saved-search toggles for on/off, pWin threshold, assignee) are part of the existing saved search edit UI, not a separate settings section.

---

### Task Group C: pWin Fix (1 task)

#### P91-C1: pWin Explainer

Add a collapsible "How is this calculated?" section on the opportunity detail page (or tooltip on the pWin gauge). Lightweight implementation — not a dedicated routed page.

**Current formula** (reference for implementation, verified against `PWinService.cs`):

| Factor | Weight | Score Logic |
|--------|--------|-------------|
| **Set-Aside Match** | 20% | Org certs vs. opp set-aside: exact=100, related=50, none=0, unknown/no set-aside=50 |
| **NAICS Experience** | 20% | Past perf + FPDS contracts in NAICS: >=5=100, >=3=75, >=1=50, 0=10 |
| **Competition Level** | 15% | Distinct vendors in NAICS (3yr): 0-3=100, 4-6=70, 7-10=40, 10+=20 |
| **Incumbent Advantage** | 15% | Is org incumbent: yes=100, no incumbent found=70, other incumbent=30 |
| **Teaming Strength** | 10% | Partners with NAICS exp: 3+=100, 1-2=60, 0=30 |
| **Time to Respond** | 10% | Days to deadline: 30+=100, 14-30=70, 7-14=40, <7=10, past=0 |
| **Contract Value Fit** | 10% | Est. value vs. org avg: <=2x=100, 2-5x=60, >5x=30, no history=50 |

**Category thresholds**: High (70-100), Medium (40-69), Low (15-39), Very Low (0-14)

#### P91-C2: Populate `prospect.win_probability`

Currently dead — never written by any code path. Fix:
- `PWinService.CalculateAsync()` writes the score to `prospect.win_probability` whenever calculated (if a prospect exists for that notice_id + org)
- Auto-prospect creation writes pWin at creation time

This ensures `ProspectSummaryDto.WinProbability` and pipeline list views show actual scores.

---

### Task Group D: UX (1 task)

#### P91-D2: Opportunity Match Reasoning
When viewing an auto-generated prospect's opportunity, show a "Match Reasons" banner:
- "Matched via saved search '{name}': NAICS 541511, WOSB set-aside, pWin 62%"
- Displayed as chips/badges on the opportunity detail page header
- Builds trust and helps users quickly triage auto-prospects

---

### Task Group E: Dynamic Awards Filter Derivation (1 task)

**Goal**: Replace hardcoded NAICS/set-aside defaults in the awards loader with DB-driven queries derived from what orgs actually track.

**Context**: Phase 90's awards loader reads `DEFAULT_AWARDS_NAICS` (24 codes) and `DEFAULT_AWARDS_SET_ASIDES` (`8A,WOSB,SBA`) from `settings.py` env vars. These were manually chosen to match the first org's profile. As orgs are added or update their NAICS/certs, the awards loader should adapt automatically.

#### P91-E1+E2: Dynamic NAICS/Set-Aside Functions + Awards Loader Wiring

New functions in `fed_prospector/etl/etl_utils.py`:

```python
def get_tracked_naics() -> list[str]:
    """Union of NAICS codes from all active orgs' organization_naics.
    Falls back to settings.DEFAULT_AWARDS_NAICS if DB returns empty."""
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT DISTINCT n.naics_code "
            "FROM organization_naics n "
            "JOIN organization o ON o.organization_id = n.organization_id "
            "WHERE o.is_active = 'Y'"
        )
        codes = [row["naics_code"] for row in cursor.fetchall()]
    if codes:
        return codes
    return [c.strip() for c in settings.DEFAULT_AWARDS_NAICS.split(",") if c.strip()]

def get_tracked_set_asides() -> list[str]:
    """Union of certification types from all active orgs' organization_certification,
    mapped to set-aside codes. Falls back to settings.DEFAULT_AWARDS_SET_ASIDES."""
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT DISTINCT c.certification_type "
            "FROM organization_certification c "
            "JOIN organization o ON o.organization_id = c.organization_id "
            "WHERE o.is_active = 'Y' AND c.is_active = 'Y'"
        )
        types = [row["certification_type"] for row in cursor.fetchall()]
    if types:
        return types
    return [c.strip() for c in settings.DEFAULT_AWARDS_SET_ASIDES.split(",") if c.strip()]
```

**Fallback behavior**: If no orgs exist or no NAICS/certs are configured (new install), falls back to env var defaults from `settings.py`.

**Files to change**:

| File | Change |
|------|--------|
| `cli/awards.py` | Replace `settings.DEFAULT_AWARDS_NAICS` / `settings.DEFAULT_AWARDS_SET_ASIDES` with `get_tracked_naics()` / `get_tracked_set_asides()` in the "no filters" fallback branch |
| `cli/load_batch.py` | Dry-run preview uses `settings.DEFAULT_AWARDS_NAICS.split(",")` for combo count — replace with same functions |
| `config/settings.py` | Keep as-is — env vars remain as fallback defaults |

Log the source and count: "Dynamic awards filter: {N} NAICS codes from org data" or "No org NAICS configured — using DEFAULT_AWARDS_NAICS ({N} codes)".

---

## Current State (What Exists Today)

| Component | Status | Gap |
|-----------|--------|-----|
| `organization.uei_sam` | Exists (advisory, no FK) | No link to entity table; no JV/partner concept |
| `organization_naics` | Exists (manual entry) | Not auto-synced from entity; doesn't include partner NAICS |
| `organization_certification` | Exists (manual entry) | Not auto-synced from `entity_sba_certification` |
| `prospect` table | Exists (5 manual rows) | No auto-generation; no `source` column; `win_probability` never populated |
| `prospect.win_probability` | Exists, **always NULL** | pWin calculates but never writes here |
| `saved_search` | Exists (filters + notify) | Doesn't auto-create prospects from matches |
| pWin calculation | Exists (7 factors, on-demand, C#) | Not persisted; uses single UEI; no explanation UI |
| Expiring contract detection | Exists (`ExpiringContractService`) | Shows data but doesn't create prospects |
| Entity search API | Exists (`GET api/v1/entities`) | Ready for entity linking UI — no new endpoint needed |
| Awards loader filters | Hardcoded in `settings.py` | Not derived from org data |

---

## Implementation Order

### Wave 1: Entity Linking (org identity must exist before auto-matching works well)

1. **A1**: `organization_entity` table with SELF, JV_PARTNER, TEAMING
2. **A3+A5**: Entity search/link UI + 3 API endpoints
3. **A2**: One-time NAICS/cert copy from SELF entity + Refresh button
4. **A4**: Aggregate NAICS service
5. **A6**: Update pWin to use aggregate UEIs

### Wave 2: Auto-Prospects (builds on org identity from Wave 1)

6. **B1**: `source` column on prospect
7. **B2**: `saved_search` auto-prospect columns
8. **B3**: Auto-prospect engine endpoint (includes notification summary)
9. **B4**: Recompete detection V1 (match to existing solicitations only)
10. **B5**: Post-load hook in scheduler
11. **C2**: Populate `prospect.win_probability` (bug fix)
12. **D2**: Match reasoning banner
13. **E1+E2**: Dynamic NAICS/set-aside functions in awards loader
14. **B7**: Auto-match count card + source filter on pipeline

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-prospects overwhelm users with noise | Users ignore all prospects | `source` column + dashboard separation; conservative pWin threshold (40+); per-saved-search control |
| NAICS coverage gap | Opportunities in NAICS codes not covered by ETL award loads get incomplete pWin | Document limitation in UI; dynamic NAICS loading (E1+E2) closes the gap over time |
| Schema change blast radius | Breaks existing prospect flow | All changes are additive; `source` column has DEFAULT 'MANUAL'; existing flows untouched |
| Multiple orgs claim same entity | Data isolation concern | `organization_entity` is per-org; each org sees only their links; entity data is shared read-only |
| C# API must be running for auto-prospect | Adds runtime dependency to batch jobs | Already true for health checks; scheduler validates API health before running |
| Empty DB on new install | `get_tracked_naics()` returns nothing | Fallback to `DEFAULT_AWARDS_NAICS` / `DEFAULT_AWARDS_SET_ASIDES` env vars |

---

## Success Criteria

1. Org can link SELF + JV partner entities via entity search UI
2. NAICS codes aggregate across all linked entities
3. pWin uses all linked entity UEIs for FPDS/incumbent/teaming queries
4. Auto-prospects appear after data loads based on saved search filters
5. Expiring contracts with existing solicitations generate recompete prospects
6. `prospect.win_probability` is populated on every pWin calculation
7. Dashboard shows auto-match count and pipeline has source filter
8. Awards loader uses dynamic NAICS/set-aside from org data with env var fallback

---

## Out of Scope / Deferred

These items were considered and intentionally cut from Phase 91. Add when justified:

| Item | Reason Deferred |
|------|----------------|
| MENTOR/PROTEGE/SUB relationship types | Add when requested — 3 types sufficient for now |
| Team member auto-population (A7) | Convenience feature — add after core entity linking works |
| Ongoing entity sync infrastructure | Refresh button sufficient; no need for `last_synced_at` tracking, diff review UI, stale cert flagging |
| `organization_auto_config` table | Put recompete settings as columns on `organization` if needed |
| Recompetes feed for contracts without solicitations (B8) | ExpiringContractsPage already shows these |
| pWin score history table (C3) | Add when prospect volume justifies tracking score changes over time |
| pWin validation dashboard (C4) | Needs outcome data (WON/LOST) that doesn't exist yet |
| Configurable pWin weights (C5) | Needs validation data to prove defaults are suboptimal |
| Onboarding wizard (D1) | Manual setup sufficient for current user count |
| Opportunity feed / new matches view (D3) | Opportunity search + auto-prospects cover discovery |
| Saved search NAICS as additional filter signal (E3) | Fix org profile instead of pulling from search filters |
| MAX_AWARDS_COMBOS ceiling (E6) | Current volume nowhere near problematic |
| Proposal document generation | Not in scope for prospecting tool |
| External bid management integration | Not in scope |
| Automated bid/no-bid decisions | Humans decide, system recommends |
| Competitor tracking via `organization_entity` | Natural extension, not this phase |
| Making `prospect.notice_id` nullable for recompetes | V2 approach, future phase |
