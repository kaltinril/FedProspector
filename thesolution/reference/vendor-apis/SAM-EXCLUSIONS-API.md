# SAM.gov Exclusions API v4

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/entity-information/v4/exclusions` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (personal, no role), 1,000/day (personal with role or system account) |
| **Pagination** | `page`/`size` -- **max 10 records per page (extremely small)** |
| **Data Format** | JSON |
| **Update Frequency** | Weekly check recommended (Monday only); ~10 calls/week budget |
| **Our CLI Command** | `python main.py load exclusions` |
| **Client File** | `fed_prospector/api_clients/sam_exclusions_client.py` |
| **Loader File** | `fed_prospector/etl/exclusions_loader.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/exclusions-api.yaml` |

## Purpose & Prospecting Value

The Exclusions API provides access to SAM.gov's list of entities that are debarred, suspended, proposed for debarment, or otherwise excluded from receiving federal contracts and subcontracts. This is a critical due diligence data source for WOSB/8(a) federal contract prospecting.

Before pursuing a teaming arrangement with any prime contractor or subcontractor, you must verify they are not on the exclusion list. Partnering with an excluded entity can disqualify your entire bid and potentially result in legal consequences. The Exclusions API makes it possible to check a specific vendor's status by UEI, CAGE code, or name.

This API is designed for **on-demand lookups**, not bulk loading. With a maximum page size of only 10 records and 167,000+ total exclusion records in the system, attempting a bulk load would consume over 16,700 API calls -- far exceeding the 1,000/day rate limit. Use this API to check specific entities when evaluating teaming partners, reviewing competitor eligibility, or conducting proposal compliance checks.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `ueiSAM` | string | `ABC123DEF456` | UEI SAM identifier |
| `q` | string | `Smith Construction` | Free-text name search (partial match) |
| `excludingAgencyCode` | string | `AF` | Agency that issued the exclusion |
| `excludingAgencyName` | string | `FEDERAL` | Agency name (partial match) |
| `exclusionType` | string | `Ineligible (Proceedings Completed)` | Type of exclusion |
| `exclusionProgram` | string | `Reciprocal` | Exclusion program |
| `exclusionName` | string | `ACME Corp` | Excluded party name |
| `excludedPartyName` | string | `John Doe` | Excluded party name (alternate) |
| `classification` | string | `Individual` | Classification type: Individual, Firm, Vessel, Special Entity Designation |
| `isActive` | string | `Y` | Active status filter (Y/N) |
| `cageCode` | string | `0Y5L9` | CAGE code lookup |
| `naicsCode` | string | `541511` | NAICS code filter |
| `pscCode` | string | `D302` | PSC code filter |
| `activationDate` | string | `01/01/2024` | Single date or range in MM/DD/YYYY |
| `activationDateFrom` | string | `01/01/2024` | Activation date range start |
| `activationDateTo` | string | `12/31/2024` | Activation date range end |
| `terminationDate` | string | `01/01/2025` | Termination date |
| `terminationDateFrom` | string | `01/01/2025` | Termination date range start |
| `terminationDateTo` | string | `12/31/2025` | Termination date range end |
| `creationDate` | string | `01/01/2024` | Record creation date |
| `createDateFrom` | string | `01/01/2024` | Creation date range start |
| `createDateTo` | string | `12/31/2024` | Creation date range end |
| `updateDate` | string | `01/01/2024` | Last update date |
| `country` | string | `USA` | Country code (3-letter) |
| `stateProvince` | string | `NC` | State/province code |
| `city` | string | `Raleigh` | City name |
| `zipCode` | string | `27601` | ZIP code |
| `ssnOrTinOrEin` | string | `XXXXXXXXX` | 9-digit identifier (sensitive) |
| `npi` | string | `1053373266` | National Provider Identifier |
| `ctCode` | string | `A` | CT code |
| `recordStatus` | string | `Active` | Record status (Active, Inactive) |
| `sort` | string | | Sort field |
| `sortOrder` | string | `asc` | Sort order: asc, desc |
| `format` | string | `csv` | Download format (csv or json) |
| `includeSections` | string | | Schema filtering parameter |
| `exactMatch` | boolean | `true` | Enable exact matching |
| `fascsaOrder` | string | `Yes` | Filter FASCSA Orders (Yes/No) |

### Pagination

The Exclusions API uses `page`/`size` pagination:

- `page` starts at **0** (0-indexed)
- `size` maximum is **10 records per page** -- this is extremely small compared to other SAM.gov APIs
- Pagination is impractical for large result sets

The tiny page size makes bulk loading completely infeasible:
- 167,000+ total exclusion records / 10 per page = **16,700+ API calls**
- At 1,000 calls/day, a full load would take **17 days** and consume the entire budget

### Date Filtering

All date parameters use `MM/DD/YYYY` format. Range filters use separate `From`/`To` parameters (unlike the Awards API which uses square-bracket ranges):

```
activationDateFrom=01/01/2024&activationDateTo=12/31/2024
```

### Bulk Extract Alternative

The API also supports a bulk extract download via `/entity-information/v4/download-exclusions`, which accepts a token to download a complete exclusions file. This is the recommended approach if full exclusion data is ever needed.

## Response Structure

The response is a JSON object with top-level keys:

```json
{
  "totalRecords": 167000,
  "excludedEntity": [
    {
      "exclusionDetails": {
        "classificationType": "Firm",
        "exclusionType": "Ineligible (Proceedings Completed)",
        "exclusionProgram": "Reciprocal",
        "excludingAgencyCode": "DOJ",
        "excludingAgencyName": "DEPARTMENT OF JUSTICE"
      },
      "exclusionIdentification": {
        "ueiSAM": "ABC123DEF456",
        "cageCode": "0Y5L9",
        "npi": null,
        "prefix": null,
        "firstName": null,
        "middleName": null,
        "lastName": null,
        "suffix": null,
        "entityName": "ACME CONSTRUCTION LLC"
      },
      "exclusionActions": {
        "listOfActions": [
          {
            "createDate": "01/15/2024",
            "updateDate": "01/15/2024",
            "activationDate": "01/15/2024",
            "terminationDate": "01/15/2027",
            "terminationType": "Definite",
            "ctCode": "A",
            "additionalComments": "...",
            "crossReference": null
          }
        ]
      },
      "exclusionAddress": {
        "addressLine1": "123 Main St",
        "addressLine2": null,
        "city": "Springfield",
        "stateOrProvinceCode": "VA",
        "zipCode": "22150",
        "country": "USA"
      },
      "exclusionOtherInformation": {
        "additionalComments": "...",
        "ctCode": "A",
        "moreLocations": null,
        "vesselDetails": null
      }
    }
  ]
}
```

Key nesting paths used by the loader:

| Data | Path |
|------|------|
| UEI | `exclusionIdentification.ueiSAM` |
| CAGE code | `exclusionIdentification.cageCode` |
| Entity name | `exclusionIdentification.entityName` |
| First/last name | `exclusionIdentification.firstName`, `.lastName` |
| Exclusion type | `exclusionDetails.exclusionType` |
| Exclusion program | `exclusionDetails.exclusionProgram` |
| Agency code | `exclusionDetails.excludingAgencyCode` |
| Agency name | `exclusionDetails.excludingAgencyName` |
| Activation date | `exclusionActions.listOfActions[0].activationDate` |
| Termination date | `exclusionActions.listOfActions[0].terminationDate` |
| Classification | `exclusionDetails.classificationType` |

## Known Issues & Quirks

1. **Maximum page size is 10 records**. This is the smallest page size of any SAM.gov API and makes bulk loading impractical. The Opportunities API allows 1,000/page, the Subawards API allows 1,000/page, and the Awards API allows 100/page.

2. **Bulk load is infeasible via API**. With 167,000+ records at 10/page, a full load requires 16,700+ calls. Use the bulk extract download endpoint (`/entity-information/v4/download-exclusions`) for full data, or limit API usage to targeted lookups.

3. **Response key is `excludedEntity`**, not `data` or `awardSummary`. This is unique to the Exclusions API.

4. **Actions are nested in an array**. Exclusion dates are under `exclusionActions.listOfActions[0]`, not directly on the exclusion object. A single exclusion can have multiple actions.

5. **Both individuals and firms are in the same endpoint**. The `classification` field distinguishes between Individual, Firm, Vessel, and Special Entity Designation. Individual records have `firstName`/`lastName` instead of `entityName`.

6. **No documented response schema in OpenAPI spec**. The spec defines the response as `application/hal+json` with no schema, so field structure must be validated empirically.

## Our Loading Strategy

### Approach: On-Demand Lookup Only

We do **not** attempt to bulk load exclusions. Instead, we use this API for targeted checks:

1. **Teaming partner verification**: Before pursuing a teaming arrangement, check the partner's UEI against the exclusion list
2. **Competitor due diligence**: Verify that competitors bidding on the same contracts are not excluded
3. **Batch check on entity load**: After loading new entities from the monthly extract, spot-check a sample against the exclusion list

### Budget

- Weekly check: ~10 API calls/week (Monday only, from 1,000/day SAM.gov budget)
- On-demand lookups: Use the `check_entity(uei)` convenience method for single checks
- Batch checks: Use `check_entities(uei_list)` for multiple UEIs (1 API call per UEI)

### Processing

- **Change detection**: SHA-256 hashing on composite key of `uei + activation_date + exclusion_type`
- **Staging table**: Raw API responses written to `stg_exclusion_raw` before normalization
- **Auto-increment PK**: `sam_exclusion.id` is auto-increment since exclusions have no natural single-column key

### CLI Usage

```bash
# Load exclusions (targeted search)
python main.py load exclusions --uei ABC123DEF456
python main.py load exclusions --name "Smith Construction"
python main.py load exclusions --agency AF

