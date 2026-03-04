# Phase 5: Extended Data Sources

**Status**: COMPLETE (2026-02-28) - All iterations complete (5A-5E, 5G); 5F deprecated
**Dependencies**: Phase 3 (Opportunities Pipeline) complete
**Deliverable**: Comprehensive data from all priority sources loaded and cross-referenced

---

> **Note (Phase 14.20):** Iteration 5B (USASpending bulk CSV) and 5C/5D analysis queries were descoped. The API-based loading path in `usaspending_loader.py` is sufficient for current needs.

## Overview

Phase 5 adds 7 additional data sources beyond the core Entity + Opportunities pipelines. Each is a self-contained iteration that can be implemented independently. The order below reflects priority ranking from [01-RESEARCH-AND-DATA-SOURCES.md](../reference/01-RESEARCH-AND-DATA-SOURCES.md).

---

## Iteration 5A: SAM.gov Contract Awards API

**Priority**: Tier 2 (High Value)
**Purpose**: Historical award data for competitive intelligence
**Status**: COMPLETE (2026-02-28)

### Tasks
- [x] Implement `api_clients/sam_awards_client.py`
  - [x] `search_awards(**filters)` - paginated search (v1 API)
  - [x] `search_awards_all(**filters)` - auto-paginate all results
  - [x] `search_by_naics(naics_code, **filters)` - NAICS-specific search
  - [x] `search_by_awardee(uei, **filters)` - awardee-specific search
  - [x] `search_by_solicitation(sol_number)` - solicitation lookup
- [x] Implement `etl/awards_loader.py`
  - [x] Transform API response -> `fpds_contract` table
  - [x] SHA-256 change detection (`record_hash` column)
  - [x] Handle modifications (same contract_id, different modification_number)
- [x] 8 new columns added to `fpds_contract`:
  - `far1102_exception_code`, `far1102_exception_name`, `reason_for_modification`
  - `solicitation_date`, `ultimate_completion_date`, `type_of_contract_pricing`
  - `co_bus_size_determination`, `record_hash`
- [x] 3 new indexes: `idx_fpds_completion`, `idx_fpds_hash`, `idx_fpds_far1102`
- [x] CLI command: `load-awards` (in `cli/awards.py`)
- [x] Cross-reference: awardee UEI links to `entity` table via `v_competitor_analysis` view

### Acceptance Criteria
- [x] `fpds_contract` table accepts data from SAM.gov Contract Awards API
- [x] `v_competitor_analysis` view returns meaningful results
- [x] Can answer: "Who won the most WOSB IT contracts last year?"

### Known Issues
- SAM.gov Contract Awards API dates are in MM/DD/YYYY format (not ISO 8601) -- awards_loader handles conversion

---

## Iteration 5B: USASpending.gov API

**Priority**: Tier 1 (Essential) for aggregate analysis
**Purpose**: Spending analysis with no rate limits
**Status**: COMPLETE (2026-02-22)

### Tasks
- [x] Implement `api_clients/usaspending_client.py`
  - [x] `search_spending_by_award(**filters)` - `/api/v2/search/spending_by_award/` (POST-based)
  - [x] `get_award(award_id)` - `/api/v2/awards/{award_id}/`
  - [x] `get_recipient(uei)` - `/api/v2/recipient/duns/{recipient_id}/`
  - [x] `get_spending_by_category(category, filters)` - aggregated data
  - [x] `request_bulk_download(filters)` - `/api/v2/bulk_download/awards/`
  - [x] No rate limits - can query aggressively
- [x] Implement `etl/usaspending_loader.py`
  - [x] SHA-256 change detection, batch upsert
  - [x] `usaspending_award` table created in MySQL (`db/schema/tables/70_usaspending.sql`)
  - [x] Incumbent search working (find previous winners by NAICS/agency)
- [ ] Implement bulk download processing:
  - [ ] Download FY archives from download center
  - [ ] Parse CSV files into database
