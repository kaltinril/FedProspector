# Phase 3: Opportunities Pipeline (Proof of Concept - Load First Data)

**Status**: COMPLETE (2026-02-28) - Historical load done, scheduled polling implemented in Phase 6
**Dependencies**: Phase 2 (Entity Pipeline) complete
**Deliverable**: Active opportunities loaded and filterable by WOSB/8(a) set-aside and NAICS code

---

## Tasks

### 3.1 SAM Opportunities API Client
- [x] Implement `api_clients/sam_opportunity_client.py`:
  - [x] `search_opportunities(posted_from, posted_to, **filters)` - paginated search
  - [x] `get_opportunity(notice_id)` - single opportunity lookup
  - [x] `get_wosb_opportunities(posted_from, posted_to, naics)` - WOSB convenience
  - [x] `get_8a_opportunities(posted_from, posted_to, naics)` - 8(a) convenience
  - [x] Handle `typeOfSetAside` single-value limitation (one set-aside per call)
  - [x] Handle date range limitation (max 1 year per request) - date range splitting implemented
  - [x] 5-call budget with priority set-aside ordering (WOSB, 8A, 8AN, EDWOSB, SBA)
- [ ] Write tests with mock API responses

### 3.2 Opportunity Loader
- [x] Implement `etl/opportunity_loader.py`:
  - [x] `load_from_api_response(api_data, load_id)` - transform and insert
  - [x] `_normalize_opportunity(raw_json)` - flatten API response
  - [x] `_upsert_opportunity(opp_data, load_id)` - insert/update with change detection
  - [x] Handle all set-aside codes (WOSB, EDWOSB, WOSBSS, EDWOSBSS, 8A, 8AN, SBA, SBP, HZC, HZS, SDVOSBC, SDVOSBS)
  - [x] Parse `resourceLinks` into JSON column
  - [x] Extract award information (amount, date, awardee UEI/name) when present
- [x] Implement change detection (SHA-256 record hashing on opportunity records)
- [x] Implement `opportunity_history` logging for changed fields (batch commits)

### 3.3 Historical Load
- [x] Load opportunities going back 2 years (COMPLETE):
  - [x] Break into 1-year chunks (API limitation) - date range splitting implemented (364-day max chunks)
  - [x] Load ALL set-aside types relevant to small business - all 12 types queried
  - [x] Initial load: 1 week of data (Feb 15-22, 2026): 57 opportunities across WOSB/EDWOSB/8A/8AN
  - [x] Full 2-year historical load completed 2026-02-28 using API key 2 (1,000/day tier)
    - 13,051 opportunities fetched across all 12 small business set-aside types
    - 12,209 unique opportunities loaded (deduplication across overlapping set-aside types)
    - 24 API calls used, ~22 seconds total
    - Date range: 03/01/2024 to 02/28/2026
    - Set-aside distribution (API totals): SBA=10,096, SDVOSBC=1,574, HZC=384, WOSB=211, 8A=152, 8AN=61, SBP=47, SDVOSBS=29, EDWOSB=29, WOSBSS=14, HZS=5, EDWOSBSS=3
    - 6 records errored due to `pop_state` > VARCHAR(2) -- column widened to VARCHAR(6) for ISO 3166-2 subdivision codes (e.g., IN-MH)
  - [ ] Also load non-set-aside opportunities for competitive analysis
- [ ] Verify data quality:
  - [ ] Check `naics_code` values resolve to `ref_naics_code`
  - [ ] Check `set_aside_code` values resolve to `ref_set_aside_type`
  - [ ] Spot-check 10 opportunities against SAM.gov website

### 3.4 WOSB/8(a) Filtered Views
- [x] Create/verify `v_target_opportunities` view works correctly
- [x] Test filtering:
  - [x] By set-aside code (WOSB, EDWOSB, 8A, 8AN)
  - [x] By NAICS code (specific target codes)
  - [x] By response deadline (show only still-open opportunities)
  - [x] By days until due (urgency ranking)
