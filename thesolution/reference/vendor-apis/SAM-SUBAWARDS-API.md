# SAM.gov Acquisition Subaward Reporting API v1

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/prod/contract/v1/subcontracts/search` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (personal, no role), 1,000/day (personal with role or system account) |
| **Pagination** | `pageNumber`/`pageSize` -- pageNumber starts at 0, max pageSize 1,000 |
| **Data Format** | JSON |
| **Update Frequency** | Monthly targeted loads recommended; ~20 calls/month budget |
| **Our CLI Command** | `python main.py load subawards` |
| **Client File** | `fed_prospector/api_clients/sam_subaward_client.py` |
| **Loader File** | `fed_prospector/etl/subaward_loader.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/subawardreportingpublicapi.yaml` |

## Purpose & Prospecting Value

The Acquisition Subaward Reporting API provides access to first-tier subcontract data reported by prime contractors under FFATA (FAR 52.204-10). Prime contractors must report subcontracts of $40,000+ (raised from $30,000 effective Oct 1, 2025) to SAM.gov by the end of the month following the month the subaward was made.

For WOSB/8(a) prospecting, subaward data is one of the most valuable intelligence sources. It reveals **which large prime contractors actively subcontract work to small businesses**, making it possible to identify potential teaming partners before an opportunity is even posted. If a prime has historically subcontracted IT work to small 8(a) firms, they are likely to do so again on their next recompete.

Specific use cases include: (1) **Teaming partner discovery** -- find primes who sub out work in your NAICS codes; (2) **Incumbent sub analysis** -- who currently holds sub positions on target contracts; (3) **Competitive intelligence** -- what is your competitor's sub team and dollar volume; (4) **Pricing intelligence** -- sub amounts reveal what primes pay for specific work scopes; (5) **Recompete intelligence** -- which contracts are up for recompete and who are the current subs; (6) **Set-aside compliance** -- verify whether primes are meeting small business subcontracting goals.

None of these use cases require all 2.7 million subaward records in the system. They work with targeted pulls by PIID, agency, or date range, combined with local NAICS-based PIID lookups.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `piid` | string | `W91QVN-20-C-0001` | Prime contract Procurement Instrument Identifier. **Most reliable filter.** Note: param name is lowercase; uppercase `PIID` is silently ignored. |
| `agencyId` | string | `9700` | Four-digit contracting agency code |
| `fromDate` | string | `2024-03-04` | Start date (yyyy-MM-dd format) |
| `toDate` | string | `2026-03-04` | End date (yyyy-MM-dd format) |
| `primeAwardType` | string | | Type of prime award |
| `status` | string | `Published` | Record status: Published or Deleted. Default: Published |
| `uniqueAwardKey` | string | | Unique award key identifier |
| `referencedIDVPIID` | string | | Referenced IDV PIID |
| `referencedIDVAgencyId` | string | | Referenced IDV agency |
| `agencyCode` | string | | Alternative agency code parameter |

### Broken/Ignored Filters (CRITICAL)

| Parameter | Status | Notes |
|-----------|--------|-------|
| `primeNaics` | **SILENTLY IGNORED** | The API accepts this param without error but returns unfiltered results. Verified by comparing `totalRecords` with and without the param -- counts are identical. This is a **response field**, not a query parameter. |
| `primeEntityUei` | **SILENTLY IGNORED** | Same behavior. The API does not filter by prime UEI despite accepting the parameter. This is a response field, not a filter. |
| `subEntityUei` | **SILENTLY IGNORED** | Same behavior. Cannot filter by subcontractor UEI. This is a response field, not a filter. |

**How we discovered this**: Our client was sending `primeNaics`, `primeEntityUei`, and `subEntityUei` as query parameters. The API returned `200 OK` with no errors but returned the same `totalRecords` count regardless of the parameter values. Comparing filtered vs unfiltered requests confirmed the API ignores these parameters entirely.

**Impact**: Any code that sends these parameters and assumes server-side filtering is getting **all records** back, not filtered results. The `search_by_naics()`, `search_by_prime()`, and `search_by_sub()` convenience methods and their corresponding broken params have been **removed** in Phase 15.

### Pagination

The Subaward API uses standard page-based pagination:

- `pageNumber` starts at **0** (0-indexed)
- `pageSize` maximum is **1,000** records per page
- Our client defaults to `pageSize=100` for budget control
- Response includes `totalPages` and `totalRecords` for calculating remaining pages
- Response also includes `nextPageLink` and `previousPageLink` URLs

Bulk pagination stats:
- 2.69 million total records / 1,000 per page = 2,692 pages
- At 1,000 calls/day, a full unfiltered load takes **3 days** of API budget

### Date Filtering

Unlike the Awards API (which uses `[MM/DD/YYYY,MM/DD/YYYY]` bracket format), the Subaward API uses **yyyy-MM-dd** format with separate `fromDate` and `toDate` parameters:

```
fromDate=2024-01-01&toDate=2026-03-04
```

The client's base class `_format_date()` method handles conversion from Python `date`/`datetime` objects.

## Response Structure

The response is a JSON object with top-level keys:

```json
{
  "totalRecords": 2690000,
  "totalPages": 2692,
  "pageNumber": 0,
  "nextPageLink": "https://api.sam.gov/prod/contract/v1/subcontracts/search?pageNumber=1&pageSize=1000",
  "previousPageLink": null,
  "data": [
    {
      "piid": "W91QVN-20-C-0001",
      "agencyId": "9700",
      "agencyName": "DEPT OF DEFENSE",
      "primeEntityUei": "PRIME123UEI456",
      "primeEntityLegalBusinessName": "BIG PRIME CONTRACTOR INC",
      "subEntityUei": "SUB789UEI012",
      "subEntityLegalBusinessName": "SMALL WOSB FIRM LLC",
      "subAwardAmount": "250000.00",
      "subAwardDate": "2024-06-15",
      "subAwardDescription": {
        "code": "R425",
        "description": "IT Support Services"
      },
      "primeNaics": {
        "code": "541511",
        "description": "Custom Computer Programming Services"
      },
      "placeOfPerformance": {
        "city": "Arlington",
        "state": {
          "code": "VA",
          "name": "Virginia"
        },
        "country": {
          "code": "USA",
          "name": "UNITED STATES"
        },
        "zip": "22201"
      },
      "recoveryModelQ1": {
        "code": "Y",
        "description": "Yes"
      },
      "recoveryModelQ2": {
        "code": "N",
        "description": "No"
      },
      "primeAwardType": "Contract",
      "status": "Published"
    }
  ]
}
```

### Dict vs Scalar Fields (Critical Quirk)

Several fields return as `{code, description}` dicts from the live API, but may appear as plain strings in test fixtures or older data. The loader must use `isinstance(dict)` guards:

| Field | Live API Format | Fallback |
|-------|----------------|----------|
| `primeNaics` | `{"code": "541511", "description": "..."}` | Plain string `"541511"` |
| `subAwardDescription` | `{"code": "R425", "description": "..."}` | Plain string |
| `recoveryModelQ1` | `{"code": "Y", "description": "Yes"}` | Plain string `"Y"` |
| `recoveryModelQ2` | `{"code": "N", "description": "No"}` | Plain string `"N"` |

Example guard pattern from the loader:

```python
naics_raw = raw.get("primeNaics")
if isinstance(naics_raw, dict):
    naics_code = naics_raw.get("code")
