# Phase 5: Extended Data Sources

**Status**: In Progress (2026-02-22) - 5B (USASpending) and 5C (GSA CALC+) complete
**Dependencies**: Phase 3 (Opportunities Pipeline) complete
**Deliverable**: Comprehensive data from all priority sources loaded and cross-referenced

---

## Overview

Phase 5 adds 7 additional data sources beyond the core Entity + Opportunities pipelines. Each is a self-contained iteration that can be implemented independently. The order below reflects priority ranking from [01-RESEARCH-AND-DATA-SOURCES.md](01-RESEARCH-AND-DATA-SOURCES.md).

---

## Iteration 5A: SAM.gov Contract Awards API

**Priority**: Tier 2 (High Value)
**Purpose**: Historical award data for competitive intelligence

### Tasks
- [ ] Implement `api_clients/sam_awards_client.py`
  - [ ] `search_awards(**filters)` - paginated search
  - [ ] `get_award(contract_id)` - single award lookup
  - [ ] Support 80+ filter parameters
  - [ ] Handle sync mode (max 100/page, 400K total) and extract mode (up to 1M)
- [ ] Implement `etl/awards_loader.py`
  - [ ] Transform API response -> `fpds_contract` table
  - [ ] Map WOSB/8(a) business type fields
  - [ ] Handle modifications (same contract_id, different modification_number)
- [ ] Load historical awards:
  - [ ] Focus on target NAICS codes, past 5 years
  - [ ] Focus on WOSB/8(a) set-aside awards
- [ ] Cross-reference: link awardee UEI to `entity` table
- [ ] Build competitor analysis:
  - [ ] Who wins contracts in our NAICS codes?
  - [ ] What are the typical dollar values?
  - [ ] Which agencies award the most?

### Acceptance Criteria
- [ ] `fpds_contract` table has 5 years of relevant award data
- [ ] `v_competitor_analysis` view returns meaningful results
- [ ] Can answer: "Who won the most WOSB IT contracts last year?"

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
  - [x] `usaspending_award` table created in MySQL (`db/schema/08_usaspending_tables.sql`)
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
- CLI command for USASpending loads (currently API-only)

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
- [x] Load all ~52K labor rate records
- [x] Implement monthly refresh (full reload via `load-calc` CLI command)
- [ ] Build pricing analysis queries:
  - [ ] Average rates by labor category
  - [ ] Rate ranges for specific SINs
  - [ ] Small business vs large business rate comparison

### Acceptance Criteria
- [x] `gsa_labor_rate` table has ~52K records
- [x] Monthly refresh job works (`python main.py load-calc`)
- [ ] Can query: "What's the average rate for 'Senior Software Developer' from small businesses?"

---

## Iteration 5D: SAM.gov Federal Hierarchy

**Priority**: Tier 1 (Essential)
**Purpose**: Agency organizational structure for targeting

### Tasks
- [ ] Implement `api_clients/sam_fedhier_client.py`
  - [ ] `get_all_organizations(status='Active')` - paginated full load
  - [ ] `get_organization(fh_org_id)` - single org lookup
  - [ ] `search_organizations(**filters)` - filtered search
  - [ ] Handle hierarchical parent-child relationships
- [ ] Implement `etl/fedhier_loader.py`
  - [ ] Transform API response -> `federal_organization` table
  - [ ] Build parent-child hierarchy (self-referencing FK)
  - [ ] Calculate `level` (depth in hierarchy)
- [ ] Load all active organizations
- [ ] Implement weekly refresh
- [ ] Cross-reference: link opportunity `department_name` / `office` to `federal_organization`

### Acceptance Criteria
- [ ] `federal_organization` table has complete active hierarchy
- [ ] Parent-child relationships correctly represent org structure
- [ ] Can navigate: Department -> Sub-tier -> Office
- [ ] Weekly refresh updates changes

---

## Iteration 5E: SAM.gov Exclusions API

**Priority**: Tier 2 (High Value)
**Purpose**: Due diligence on teaming partners and competitors

### Tasks
- [ ] Implement `api_clients/sam_exclusions_client.py`
  - [ ] `search_exclusions(**filters)` - paginated search
  - [ ] Filter by UEI, name, agency, type
- [ ] Implement exclusions loader (could be separate table or flag on entity)
- [ ] Implement weekly exclusion check:
  - [ ] Check all entities in `prospect_team_member` against exclusions
  - [ ] Flag any excluded entities
- [ ] Build due diligence query:
  - [ ] `check-exclusion --uei` CLI command
  - [ ] Show exclusion details if found

### Acceptance Criteria
- [ ] Can check any entity for exclusions
- [ ] Weekly check flags excluded teaming partners
- [ ] Alert mechanism when a watched entity becomes excluded

---

## Iteration 5F: FPDS ATOM Feed (Historical)

**Priority**: Tier 2 (High Value)
**Purpose**: Deep historical procurement data (since 2004)

> **Note**: FPDS.gov has announced plans to migrate award data to SAM.gov. The SAM.gov Contract Awards API (Iteration 5A) may eventually replace FPDS as the primary historical awards source. Implement 5A first and evaluate FPDS data gaps before investing in FPDS ATOM parsing.

### Tasks
- [ ] Implement `api_clients/fpds_client.py`
  - [ ] Parse ATOM XML feed responses
  - [ ] Build query strings for FPDS search syntax
  - [ ] Handle pagination (10 records/thread, 10 threads/search)
  - [ ] No auth required, no daily limit
- [ ] Implement `etl/fpds_loader.py`
  - [ ] Map ATOM XML fields to `fpds_contract` table
  - [ ] Handle FPDS-specific fields not in SAM Contract Awards API
  - [ ] Deduplicate with data already loaded from SAM Contract Awards (5A)
- [ ] Load historical data for target NAICS codes
- [ ] Implement weekly refresh for recent modifications

### Acceptance Criteria
- [ ] Historical awards back to 2015+ loaded for target NAICS codes
- [ ] No duplicates with SAM Contract Awards data
- [ ] Can analyze long-term trends in contract awards

---

## Iteration 5G: SAM.gov Subaward Reporting API

**Priority**: Tier 3 (Supplement)
**Purpose**: Subcontracting intelligence for teaming strategy

### Tasks
- [ ] Implement `api_clients/sam_subaward_client.py`
  - [ ] `search_subcontracts(**filters)` - paginated search
  - [ ] Filter by PIID, agency, date range
- [ ] Implement loader for subaward data
- [ ] Load recent subcontract data (2-3 years)
- [ ] Build teaming analysis:
  - [ ] Which large primes subcontract to small businesses?
  - [ ] Which primes work in our NAICS codes?
  - [ ] What are typical subcontract values?

### Acceptance Criteria
- [ ] Subaward data loaded for recent years
- [ ] Can identify potential teaming partners (primes who sub to small businesses)

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
