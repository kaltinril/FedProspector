# USASpending.gov API v2

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.usaspending.gov/` (multiple endpoints) |
| **Auth** | None required |
| **Rate Limit** | None (effectively unlimited) |
| **Pagination** | Page-based (`page=1`, `page=2`, ...), max 100 per page for search; up to 5,000 for transactions |
| **Data Format** | JSON (API), CSV (bulk downloads) |
| **Update Frequency** | Regular (sourced from FPDS and agency systems) |
| **Coverage** | FY2008 to present |
| **Our CLI Command** | `python main.py load spending` |
| **Client File** | `fed_prospector/api_clients/usaspending_client.py` |
| **Loader File** | `fed_prospector/etl/usaspending_loader.py` |
| **OpenAPI Spec** | N/A (docs at https://api.usaspending.gov) |

## Purpose & Prospecting Value

USASpending.gov is the U.S. government's official source for federal spending data, covering all awards from FY2008 to present. For contract prospecting, it provides comprehensive historical award data that answers critical business development questions: Who won similar contracts? For how much? Under which set-aside? How does spending trend over time for a given NAICS or agency?

The key advantage over SAM.gov's Contract Awards API is that USASpending has **no rate limits and no authentication requirements**. This makes it ideal for bulk analysis, incumbent research, and competitive intelligence. You can run thousands of queries per day without worrying about API budgets. It also offers bulk CSV downloads for entire fiscal years, enabling offline analysis of millions of records.

For WOSB and 8(a) prospecting specifically, USASpending enables: (1) **Incumbent analysis** -- find who won the previous contract before a rebid appears on SAM.gov; (2) **Spending trends** -- identify which agencies and NAICS codes have growing WOSB/8(a) set-aside spending; (3) **Burn rate analysis** -- track per-modification funding timelines to understand contract execution patterns; (4) **Competitive intelligence** -- identify top recipients by category to understand the competitive landscape; (5) **Rebid prediction** -- find contracts with end dates 6-12 months out that will likely be rebid. It also serves as an alternative subaward data source via CSV bulk downloads (free, no rate limits, but with 30-60 day data lag compared to SAM.gov's Subaward API).

## Endpoints

### Award Search
| Property | Value |
|----------|-------|
| **URL** | `POST /api/v2/search/spending_by_award/` |
| **Purpose** | Search contract awards with filters |
| **Max per page** | 100 |
| **Pagination** | `page` (1-based), `limit` |

### Award Detail
| Property | Value |
|----------|-------|
| **URL** | `GET /api/v2/awards/{generated_unique_award_id}/` |
| **Purpose** | Full award details by ID |
| **Notes** | Contains fields not available in search results (NAICS, PSC, solicitation ID, set-aside description, parent recipient) |

### Spending by Category
| Property | Value |
|----------|-------|
| **URL** | `POST /api/v2/search/spending_by_category/{category}/` |
| **Purpose** | Aggregate spending by recipient, agency, NAICS, PSC, etc. |
| **Categories** | `recipient`, `awarding_agency`, `naics`, `psc`, `awarding_subagency` |

### Transactions
| Property | Value |
|----------|-------|
| **URL** | `POST /api/v2/transactions/` |
| **Purpose** | Per-modification funding timeline for burn rate analysis |
| **Max per page** | 5,000 |
| **Pagination** | `page` (1-based), `limit` |

### Bulk Download
| Property | Value |
|----------|-------|
| **URL** | `POST /api/v2/bulk_download/awards/` |
| **Purpose** | Request bulk CSV download for a fiscal year |
| **Archive** | `https://www.usaspending.gov/download_center/award_data_archive` |
| **Coverage** | FY2008-present |

## Query Parameters

### Award Search Filters (POST body)

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `award_type_codes` | array | `["A","B","C","D"]` | Contract types: A=BPA Call, B=Purchase Order, C=Delivery Order, D=Definitive Contract |
| `naics_codes` | array | `["541512"]` | NAICS code filter |
| `psc_codes` | array | `["D302"]` | Product Service Code filter |
| `agencies` | array | `[{"type":"awarding","tier":"toptier","name":"..."}]` | Agency filter with type, tier, name |
| `time_period` | array | `[{"start_date":"2024-01-01","end_date":"2025-12-31"}]` | Date range (YYYY-MM-DD format) |
| `set_aside_type_codes` | array | `["WOSB"]` | Set-aside filter |
| `recipient_search_text` | array | `["Acme Corp"]` | Recipient name search |
| `keywords` | array | `["cybersecurity"]` | Free-text keyword search |

