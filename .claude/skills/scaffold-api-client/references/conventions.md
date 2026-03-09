# API Client Conventions

## BaseAPIClient Contract

### Constructor
`__init__(self, base_url, api_key, source_name, max_daily_requests)`

### HTTP Methods
- `self.get(endpoint, params)` — GET request with automatic rate limiting and retries
- `self.post(endpoint, json_body)` — POST request with automatic rate limiting and retries
- `self.get_binary(endpoint, params, stream=True)` — Binary download (for file endpoints)

### Rate Limiting
- Automatic via `_check_rate_limit()` and `_increment_rate_counter()` (only counts 200 responses)
- `_get_remaining_requests()` -> int (unused quota for today)
- Tracked in `etl_rate_limit` table per source_system per day

### Retry Logic
`_request_with_retry(method, url, params, max_retries=3, backoff_factor=2)`
- Retries on: 429, 5xx, ConnectionError, Timeout
- Does NOT retry on 4xx (except 429)
- Backoff: 2^n seconds between retries

### Date Helper
`_format_date(value, fmt="%Y-%m-%d")` — format dates consistently

### Logger
Auto-created as `self.logger` — use instead of module-level logger for instance methods

## Pagination via self.paginate()

### Parameters
| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| endpoint | str | required | API endpoint path |
| params | dict | required | Query parameters |
| page_size | int | 100 | Results per page |
| pagination_style | str | "offset" | "offset" or "page" |
| offset_param | str | "offset" | Query param name for offset |
| page_param | str | "page" | Query param name for page number |
| size_param | str | "limit" | Query param name for page size |
| offset_start | int | 0 | Starting offset value |
| page_start | int | 1 | Starting page number |
| total_key | str | None | Response key for total record count |
| results_key | str | None | Response key for results array |
| has_next_key | str | None | Response key for "has more" boolean |
| total_pages_key | str | None | Response key for total page count |

### End-of-Pagination Detection (3 strategies)
1. **`has_next_key`** — stop when `response[key]` is falsy (USASpending style)
2. **`total_pages_key`** — stop when page >= `response[key]`
3. **`total_key`** (default) — stop when offset >= `response[key]`

The method yields the results array (extracted via `results_key`) for each page.

## Rate Limit Table

- Table: `etl_rate_limit`
- Columns: `source_system`, `request_date`, `requests_made`, `max_requests`, `last_request_at`
- Base class manages this automatically — do NOT insert/update manually

## Dual-Key Pattern (SAM.gov)

Use when an API supports multiple API keys with different rate limits:

```python
def __init__(self, api_key_number=1):
    if api_key_number == 2:
        api_key = settings.SAM_API_KEY_2
        source_name = "MY_SOURCE_KEY2"
        limit = settings.MY_DAILY_LIMIT_2
    else:
        api_key = settings.SAM_API_KEY
        source_name = "MY_SOURCE"
        limit = settings.MY_DAILY_LIMIT
    super().__init__(
        base_url=settings.MY_BASE_URL,
        api_key=api_key,
        source_name=source_name,
        max_daily_requests=limit,
    )
```

## No-Auth Pattern

For public APIs that do not require authentication:

```python
super().__init__(
    base_url=settings.MY_BASE_URL,
    api_key="",
    source_name="MY_SOURCE",
    max_daily_requests=999999,
)
```

## Anti-Patterns

- Do NOT override `get()` or `post()` unless API requires special headers
- Do NOT hardcode API keys — always use `config.settings`
- Do NOT implement custom pagination if `self.paginate()` fits
- Do NOT increment rate counter manually — base class handles it
- Do NOT catch and swallow exceptions — log + re-raise or return None
- Always use `.get()` with defaults on response dicts (e.g., `data.get("field", "")`)

## Canonical Examples

| Client | File | Notes |
|--------|------|-------|
| SAM Opportunity | `fed_prospector/api_clients/sam_opportunity_client.py` | Dual-key, paginated |
| USASpending | `fed_prospector/api_clients/usaspending_client.py` | POST-based pagination |
| GSA CALC | `fed_prospector/api_clients/calc_client.py` | No-auth, simple GET |
