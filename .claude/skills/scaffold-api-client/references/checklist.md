# Scaffold API Client -- Checklist

## Files to Create/Modify
- [ ] `fed_prospector/api_clients/{client_name}_client.py`
- [ ] `fed_prospector/tests/test_api_clients/test_{client_name}_client.py`
- [ ] `fed_prospector/tests/fixtures/{client_name}_response.json` (optional)
- [ ] Add settings to `fed_prospector/config/settings.py`
- [ ] Add env vars to `fed_prospector/.env`

## Client Class Requirements
- [ ] Inherits `BaseAPIClient`
- [ ] `super().__init__(base_url, api_key, source_name, max_daily_requests)`
- [ ] At least one public search/fetch method
- [ ] Uses `.get()` defaults on all response dict access
- [ ] Does NOT override base class HTTP methods
- [ ] Does NOT hardcode API keys

## If Paginated
- [ ] Uses `self.paginate()` or manual page loop
- [ ] Generator method yielding individual records
- [ ] Handles empty results gracefully

## If Dual-Key
- [ ] `api_key_number` parameter in `__init__`
- [ ] Separate source_name per key (e.g., `SOURCE_KEY2`)
- [ ] Separate daily limit per key

## Tests
- [ ] Test construction (base_url, source_name, api_key)
- [ ] Test successful request returns data
- [ ] Test API key passed in params
- [ ] Test retry on 429
- [ ] Test pagination (if applicable)
- [ ] Uses `_make_client()` helper with `request_delay=0`
- [ ] Uses `make_mock_response` from conftest