# Batch check (checks multiple UEIs)
python main.py load exclusions --key 2
```

## Data Quality Issues

- **No single natural key**: Exclusions for individuals may lack a UEI. The loader uses a composite of `uei/entity_name + activation_date + exclusion_type` as the logical key for change detection.
- **Date format**: All dates in MM/DD/YYYY format, converted during load.
- **Null fields common**: Many exclusion records have sparse data -- especially for individuals who may only have a name and no UEI, CAGE code, or address.
- **Duplicate actions**: A single exclusion entity can have multiple actions in `listOfActions[]`. The loader processes the first action for dates.

## Cross-References

- **Related tables**: `sam_exclusion` (target), `stg_exclusion_raw` (staging)
- **Linking fields**: `uei` links to `entity.uei_sam` for cross-referencing excluded entities with registered vendors
- **Alternative sources**: SAM.gov Exclusions Extract (bulk download via `/entity-information/v4/download-exclusions` -- recommended for full dataset)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Extremely slow pagination | Max page size is only 10 | Don't attempt bulk loads; use targeted lookups by UEI or name |
| No results for known excluded entity | Using wrong search field | Try `ueiSAM`, `q` (free text), or `exclusionName` |
| 401 Unauthorized | Invalid or expired API key | Regenerate at SAM.gov; keys expire every 90 days |
| Rate limit exceeded | Exceeded daily SAM.gov API budget | Wait until next day; check `etl_rate_limit` table |
| Missing UEI on individual exclusions | Individuals often lack UEI | Search by name using `q` parameter instead |
| Empty `excludedEntity` array | No matching exclusions | This is normal -- the entity is not excluded |