- [ ] Verify JOIN to `ref_naics_code` and `ref_sba_size_standard` provides enriched data
- [ ] Verify LEFT JOIN to `prospect` shows tracking status when available

### 3.5 Scheduled Polling
- [x] Implement 4-hour polling job in scheduler:
  - [x] Fetch opportunities posted since last successful load
  - [x] Detect new vs updated opportunities
  - [x] Log results in `etl_load_log`
- [x] Implement rate limit awareness:
  - [x] With 10/day limit: strategically choose which set-aside types to query
  - [x] With 1000/day limit: query all set-aside types individually
- [x] Handle edge cases:
  - [x] API downtime (retry next cycle)
  - [x] Duplicate records across queries
  - [x] Opportunities that change set-aside type

### 3.6 CLI Commands
- [x] Add `load-opportunities --days-back=N` command (also --max-calls, --historical, --set-aside)
- [x] Add `load-opportunities --set-aside=WOSB --naics=541511` command
- [x] Add `search --set-aside=WOSB --naics=541511 --open-only` command (also --days)
- [x] Show results with: title, deadline, days until due, set-aside, NAICS, tracking status

---

## Acceptance Criteria

1. `opportunity` table has 2+ years of historical data
2. `v_target_opportunities` view returns WOSB/8(a) opportunities with enriched data
3. 4-hour polling job runs and correctly identifies new/changed opportunities
4. `opportunity_history` tracks field-level changes (deadline extensions, award announcements)
5. CLI `search` command returns results within 2 seconds
6. Rate limits are respected (never exceeds daily quota)

---

## API Clarification

**API clarification**: SAM.gov has two Opportunity APIs:
- **Public API** (`/opportunities/v2/search`) — Read-only search. Requires public API key. Returns notices, POC data, set-aside info, award details. **This is what we use.**
- **Authenticated Management API** (`/prod/opportunity/v1/api/`) — Full CRUD with 26 endpoints including full description text, attachment downloads, Interested Vendor List, and revision history. Requires System Account with IP whitelisting. **Not available to us.**

The public API returns `pointOfContact` data (CO name, email, phone, title) which is captured starting in Phase 9 via the `contracting_officer` and `opportunity_poc` tables.

---

## API Call Budget Strategy

**With 10 calls/day (no role)**:
Each call returns up to 1,000 opportunities.
- Call 1: WOSB opportunities, last 24 hours
- Call 2: EDWOSB opportunities, last 24 hours
- Call 3: 8A opportunities, last 24 hours
- Call 4: 8AN opportunities, last 24 hours
- Call 5: SBA (total small business), last 24 hours
- Calls 6-10: Reserved for on-demand lookups

**With 1,000 calls/day (with role)**:
- Query each set-aside type separately every 4 hours (6 calls * 6 cycles = 36 calls)
- Use remaining calls for entity lookups and other sources
- Much more data per day

**Recommendation**: Prioritize getting a SAM.gov role assigned to increase from 10 to 1,000 calls/day.

---

## Data Mapping: API Response -> opportunity Table