### Award Search Request Fields

Our client requests these fields from the search endpoint:

| Field | Maps to DB Column | Notes |
|-------|-------------------|-------|
| `Award ID` | `piid` | The contract PIID (not the unique award ID) |
| `Recipient Name` | `recipient_name` | |
| `Recipient UEI` | `recipient_uei` | |
| `Start Date` | `start_date` | |
| `End Date` | `end_date` | |
| `Award Amount` | `total_obligation` | |
| `Total Outlays` | -- | Not stored |
| `Description` | `award_description` | |
| `Contract Award Type` | `award_type` | |
| `Awarding Agency` | `awarding_agency_name` | |
| `Awarding Sub Agency` | `awarding_sub_agency_name` | |
| `Funding Agency` | `funding_agency_name` | |
| `NAICS Code` | `naics_code` | May be None in search; available via detail endpoint |
| `PSC Code` | `psc_code` | May be None in search; available via detail endpoint |
| `Type of Set Aside` | `type_of_set_aside` | |
| `generated_unique_award_id` | `generated_unique_award_id` | Often None in search; fallback to `generated_internal_id` |

### Pagination

Page-based pagination (not offset-based):
- `page`: 1-based page number
- `limit`: Records per page (max 100 for search, 5,000 for transactions)

The response includes `page_metadata`:
```json
{
  "page_metadata": {
    "page": 1,
    "hasNext": true,
    "total": 5432,
    "limit": 100
  }
}
```

Stop when `hasNext` is `false`.

## Response Structure

### Award Search Response
```json
{
  "results": [
    {
      "Award ID": "W911NF-25-C-0001",
      "Recipient Name": "ACME CORP",
      "Recipient UEI": "ABC123DEF456",
      "Award Amount": 1500000.00,
      "Start Date": "2025-01-15",
      "End Date": "2026-01-14",
      "Contract Award Type": "D",
      "Awarding Agency": "Department of Defense",
      "NAICS Code": "541512",
      "Type of Set Aside": "WOSB",
      "generated_internal_id": "CONT_AWD_W911NF25C0001_9700_W911NF_9700"
    }
  ],
  "page_metadata": {
    "page": 1,
    "hasNext": true,
    "total": 342,
    "limit": 100
  }
}
```

### Award Detail Response
Contains deeply nested data including:
- `recipient.parent_recipient_name`, `recipient.parent_recipient_uei`
- `naics_hierarchy.base_code.code`, `naics_hierarchy.base_code.description`
- `psc_hierarchy.base_code.code`
- `latest_transaction_contract_data.type_of_set_aside`, `.solicitation_identifier`
- `place_of_performance.state_code`, `.location_country_code`, `.zip5`, `.city_name`
- `period_of_performance.last_modified_date`

### Transaction Response
```json
{
  "results": [
    {
      "action_date": "2025-01-15",
      "modification_number": "0",
      "action_type": "A",
      "action_type_description": "New Award",
      "federal_action_obligation": 500000.00,
      "description": "Initial funding"
    }
  ],
  "page_metadata": { "page": 1, "hasNext": true, "total": 25, "limit": 5000 }
}
```

## Known Issues & Quirks

1. **`generated_unique_award_id` is often None in search results** -- The requested field returns None. The loader falls back to `generated_internal_id` (which is always populated and equals `generated_unique_award_id` from the detail endpoint). Format: `CONT_AWD_{piid}_{agency}_{parent_piid}_{parent_agency}`.

2. **"Award ID" is actually the PIID** -- In search results, the field labeled `Award ID` is the contract number (PIID), not a unique identifier. The actual unique key is `generated_internal_id`.

3. **Several fields are None in search results** -- `NAICS Code`, `PSC Code`, `solicitation_identifier`, `type_of_set_aside_description`, `recipient_parent_name`, and `last_modified_date` may only be available from the award detail endpoint. Use `enrich_from_detail()` to fill these in when needed.

4. **All search endpoints use POST** -- Unlike most REST APIs, all USASpending search endpoints accept POST requests with a JSON body, not GET with query parameters. The detail endpoint (`/api/v2/awards/{id}/`) uses GET.

5. **Date format is YYYY-MM-DD** -- Unlike SAM.gov APIs which use various date formats, USASpending consistently uses ISO 8601 date format.

6. **No rate limits means no rate tracking needed** -- Our client sets `max_daily_requests=999999` to effectively disable rate limit checking.

## Our Loading Strategy