else:
    naics_code = naics_raw
```

### Foreign Place of Performance

For non-US addresses, `placeOfPerformance.state.code` is `null` and `state.name` contains the full province/state name. The `pop_state` column was widened to `VARCHAR(100)` to accommodate these longer values.

### Key Response Fields

| Data | Path | Notes |
|------|------|-------|
| Prime PIID | `piid` | Links to `fpds_contract.contract_id` |
| Prime agency | `agencyId`, `agencyName` | |
| Prime UEI | `primeEntityUei` | Links to `entity.uei_sam` |
| Prime name | `primeEntityLegalBusinessName` | |
| Sub UEI | `subEntityUei` | Links to `entity.uei_sam` |
| Sub name | `subEntityLegalBusinessName` | |
| Sub amount | `subAwardAmount` | Dollar value of the subaward |
| Sub date | `subAwardDate` | Date subaward was made |
| Sub description | `subAwardDescription` | Dict: `{code, description}` |
| NAICS | `primeNaics` | Dict: `{code, description}` |
| POP | `placeOfPerformance` | Nested: city, state, country, zip |
| Status | `status` | Published or Deleted |

## Known Issues & Quirks

1. **`primeNaics`, `primeEntityUei`, and `subEntityUei` are SILENTLY IGNORED as query filters**. The API accepts them without error but returns unfiltered results. These are response fields, not valid query parameters. Verified 2026-03-04 by comparing `totalRecords` with and without these params.

2. **Response schema is undocumented in the OpenAPI spec**. The spec defines the response as bare `type: object` with no field definitions. Actual field structure is documented on the GSA website ([Acquisition API](https://open.gsa.gov/api/acquisition-subaward-reporting-api/)) but not in the YAML.

3. **Dict vs scalar fields**. `recoveryModelQ1`, `recoveryModelQ2`, `primeNaics`, and `subAwardDescription` return as `{code, description}` objects from the live API but may appear as plain strings in test fixtures. Always use `isinstance(dict)` guards.

4. **Foreign POP state codes**. For non-US addresses, `placeOfPerformance.state.code` returns `null`. The `state.name` field contains the full province/state name. Column widened to `VARCHAR(100)`.

5. **Address field confusion**. The correct place of performance field is `placeOfPerformance`, NOT `entityPhysicalAddress` (which is the entity's mailing address). A loader bug using the wrong field was fixed 2026-03-03.

6. **Data quality: ~11% likely duplicates**. Per GAO-24-106237, approximately 11% of contract subawards are likely duplicates. No de-duplication is performed by SAM.gov.

7. **First-tier only**. Only direct subcontracts from the prime contractor are reported. Sub-to-sub chains are not captured, meaning the actual subcontracting landscape is deeper than what the data shows.

8. **Reporting threshold**. Only subawards of $40,000+ (contracts) are reported. Smaller subcontracts are invisible.

9. **Reporting lag**. Primes have until the end of the month following the subaward month to report. Practical data availability lag is 30-60 days.

10. **Self-reported data**. No independent verification of subaward amounts or details. Data quality depends on prime contractor compliance.

11. **Exempt primes**. Primes with gross income under $300K in the prior tax year are exempt from reporting.

## Our Loading Strategy

### The Problem

The subaward API has 2.7 million records but **no working NAICS filter**. The `primeNaics` param we send is silently ignored -- the API returns ALL records regardless. Loading everything wastes API budget, time, and storage on irrelevant data.

### The Solution: PIID-Driven Loading

Instead of asking the subaward API "give me subawards for NAICS 541511" (which it cannot do), we flip the approach:

```
User runs:  python main.py load subawards --naics 541511,541611 --years-back 2

