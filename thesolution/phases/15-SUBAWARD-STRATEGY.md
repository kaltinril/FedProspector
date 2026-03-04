# Phase 15 — Subaward Data Strategy

## Status: COMPLETE (2026-03-04) — P0-P2 implemented, P3 handled by existing hash detection, P4 deferred

---

## Context

The subaward loader (`load subawards`) currently uses the SAM.gov Acquisition Subaward Reporting API with page-based pagination. An unfiltered load returns **2.69 million records** across 2,692 pages — consuming the full 1,000/day API key budget for nearly 3 days. The CLI lacks parity with the awards loader (no multi-NAICS, no date filtering, no resume).

This phase documents research findings, evaluates data source alternatives, and plans improvements to make subaward loading practical for prospecting use cases.

---

## 1. What Subawards Are

A **subaward** (subcontract) is when a prime contractor hires a smaller company to perform part of the work on a federal contract. Primes are legally required to report first-tier subcontracts to SAM.gov under FFATA (FAR 52.204-10).

### Reporting Rules

| Rule | Detail |
|------|--------|
| **Threshold** | $40,000+ (raised from $30,000 effective Oct 1, 2025 per FAR 4.1403(a)) |
| **Scope** | First-tier only — sub-to-sub chains are NOT captured |
| **Deadline** | End of month following the month the subaward was made |
| **Exemption** | Prime or sub had gross income < $300K in prior tax year |
| **Grants** | $30,000 threshold (2 CFR Part 170), separate API |

### How Subawards Link to Other Tables

```
opportunity → fpds_contract → sam_subaward
               (PIID)          (prime_piid)
               (vendor_uei)    (prime_uei)
                                (sub_uei) → entity
```

| From | Field | To | Field |
|------|-------|----|-------|
| `sam_subaward` | `prime_piid` | `fpds_contract` | `contract_id` |
| `sam_subaward` | `prime_uei` | `entity` | `uei_sam` |
| `sam_subaward` | `sub_uei` | `entity` | `uei_sam` |

---

## 2. Prospecting Use Cases

| Use Case | Description | Who Needs It |
|----------|-------------|--------------|
| **Teaming partner discovery** | Which primes sub out work in my NAICS codes? | WOSB/8(a) firms seeking prime partners |
| **Incumbent sub analysis** | Who currently holds sub positions on target contracts? | Any bidder planning a team |
| **Relationship mapping** | Build prime↔sub relationship graphs over time | Business development |
| **Competitive intelligence** | What's my competitor's sub team and dollar volume? | Capture managers |
| **Recompete intelligence** | Which contracts are up for recompete, who are current subs? | Pipeline builders |
| **Set-aside compliance** | Is this prime meeting small business subcontracting goals? | Small businesses evaluating primes |
| **Pricing intelligence** | Sub amounts reveal what primes pay for specific work scopes | Proposal pricing |

None of these require all 2.7M subawards. They work with **targeted pulls by NAICS, agency, or prime/sub UEI**.

---

## 3. Data Sources Comparison

### Source A: SAM.gov Acquisition Subaward API (Current)

- **Endpoint**: `GET /prod/contract/v1/subcontracts/search`
- **Auth**: API key (query param `api_key`)
- **Rate limits**: 10/day (personal, no entity role), 1,000/day (entity role or system account), 10,000/day (federal system account)
- **Max page size**: 1,000 records
- **Data freshness**: Near real-time (as soon as prime reports)

