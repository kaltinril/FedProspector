# Phase 83: Vendor API Client Hardening

**Status**: PLANNED
**Priority**: HIGH
**Depends on**: None

## Overview
Review of all 9 vendor API clients (SAM.gov x6, USASpending, GSA CALC, base client) identified rate limiting bypasses, missing response validation, pagination risks, and error handling gaps. These affect data loading reliability and API quota management.

## Issues

### CRITICAL

#### 83-1: USASpending Direct Session Usage Bypasses Rate Limiting
- **File**: `fed_prospector/api_clients/usaspending_client.py` lines 506, 553, 662
- **Issue**: `poll_bulk_download()`, `download_bulk_file()`, and `download_archive_file()` use `self.session.get()` directly instead of `self.get()`. This bypasses rate limit checks, retry logic, request throttling, and error logging.
- **Fix**: Replace `self.session.get()` with `self.get()` or create a separate `_download_request()` method that includes retry logic but skips rate counting.

#### 83-2: No API Response Schema Validation
- **Files**: All clients (e.g., `sam_opportunity_client.py:182`, `usaspending_client.py:160-162`)
- **Issue**: None of the clients validate that response JSON contains expected keys. If API schema changes, clients fail with KeyError or return empty results silently.
- **Fix**: Add response validation method to BaseAPIClient: `_validate_response(data, required_keys)`. Call after every API response parse.

#### 83-3: Streaming Downloads Can Hang Indefinitely
- **File**: `fed_prospector/api_clients/usaspending_client.py` lines 570-589
- **Issue**: `download_bulk_file()` uses `response.iter_content()` with timeout only on initial request. If server closes connection mid-transfer, iteration hangs forever.
- **Fix**: Add socket-level timeout via `requests.adapters.HTTPAdapter(timeout=...)` or wrap iter_content in a timeout context.

#### 83-4: Bare Exception Handling in get_award()
- **File**: `fed_prospector/api_clients/usaspending_client.py` lines 214-216
- **Issue**: Catches `Exception` broadly, returns None. Cannot distinguish between RateLimitExceeded, HTTPError, and legitimate "not found". All errors silently return None.
- **Fix**: Catch specific exceptions (HTTPError -> return None for 404, re-raise for others; RateLimitExceeded -> re-raise).

### HIGH

#### 83-5: No Pagination Timeout/Max Iterations Guard
- **Files**: All clients with `paginate()` (e.g., `sam_entity_client.py:242-247`)
- **Issue**: `paginate()` loops until all records fetched. If API returns `hasNext=true` indefinitely, pagination runs forever, consuming entire daily budget.
- **Fix**: Add `max_pages` parameter to paginate() with sensible default (e.g., 1000). Log warning when limit hit.

#### 83-6: SAM Extracts Client Resource Leak on Error
- **File**: `fed_prospector/api_clients/sam_extract_client.py` lines 297-298, 319
- **Issue**: `response.close()` called after download but if exception occurs between opening response and close, file handle leaks.
- **Fix**: Use `with` context manager for response: `with self.get(..., stream=True) as response:`

#### 83-7: Missing Response Validation Before JSON Parse (USASpending)
- **File**: `fed_prospector/api_clients/usaspending_client.py` lines 506-515
- **Issue**: `poll_bulk_download()` calls `response.json()` before checking status code. Non-200 responses may not be valid JSON.
- **Fix**: Check `response.status_code` before `response.json()`. Handle HTML error pages gracefully.

#### 83-8: Paginator Results Key Silently Returns Empty
- **File**: `fed_prospector/api_clients/base_client.py` line 334
- **Issue**: `data.get(results_key, [])` returns empty list if key missing. A missing key is indistinguishable from "no results", hiding API schema drift.
- **Fix**: If results_key not in data, log warning with actual response keys. Optionally raise if strict mode enabled.