Step 0:  Parse comma-separated NAICS codes
         -> ['541511', '541611']

Step 1:  Query local fpds_contract table for PIIDs matching the NAICS codes:
         SELECT DISTINCT idv_piid FROM fpds_contract
         WHERE naics_code IN ('541511', '541611')
           AND date_signed >= '2024-03-04'
         -> 176 PIIDs (47 + 129, deduplicated)

Step 2:  For each PIID, call the subaward API with PIID filter:
         GET /prod/contract/v1/subcontracts/search?piid=<piid>&fromDate=2024-03-04
         -> 176 API calls, each returning 0-20 subawards

Step 3:  Load results into sam_subaward table with change detection

Result:  ~400-800 relevant subaward records loaded in 176 API calls
         vs. 2,700+ calls to page through all 2.7M records unfiltered
```

### Why PIID-Driven Works

- **PIID is a supported filter** -- the API actually respects it and returns only matching records
- **PIID counts are small** -- validated against local DB (2026-03-04):

  | NAICS | Distinct PIIDs (all time) | With 2-year lookback |
  |-------|--------------------------|---------------------|
  | 541611 | 161 | 129 |
  | 541519 | 102 | 72 |
  | 541330 | 82 | 67 |
  | 541511 | 55 | 47 |
  | 541512 | 40 | 27 |

- **Each call returns a focused result set** -- subawards for one specific prime contract
- **Date filtering also works** -- `fromDate`/`toDate` are supported API params and can further reduce results
- **Requires awards data first** -- must load awards before subawards: `python main.py load awards --naics 541511`

### Prerequisite: Awards Data

The PIID-driven strategy requires `fpds_contract` data for the target NAICS codes. If no PIIDs are found:

```
WARNING: No awards found for NAICS 541511 in local DB. Load awards first.
SUGGESTION: python main.py load awards --naics 541511 --years-back 2
```

The loader does NOT fall back to unfiltered loading.

### Data Flow

```
opportunity -> fpds_contract -> sam_subaward
                (PIID)          (prime_piid)
                (vendor_uei)    (prime_uei)
                                 (sub_uei) -> entity
```

### Budget

- Monthly targeted loads: ~20 API calls/month (from 1,000/day SAM.gov budget)
- PIID-driven NAICS loads: 50-200 calls per NAICS depending on date range
- Each PIID requires 1 call (API does not support batch/multi-value PIID queries)

### Processing

- **Page-by-page DB commit** planned (Phase 15, Priority 2): Each page committed immediately
- **Resumable** planned (Phase 15, Priority 2): Resume from last PIID checkpoint
- **Change detection**: SHA-256 hashing on composite key `prime_piid + sub_uei + sub_date`
- **Staging table**: Raw API responses written to `stg_subaward_raw` before normalization
- **Filter validation**: At least one filter required -- prevents accidental 2.7M unfiltered loads

### CLI Usage

```bash
# PIID-driven NAICS load (queries local fpds_contract for PIIDs first)
python main.py load subawards --naics 541611,541512 --years-back 2

