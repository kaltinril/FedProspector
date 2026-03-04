# SAM.gov Opportunities API v2

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/opportunities/v2/search` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (free tier, no role), 1,000/day (with role) |
| **Pagination** | `limit`/`offset` (record offset), max `limit=1000` |
| **Data Format** | JSON |
| **Update Frequency** | Active notices daily, archived weekly |
| **Our CLI Command** | `python main.py load opportunities` |
| **Client File** | `fed_prospector/api_clients/sam_opportunity_client.py` |
| **Loader File** | `fed_prospector/etl/opportunity_loader.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/get-opportunities-v2.yaml` |

## Purpose & Prospecting Value

The SAM.gov Opportunities API is THE authoritative source for active federal contract solicitations -- RFPs, RFQs, RFIs, pre-solicitation notices, combined synopsis/solicitations, and sources sought. Every federal contract opportunity that is publicly posted flows through this API. For WOSB and 8(a) prospecting, this is the primary pipeline of actionable contract leads.

The API supports filtering by set-aside type, which makes it possible to directly target WOSB, EDWOSB, and 8(a) opportunities. By monitoring this API on a regular cadence (every 4 hours with a 1,000/day budget), the system can detect new postings within the same business day and surface them to users before competitors. The `typeOfSetAside` filter combined with NAICS code filtering produces a highly targeted feed of opportunities that match both the firm's certifications and capabilities.

Beyond active bidding, the Opportunities API data enables competitive intelligence: tracking which agencies consistently post WOSB/8(a) solicitations, identifying recompete patterns (same agency + NAICS + PSC recurring annually), and monitoring award decisions to build incumbent intelligence. When an opportunity transitions from "active" to "awarded", the `award` object in the response reveals the winner's UEI, name, and award amount -- feeding directly into competitor analysis.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `typeOfSetAside` | string | `WOSB` | Set-aside code. **Only ONE value per request.** |
| `postedFrom` | string | `01/01/2026` | Start date (required with `limit`). `MM/dd/yyyy` format. |
| `postedTo` | string | `03/01/2026` | End date (required with `limit`). `MM/dd/yyyy` format. |
| `ncode` | string | `541511` | NAICS code filter (max 6 digits). |
| `ccode` | string | `D302` | PSC classification code filter. |
| `ptype` | string/array | `o` | Procurement type: `o`=solicitation, `k`=combined, `p`=presolicitation, `r`=sources sought. |
| `state` | string | `VA` | Place of performance state code. |
| `zip` | string | `22030` | Place of performance ZIP code. |
| `organizationCode` | string | `3600` | Agency/organization code. |
| `title` | string | `IT support` | Opportunity title search string. |
| `solnum` | string | `W52P1J-26-R-0001` | Solicitation number. |
| `noticeid` | string | `abc123...` | Unique notice ID for single-record lookup. |
| `rdlfrom` | string | `01/01/2026` | Response deadline from date. |
| `rdlto` | string | `03/01/2026` | Response deadline to date. |
| `limit` | string | `1000` | Records per page (max 1000). Required. |
| `offset` | string | `0` | Record offset for pagination. Required. |

### WOSB/8(a) Set-Aside Codes

| Code | Description | Priority |
|------|-------------|----------|
| `WOSB` | Women-Owned Small Business Program Set-Aside | Tier 1 |
| `EDWOSB` | Economically Disadvantaged WOSB Set-Aside | Tier 1 |
| `8A` | 8(a) Set-Aside | Tier 1 |
| `8AN` | 8(a) Sole Source | Tier 1 |
| `SBA` | Total Small Business Set-Aside | Tier 2 |
| `HZC` | HUBZone Set-Aside | Tier 2 |
| `SDVOSBC` | Service-Disabled Veteran-Owned SB Set-Aside | Tier 2 |
| `SBP` | Partial Small Business Set-Aside | Tier 2 |
| `WOSBSS` | WOSB Program Sole Source | Tier 3 |
| `EDWOSBSS` | EDWOSB Program Sole Source | Tier 3 |
| `HZS` | HUBZone Sole Source | Tier 3 |
| `SDVOSBS` | SDVOSB Sole Source | Tier 3 |

### Pagination

The Opportunities API uses **record offset** pagination (not page-based):

- `offset=0, limit=1000` returns records 0-999
- `offset=1000, limit=1000` returns records 1000-1999
- Continue until returned records < limit or `totalRecords` is reached

The response includes `totalRecords` indicating the total result count for the query. Our client (`SAMOpportunityClient`) handles pagination automatically via the `BaseAPIClient.paginate()` method.

### Date Filtering

- **Format**: `MM/dd/yyyy` (e.g., `01/15/2026`)
- **Required**: `postedFrom` and `postedTo` are required when using `limit`
- **Maximum range**: 1 year (but see Quirk #1 below -- actually 364 days)
- **Date chunking**: Our client automatically splits ranges longer than 364 days into consecutive chunks

## Response Structure

```json
{
  "totalRecords": 42,
  "opportunitiesData": [
    {
      "noticeId": "abc123def456...",
      "title": "IT Professional Services",
      "solicitationNumber": "W52P1J-26-R-0001",
      "fullParentPathName": "DEPT OF DEFENSE.DEPT OF THE ARMY.W7MR ARMY",
      "fullParentPathCode": "097.021.W7MR",
      "postedDate": "2026-01-15",
      "type": "Solicitation",
      "baseType": "Solicitation",
      "archiveType": "autocustom",
      "archiveDate": "2026-04-15",
      "typeOfSetAsideDescription": "Women-Owned Small Business (WOSB) Program Set-Aside (FAR 19.15)",
      "typeOfSetAside": "WOSB",
      "responseDeadLine": "2026-02-15T17:00:00-05:00",
      "naicsCode": "541511",
      "classificationCode": "D302",
      "active": "Yes",
      "description": "https://api.sam.gov/opportunities/v1/noticedesc?noticeid=abc123...",
      "organizationType": "OFFICE",
      "officeAddress": {
        "city": "Rock Island",
        "state": "IL",
        "zipcode": "61299"
      },
      "placeOfPerformance": {
        "city": { "code": "12345", "name": "Springfield" },
        "state": { "code": "VA", "name": "Virginia" },
        "zip": "22030",
        "country": { "code": "USA", "name": "UNITED STATES" }
      },
      "pointOfContact": [
        {
          "fax": "",
          "type": "primary",
          "email": "contract.officer@army.mil",
          "phone": "309-782-1234",
          "title": "Contracting Officer",
          "fullName": "Jane Smith"
        }
      ],
      "award": {
        "date": "2026-03-01",
        "number": "W52P1J-26-C-0001",
        "amount": "1500000.00",
        "awardee": {
          "name": "Acme Solutions LLC",
          "ueiSAM": "XYZ789ABC123",
          "location": { "city": { "name": "Reston" }, "state": { "code": "VA" } }
        }
      },
      "resourceLinks": ["https://sam.gov/opp/..."],
      "link": [
        { "rel": "self", "href": "https://api.sam.gov/opportunities/v2/search?noticeid=..." }
      ]
    }
  ]
}
```

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `noticeId` | string | Unique identifier for the opportunity |
| `solicitationNumber` | string | The official solicitation number |
| `fullParentPathName` | string | Dot-separated agency hierarchy (see Quirk #4) |
| `typeOfSetAside` | string | Set-aside code (WOSB, 8A, etc.) |
| `naicsCode` | string | NAICS code for the work |
| `classificationCode` | string | PSC code |
| `description` | string | **A URL, not text** (see Quirk #5) |
| `award` | object | Populated when opportunity is awarded |
| `placeOfPerformance.state.code` | string | May contain ISO 3166-2 codes > 2 chars for foreign POP |
| `active` | string | "Yes" or "No" |

## Known Issues & Quirks

1. **365-day range rejection**: The API rejects date ranges of exactly 365 days with the error "Date range must be null year(s) apart." Our client uses a maximum of 364 days per chunk (`MAX_DATE_RANGE_DAYS = 364`) to stay safely under the limit.

2. **Only ONE set-aside per request**: The `typeOfSetAside` parameter accepts only a single value. To search across WOSB, EDWOSB, 8A, and 8AN, you must make 4 separate API calls. Our client's `_search_multiple_set_asides()` method handles this with deduplication by `noticeId`.

3. **Feb 29 rejection**: The API rejects February 29 as a start date in leap years. Our historical loader skips leap day.

4. **`fullParentPathName` is dot-separated**: The agency hierarchy comes as a single dot-separated string (e.g., `"DEPT OF DEFENSE.DEPT OF THE ARMY.W7MR ARMY"`), not as separate department/subTier/office fields. The loader must parse this to extract department, sub-tier, and office.

5. **`description` is a URL, not text**: The description field contains a URL pointing to the full notice description, not the actual text. Fetching the full text requires a separate authenticated request.

6. **`pop_state` can contain long ISO codes**: For foreign places of performance, `placeOfPerformance.state.code` can contain ISO 3166-2 subdivision codes longer than 2 characters (e.g., `IN-MH` for Maharashtra, India). Our DB column is `VARCHAR(6)` to accommodate this.

7. **Date format is MM/dd/yyyy**: Not ISO 8601. All date parameters must use `MM/dd/yyyy` format (e.g., `01/15/2026`).

## Our Loading Strategy

### Daily Refresh (Primary)

- **Frequency**: Every 4 hours (6 times/day with 1,000/day budget)
- **Method**: Query by `postedFrom`/`postedTo` for the current day, cycling through priority set-aside codes
- **Budget**: 6-72 calls/day depending on how many set-aside codes are queried
- **Priority order**: WOSB, EDWOSB, 8A, 8AN are queried first (Tier 1), then SBA, HZC, SDVOSBC, SBP (Tier 2), then sole-source variants (Tier 3)

### Historical Load (Initial)

- **Frequency**: Once, at setup
- **Method**: API pagination over 2-year date range, split into 364-day chunks
- **Budget**: 3-5 days at 10/day; 1 day at 1,000/day
- **Resumable**: The loader supports `--start-page` and `--max-calls` for resuming interrupted loads

### Call Budget Management

The `SAMOpportunityClient` has a per-invocation call budget (default 5) that limits how many API calls the multi-set-aside convenience methods will make. This reserves half of the 10/day free-tier quota for entity and other API work. Set-aside types are queried in priority order so the most important ones complete first if the budget runs out.

### Page-by-Page Resumable Loading

The `iter_opportunity_pages()` method yields `(opps_list, page_number, total_records)` tuples, allowing the loader to save progress after each page and resume from the last completed page on the next run.

## Data Quality Issues

- **Issue #13**: `fullParentPathName` is dot-separated, not separate fields. Parsed during load.
- **Issue #14**: `description` field is a URL, not text. Stored as-is; full text fetch is deferred.
- **Issue #15**: Rejects date ranges of exactly 365 days. Handled by 364-day max chunks.
- **Issue #16**: Rejects Feb 29 as start date. Historical loader skips leap day.
- **Issue #17**: `pop_state` can contain ISO 3166-2 codes > 2 chars. Column widened to `VARCHAR(6)`.

## Cross-References

- **Related tables**: `opportunity` (main), `stg_opportunity_raw` (staging)
- **Linking fields**: `notice_id` (unique key), `solicitation_number` (links to awards), `naics_code` (links to `naics_code` reference), `classification_code` (links to `psc_code` reference), `awardee_uei` (links to `entity.uei_sam`)
- **Alternative sources**: None -- SAM.gov Opportunities API is the single authoritative source for active federal solicitations
- **Related APIs**: SAM.gov Contract Awards API (historical award data for the same solicitations), USASpending.gov (spending data for awarded contracts)

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Date range must be null year(s) apart" | Date range >= 365 days | Reduce to 364-day max chunks (automatic in our client) |
| `RateLimitExceeded` | Hit daily API call limit | Wait until next day, or switch to API key 2 (`--key=2`) |
| HTTP 403 | Invalid or expired API key | Regenerate key at api.data.gov; keys expire every 90 days |
| Empty `opportunitiesData` with `totalRecords > 0` | API inconsistency | Logged as warning; retry on next scheduled run |
| `totalRecords` returns 0 for known solicitation | Solicitation may be archived or date range wrong | Widen `postedFrom`/`postedTo` range |
| `description` URL returns 403 | Full text requires System Account auth | Use Public API; store URL, not text |