- [ ] Load aggregate spending data:
  - [ ] Spending by agency for WOSB/8(a) contracts
  - [ ] Spending by NAICS code
  - [ ] Top awardees by category
  - [ ] Spending trends over time

### Acceptance Criteria
- [x] Can query spending data without rate limit concerns
- [ ] Can answer: "Which agencies spend the most on WOSB contracts in NAICS 541511?"
- [ ] Can show spending trends over 3-5 years

### Remaining Work
- Bulk CSV download from USASpending download center
- Aggregate spending analysis queries
- ~~CLI command for USASpending loads~~ DONE -- `load-transactions` and `burn-rate` commands implemented in Phase 5B-Enhance

---

## Iteration 5B-Enhance: USASpending Transaction History

**Priority**: Enhancement to 5B
**Purpose**: Transaction-level spending data for burn rate analysis
**Status**: COMPLETE (2026-02-28)

### Tasks
- [x] New table: `usaspending_transaction` (in `tables/70_usaspending.sql`)
  - Columns: id, award_id (FK), action_date, modification_number, action_type, action_type_description, federal_action_obligation, description, first_loaded_at, last_load_id
  - Indexes: idx_ut_award, idx_ut_date
- [x] Enhanced `api_clients/usaspending_client.py`
  - [x] `get_award_transactions(award_id)` - single award transaction history
  - [x] `get_all_transactions(award_id)` - auto-paginate all transactions
- [x] Enhanced `etl/usaspending_loader.py`
  - [x] `load_transactions(award_id)` - load transaction detail from API
  - [x] `calculate_burn_rate(award_id)` - compute spend velocity analysis
- [x] CLI commands (in `cli/spending.py`):
  - [x] `load-transactions` - load transaction history for a USASpending award
  - [x] `burn-rate` - calculate and display burn rate for an award

### Acceptance Criteria
- [x] Transaction-level spending data loads into `usaspending_transaction`
- [x] Burn rate calculation shows spend velocity over time
- [x] Can analyze: how fast is an incumbent spending down their contract?

---

## Iteration 5C: GSA CALC+ Labor Rates

**Priority**: Tier 2 (High Value)
**Purpose**: Pricing intelligence for proposal development
**Status**: COMPLETE (2026-02-22)

### Tasks
- [x] Implement `api_clients/calc_client.py`
  - [x] `search_rates(**filters)` - paginated search (GET-based)
  - [x] Filter by: keyword, business_size, price_range, education_level, security_clearance
  - [x] No auth required, no rate limits
- [x] Implement `etl/calc_loader.py` (full_refresh with TRUNCATE + reload)
- [x] Load all ~122K labor rate records
- [x] Implement monthly refresh (full reload via `load-calc` CLI command)
- [ ] Build pricing analysis queries:
  - [ ] Average rates by labor category
  - [ ] Rate ranges for specific SINs
  - [ ] Small business vs large business rate comparison

### Acceptance Criteria
- [x] `gsa_labor_rate` table has ~122K records
- [x] Monthly refresh job works (`python main.py load-calc`)
- [ ] Can query: "What's the average rate for 'Senior Software Developer' from small businesses?"

---

## Iteration 5D: SAM.gov Federal Hierarchy

**Priority**: Tier 1 (Essential)
**Purpose**: Agency organizational structure for targeting
**Status**: COMPLETE (2026-02-28)

### Tasks
- [x] Implement `api_clients/sam_fedhier_client.py`
  - [x] `get_all_organizations(status='Active')` - paginated full load
  - [x] `get_organization(fh_org_id)` - single org lookup
  - [x] `search_organizations(**filters)` - filtered search (fhorgid, fhorgname, status, fhorgtype, agencycode, cgac, fhparentorgname, date range)
  - [x] `search_organizations_all(**filters)` - auto-paginate all results
  - [x] Handle hierarchical parent-child relationships (via fhorgparenthistory)
