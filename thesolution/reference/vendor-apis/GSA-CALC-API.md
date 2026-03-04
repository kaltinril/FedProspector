# GSA CALC+ Quick Rate API v3

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.gsa.gov/acquisition/calc/v3/api/ceilingrates/` |
| **Auth** | None required |
| **Rate Limit** | None (effectively unlimited) |
| **Pagination** | Page-based (`page=1`, `page_size=100`), but limited by Elasticsearch `max_result_window` of 10,000 |
| **Backend** | Elasticsearch |
| **Data Format** | JSON (Elasticsearch response format) |
| **Total Records** | ~230,000 labor rates |
| **Update Frequency** | Nightly refresh |
| **Our CLI Command** | `python main.py load calc` |
| **Client File** | `fed_prospector/api_clients/calc_client.py` |
| **Loader File** | `fed_prospector/etl/calc_loader.py` |
| **OpenAPI Spec** | N/A (docs at https://open.gsa.gov/api/calc/) |

## Purpose & Prospecting Value

The CALC+ (Contract Awarded Labor Category) Quick Rate API provides awarded ceiling rates on GSA professional services schedules. It contains approximately 230,000 labor rate records from contractors with GSA Schedule contracts, covering labor categories like "Software Developer," "Project Manager," and "Systems Engineer" across all GSA service schedules.

For WOSB and 8(a) federal contract prospecting, CALC+ data is essential for **proposal pricing intelligence**. Before bidding on a contract, you need to know the market rate range for each labor category. CALC+ provides the actual awarded ceiling rates (the maximum a contractor can charge), giving you benchmarks to price competitively. You can filter by `business_size` to compare small business rates versus large business rates, and by `security_clearance` to understand the premium for cleared positions.

The API is also valuable for **competitive analysis**. By searching for specific contractors (`vendor_name`), you can see their full rate card across all labor categories. Combined with award data from USASpending and SAM.gov, this enables a complete picture of competitor pricing and capability. The data refreshes nightly, so rates are always current. Since there are no rate limits or authentication requirements, it is freely available for unlimited analysis.

## Query Parameters

### Search Parameters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `keyword` | string | `software developer` | Labor category text search (Elasticsearch full-text match) |
| `page` | int | `1` | 1-based page number |
| `page_size` | int | `100` | Results per page. Default 100, max 10,000 |
| `sort` | string | `asc` | Sort direction: `asc` or `desc` |
| `ordering` | string | `vendor_name` | Sort field. Options: `vendor_name`, `labor_category`, `id`, `schedule`, `education_level`, `worksite`, `security_clearance`, `min_years_experience`. Default sorts by `current_price`. |

### Pagination

Page-based pagination backed by Elasticsearch:
- `page`: 1-based page number
- `page_size`: Records per page (default 100, max 10,000)
- **Hard limit**: `page * page_size` must not exceed **10,000** (ES `max_result_window`)

This means a single sorted query can return at most 10,000 records. Since the full dataset contains ~230,000 records, a special multi-query strategy is required for full extraction (see "Our Loading Strategy" below).

## Response Structure

The API returns raw Elasticsearch responses:

```json
{
  "hits": {
    "total": {
      "value": 10000,
      "relation": "gte"
    },
    "hits": [
      {
        "_id": "abc123",
        "_source": {
          "labor_category": "Software Developer - Senior",
          "education_level": "Bachelors",
          "min_years_experience": 8,
          "current_price": 185.50,
          "next_year_price": 190.25,
          "second_year_price": 195.00,
          "schedule": "OASIS SB",
          "vendor_name": "ACME SOLUTIONS LLC",
          "sin": "541611,541512",
          "business_size": "s",
          "security_clearance": "Top Secret",
          "worksite": "Both",
          "contract_start": "2023-01-01",
          "contract_end": "2028-12-31",
          "idv_piid": "47QRAA23D0001",
          "category": "IT Services",
          "subcategory": "Software Development"
        }
      }
    ]
  },
  "aggregations": {
    "wage_stats": {
      "count": 230000,
      "min": 15.0,
      "max": 650.0,
      "avg": 125.75,
      "sum": 28923750.0
    }
  }
}
```

### Key Response Fields

| Field | Type | DB Column | Notes |
|-------|------|-----------|-------|
| `_id` | string | -- | Elasticsearch document ID (used for dedup) |
| `labor_category` | string | `labor_category` | Labor category title (max 200 chars) |
| `education_level` | string | `education_level` | Required education (max 50 chars) |
| `min_years_experience` | int | `min_years_experience` | Minimum years experience |
| `current_price` | float | `current_price` | Current ceiling rate ($/hr) |
| `next_year_price` | float | `next_year_price` | Next year ceiling rate |
| `second_year_price` | float | `second_year_price` | Year after next ceiling rate |
| `schedule` | string | `schedule` | GSA Schedule name (max 200 chars) |
| `vendor_name` | string | `contractor_name` | Contractor company name (max 200 chars) |
| `sin` | string | `sin` | Schedule Item Number(s), can be multi-line comma-separated |
| `business_size` | string | `business_size` | `s` (small) or `o` (other/large) (max 10 chars) |
| `security_clearance` | string | `security_clearance` | Required clearance level (max 50 chars); can be boolean `false`/`true` |
| `worksite` | string | `worksite` | `Contractor`, `Customer`, or `Both` (max 100 chars) |
| `contract_start` | string | `contract_start` | Contract start date |
| `contract_end` | string | `contract_end` | Contract end date |
| `idv_piid` | string | `idv_piid` | IDV contract number (max 50 chars) |
| `category` | string | `category` | High-level service category (max 200 chars) |
| `subcategory` | string | `subcategory` | Service subcategory (max 500 chars) |

### Total Count

The `hits.total.value` field caps at 10,000 when `relation` is `"gte"`. To get the true total count, use `aggregations.wage_stats.count` which returns the actual number of matching documents.

## Known Issues & Quirks

1. **Elasticsearch `max_result_window` = 10,000** -- The most critical quirk. A single query (regardless of pagination) can only access the first 10,000 results in a given sort order. Requesting `page * page_size > 10,000` fails. To retrieve the full ~230K dataset, our client uses 18 different sort orderings and de-duplicates by `_id`.

2. **`hits.total.value` caps at 10,000** -- When total matches exceed 10,000, the response shows `{"value": 10000, "relation": "gte"}`. Use `aggregations.wage_stats.count` for the true total.

3. **`security_clearance` can be boolean** -- Some records return `false` or `true` instead of a string like "Top Secret". The loader coerces all string fields with `str()` to handle this.

4. **`sin` values can be multi-line** -- SIN (Schedule Item Number) values sometimes contain newlines and commas (e.g., `"541611,541930,\n611430"`). The loader collapses these to single-line comma-separated values.

5. **No documented rate limits** -- The API has no authentication and no documented rate limits. Our client sets `max_daily_requests=999999` to disable rate limit tracking.

6. **Record count discrepancy vs documentation** -- The research doc (Phase 1) noted ~51,863 records, but the live API contains ~230,000. The 51K figure may have been for a filtered keyword search. The full dataset requires the multi-sort strategy.

7. **Response is raw Elasticsearch format** -- Unlike typical REST APIs, the response uses Elasticsearch's native `hits.hits[]._source` nesting, not a simple `results` array.

## Our Loading Strategy

### The 10K Window Problem

Elasticsearch limits any single query to 10,000 results. The full CALC+ dataset contains ~230,000 records. To retrieve all records, we use a **multi-sort de-duplication strategy**:

1. Issue 18 separate queries, each with a different `(ordering, sort)` combination:
   - `vendor_name asc`, `vendor_name desc`
   - `labor_category asc`, `labor_category desc`
   - `id asc`, `id desc`
   - `schedule asc`, `schedule desc`
   - `education_level asc`, `education_level desc`
   - `worksite asc`, `worksite desc`
   - `security_clearance asc`, `security_clearance desc`
   - `min_years_experience asc`, `min_years_experience desc`
   - default (price) `asc`, default (price) `desc`

2. Each query requests the maximum 10,000 records (`page=1, page_size=10000`).

3. De-duplicate results by Elasticsearch `_id` field across all 18 queries.

4. Each sort order returns a different 10K slice of the data, and the overlaps are collapsed. This typically retrieves 100K-140K unique records (not the full 230K, but a substantial majority).

### Full Refresh Process

The `full_refresh()` method in the loader:
1. **TRUNCATE** the `gsa_labor_rate` table (safe here because the data is fully replaceable)
2. Call `CalcPlusClient.get_all_rates()` which executes the 18-query strategy
3. Batch-INSERT normalized records (1,000 per batch)
4. Total time: approximately 1 hour
5. Total API calls: 18

### Alternative: CSV Loading

The loader also supports `LOAD DATA INFILE` from a pre-downloaded CSV:
1. Convert CSV to TSV with normalized values
2. Execute `LOAD DATA INFILE` for maximum speed
3. Falls back to batch INSERT if FILE privilege is unavailable

### Refresh Schedule

- **Frequency**: Monthly (our schedule), though data refreshes nightly on GSA's side
- **Method**: Full refresh (TRUNCATE + reload via API)
- **Budget impact**: 18 API calls per load (unlimited budget)
- **No change detection**: Since data is fully refreshed (TRUNCATE + reload), SHA-256 hashing is not used for this source

## Data Quality Issues

- **Boolean values in string fields**: `security_clearance` can return `false`/`true` instead of descriptive strings. The loader coerces with `str()`.
- **Multi-line SIN values**: Collapsed to single-line comma-separated during normalization.
- **String truncation**: Labor categories, schedules, contractor names, and other string fields are truncated to fit DB column widths during normalization. Affected limits: `labor_category` 200, `education_level` 50, `schedule` 200, `contractor_name` 200, `sin` 500, `business_size` 10, `security_clearance` 50, `worksite` 100, `idv_piid` 50, `category` 200, `subcategory` 500.

## Cross-References

- **Related tables**: `gsa_labor_rate` (primary, auto-increment PK `id`)
- **Linking fields**: `contractor_name` (can be matched to `entity.legal_business_name`), `idv_piid` (links to IDV contract in `fpds_contract`), `business_size` (correlates with entity `business_type_string`), `naics_code` is not directly in the rate data but `sin` and `schedule` provide service category context
- **Alternative sources**: GovWin IQ (paid, $5K-$119K/year) provides similar pricing intelligence. CALC+ is the free, authoritative government source.
- **Complementary sources**: USASpending award amounts provide actual contract values to compare against CALC+ ceiling rates. SAM.gov Entity data provides contractor WOSB/8(a) certification status.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `page * page_size > 10000` error | Exceeded ES max_result_window | Use `page_size=10000, page=1` maximum. For full dataset, use `get_all_rates()` multi-sort strategy. |
| Only ~10K records returned | Single query hit ES window limit | Use `CalcPlusClient.get_all_rates()` instead of `search_rates_all()`. |
| `security_clearance` shows `False` | API returns boolean instead of string | Already handled by loader's `str()` coercion. |
| SIN field contains newlines | Multi-value SIN entries | Already handled by loader's newline-to-comma normalization. |
| Sort strategy fails | Specific ordering not supported for current data | Logged as warning, skipped. Other strategies compensate. |
| Low unique count after dedup | Many overlapping sort windows | Expected behavior. 18 strategies typically yield 100K-140K unique records. Adjust strategy list if needed. |
| Timeout during full load | Network issues during 18-query sequence | Set `timeout=120` (already configured). Retry the full_refresh command. |
| LOAD DATA INFILE fails | Missing FILE privilege on MySQL user | Falls back to batch INSERT automatically. Or grant: `GRANT FILE ON *.* TO 'fed_app'@'localhost'`. |