### Primary Use: Incumbent Research & Competitive Intelligence
USASpending is not loaded in bulk as our primary award data source (that role belongs to SAM.gov Contract Awards via FPDS data). Instead, it is used for:
- On-demand incumbent searches (`search_incumbent()`)
- Aggregate spending analysis (`get_spending_by_category()`)
- Top recipient identification (`get_top_recipients()`)
- Burn rate analysis via transaction loading (`load_transactions()`, `calculate_burn_rate()`)

### Award Loading
- **Method**: API pagination via `search_awards_all()` generator
- **Change detection**: SHA-256 hashing on 28 business-meaningful fields
- **Upsert**: `INSERT ... ON DUPLICATE KEY UPDATE` on `generated_unique_award_id`
- **Batch size**: 500 records per commit
- **Enrichment**: Detail endpoint called per award for fields missing from search results

### Transaction Loading (Burn Rate)
- **Method**: `get_all_transactions()` generator, paginated at 5,000/page
- **Dedup**: `INSERT IGNORE` with unique key on `(award_id, modification_number, action_date)`
- **Use case**: Build monthly obligation timeline for burn rate calculation

### Bulk Download
- **CSV archive**: `https://www.usaspending.gov/download_center/award_data_archive`
- **Coverage**: FY2008-present, downloadable by fiscal year
- **Use case**: Historical bulk analysis when API pagination would take too long
- **Time estimate**: 2-4 hours per fiscal year to download and process

### Refresh Schedule
- **Frequency**: Monthly (per our refresh schedule)
- **Rate impact**: 0 (no rate limits)
- **Method**: Bulk CSV download preferred for large loads; API for incremental updates

## Data Quality Issues

No major data quality issues have been found specific to USASpending data. The API returns clean, well-structured JSON with consistent field naming. Key considerations:
- Some fields from the search endpoint are incomplete and require a follow-up detail endpoint call
- Dollar amounts are returned as numbers (not strings), so no parsing issues
- Dates are consistently YYYY-MM-DD format

## Cross-References

- **Related tables**: `usaspending_award` (primary), `usaspending_transaction` (detail), `fpds_contract` (overlapping award data from SAM.gov)
- **Linking fields**: `generated_unique_award_id` (PK), `piid` (links to FPDS `contract_id`), `recipient_uei` (links to `entity.uei_sam`), `naics_code` (links to `naics_code` reference table), `solicitation_identifier` (links to `opportunity.solicitation_number`)
- **Alternative sources**: SAM.gov Contract Awards API provides similar award data but with rate limits. FPDS ATOM Feed has the deepest history. USASpending data is sourced from FPDS and agency systems.
- **Complementary sources**: SAM.gov Subaward API for subcontract data; GSA CALC+ for pricing context on awards

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| Empty `results` array | No matching awards for filters | Broaden search criteria. Check date range covers the target period. |
| `generated_unique_award_id` is None | Field not populated in search results | Use `generated_internal_id` as fallback (our loader does this automatically). |
| NAICS/PSC codes are None | Not available in search results | Call `get_award(award_id)` detail endpoint and use `enrich_from_detail()`. |
| Timeout on large searches | Query too broad | Add more specific filters (NAICS, agency, date range). Default timeout is 60 seconds. |
| Bulk download returns `status_url` instead of `file_url` | Download is being prepared asynchronously | Poll the `status_url` until the file is ready. |
| `422 Unprocessable Entity` | Malformed filter body | Verify `award_type_codes` is a list, `time_period` format matches expected schema. |
| Missing burn rate data | No transactions loaded for this award | Run `load spending --transactions --award-id={id}` to load transaction history first. |

## Additional Endpoints Worth Considering

USASpending.gov exposes **228 endpoints** across 18 categories. We use 5. Of the remaining 223, here are the ones relevant to contract prospecting. The rest (179 endpoints covering disaster funding, budget compliance, reporting, financial balances, treasury accounts, etc.) can be browsed at https://api.usaspending.gov/docs/endpoints.

| Status | Count | Description |
|--------|-------|-------------|
| **Currently Using** | 5 | Documented above |
| **Recommended** | 19 | High prospecting value |
| **Nice-to-Have** | 25 | Useful for UI or future analysis |
| **Not Relevant** | 179 | Disaster, budget, compliance, reporting |

### Recommended Additions (19 endpoints)

#### Recipient Intelligence