**Supported query filters** (validated against [GSA docs](https://open.gsa.gov/api/acquisition-subaward-reporting-api/) and OpenAPI spec, 2026-03-04):

| Filter | Param Name | Actually Works? | Status in Our Code |
|--------|------------|-----------------|-------------------|
| PIID | `PIID` | **YES** | In client, NOT in CLI |
| Agency (4-digit) | `agencyId` | **YES** | In client + CLI |
| From/To Date | `fromDate`, `toDate` | **YES** | In client, NOT in CLI |
| Prime Award Type | `primeAwardType` | **YES** | NOT implemented |
| Prime Contract Key | `primeContractKey` | **YES** | NOT implemented |
| Referenced IDV PIID | `referencedIdvPIID` | **YES** | NOT implemented |
| Referenced IDV Agency | `referencedIDVAgencyID` | **YES** | NOT implemented |
| Status | `status` | **YES** | Hardcoded "Published" |
| **NAICS** | `primeNaics` | **NO — silently ignored** | In client + CLI (**BUG**) |
| **Prime UEI** | `primeEntityUei` | **NO — silently ignored** | In client + CLI (**BUG**) |
| **Sub UEI** | `subEntityUei` | **NO — silently ignored** | In client (**BUG**) |

**CRITICAL FINDING**: `primeNaics`, `primeEntityUei`, and `subEntityUei` are **response fields**, not query parameters. The API silently ignores them and returns unfiltered results. Our client sends them as query params, giving the false impression that server-side filtering is happening. Verified by comparing filtered vs unfiltered `totalRecords` counts — they are identical.

### NAICS Filtering Strategy: PIID-Driven Lookup

Since the subaward API does not support NAICS filtering, the correct approach is:

1. **Query local `fpds_contract` table** for PIIDs matching the target NAICS code(s)
2. **Call the subaward API once per PIID** — each call returns only subawards for that specific prime contract
3. **Combine with `--years-back`** to limit to recent contracts via `date_signed`

This is practical because PIID counts per NAICS are small (validated against local DB, 2026-03-04):

| NAICS | Distinct PIIDs (all time) | With 2-year lookback |
|-------|--------------------------|---------------------|
| 541611 | 161 | 129 |
| 541519 | 102 | 72 |
| 541330 | 82 | 67 |
| 541511 | 55 | 47 |
| 541512 | 40 | 27 |

Even the largest (541611) needs only 129 API calls with a 2-year window — well within the 1,000/day budget on key 2. The API only supports single-value PIID queries (no batch/multi-value), but the small counts make this viable.

**Pros**: Real-time data, direct from source, JSON format
**Cons**: Rate-limited, expensive for bulk loads, 2.7M+ total records unfiltered

### Source B: USASpending.gov Bulk Download (Alternative)

- **URL**: https://www.usaspending.gov/download_center/custom_award_data
- **Auth**: None required
- **Rate limits**: None (bulk CSV download)
- **Format**: CSV/TSV/pipe-delimited, zipped
- **Limit**: 500,000 records per download (can use Award Data Archive for full agency dumps)
- **Data freshness**: Nightly from DATA Act Broker, but subaward data has ~30-60 day lag

**Available filters** (via download UI or API):
- Agency / Sub-Agency
- Date range (action_date or last_modified_date)
- NAICS (for procurement subawards)
- Award type
- Place of performance
- Recipient location
- Keyword search

**CSV fields** (File F — Subaward Attributes):
- Subaward: `subaward_number`, `subaward_amount`, `subaward_action_date`, `subaward_description`
- Prime linkage: `prime_award_piid`, `prime_award_amount`, `prime_awardee_uei`, `prime_awardee_name`
- Sub entity: `sub_awardee_uei`, `sub_awardee_name`, `sub_awardee_parent_uei`
- Agency: `awarding_agency_code`, `awarding_agency_name`, `funding_agency_code`
- Location: `sub_awardee_address`, `place_of_performance` (city, state, ZIP, congressional district)
- Classification: NAICS code, `contracting_office_code`, `referenced_idv_piid`

**Pros**: Free, no rate limits, NAICS filtering, large bulk loads, enriched data
**Cons**: 30-60 day lag, 500K record limit per download, CSV parsing needed

### Source C: USASpending.gov API (Hybrid)

- **Endpoint**: `POST /api/v2/search/spending_by_award/` (paginated search)
- **Bulk download**: `POST /api/v2/bulk_download/awards/` (async ZIP generation)
- **Auth**: None required
- **Rate limits**: Generous (no hard daily cap documented)
- **Format**: JSON (search) or CSV (bulk download)

**Pros**: Combines API flexibility with no rate limits
**Cons**: Different field names from SAM.gov, would need new client/loader

---

## 4. Data Quality Warnings

Per GAO-24-106237 (Federal Spending Transparency, 2024):

| Issue | Detail |
|-------|--------|
| **Duplicates** | 26% of grant subawards, 11% of contract subawards likely duplicates |
| **Missing fields** | Significant gaps in required data elements |
| **Self-reported** | No independent verification of subaward amounts or details |
| **First-tier only** | Sub-sub chains invisible — actual subcontracting landscape is deeper |
| **Reporting lag** | 30-60 days between subaward and data availability |
| **$40K threshold** | Subawards under $40K (contracts) or $30K (grants) not reported |

### How GovCon Competitors Handle This

| Tool | Approach |
|------|----------|
| **HigherGov** | Actively de-duplicates "a significant percentage" of reported subcontracts |
| **GovTribe** | Avoids aggregate subaward searching entirely due to quality concerns; only shows vendor-level and prime-award-level detail |
| **GovWin (Deltek)** | Adds analyst enrichment on top of raw data |
| **GovSpend** | Cross-references eSRS (subcontracting plan goals) with FFATA actual data |

**Recommendation**: Add a data quality rule in `etl_data_quality_rule` for subaward duplicate detection (same prime_piid + sub_uei + sub_amount + sub_date = likely duplicate).

---

## 5. Current State vs. Desired State

### CLI Options Gap

| Feature | Awards CLI | Subawards CLI | Needed? |
|---------|-----------|--------------|---------|
| Multi-NAICS (comma-separated) | Yes | No | **YES** |
| `--years-back` / date filtering | Yes (`--fiscal-year`, `--years-back`) | No (API supports it) | **YES** |
| `--sub-uei` (search by subcontractor) | N/A | No (API supports it) | **YES** |
| `--piid` (search by prime contract) | Yes | No (API supports it) | YES |
| Page-by-page processing + DB commit | Yes (Phase 14.26) | No (collects all in memory) | **YES** |
| Resume from last page | Yes (Phase 14.26) | No | **YES** |
| Multi-NAICS budget tracking | Yes | No | Nice to have |
| `--set-aside` filter | Yes | No (API doesn't support it) | Can't add |
| Minimum filter requirement | Yes (at least 1 filter required) | No (allows unfiltered load) | **YES** — prevent 2.7M unfiltered loads |

### Loader Logic Gap

| Feature | Awards Loader | Subawards Loader |
|---------|---------------|------------------|
| Page-by-page DB commit | Yes | No (collects all, then loads) |
| Ctrl+C graceful handling | Yes | No (loses all fetched data) |
| Resume from checkpoint | Yes | No |
| Load type | HISTORICAL | FULL |
| Memory usage | O(page_size) | O(total_records) — 2.7M records in memory |

---

## 6. Recommended Changes

### Priority 0: Fix Broken API Params (CRITICAL)

Remove silently-ignored query params from `fed_prospector/api_clients/sam_subaward_client.py`:

1. **Remove `primeNaics`** from `search_subcontracts()` and `_build_params()` — not a valid API filter
2. **Remove `primeEntityUei`** from both methods — not a valid API filter
3. **Remove `subEntityUei`** from both methods — not a valid API filter
4. **Remove `search_by_naics()`** convenience method — fundamentally broken (server ignores param)
5. **Remove `search_by_prime()`** and **`search_by_sub()`** — rely on broken UEI params
6. Remove `naics_code`, `prime_uei`, `sub_uei` args from method signatures (or repurpose for client-side filtering)
7. Update docstrings to document only the params that actually work

### Priority 1: CLI Parity + PIID-Driven NAICS Loading (HIGH)

Add missing CLI options to `fed_prospector/cli/subaward.py`:

1. **`--years-back N`** — compute `from_date = today - N years`, pass to API's `fromDate` (which actually works)
2. **`--naics` multi-value** — comma-separated; triggers PIID-driven strategy:
   - Query `fpds_contract` for PIIDs matching the NAICS code(s) + optional date window
   - Call subaward API once per PIID using the `PIID` param (which actually works)
   - Log the number of PIIDs found and API calls needed
3. **`--piid`** — expose existing client parameter (direct API param, works)
4. **Require at least one filter** — prevent unfiltered 2.7M loads with a validation check
5. **Remove `--prime-uei`** from CLI — API doesn't support it as a filter

### Priority 2: Page-by-Page Processing + Resume (HIGH)

Apply the Phase 14.26 pattern to subaward loading:

1. Process and commit each page to DB immediately (not collect-then-load)
2. Save page checkpoint to `etl_load_log.parameters` after each page
3. On resume, query last checkpoint and start from next page
4. Handle `KeyboardInterrupt` gracefully — commit current page, log resume point

Files to modify:
- `fed_prospector/cli/subaward.py` — restructure load loop
- `fed_prospector/etl/subaward_loader.py` — add `load_subaward_batch()` for per-page processing

### Priority 3: Data Quality Rule (MEDIUM)

Add duplicate detection rule to `etl_data_quality_rule`:
- Rule: Flag records where `prime_piid + sub_uei + sub_amount + sub_date` matches an existing record
- Action: Skip or merge (keep most recent)

### Priority 4: USASpending Bulk Source (LOW — Future)

Consider adding a USASpending bulk download path for initial data seeding:
- Download subaward CSV from USASpending for target NAICS codes (free, no rate limits)
- Use SAM.gov API only for incremental updates (new subawards since last load)
- This hybrid approach gets the best of both sources

This is NOT blocking for V1 — the SAM.gov API with proper filtering is sufficient for targeted prospecting loads.

---

## 7. Smart Loading Strategy

### The Problem

The subaward API has 2.7M records but **no NAICS filter**. The `--naics` param we send (`primeNaics`) is silently ignored — the API returns ALL records regardless. Loading everything wastes API budget, time, and storage on irrelevant data.

### The Solution: PIID-Driven Loading

Instead of asking the subaward API "give me subawards for NAICS 541511" (which it can't do), we flip the approach:

1. **Ask our local database**: "What prime contracts exist for NAICS 541511?" → returns a list of PIIDs
2. **Ask the subaward API per PIID**: "Give me subawards for PIID X" → returns only relevant subawards
3. **Combine with date filtering**: `--years-back 2` limits both the PIID lookup and API `fromDate`

```
User runs:  python main.py load subawards --naics 541511,541611 --years-back 2

Step 0:  Parse comma-separated NAICS (same pattern as awards CLI):
         naics_codes = [c.strip() for c in naics.split(',') if c.strip()]
         → ['541511', '541611']

Step 1:  SELECT DISTINCT idv_piid FROM fpds_contract
         WHERE naics_code IN ('541511', '541611')
           AND date_signed >= '2024-03-04'
         → 176 PIIDs (47 + 129, deduplicated)

Step 2:  For each PIID, call:
         GET /prod/contract/v1/subcontracts/search?PIID=<piid>&fromDate=2024-03-04
         → 176 API calls, each returning 0-20 subawards

Step 3:  Load results into sam_subaward with change detection

Result:  ~400-800 relevant subaward records loaded in 176 API calls
         vs. 2,700+ API calls to page through all 2.7M records unfiltered
```

### Why This Works

- **PIID is a supported filter** — the API actually respects it
- **PIID counts are small** — 47-161 per NAICS with a 2-year window (see table in Section 3)
- **Each call returns a focused result set** — subawards for one specific prime contract
- **Date filtering works too** — `fromDate`/`toDate` are supported API params
- **Requires `fpds_contract` data** — must load awards first (`python main.py load awards --naics 541511`)

### Fallback: No Local Award Data

If `fpds_contract` has no PIIDs for the requested NAICS (awards not yet loaded):
- Warn the user: "No awards found for NAICS 541511 in local DB. Load awards first."
- Suggest: `python main.py load awards --naics 541511 --years-back 2`
- Do NOT fall back to unfiltered loading

### Files to Modify

| File | Change |
|------|--------|
| `fed_prospector/api_clients/sam_subaward_client.py` | Remove broken `primeNaics`/`primeEntityUei`/`subEntityUei` params; remove `search_by_naics`/`search_by_prime`/`search_by_sub` methods |
| `fed_prospector/cli/subaward.py` | Add `--years-back`, `--piid`, multi-NAICS with PIID-driven strategy, filter validation, page-by-page processing |
| `fed_prospector/etl/subaward_loader.py` | Add `load_subaward_batch()` for per-page processing; add PIID lookup helper |
| `fed_prospector/db/schema/tables/40_federal.sql` | Add duplicate detection index if needed |
| `thesolution/reference/09-SAM-API-QUIRKS.md` | Document that NAICS/UEI are not valid subaward API filters |

---

## 8. Verification

```bash
# Prerequisites: load awards for target NAICS first
python main.py load awards --naics 541611,541512 --years-back 3

# PIID-driven subaward load (queries local fpds_contract for PIIDs, then fetches per-PIID)
python main.py load subawards --naics 541611,541512 --years-back 3 --max-calls 200
# Expected output:
#   Found 156 PIIDs for NAICS 541611,541512 (2-year lookback)
#   Fetching subawards for PIID 1/156: W91QVN-20-C-0001 ...
#   ...
#   Loaded 423 subaward records in 156 API calls

# Direct PIID load (no local lookup needed)
python main.py load subawards --piid W91QVN-20-C-0001

# Agency + date filter (uses supported API params directly)
python main.py load subawards --agency 9700 --years-back 2 --max-calls 50

# Verify filter required (should error)
python main.py load subawards --max-calls 5
# Expected: "ERROR: At least one filter required (--naics, --agency, or --piid)"

# Verify NAICS without local awards data (should warn)
python main.py load subawards --naics 999999
# Expected: "No awards found for NAICS 999999 in local DB. Load awards first."

# Resume test: start load, Ctrl+C, re-run same command
python main.py load subawards --naics 541611 --max-calls 200
# (Ctrl+C at PIID 50)
python main.py load subawards --naics 541611 --max-calls 200
# Expected: "Resuming from PIID 51/156 (load_id=XX)"
```

---

## Sources

- [USASpending Download Center](https://www.usaspending.gov/download_center/custom_award_data)
- [SAM.gov Acquisition Subaward API](https://open.gsa.gov/api/acquisition-subaward-reporting-api/)
- [SAM.gov Assistance Subaward API](https://open.gsa.gov/api/assistance-subaward-reporting-api/)
- [FSRS to SAM.gov Transition](https://www.federalfiling.com/fsrs-to-sam-transition/)
- [GAO-24-106237: Subaward Data Quality](https://www.gao.gov/products/gao-24-106237)
- [FAR 52.204-10: Subaward Reporting](https://www.acquisition.gov/far/52.204-10)
- [FAR Threshold Changes Oct 2025](https://www.acquisition.gov/threshold-changes)
- [GovTribe: Subcontract Data](https://docs.govtribe.com/user-guide/use-cases/research-subcontract-award-data)
- [HigherGov: Subcontracts](https://docs.highergov.com/find-opportunities/federal-subcontracts-and-subgrants)
- [GovSpend: Federal Subcontracting](https://govspend.com/blog/federal-subcontracting-data-what-it-tells-us-and-how-to-use-it/)
- [USASpending Data Sources (PDF)](https://www.usaspending.gov/data/data-sources-download.pdf)