| API Field | DB Column | Notes |
|-----------|-----------|-------|
| `noticeId` | `notice_id` | Primary key |
| `title` | `title` | |
| `solicitationNumber` | `solicitation_number` | |
| `department` | `department_name` | |
| `subTier` | `sub_tier` | |
| `office` | `office` | |
| `postedDate` | `posted_date` | Parse date |
| `responseDeadLine` | `response_deadline` | Parse datetime |
| `archiveDate` | `archive_date` | Parse date |
| `type` | `type` | Solicitation, Pre-solicitation, Award, etc. |
| `baseType` | `base_type` | |
| `typeOfSetAside` | `set_aside_code` | |
| `typeOfSetAsideDescription` | `set_aside_description` | |
| `classificationCode` | `classification_code` | PSC code |
| `naicsCode` | `naics_code` | 6-digit |
| `placeOfPerformance.state.code` | `pop_state` | |
| `placeOfPerformance.zip` | `pop_zip` | |
| `placeOfPerformance.country.code` | `pop_country` | |
| `placeOfPerformance.city.name` | `pop_city` | |
| `active` | `active` | Y/N |
| `award.number` | `award_number` | |
| `award.date` | `award_date` | |
| `award.amount` | `award_amount` | |
| `award.awardee.ueiSAM` | `awardee_uei` | |
| `award.awardee.name` | `awardee_name` | |
| `description` | `description` | May be URL requiring API key |
| `uiLink` | `link` | |
| `resourceLinks` | `resource_links` | JSON array |
| `officeAddress.officeId` | `contracting_office_id` | |

> **Not currently captured**: The API also returns a `pointOfContact` array containing contact objects with `type`, `fullName`, `title`, `email`, `phone`, `fax`, and `additionalInfo` fields. This data is not captured by the current ETL pipeline. Starting in Phase 9, these contacts will be stored in the `contracting_officer` and `opportunity_poc` tables (see `thesolution/14-PHASE9-SCHEMA-EVOLUTION.md`).

---

## Data Loaded

### Initial Load (2026-02-22)
- 57 opportunities loaded (WOSB=19, 8A=26, 8AN=10, EDWOSB=2)
- 4 API calls used of 5 budgeted (1 spare)
- Date range: last 7 days (Feb 15-22, 2026)

### Full Historical Load (2026-02-28)
- 12,209 unique opportunities loaded into database
- 13,051 total fetched across all 12 small business set-aside types (some overlap)
- 24 API calls used, ~22 seconds total
- Date range: 03/01/2024 to 02/28/2026 (2 full years)
- API key 2 (1,000/day tier)
- Set-aside distribution (API totals):
  - SBA (Total Small Business): 10,096
  - SDVOSBC (Service-Disabled Veteran-Owned Small Business): 1,574
  - HZC (HUBZone): 384
  - WOSB (Women-Owned Small Business): 211
  - 8A (8(a) Competed): 152
  - 8AN (8(a) Sole Source): 61
  - SBP (Small Business): 47
  - SDVOSBS (SDVOSB Sole Source): 29
  - EDWOSB (Economically Disadvantaged WOSB): 29
  - WOSBSS (WOSB Sole Source): 14
  - HZS (HUBZone Sole Source): 5
  - EDWOSBSS (EDWOSB Sole Source): 3

---

## Known Issues

1. `fullParentPathName` parsing implemented for department/sub_tier/office - API returns dot-separated hierarchy (e.g., "DEPT OF DEFENSE.DEPT OF THE ARMY.W6QK ACC-APG NATICK"), not separate fields
2. `description` field is a URL, not the actual text (requires separate API call with key to fetch the description content)
3. `placeOfPerformance` is often NULL in API responses
4. Some `responseDeadLine` values are date-only (no time component), handled gracefully
5. SAM.gov API rejects date ranges of exactly 365 days -- fixed by using 364-day max chunks
6. Leap year start dates (Feb 29) also rejected by API -- historical load avoids Feb 29 start
7. `pop_state` widened from VARCHAR(2) to VARCHAR(6) -- some opportunities use ISO 3166-2 subdivision codes (e.g., IN-MH for India-Maharashtra) instead of 2-letter US state codes (6 records in historical load)
8. Empty `award_amount` strings cause parse warnings (harmless, already handled)

---

## Pending Items

- ~~Historical load~~ DONE (2026-02-28)
- Non-set-aside opportunities for competitive analysis
- Data quality verification (NAICS/set-aside code validation against ref tables)
- ~~Scheduled polling~~ DONE (Phase 6 - `run-job opportunities`)
- Unit tests for opportunity_loader and sam_opportunity_client
- Daily incremental load testing
