# Phase 3: Opportunities Pipeline (Proof of Concept - Load First Data)

**Status**: In Progress - Core pipeline complete, initial data loaded
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
- [~] Load opportunities going back 2 years (PARTIALLY DONE):
  - [x] Break into 1-year chunks (API limitation) - date range splitting implemented
  - [x] Load ALL set-aside types relevant to small business - priority ordering implemented
  - [x] Initial load: 1 week of data (Feb 15-22, 2026): 57 opportunities across WOSB/EDWOSB/8A/8AN
  - [ ] Full 2-year historical load pending rate limit upgrade to 1,000/day
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
- [ ] Implement 4-hour polling job in scheduler:
  - [ ] Fetch opportunities posted since last successful load
  - [ ] Detect new vs updated opportunities
  - [ ] Log results in `etl_load_log`
- [ ] Implement rate limit awareness:
  - [ ] With 10/day limit: strategically choose which set-aside types to query
  - [ ] With 1000/day limit: query all set-aside types individually
- [ ] Handle edge cases:
  - [ ] API downtime (retry next cycle)
  - [ ] Duplicate records across queries
  - [ ] Opportunities that change set-aside type

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

---

## Data Loaded (2026-02-22)

- 57 opportunities loaded (WOSB=19, 8A=26, 8AN=10, EDWOSB=2)
- 4 API calls used of 5 budgeted (1 spare)
- Date range: last 7 days (Feb 15-22, 2026)
- Full historical load (2 years) pending rate limit upgrade to 1,000/day

---

## Known Issues

1. `fullParentPathName` parsing implemented for department/sub_tier/office - API returns dot-separated hierarchy (e.g., "DEPT OF DEFENSE.DEPT OF THE ARMY.W6QK ACC-APG NATICK"), not separate fields
2. `description` field is a URL, not the actual text (requires separate API call with key to fetch the description content)
3. `placeOfPerformance` is often NULL in API responses
4. Some `responseDeadLine` values are date-only (no time component), handled gracefully

---

## Pending Items

- Historical load (requires 1,000/day rate limit - need ~24 API calls for 2 years x 12 set-aside types)
- Scheduled polling (Phase 6)
- Unit tests for opportunity_loader and sam_opportunity_client
- Daily incremental load testing
