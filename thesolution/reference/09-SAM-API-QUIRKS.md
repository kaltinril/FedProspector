# SAM.gov API Quirks

Validated 2026-02-28. Always validate with a live API call before bulk loading -- SAM.gov documentation is frequently wrong/outdated.

> **Per-API reference docs**: See `thesolution/reference/vendor-apis/` for detailed docs per data source (endpoint, auth, working vs broken filters, response structure, loading strategy, troubleshooting).

---

## Pagination Conventions (each sub-API is different)

| Sub-API | Params | Notes |
|---------|--------|-------|
| Opportunities | `limit`/`offset` | Record offset, max limit=1000 |
| Federal Hierarchy | `limit`/`offset` | Record offset, max limit=100 |
| Contract Awards | `limit`/`offset` | `offset` is a **PAGE INDEX** (not record offset). offset=0 is page 0, offset=1 is page 1 |
| Exclusions v4 | `size`/`page` | Max size=10 per page (extremely small) |
| Subawards | `size`/`page` | Max size=25 |

## Awards API

- **Param names**: `typeOfSetAsideCode` (not `typeOfSetAside`), `contractingDepartmentCode` (not `agencyCode`), `awardeeUniqueEntityId` (not `awardeeUEI`)
- **Date format**: `[MM/DD/YYYY,MM/DD/YYYY]` with square brackets (not ISO 8601)
- **Response key**: `awardSummary` (not `data`), `totalRecords` returned as **string** not int
- **Response structure**: Deeply nested -- `contractId.piid`, `coreData.federalOrganization`, `awardDetails.awardeeData.awardeeHeader`, `awardDetails.totalContractDollars`, `coreData.productOrServiceInformation.principalNaics[0].code`

## Exclusions API

- **Response structure**: Nested under `exclusionDetails`, `exclusionIdentification`, `exclusionActions.listOfActions[0]`, `exclusionOtherInformation`
- **Bulk load impractical**: 167K+ records at 10/page = 16,777+ API calls. Use as on-demand lookup only.

## Subawards API

- **Bulk load impractical**: 2.7M+ records. Not needed for core bidding workflow.
- **Response schema undocumented**: The OpenAPI spec defines response as bare `type: object` with no field definitions. Field structure is only documented on the GSA website (not in the YAML): [Acquisition](https://open.gsa.gov/api/acquisition-subaward-reporting-api/), [Assistance](https://open.gsa.gov/api/assistance-subaward-reporting-api/).
- **Dict vs scalar fields**: `recoveryModelQ1`, `recoveryModelQ2`, `primeNaics`, and `subAwardDescription` return as `{code, description}` objects from live API, but may appear as plain strings in test fixtures. Always use `isinstance(dict)` guards.
- **Foreign POP state codes**: For non-US addresses, `placeOfPerformance.state.code` is `null` and `state.name` contains the full name. US states use 2-char codes (e.g., "VA").


## General

- **Always validate with a live API call** before bulk loading -- documentation is frequently wrong/outdated.