- [x] Implement `etl/fedhier_loader.py`
  - [x] Transform API response -> `federal_organization` table
  - [x] Build parent-child hierarchy (self-referencing FK via parent_org_id)
  - [x] Calculate `level` (depth in hierarchy: 1=Department, 2=Sub-Tier, 3=Office)
  - [x] SHA-256 change detection (`record_hash` column)
  - [x] `full_refresh()` - TRUNCATE + reload for periodic complete refreshes
- [x] `federal_organization` table enhanced with `record_hash`, `last_load_id`, and 3 new indexes
- [x] CLI commands (in `cli/fedhier.py`):
  - [x] `load-hierarchy` - full refresh or incremental load of federal hierarchy
  - [x] `search-agencies` - search organizations by name, code, or type in local DB
- [ ] Load all active organizations (requires API call)
- [ ] Cross-reference: link opportunity `department_name` / `office` to `federal_organization`

### Acceptance Criteria
- [x] `federal_organization` table schema supports complete active hierarchy
- [x] Parent-child relationships correctly represent org structure
- [x] Can navigate: Department -> Sub-tier -> Office (via level + parent_org_id)
- [x] Weekly/periodic refresh supported via `load-hierarchy` (incremental or --full-refresh)

---

## Iteration 5E: SAM.gov Exclusions API

**Priority**: Tier 2 (High Value)
**Purpose**: Due diligence on teaming partners and competitors
**Status**: COMPLETE (2026-02-28)

### Tasks
- [x] Implement `api_clients/sam_exclusions_client.py`
  - [x] `search_exclusions(**filters)` - paginated search
  - [x] `search_exclusions_all(**filters)` - auto-paginate all results
  - [x] `check_entity(uei)` - check single UEI for exclusions
  - [x] `check_entities(uei_list)` - batch check multiple UEIs
  - [x] `search_by_name(name)` - free-text name search
  - [x] Filter by UEI, name, agency, type, program
- [x] Implement `etl/exclusions_loader.py`
  - [x] `load_exclusions(exclusions_data)` - load exclusion records with change detection
  - [x] `full_refresh(client)` - reload all active exclusions
  - [x] `check_prospects()` - check prospect_team_member UEIs against exclusions
  - [x] `check_team_members()` - alias for check_prospects
  - [x] SHA-256 change detection via `record_hash` column
- [x] New table: `sam_exclusion` (in `tables/40_federal.sql`)
  - 20 columns including person name fields (first/middle/last/prefix/suffix)
  - 4 indexes: uei, entity_name, activation_date, exclusion_type
- [x] CLI commands (in `cli/exclusions.py`):
  - [x] `load-exclusions` - full refresh of exclusions data
  - [x] `check-exclusion` - check a specific UEI or entity name (API + local fallback)
  - [x] `check-prospects` - check all prospect team members against local exclusions
- [x] Registered in `main.py` (29 CLI commands total in 8 `cli/` modules)

### Acceptance Criteria
- [x] Can check any entity for exclusions via API or local DB
- [x] check-prospects flags excluded teaming partners from local data
- [x] load-exclusions populates local DB for offline checks

---

## Iteration 5F: FPDS ATOM Feed (Historical) -- DEPRECATED

**Priority**: ~~Tier 2 (High Value)~~ DEPRIORITIZED
**Purpose**: Deep historical procurement data (since 2004)
**Status**: DEPRECATED -- Do not implement

> **DEPRECATION NOTICE (Phase 7, 2026-02-28)**: FPDS.gov is being decommissioned:
> - **Feb 24, 2026**: ezSearch on FPDS.gov shut down
> - **Later FY2026**: ATOM feed (`https://www.fpds.gov/dbsight/FEEDS/ATOM`) will sunset entirely
> - **Replacement**: SAM.gov Contract Awards API at `https://api.sam.gov/contract-awards/v1/search` (already implemented in Iteration 5A)
>
> Building a new FPDS ATOM client is inadvisable. Use the SAM.gov Contract Awards API (5A) instead, which returns the same underlying FPDS data in JSON format with 80+ filter parameters and uses the same SAM.gov API key. The `SAM_CONTRACT_AWARDS_URL` setting has been added to `settings.py`.

