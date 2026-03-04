# SAM.gov Entity Management API v3

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/entity-information/v3/entities` |
| **Auth** | `api_key` query parameter (personal key) or Basic Auth + `x-api-key` (system account) |
| **Rate Limit** | 10/day (free tier, no role), 1,000/day (with role), 10,000/day (federal system account) |
| **Pagination** | `page`/`size` (page-based), max `size=10` per page |
| **Data Format** | JSON or CSV (via `format` param) |
| **Update Frequency** | Real-time (entity updates reflected same day) |
| **Our CLI Command** | `python main.py load entities` (API mode) |
| **Client File** | `fed_prospector/api_clients/sam_entity_client.py` |
| **Loader File** | `fed_prospector/etl/entity_loader.py` (API), `fed_prospector/etl/bulk_loader.py` (bulk) |
| **OpenAPI Spec** | `thesolution/sam_gov_api/entity-api.yaml` |

## Purpose & Prospecting Value

The SAM.gov Entity Management API provides access to federal contractor registration data -- every business that wants to do business with the federal government must register in SAM.gov. This API contains the legal business name, Unique Entity Identifier (UEI), CAGE code, physical addresses, NAICS codes, PSC codes, business type certifications, SBA certifications (WOSB, EDWOSB, 8(a)), points of contact, and registration status for approximately 1.3 million entities (~576K active).

For WOSB and 8(a) prospecting, this API serves two critical functions. First, it identifies the firm's own competitors: by filtering on `businessTypeCode=8W` (WOSB) or `sbaBusinessTypeCode=A4` (8(a) certified), combined with NAICS codes, you can find every certified small business competing in your space. Second, it enables teaming partner discovery: finding complementary firms with the right certifications and capabilities to form joint ventures or mentor-protege arrangements.

The Entity Management API is also essential for due diligence. Before pursuing a teaming arrangement or subcontracting opportunity, you verify the potential partner's registration status, certifications, and exclusion status. The `sbaBusinessTypeList` field includes `certificationEntryDate` and `certificationExitDate`, so you can confirm whether a firm's 8(a) or WOSB certification is still active.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `ueiSAM` | string | `ABC123DEF456` | 12-digit UEI. Max 100 comma-separated values. |
| `legalBusinessName` | string | `Acme Solutions` | Partial or complete match. |
| `dbaName` | string | `Acme` | Partial or complete match. |
| `registrationStatus` | string | `A` | `A`=Active, `E`=Expired. |
| `updateDate` | string | `01/15/2026` | Single date or date range in `MM/DD/YYYY` format. |
| `registrationDate` | string | `01/15/2026` | Single date or date range. |
| `activationDate` | string | `01/15/2026` | Single date or date range. |
| `expirationDate` | string | `01/15/2026` | Single date or date range. |
| `physicalAddressCity` | string | `Reston` | City name. |
| `physicalAddressProvinceOrStateCode` | string | `VA` | 2-character state code. |
| `physicalAddressCountryCode` | string | `USA` | 3-character country code. |
| `physicalAddressZipPostalCode` | string | `20190` | 5-digit ZIP code. |
| `naicsCode` | string | `541511` | 6-digit NAICS code. |
| `primaryNaics` | string | `541511` | Primary NAICS only. Accepts multiple values. |
| `pscCode` | string | `D302` | 4-character PSC code. |
| `businessTypeCode` | string | `8W` | 2-character business type code (see codes below). |
| `sbaBusinessTypeCode` | string | `A4` | 2-character SBA business type code. |
| `entityStructureCode` | string | `2L` | 2-character entity structure code. |
| `cageCode` | string | `1ABC2` | 5-character CAGE code. Max 100 values. |
| `dodaac` | string | `123456789` | 9-character DoDAAC. |
| `exclusionStatusFlag` | string | `D` | `D`=debarred/excluded, or null. |
| `includeSections` | string | `all` | Sections to include in response (see below). |
| `sensitivity` | string | `public` | Data sensitivity level. |
| `format` | string | `JSON` | `JSON` or `CSV`. |
| `sort` | string | `legalBusinessName` | Sort field. |
| `sortOrder` | string | `asc` | `asc` or `desc`. |

### WOSB/8(a) Business Type Codes

#### General Business Type Codes (`businessTypeCode` param)

| Code | Description |
|------|-------------|
| `A2` | Woman Owned Business |
| `8W` | Woman Owned Small Business (WOSB) |
| `8E` | Economically Disadvantaged Women-Owned Small Business (EDWOSB) |
| `8C` | Joint Venture Women Owned Small Business |
| `8D` | Joint Venture Economically Disadvantaged Women-Owned Small Business |

#### SBA Business Type Codes (`sbaBusinessTypeCode` param)

| Code | Description |
|------|-------------|
| `A4` | SBA Certified 8(a) Program Participant |
| `A6` | SBA Certified 8(a) Participant (alternate code) |

### Response Sections (`includeSections`)

| Section | Content |
|---------|---------|
| `entityRegistration` | UEI, CAGE, legal name, status, dates |
| `coreData` | Addresses, NAICS, PSC, business types, SBA certifications |
| `assertions` | Goods/services, size metrics, predecessor info |
| `repsAndCerts` | FAR/DFAR certifications and representations |
| `mandatoryPOCs` | Required points of contact |
| `optionalPOCs` | Optional points of contact |
| `all` | All of the above |

### Data Sensitivity Levels

| Level | Content | Access Required |
|-------|---------|-----------------|
| Public | Name, UEI, addresses, business types, NAICS | Any API key |
| FOUO (CUI) | Hierarchy, security clearance, contact emails/phones | Federal System Account |
| Sensitive (CUI) | Banking info, SSN/TIN/EIN | Federal System Account + POST only |

### Pagination

The Entity Management API uses **page-based** pagination with an extremely small page size:

- Maximum `size=10` records per page
- `page=0` is the first page (0-based)
- `page * size` cannot exceed 10,000 (hard cap of 10,000 records per query)
- Response includes `totalRecords` indicating total matching entities

This is the smallest page size of any SAM.gov sub-API and makes bulk loading via the API impractical. For example, loading all ~576K active entities at 10 per page would require 57,600 API calls -- far exceeding any daily rate limit. **Use the Bulk Extract API for large loads; reserve this API for targeted lookups.**

Our client configuration:

```python
_ENTITY_PAGINATE_KWARGS = dict(
    pagination_style="page",
    page_param="page",
    size_param="size",
    page_size=10,
    page_start=0,
    total_key="totalRecords",
)
```

### Date Filtering

- **Format**: `MM/DD/YYYY` (e.g., `01/15/2026`)
- **Range format**: Supports single date or date range
- **Date fields**: `updateDate`, `registrationDate`, `activationDate`, `expirationDate`
- **Useful for daily refresh**: Query `updateDate` for today's date to find entities modified today

## Response Structure

```json
{
  "totalRecords": 3,
  "entityData": [
    {
      "entityRegistration": {
        "samRegistered": "Yes",
        "ueiSAM": "ABC123DEF456",
        "cageCode": "1ABC2",
        "dodaac": null,
        "legalBusinessName": "Acme Solutions LLC",
        "dbaName": null,
        "registrationStatus": "Active",
        "registrationDate": "2020-01-15",
        "activationDate": "2025-06-01",
        "registrationExpirationDate": "2026-06-01",
        "lastUpdateDate": "2025-12-15",
        "purposeOfRegistrationCode": "Z2",
        "purposeOfRegistrationDesc": "All Awards"
      },
      "coreData": {
        "physicalAddress": {
          "addressLine1": "123 Main Street",
          "addressLine2": "Suite 400",
          "city": "Reston",
          "stateOrProvinceCode": "VA",
          "zipCode": "20190",
          "zipCodePlus4": "1234",
          "countryCode": "USA"
        },
        "mailingAddress": { ... },
        "congressionalDistrict": "11",
        "businessTypes": {
          "businessTypeList": [
            { "businessTypeCode": "8W", "businessTypeDesc": "Woman Owned Small Business" },
            { "businessTypeCode": "A2", "businessTypeDesc": "Woman Owned Business" },
            { "businessTypeCode": "23", "businessTypeDesc": "Minority Owned Business" }
          ],
          "sbaBusinessTypeList": [
            {
              "sbaBusinessTypeCode": "A4",
              "sbaBusinessTypeDesc": "SBA Certified 8(a) Program Participant",
              "certificationEntryDate": "2023-01-15",
              "certificationExitDate": "2032-01-15",
              "expirationDate": null
            }
          ]
        },
        "naicsList": [
          {
            "naicsCode": "541511",
            "naicsDescription": "Custom Computer Programming Services",
            "sbaSmallBusiness": "Y",
            "isPrimary": true
          }
        ],
        "pscList": [
          { "pscCode": "D302", "pscDescription": "IT and Telecom - Systems Development" }
        ]
      },
      "assertions": { ... },
      "repsAndCerts": { ... },
      "mandatoryPOCs": { ... },
      "optionalPOCs": { ... }
    }
  ]
}
```

### Key Fields for WOSB/8(a) Prospecting

| Field Path | Purpose |
|------------|---------|
| `entityRegistration.ueiSAM` | Primary entity identifier, links to opportunities and awards |
| `entityRegistration.legalBusinessName` | Official business name |
| `entityRegistration.registrationStatus` | Active vs Expired |
| `entityRegistration.registrationExpirationDate` | Registration currency check |
| `coreData.businessTypes.businessTypeList[].businessTypeCode` | WOSB codes: A2, 8W, 8E, 8C, 8D |
| `coreData.businessTypes.sbaBusinessTypeList[].sbaBusinessTypeCode` | 8(a) code: A4 |
| `coreData.businessTypes.sbaBusinessTypeList[].certificationEntryDate` | When 8(a) cert started |
| `coreData.businessTypes.sbaBusinessTypeList[].certificationExitDate` | When 8(a) cert expires |
| `coreData.naicsList[].naicsCode` | NAICS capabilities |
| `coreData.naicsList[].isPrimary` | Primary NAICS indicator |
| `coreData.pscList[].pscCode` | Product/service codes |
| `coreData.physicalAddress.stateOrProvinceCode` | Location for geographic analysis |

## Known Issues & Quirks

1. **Extremely small page size (max 10)**: The `size` parameter cannot exceed 10 records per page. This is the smallest page size of any SAM.gov sub-API and makes bulk loading via the API completely impractical. Always use the Bulk Extract API for large loads.

2. **10,000 record cap**: The product of `page * size` cannot exceed 10,000, meaning you can never access more than 10,000 records in a single query even with pagination. Narrow your filters if your query matches more than 10,000 entities.

3. **One business type code per request**: The `businessTypeCode` and `sbaBusinessTypeCode` parameters accept only a single value. Searching for both WOSB (8W) and EDWOSB (8E) entities requires two separate API calls.

4. **API keys expire every 90 days**: Keys must be regenerated at api.data.gov. Build monitoring to detect 403 responses indicating an expired key.

5. **SBA certification dates are embedded in the `sbaBusinessTypeList`**: Unlike general business types (which are simple code/description pairs), SBA certifications include `certificationEntryDate` and `certificationExitDate` fields that must be parsed to determine if a certification is current.

6. **v1 vs v3 vs v4 endpoint versions**: Multiple versions of the Entity Management API coexist. Our client uses v3 (`/entity-information/v3/entities`). Versions differ in parameter names and response structures. The OpenAPI spec documents v1 through v4.

## Our Loading Strategy

### Primary: Bulk Extracts (Not This API)

Entity data is primarily loaded via the SAM.gov Bulk Extract API (`SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP`), which downloads all ~576K active entities in a single API call. See `SAM-ENTITY-EXTRACTS.md` for details. This API is reserved for targeted, on-demand lookups.

### Secondary: API for Targeted Lookups

- **Single entity by UEI**: `get_entity_by_uei("ABC123DEF456")` -- 1 API call
- **Entities updated on a date**: `get_entities_by_date(date(2026, 3, 1))` -- multiple pages at 10/entity each
- **WOSB entity search**: `search_wosb_entities(stateCode="VA")` -- 2+ API calls (8W + 8E)
- **8(a) entity search**: `search_8a_entities(naicsCode="541511")` -- 1 API call

### Daily Budget Allocation

With a 1,000/day budget, we allocate ~100 calls/day for entity lookups. At 10 entities per call, this supports up to 1,000 entity lookups per day -- sufficient for on-demand verification of teaming partners, competitors, and awardees discovered through opportunity monitoring.

### Page-by-Page Resumable Loading

The `iter_entity_pages_by_date()` method yields `(entities_list, page_number, total_records)` tuples, enabling the loader to save progress after each page and resume from the last completed page if interrupted.

## Data Quality Issues

- **Issue #1**: ZIP codes containing city/state/country names (9,294 records in first import). Handled by ETL cleaner.
- **Issue #2**: ZIP codes containing PO BOX data (27 records). Handled by ETL cleaner.
- **Issue #3**: State fields containing dates (e.g., "05/03/1963"). Handled by ETL cleaner.
- **Issue #4**: Foreign addresses with province names > 2 chars in state field. Column accommodates.
- **Issue #5**: Non-ASCII characters in country names (Reunion, Cote d'Ivoire). UTF-8 handling.
- **Issue #6**: Missing 3-letter country codes (XKS=Kosovo, XWB=West Bank, XGZ=Gaza). Custom mappings.
- **Issue #7**: CAGE codes with multiple values separated by comma+space. Parsed by loader.
- **Issue #8**: NAICS codes from retired vintages not in current lookup tables. Logged, loaded as-is.
- **Issue #11**: SBA type entries concatenate code+date (e.g., "A620291223" = code "A6" + date "20291223"). Parsed by DAT parser.
- **Issue #12**: Duplicate NAICS entries -- same code, different flags (7 occurrences in monthly extract). Deduplicated during load.

## Cross-References

- **Related tables**: `entity` (main), `entity_address`, `entity_naics`, `entity_psc`, `entity_business_type`, `entity_sba_certification`, `entity_poc`
- **Linking fields**: `uei_sam` (primary key, links to `opportunity.awardee_uei` and `award.awardee_uei`), `cage_code` (links to CAGE reference), `naics_code` (links to `naics_code` reference), `psc_code` (links to `psc_code` reference)
- **Alternative sources**: SAM.gov Bulk Extract API (preferred for bulk loads -- see `SAM-ENTITY-EXTRACTS.md`), SBA Dynamic Small Business Search (same data, no API)

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `RateLimitExceeded` | Hit daily API call limit | Wait until next day, or switch to key 2 (`--key=2`) |
| HTTP 403 | Invalid/expired API key | Regenerate at api.data.gov; keys expire every 90 days |
| HTTP 403 on FOUO fields | Personal key cannot access FOUO data | Federal System Account required; use public sensitivity |
| `totalRecords > 10000` | Query too broad | Add more filters to narrow below 10,000 results |
| Empty `entityData` with `totalRecords > 0` | API inconsistency | Logged as warning; retry |
| Missing `sbaBusinessTypeList` | Entity has no SBA certifications | Normal -- field is only present when certifications exist |
| `registrationStatus` is "Expired" | Entity registration lapsed | Not a data error; entity may re-register |