# Direct PIID load (no local lookup needed)
python main.py load subawards --piid W91QVN-20-C-0001

# Agency + date filter (uses supported API params directly)
python main.py load subawards --agency 9700 --years-back 2 --max-calls 50

# Verify filter required (should error)
python main.py load subawards --max-calls 5
# ERROR: At least one filter required (--naics, --agency, or --piid)
```

## Data Quality Issues

- **Issue #19**: Dict vs scalar fields -- `recoveryModelQ1`, `recoveryModelQ2`, `primeNaics`, `subAwardDescription` return as `{code, description}` dicts from live API but as plain strings in test fixtures. Loader uses `isinstance(dict)` guards.
- **Issue #20**: Loader was reading wrong address field -- `placeOfPerformance` is the correct POP field, not `entityPhysicalAddress`. Fixed 2026-03-03. Prod subaward POP data needs reload.
- **Issue #21**: Foreign POP `state.code` is null -- for non-US addresses. Column widened to `VARCHAR(100)`.
- **~11% duplicate rate** (GAO-24-106237): No de-duplication by SAM.gov. Plan to add duplicate detection rule: same `prime_piid + sub_uei + sub_amount + sub_date` = likely duplicate.
- **~26% duplicate rate for grants**: Grant subawards (separate API) have even higher duplicate rates.
- **Missing fields**: Significant gaps in required data elements per GAO report.
- **Self-reported**: No independent verification of subaward amounts or details.
- **$40K threshold**: Subawards under $40,000 are not reported (contracts). Grants threshold is $30,000.

### How GovCon Competitors Handle Quality Issues

| Tool | Approach |
|------|----------|
| **HigherGov** | Actively de-duplicates "a significant percentage" of reported subcontracts |
| **GovTribe** | Avoids aggregate subaward searching entirely due to quality concerns; only shows vendor-level and prime-award-level detail |
| **GovWin (Deltek)** | Adds analyst enrichment on top of raw data |
| **GovSpend** | Cross-references eSRS (subcontracting plan goals) with FFATA actual data |

## Cross-References

- **Related tables**: `sam_subaward` (target), `stg_subaward_raw` (staging)
- **Linking fields**:
  - `prime_piid` links to `fpds_contract.contract_id` (PIID)
  - `prime_uei` links to `entity.uei_sam`
  - `sub_uei` links to `entity.uei_sam`
- **Alternative sources**:
  - **USASpending.gov Bulk CSV** (File F -- Subaward Attributes): Free, no rate limits, NAICS filtering supported, but 30-60 day data lag and 500K record limit per download. Available at https://www.usaspending.gov/download_center/custom_award_data
  - **USASpending.gov API** (`POST /api/v2/search/spending_by_award/`): JSON format, no hard rate limits, but different field names from SAM.gov
  - **eSRS (Electronic Subcontracting Reporting System)**: Being decommissioned February 2026. Contains subcontracting plan goals (not actuals).
- **Phase plan**: `thesolution/phases/15-SUBAWARD-STRATEGY.md` (detailed strategy, CLI gap analysis, recommended changes)
- **Subaward reporting rules**: FAR 52.204-10, $40K threshold (contracts), first-tier only

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| NAICS filter returns all records | `primeNaics` is silently ignored by the API | Use PIID-driven strategy: load awards first, then query subawards by PIID |
| UEI filter returns all records | `primeEntityUei` and `subEntityUei` are silently ignored | Filter client-side after fetching, or use PIID-based queries |
| `TypeError` on `primeNaics` field | Field is a dict `{code, description}`, not a string | Use `isinstance(dict)` guard; extract `.get("code")` |
| Wrong POP data | Reading `entityPhysicalAddress` instead of `placeOfPerformance` | Fixed in loader 2026-03-03. Reload affected data. |
| Null `state.code` in POP | Non-US address; state code is null for foreign locations | Use `state.name` instead; column accommodates long values |
| 401 Unauthorized | Invalid or expired API key | Regenerate at SAM.gov; keys expire every 90 days |
| Rate limit exceeded | Exceeded daily SAM.gov API budget | Wait until next day; check `etl_rate_limit` table |
| "No awards found for NAICS" | Awards not loaded for that NAICS code | Run `python main.py load awards --naics <code> --years-back 2` first |
| 2.7M+ records returned | No filter applied; API returned everything | Always require at least one filter (--naics, --agency, or --piid) |
| Duplicate subaward records | ~11% duplicate rate in source data (GAO-24-106237) | Plan: add de-duplication rule on `prime_piid + sub_uei + sub_amount + sub_date` |