### Tasks
- [x] ~~Implement `api_clients/fpds_client.py`~~ -- Not needed; use SAM Contract Awards API (5A)
- [x] ~~Implement `etl/fpds_loader.py`~~ -- Not needed; `awards_loader.py` handles this via 5A
- [x] ~~Load historical data for target NAICS codes~~ -- Use `load-awards` CLI command instead

### Acceptance Criteria
- [x] Historical awards loaded via SAM.gov Contract Awards API (Iteration 5A)
- [x] No duplicates with SAM Contract Awards data (single source now)
- [ ] Can analyze long-term trends in contract awards

---

## Iteration 5G: SAM.gov Subaward Reporting API

**Priority**: Tier 3 (Supplement)
**Purpose**: Subcontracting intelligence for teaming strategy
**Status**: COMPLETE (2026-02-28)

### Tasks
- [x] Implement `api_clients/sam_subaward_client.py`
  - [x] `search_subcontracts(**filters)` - paginated search (v1 API, page-based pagination)
  - [x] `search_subcontracts_all(**filters)` - auto-paginate generator with max_pages
  - [x] `search_by_prime(uei)` - prime contractor search
  - [x] `search_by_sub(uei)` - subcontractor search
  - [x] `search_by_naics(naics_code)` - NAICS-specific search
  - [x] `search_by_piid(piid)` - contract number search
  - [x] Filter by PIID, agency, date range, prime UEI, sub UEI, NAICS
- [x] Implement `etl/subaward_loader.py`
  - [x] `load_subawards(subawards_data)` - load with SHA-256 change detection
  - [x] `full_refresh(client)` - reload subawards by NAICS/agency
  - [x] `find_teaming_partners(naics_code, min_subs)` - local DB teaming analysis
  - [x] Composite key: `prime_piid|sub_uei|sub_date` for change detection
  - [x] NULL-safe comparison (`<=>`) in upsert WHERE clauses
- [x] New table: `sam_subaward` (in `tables/40_federal.sql`)
  - 22 columns including prime/sub entity info, amounts, business type
  - 6 indexes: prime_uei, sub_uei, naics, prime_piid, sub_date, record_hash
- [x] CLI commands (in `cli/subaward.py`):
  - [x] `load-subawards` - load subaward data from SAM.gov API (--naics, --agency, --prime-uei, --max-calls, --key)
  - [x] `search-subawards` - search local subaward data (--prime-uei, --sub-uei, --naics, --piid)
  - [x] `teaming-partners` - find potential teaming partners from subawards (--naics, --min-subs, --limit)
- [x] Registered in `main.py` (39 CLI commands total in 12 `cli/` modules)

### Acceptance Criteria
- [x] Subaward data loaded for recent years
- [x] Can identify potential teaming partners (primes who sub to small businesses)
- [x] Teaming analysis shows prime→sub relationships by NAICS code

---

## Implementation Order

These iterations can be worked in priority order or in parallel where rate limits allow:

```
5A: Contract Awards ──┐
5B: USASpending ──────┼── Can run in parallel (different APIs)
5C: CALC+ Rates ──────┤
5D: Federal Hierarchy ┘
5E: Exclusions ──────── After 5A-5D
5F: FPDS Historical ── After 5A (deduplicate)
5G: Subaward ────────── After 5E
```

---

## Shared Rate Limit Consideration

SAM.gov APIs (5A, 5D, 5E, 5G) share the same daily rate limit pool. With 10 calls/day:
- Allocate carefully across sources
- Use bulk extracts where available
- USASpending (5B) and CALC+ (5C) and FPDS ATOM (5F) have no rate limits - prioritize these for heavy loading

With 1,000 calls/day (with role):
- Ample budget for all sources
- Still track usage to avoid waste