#### 83-9: Date Format Validation Missing
- **File**: `fed_prospector/api_clients/sam_awards_client.py` lines 295-332
- **Issue**: `_format_date_range()` accepts multiple formats. If date doesn't match any format, returns string as-is, allowing malformed dates to reach the API.
- **Fix**: Raise ValueError if date format not recognized. Validate date ranges (start < end).

#### 83-10: SAM Opportunity Budget Tracking Race Condition
- **File**: `fed_prospector/api_clients/sam_opportunity_client.py` lines 445, 455
- **Issue**: Budget tracking reads rate counter before/after each set-aside search. If multiple processes use same source_name concurrently, budget calculations are incorrect.
- **Fix**: Use database-level atomic counter or advisory locks for budget tracking.

### MEDIUM

#### 83-11: No Connection Pooling Configuration
- **File**: `fed_prospector/api_clients/base_client.py` line 32
- **Issue**: `requests.Session()` uses default connection pool limits. May be insufficient for high-volume loading.
- **Fix**: Configure `HTTPAdapter(pool_connections=10, pool_maxsize=10)` and mount on session.

#### 83-12: CalcPlus Client Silently Skips ES Errors
- **File**: `fed_prospector/api_clients/calc_client.py` lines 244-248
- **Issue**: `get_all_rates()` catches `Exception` on sort strategy failure, logs warning, and skips that 10K chunk. Records silently missed.
- **Fix**: Track skipped chunks. Retry with different sort strategy. Log ERROR not WARNING.

#### 83-13: Error Response Truncation
- **File**: `fed_prospector/api_clients/base_client.py` line 212
- **Issue**: Error response text truncated to 500 chars. Detailed error info from APIs is lost.
- **Fix**: Increase to 2000 chars or log full response at DEBUG level.

#### 83-14: Inconsistent Timeout Configuration
- **Files**: Various clients
- **Issue**: Some POST calls use `timeout=60`, others use default 30. No consistency.
- **Fix**: Define timeout constants per operation type: `TIMEOUT_DEFAULT=30`, `TIMEOUT_DOWNLOAD=600`, `TIMEOUT_POLL=120`. Apply consistently.

### LOW

#### 83-15: Rate Counter Not Rolled Back on Partial Success
- **File**: `fed_prospector/api_clients/base_client.py` lines 157-162
- **Issue**: Rate counter incremented on 200 success. If caller crashes after count increment, quota consumed for unprocessed records.
- **Fix**: Accept as design tradeoff. Document in code comments.

#### 83-16: SAM FedHier Lowercase "totalrecords" API Inconsistency
- **File**: `fed_prospector/api_clients/sam_fedhier_client.py` line 136
- **Issue**: SAM FedHier uses `"totalrecords"` (lowercase) unlike other SAM APIs (`"totalRecords"`). Documented in code but fragile.
- **Fix**: Add case-insensitive key lookup helper in base_client. Or just add a code comment -- this is an API quirk.

### TEST GAPS

#### 83-T1: No Tests for Malformed JSON Responses
- **Issue**: Tests don't cover API returning HTML error pages instead of JSON.
- **Fix**: Add test cases with non-JSON responses.

#### 83-T2: No Tests for Concurrent Rate Limit Updates
- **Issue**: No test for race conditions on etl_rate_limit table.
- **Fix**: Add concurrent test with threading.

#### 83-T3: No Tests for Budget Exhaustion Mid-Search
- **Issue**: No test for `_search_multiple_set_asides()` hitting budget limit.
- **Fix**: Add test that mocks rate counter reaching budget mid-iteration.

## Verification
1. All Python API client tests pass: `python -m pytest fed_prospector/tests/test_base_client.py test_sam_*.py test_usaspending.py test_calc_client.py -v`
2. Simulate 429 response -> verify proper retry with backoff
3. Simulate malformed JSON response -> verify graceful error (not crash)
4. Simulate infinite pagination -> verify max_pages guard triggers
5. Run full opportunity load -> verify budget tracking accurate
