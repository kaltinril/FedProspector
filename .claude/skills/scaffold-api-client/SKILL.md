---
name: scaffold-api-client
description: "Scaffold a new vendor API client following FedProspect patterns: BaseAPIClient subclass with rate limiting, pagination, retry logic, and tests. Use this skill whenever the user wants to integrate a new external API, add a new data source, or create a new API client for a government data system. Usage: /scaffold-api-client <ClientName> <BaseURL>"
argument-hint: "<ClientName> <BaseURL> [--no-auth] [--paginated] [--dual-key]"
disable-model-invocation: true
---

# Scaffold API Client

## Arguments

Parse `$ARGUMENTS`:

| Argument | Example | Purpose |
|----------|---------|---------|
| ClientName | `FedBizOps` | PascalCase -> `FedBizOpsClient` class |
| BaseURL | `https://api.example.gov` | API base URL for settings |
| --no-auth | flag | No API key required (set key="" and limit=999999) |
| --paginated | flag | Include paginated search method |
| --dual-key | flag | Support dual API key selection (like SAM.gov) |

Derive names:
- Class: `{ClientName}Client`
- Module: `{client_name}_client.py` (snake_case)
- Source name: `{CLIENT_NAME}` (UPPER_SNAKE)
- Settings vars: `{CLIENT_NAME}_API_BASE_URL`, `{CLIENT_NAME}_API_KEY`, `{CLIENT_NAME}_DAILY_LIMIT`
- Test file: `tests/test_api_clients/test_{client_name}_client.py`

## Workflow

### Step 1: Read reference files
Read `references/conventions.md` for BaseAPIClient contract, rate limiting, and pagination patterns. Read `references/templates.md` for code templates.

### Step 2: Add settings
Add to `fed_prospector/config/settings.py`:
- `{CLIENT_NAME}_API_BASE_URL`
- `{CLIENT_NAME}_API_KEY` (skip if --no-auth)
- `{CLIENT_NAME}_DAILY_LIMIT`

Add corresponding entries to `fed_prospector/.env`.

### Step 3: Create client class
Create `fed_prospector/api_clients/{client_name}_client.py` using the template. The class MUST:
- Inherit from `BaseAPIClient`
- Call `super().__init__()` with base_url, api_key, source_name, max_daily_requests
- Implement at least one public method (e.g., `search()`, `get_by_id()`)
- If --paginated: implement `search_all()` generator using `self.paginate()` or manual loop
- If --dual-key: implement dual key selection in `__init__`

### Step 4: Create test file
Create `fed_prospector/tests/test_api_clients/test_{client_name}_client.py` with:
- Test construction (verify base_url, source_name, api_key)
- Test successful GET returns response
- Test API key added to params
- Test retry on 429 then success
- Test pagination yields all pages (if --paginated)
- Test fixture file in `tests/fixtures/` if needed

### Step 5: Verify
```bash
cd fed_prospector && python -c "from api_clients.{client_name}_client import {ClientName}Client; print('Import OK')"
python -m pytest tests/test_api_clients/test_{client_name}_client.py -v
```

## Conventions Summary

| Item | Pattern |
|------|---------|
| Base class | `BaseAPIClient` from `api_clients.base_client` |
| Rate limiting | Automatic via base class; tracks in `etl_rate_limit` table |
| Retries | `_request_with_retry()`: 3 retries, exponential backoff (2^n seconds) |
| Pagination | Use `self.paginate()` with `pagination_style`, `total_key`, `results_key` params |
| API key injection | Base class auto-adds `api_key` param to requests |
| Error handling | Catch `RateLimitExceeded` gracefully; let `HTTPError` propagate |
| Logging | Auto-created: `fed_prospector.api.{source_name}` |
| Test helper | `make_mock_response(status_code, json_data)` from conftest |

## Quick Reference
See `references/checklist.md` for a condensed scaffolding checklist.
