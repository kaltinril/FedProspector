# SAM.gov Contract Awards API v1 (FPDS Data)

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/contract-awards/v1/search` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (personal, no role), 1,000/day (personal with role or system account) |
| **Pagination** | `limit`/`offset` -- max 100/page. **offset is PAGE INDEX, not record offset** |
| **Data Format** | JSON (also supports CSV via `format=csv`) |
| **Update Frequency** | Weekly refresh recommended; ~50 calls/week budget |
| **Our CLI Command** | `python main.py load awards` |
| **Client File** | `fed_prospector/api_clients/sam_awards_client.py` |
| **Loader File** | `fed_prospector/etl/awards_loader.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/contract-awards.yaml` |

## Purpose & Prospecting Value

The Contract Awards API is the modernized replacement for FPDS-NG on SAM.gov. It provides structured JSON access to all federal contract award data including initial awards, modifications, and option exercises. For WOSB/8(a) prospecting, this API answers the critical question: **who won what, for how much, under which set-aside?**

Award history is essential for competitive intelligence. By searching awards by NAICS code, agency, or set-aside type, we can identify incumbent contractors on recompete opportunities, analyze pricing trends, and understand which agencies consistently award to small businesses. The `numberOfOffersReceived` field reveals how competitive a given contract was, and the `typeOfSetAsideCode` shows whether a contract was set aside for small businesses.

The API also enables PIID-based linking. Each award has a PIID (Procurement Instrument Identifier) that links to SAM.gov opportunities via solicitation number and to subaward records via `prime_piid`. This creates the chain: `opportunity -> fpds_contract -> sam_subaward` that powers our teaming partner analysis.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `naicsCode` | string | `541511` | NAICS code filter |
| `typeOfSetAsideCode` | string | `WOSB` | Set-aside type (**not** `typeOfSetAside` as docs suggest) |
| `contractingDepartmentCode` | string | `9700` | Awarding agency code (**not** `agencyCode`) |
| `awardeeUniqueEntityId` | string | `ABC123DEF456` | Awardee UEI (**not** `awardeeUEI`) |
| `productOrServiceCode` | string | `D302` | PSC code |
| `piid` | string | `W91QVN-20-C-0001` | Contract PIID |
| `fiscalYear` | string | `2025` | Federal fiscal year |
| `popState` | string | `VA` | Place of performance state |
| `dateSigned` | string | `[10/01/2024,09/30/2025]` | Date range (see Date Filtering below) |
| `dollarsObligated` | string | | Dollar amount filter |
| `totalDollarsObligated` | string | | Total dollars filter |
| `coBusSizeDeterminationCode` | string | | Business size determination |
| `modificationNumber` | string | `0` | Specific modification number |
| `solicitationID` | string | | Solicitation number |
| `q` | string | `cybersecurity` | Free-text search |
| `includeSections` | string | | Schema filtering |
| `format` | string | `csv` | Response format (JSON default) |

### Pagination

**CRITICAL**: The `offset` parameter is a **PAGE INDEX**, not a record offset. This is different from most APIs and from the Opportunities API.

- `offset=0` returns records 0-99 (page 0)
- `offset=1` returns records 100-199 (page 1)
- `offset=2` returns records 200-299 (page 2)
- `limit` max value is **100** per page

Our client handles this via `pagination_style="page"` with `page_param="offset"` in the `paginate()` call, so SAM's unusual naming convention (using "offset" for what is actually a page index) is abstracted away.

The OpenAPI spec lists the default `offset` as `1` (not `0`), but our client uses `0` as the start page.

### Date Filtering

The `dateSigned` parameter requires a specific format with **square brackets**:

```
[MM/DD/YYYY,MM/DD/YYYY]
```

Examples:
- Range: `[10/01/2024,09/30/2025]`
- Single date: `10/01/2024` (no brackets)

This is **not** ISO 8601 format. The client's `_format_date_range()` method handles conversion from Python `date`/`datetime` objects or `YYYY-MM-DD`/`YYYYMMDD` strings to the required format.

## Response Structure

The response is a JSON object with top-level keys:

```json
{
  "totalRecords": "1234",     // STRING, not int -- must parseInt()
  "limit": "100",             // STRING
  "offset": "0",              // STRING
  "awardSummary": [           // Array of award objects (NOT "data")
    {
      "contractId": {
        "piid": "W91QVN-20-C-0001",
        "modNumber": "P00003",
        "transactionNumber": "0"
      },
      "oldContractId": { ... },
      "coreData": {
        "federalOrganization": {
          "contractingDepartmentCode": "9700",
          "contractingDepartmentName": "DEPT OF DEFENSE",
          "contractingSubtierCode": "21AG",
          "contractingSubtierName": "ARMY CONTRACTING COMMAND",
          "contractingOfficeCode": "W91QVN",
          "contractingOfficeName": "..."
        },
        "productOrServiceInformation": {
          "principalNaics": [
            { "code": "541511", "description": "..." }
          ],
          "productOrServiceCode": { "code": "D302", "name": "..." }
        },
        "placeOfPerformance": { ... },
        "createdDate": "...",
        "lastModifiedDate": "..."
      },
      "awardDetails": {
        "dates": {
          "dateSigned": "01/15/2024",
          "effectiveDate": "01/15/2024",
          "currentCompletionDate": "01/14/2025",
          "ultimateCompletionDate": "01/14/2029"
        },
        "dollars": {
          "dollarsObligated": "1234567.89"
        },
        "totalContractDollars": {
          "baseAndAllOptions": "5000000.00",
          "ultimateContractValue": "5000000.00"
        },
        "competitionInformation": {
          "extentCompeted": { "code": "A", "name": "Full and Open Competition" },
          "solicitationProcedures": { ... },
          "numberOfOffersReceived": "5",
          "typeOfSetAside": { "code": "WOSB", "name": "Women-Owned Small Business" }
        },
        "awardeeData": {
          "awardeeHeader": {
            "awardeeName": "ACME CONSULTING LLC",
            "legalBusinessName": "ACME CONSULTING LLC"
          },
          "awardeeUEIInformation": {
            "uniqueEntityId": "ABC123DEF456",
            "cageCode": "1A2B3"
          },
          "certifications": {
            "sbaCertified8aProgramParticipant": "Y",
            "sbaCertifiedEconomicallyDisadvantagedWomenOwnedSmallBusiness": "Y"
          }
        }
      }
    }
  ]
}
```

Key nesting paths used by the loader:

| Data | Path |
|------|------|
| PIID | `contractId.piid` |
| Modification | `contractId.modNumber` |
| Agency code | `coreData.federalOrganization.contractingDepartmentCode` |
| NAICS code | `coreData.productOrServiceInformation.principalNaics[0].code` |
| PSC code | `coreData.productOrServiceInformation.productOrServiceCode.code` |
| Awardee name | `awardDetails.awardeeData.awardeeHeader.awardeeName` |
| Awardee UEI | `awardDetails.awardeeData.awardeeUEIInformation.uniqueEntityId` |
| Dollars obligated | `awardDetails.dollars.dollarsObligated` |
| Set-aside type | `awardDetails.competitionInformation.typeOfSetAside.code` |
| Number of offers | `awardDetails.competitionInformation.numberOfOffersReceived` |

## Known Issues & Quirks

1. **Parameter names don't match documentation**. The API uses `typeOfSetAsideCode` (not `typeOfSetAside`), `contractingDepartmentCode` (not `agencyCode`), and `awardeeUniqueEntityId` (not `awardeeUEI`). Always validate parameter names with a live API call.

2. **`totalRecords` is returned as a string**, not an integer. Must be parsed to int for pagination calculations: `int(response["totalRecords"])`.

3. **`offset` is a page index**, not a record offset. `offset=0` is page 0 (records 0-99), `offset=1` is page 1 (records 100-199). This is unique among SAM.gov APIs -- the Opportunities API uses true record offsets.

4. **Response key is `awardSummary`**, not `data`. Other SAM.gov APIs use `data` for results arrays.

5. **Dates are in MM/DD/YYYY format**, not ISO 8601. The awards_loader converts these during loading. Date range queries must use square brackets: `[MM/DD/YYYY,MM/DD/YYYY]`.

6. **Deeply nested response structure**. Awardee information is buried under `awardDetails.awardeeData.awardeeHeader` and `awardDetails.awardeeData.awardeeUEIInformation`. The loader's `_normalize_award()` method flattens this into a single-level dict for database insertion.

7. **Max sync results: ~400K records**. The API supports an async extract mode via `/contract-awards/v1/download` for larger result sets (up to 1M records), requiring a token-based download flow.

8. **OpenAPI spec default for offset is 1**, but page indexing is 0-based. Our client starts at `offset=0`.

## Our Loading Strategy

### Approach: Incremental by NAICS + Date Range

We do not attempt to load all contract awards. Instead, we load awards relevant to our target NAICS codes with a configurable lookback period.

```
python main.py load awards --naics 541511,541611 --years-back 3
```

### Budget

- Weekly refresh: ~50 API calls/week (allocated from 1,000/day SAM.gov budget)
- Initial bulk load: 2-3 days at 1,000 calls/day
- Each NAICS code requires at least 1 call, plus 1 per additional page of 100 results

### Processing

- **Page-by-page DB commit** (Phase 14.26 pattern): Each page is committed to the database immediately, not collected in memory
- **Resumable**: If interrupted (rate limit, Ctrl+C), resumes from the last completed page via `etl_load_log` checkpoints
- **Change detection**: SHA-256 hashing on business-meaningful fields. Records with unchanged hashes are skipped.
- **Staging table**: Raw API responses written to `stg_fpds_award_raw` before normalization, enabling debugging and replay
- **Composite PK**: `fpds_contract` uses `(contract_id, modification_number)` as the primary key

### Load Types

| CLI Option | Behavior |
|------------|----------|
| `--naics 541511,541611` | Search by one or more NAICS codes |
| `--fiscal-year 2025` | Limit to a specific fiscal year |
| `--years-back 3` | Compute date range from today minus N years |
| `--key 2` | Use API key 2 (1,000/day budget) |

## Data Quality Issues

- **Issue #18**: Dates in MM/DD/YYYY format (not ISO 8601). The awards_loader converts during load.
- **Dollar amounts as strings**: All dollar values in the response are strings, requiring `parse_decimal()` conversion.
- **Null nesting**: Any level of the nested response can be `null`/missing. The loader must use safe navigation (`.get()` chains) throughout.
- **Duplicate modifications**: The same PIID + modification number can appear in paginated results if data changes between API calls. The composite PK upsert handles this gracefully.

## Cross-References

- **Related tables**: `fpds_contract` (target), `stg_fpds_award_raw` (staging)
- **Linking fields**: `contract_id` (PIID) links to `sam_subaward.prime_piid`; `vendor_uei` links to `entity.uei_sam`; `solicitation_number` links to `opportunity.solicitation_number`
- **Alternative sources**: USASpending.gov (no rate limits, but different field names and structure), FPDS ATOM Feed (deepest history, XML format, unlimited searches)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `totalRecords` always 0 | Wrong parameter name (e.g., `typeOfSetAside` instead of `typeOfSetAsideCode`) | Check exact parameter names in this doc |
| 401 Unauthorized | Invalid or expired API key | Regenerate at SAM.gov; keys expire every 90 days |
| Empty `awardSummary` array | Filters too narrow or date format wrong | Verify date format is `[MM/DD/YYYY,MM/DD/YYYY]` with brackets |
| Results don't change with pagination | Using `offset` as record offset instead of page index | Ensure `offset` increments by 1 per page, not by `limit` |
| Rate limit exceeded | Exceeded daily SAM.gov API budget (shared across all SAM APIs) | Wait until next day or use API key 2; check `etl_rate_limit` table |
| `KeyError` on response parsing | Nested field is null at some level | Use `.get()` chains; check the loader's `_normalize_award()` for safe patterns |