| Endpoint | Method | What It Gives Us |
|----------|--------|-----------------|
| `/api/v2/recipient/{hash}/` | GET | Full recipient profile — total awards, counts by type, % of spending |
| `/api/v2/recipient/children/{uei}/` | GET | Subsidiaries/child companies of a parent (teaming partner analysis) |
| `/api/v2/recipient/count/` | POST | Count recipients matching filters |
| `/api/v2/recipient/state/{fips}/` | GET | State-level award breakdown for geographic targeting |
| `/api/v2/recipient/state/awards/{fips}/` | GET | Award category breakdown by state |

#### IDV/IDIQ Analysis

Critical for task order prospecting — drill into IDIQ vehicles to find individual task orders.

| Endpoint | Method | What It Gives Us |
|----------|--------|-----------------|
| `/api/v2/idvs/awards/` | POST | List task orders/contracts under an IDIQ vehicle |
| `/api/v2/idvs/amounts/{id}/` | GET | IDV total amounts and child award counts |
| `/api/v2/idvs/activity/` | POST | Child and grandchild award activity timeline |
| `/api/v2/idvs/funding_rollup/` | POST | Aggregated funding across all contracts under an IDV |
| `/api/v2/idvs/funding/` | POST | File C funding records for an IDV |

#### Search & Analytics

| Endpoint | Method | What It Gives Us |
|----------|--------|-----------------|
| `/api/v2/search/spending_by_geography/` | POST | Geographic spending heatmap data for market analysis |
| `/api/v2/search/spending_over_time/` | POST | Time series for trend charts (UI Phase 20+) |
| `/api/v2/search/spending_by_award_count/` | POST | Award counts by type (contracts, IDVs, grants, etc.) |
| `/api/v2/subawards/` | POST | Subaward records (different data angle than SAM subaward API) |

#### Reference Data

| Endpoint | Method | What It Gives Us |
|----------|--------|-----------------|
| `/api/v2/references/toptier_agencies/` | GET | Full agency list with codes — for dropdowns and reference |
| `/api/v2/references/naics/{code}/` | GET | NAICS hierarchy with spending data attached |
| `/api/v2/references/filter_tree/psc/` | GET | PSC hierarchy tree for classification |

#### UI Autocomplete (Phase 20+)

Will power search typeaheads in the React UI.

| Endpoint | Method | What It Gives Us |
|----------|--------|-----------------|
| `/api/v2/autocomplete/recipient/` | POST | Recipient name/UEI autocomplete |
| `/api/v2/autocomplete/naics/` | POST | NAICS code autocomplete |
| `/api/v2/autocomplete/psc/` | POST | PSC code autocomplete |
| `/api/v2/autocomplete/awarding_agency/` | POST | Awarding agency autocomplete |

### Nice-to-Have (25 endpoints)

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/api/v2/search/new_awards_over_time/` | POST | New award trends by time period |
| `/api/v2/search/spending_by_category/country/` | POST | International contract spending |
| `/api/v2/search/spending_by_category/county/` | POST | County-level spending breakdown |
| `/api/v2/search/spending_by_category/district/` | POST | Congressional district spending |
| `/api/v2/search/spending_by_category/state_territory/` | POST | State/territory aggregation |
| `/api/v2/search/spending_by_category/funding_agency/` | POST | Spending by funding agency |
| `/api/v2/search/spending_by_category/funding_subagency/` | POST | Spending by funding sub-agency |
| `/api/v2/search/spending_by_category/cfda/` | POST | Spending by CFDA program |
| `/api/v2/search/spending_by_category/recipient_duns/` | POST | Spending by recipient DUNS |
| `/api/v2/search/transaction_spending_summary/` | POST | Transaction counts and obligation sums |
| `/api/v2/search/spending_by_subaward_grouped/` | POST | Subaward counts/obligations by prime award |
| `/api/v2/awards/last_updated/` | GET | Data freshness check |
| `/api/v2/awards/funding/` | POST | Federal account funding for an award |
| `/api/v2/awards/funding_rollup/` | POST | Aggregated agency/account funding |
| `/api/v2/awards/count/subaward/{id}/` | GET | Subaward count for an award |
| `/api/v2/awards/count/transaction/{id}/` | GET | Transaction count for an award |
| `/api/v2/bulk_download/list_monthly_files/` | POST | Available monthly bulk files |
| `/api/v2/bulk_download/status/` | GET | Bulk download job status |
| `/api/v2/bulk_download/list_agencies/` | POST | Agencies for bulk download |
| `/api/v2/download/contract/` | POST | Contract data as CSV |
| `/api/v2/download/awards/` | POST | Filtered awards as CSV |
| `/api/v2/download/status/` | GET | Download job status |
