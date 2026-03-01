# SAM.gov Contract Awards API v1 - Research Notes

Researched: 2026-02-28

## Endpoint
- **Production**: `https://api.sam.gov/contract-awards/v1/search`
- **Alpha/Test**: `https://api-alpha.sam.gov/contract-awards/v1/search`
- **Method**: GET (not POST)
- **Auth**: Query parameter `api_key=YOUR_KEY`

## Pagination
- Offset-based: `limit` (max 100) + `offset` (start at 0)
- Response includes `totalRecords` (capped at 400,000 for sync queries)
- Async extract mode: up to 1,000,000 records via POST to `/v1/extracts`

## Rate Limits
- Shares same daily quota with all SAM.gov APIs (Entity, Opportunities, etc.)
- Free tier: 10/day, Premium: 1,000/day, Federal: 10,000/day

## Key Filter Parameters (query string)
| Parameter | Type | Notes |
|-----------|------|-------|
| `naicsCode` | string | 6-digit, supports multiple |
| `typeOfSetAsideCode` | string | WOSB, 8A, 8AN, etc. |
| `awardeeUniqueEntityId` | string | 12-char UEI |
| `dollarsObligated` | range | `100000,500000` format |
| `dateSigned` | date range | `YYYYMMDD,YYYYMMDD` format |
| `productOrServiceCode` | string | PSC code |
| `contractingDepartmentCode` | string | CGAC agency code |
| `fiscalYear` | integer | e.g. 2024 |
| `extentCompetedCode` | string | A=full, B=not avail, C=not competed, D=full after exclusion |
| `piid` | string | Contract identifier |
| `idvPiid` | string | Parent IDV |
| `awardeeBusinessTypeName` | string | "Small Business", "Woman Owned" |
| `coBusSizeDeterminationName` | string | "Small Business" or "Large Business" |
| `popStateCode` | string | Place of performance state |
| `modifiedDate` | date range | Last modification date |

Special chars not allowed in values: `& | { } ^ \`

## Response JSON Structure
```json
{
  "totalRecords": 34,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "contractId": {
        "contractNumber": "W911NF25C0001",
        "modificationNumber": "0",
        "transactionNumber": "1"
      },
      "awardeeData": {
        "awardeeHeader": {
          "awardeeName": "Acme Corp",
          "awardeeUEIInformation": {
            "uniqueEntityId": "ABC123DEF456",
            "cageCode": "1A2B3",
            "awardeeUltimateParentUniqueEntityId": "...",
            "awardeeUltimateParentName": "..."
          }
        }
      },
      "awardContractData": {
        "naicsCode": "541511",
        "productOrServiceCode": "1001",
        "typeOfSetAsideCode": "WOSB",
        "typeOfContractCode": "A",
        "extentCompetedCode": "A",
        "numberOfOffersReceived": 5,
        "contractDescription": "...",
        "far1102ExceptionCode": "...",
        "dollarsObligated": 250000.00,
        "baseAndAllOptionsValue": 500000.00,
        "dateSignedFormat": {
          "dateSignedShortFormat": "02/15/2024"
        },
        "effectiveDate": "02/15/2024",
        "completionDate": "02/14/2025",
        "lastModifiedDate": "02/28/2026",
        "placeOfPerformance": {
          "stateCode": "VA",
          "countryCode": "USA",
          "cityName": "Arlington",
          "zipCode": "22202"
        }
      }
    }
  ]
}
```

## Field Mapping to fpds_contract Table
| API Response Path | DB Column |
|---|---|
| `contractId.contractNumber` | `contract_id` |
| `contractId.modificationNumber` | `modification_number` |
| `awardeeData.awardeeHeader.awardeeUEIInformation.uniqueEntityId` | `vendor_uei` |
| `awardeeData.awardeeHeader.awardeeName` | `vendor_name` |
| `awardContractData.naicsCode` | `naics_code` |
| `awardContractData.productOrServiceCode` | `psc_code` |
| `awardContractData.typeOfSetAsideCode` | `set_aside_type` |
| `awardContractData.typeOfContractCode` | `type_of_contract` |
| `awardContractData.extentCompetedCode` | `extent_competed` |
| `awardContractData.numberOfOffersReceived` | `number_of_offers` |
| `awardContractData.dollarsObligated` | `dollars_obligated` |
| `awardContractData.baseAndAllOptionsValue` | `base_and_all_options` |
| `awardContractData.dateSignedFormat.dateSignedShortFormat` | `date_signed` (parse MM/DD/YYYY) |
| `awardContractData.effectiveDate` | `effective_date` (parse MM/DD/YYYY) |
| `awardContractData.completionDate` | `completion_date` (parse MM/DD/YYYY) |
| `awardContractData.lastModifiedDate` | `last_modified_date` (parse MM/DD/YYYY) |
| `awardContractData.placeOfPerformance.stateCode` | `pop_state` |
| `awardContractData.placeOfPerformance.countryCode` | `pop_country` |
| `awardContractData.placeOfPerformance.zipCode` | `pop_zip` |
| `awardContractData.far1102ExceptionCode` | `far1102_exception_code` |
| `awardContractData.contractDescription` | `description` |

## Modification Handling
- Same `contractNumber` can have multiple rows (mod 0, 1, 2...)
- DB PK is composite: `(contract_id, modification_number)`
- Each modification is a separate record
- For prospecting: want latest modification (highest mod number) for current status

## Date Format
- API returns dates as `MM/DD/YYYY` in `dateSignedShortFormat`
- Also `effectiveDate` and `completionDate` in `MM/DD/YYYY`
- Filter params use `YYYYMMDD` format (no separators)

## Key Fields for Capture Management
- `numberOfOffersReceived` (int) — ONLY public source for bidder count
- `far1102ExceptionCode` — classified contract indicator
- `extentCompetedCode` — competition type
- `coBusSizeDeterminationName` — small/large business determination
