# API Client Templates

All templates use `{{placeholders}}` — replace before writing files.

## 1. Client Class (Standard)

```python
"""{{ClientName}} API client."""

import logging
from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings

logger = logging.getLogger("fed_prospector.api.{{client_name}}")

SEARCH_ENDPOINT = "/api/v1/search"
DETAIL_ENDPOINT = "/api/v1/resource"


class {{ClientName}}Client(BaseAPIClient):
    """Client for {{ClientName}} API.

    Inherits rate limiting, retries, pagination from BaseAPIClient.
    """

    def __init__(self, api_key=None):
        super().__init__(
            base_url=settings.{{CLIENT_NAME}}_API_BASE_URL,
            api_key=api_key or settings.{{CLIENT_NAME}}_API_KEY,
            source_name="{{CLIENT_NAME}}",
            max_daily_requests=settings.{{CLIENT_NAME}}_DAILY_LIMIT,
        )

    def search(self, **filters):
        """Search for resources.

        Returns:
            dict: API response with results.
        Raises:
            RateLimitExceeded: If daily quota exhausted.
        """
        params = {k: v for k, v in filters.items() if v is not None}
        response = self.get(SEARCH_ENDPOINT, params=params)
        return response.json()

    def search_all(self, **filters):
        """Generator: paginate through all results.

        Yields:
            dict: Individual resource records.
        """
        for page_data in self.paginate(
            SEARCH_ENDPOINT,
            params={k: v for k, v in filters.items() if v is not None},
            page_size=100,
            pagination_style="offset",
            total_key="totalRecords",
            results_key="results",
        ):
            for record in page_data:
                yield record

    def get_by_id(self, resource_id):
        """Fetch single resource by ID.

        Returns:
            dict or None: Resource data, or None if not found.
        """
        try:
            response = self.get(f"{DETAIL_ENDPOINT}/{resource_id}")
            return response.json()
        except Exception as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
                self.logger.info("Not found: %s", resource_id)
                return None
            raise
```

## 2. Client Class (No-Auth Variant)

Replace `__init__` with:

```python
    def __init__(self):
        super().__init__(
            base_url=settings.{{CLIENT_NAME}}_API_BASE_URL,
            api_key="",
            source_name="{{CLIENT_NAME}}",
            max_daily_requests=999999,
        )
```

Remove `api_key` parameter and `{{CLIENT_NAME}}_API_KEY` from settings.

## 3. Client Class (Dual-Key Variant)

Replace `__init__` with:

```python
    def __init__(self, api_key_number=1):
        if api_key_number == 2:
            api_key = settings.{{CLIENT_NAME}}_API_KEY_2
            source_name = "{{CLIENT_NAME}}_KEY2"
            limit = settings.{{CLIENT_NAME}}_DAILY_LIMIT_2
        else:
            api_key = settings.{{CLIENT_NAME}}_API_KEY
            source_name = "{{CLIENT_NAME}}"
            limit = settings.{{CLIENT_NAME}}_DAILY_LIMIT
        super().__init__(
            base_url=settings.{{CLIENT_NAME}}_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=limit,
        )
```

Add to settings: `{{CLIENT_NAME}}_API_KEY_2`, `{{CLIENT_NAME}}_DAILY_LIMIT_2`.

## 4. Test File Template

```python
"""Tests for {{ClientName}}Client."""

from unittest.mock import MagicMock, patch
import pytest
from api_clients.{{client_name}}_client import {{ClientName}}Client


def _make_client(**kwargs):
    """Create client with zero request_delay for tests."""
    client = {{ClientName}}Client(**kwargs)
    client.request_delay = 0
    return client


class TestConstruction:
    def test_init_sets_attributes(self):
        client = _make_client()
        assert client.base_url == "expected_base_url"
        assert client.source_name == "{{CLIENT_NAME}}"

    def test_init_uses_settings_api_key(self):
        client = _make_client()
        assert client.api_key == "expected_api_key"


class TestSearch:
    def test_search_returns_response(self, make_mock_response):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 1, "results": [{"id": "1"}]})
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search(query="test")

        assert result["totalRecords"] == 1
        assert len(result["results"]) == 1

    def test_search_passes_filters_as_params(self, make_mock_response):
        client = _make_client()
        mock_resp = make_mock_response(200, {"results": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search(query="test", status="active")

        call_kwargs = client.session.request.call_args.kwargs
        assert "query" in call_kwargs["params"]
        assert "status" in call_kwargs["params"]


class TestRetryBehavior:
    @patch("time.sleep")
    def test_retries_on_429(self, mock_sleep, make_mock_response):
        client = _make_client()
        resp_429 = make_mock_response(429)
        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(side_effect=[resp_429, resp_200])

        response = client.get("/endpoint")

        assert response.status_code == 200
        assert client.session.request.call_count == 2


class TestGetById:
    def test_returns_data_on_200(self, make_mock_response):
        client = _make_client()
        mock_resp = make_mock_response(200, {"id": "123", "name": "Test"})
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_by_id("123")

        assert result["id"] == "123"
```

## 5. Settings Additions Template

Add to `fed_prospector/config/settings.py` in the appropriate section:

```python
# {{ClientName}} API
{{CLIENT_NAME}}_API_BASE_URL = os.getenv("{{CLIENT_NAME}}_API_BASE_URL", "{{base_url}}")
{{CLIENT_NAME}}_API_KEY = os.getenv("{{CLIENT_NAME}}_API_KEY", "")
{{CLIENT_NAME}}_DAILY_LIMIT = int(os.getenv("{{CLIENT_NAME}}_DAILY_LIMIT", "1000"))
```

Add to `fed_prospector/.env`:

```
# {{ClientName}} API
{{CLIENT_NAME}}_API_BASE_URL={{base_url}}
{{CLIENT_NAME}}_API_KEY=
{{CLIENT_NAME}}_DAILY_LIMIT=1000
```

## 6. Fixture File Template

Create `fed_prospector/tests/fixtures/{{client_name}}_response.json`:

```json
{
    "totalRecords": 2,
    "results": [
        {
            "id": "FIXTURE-001",
            "name": "Test Record 1"
        },
        {
            "id": "FIXTURE-002",
            "name": "Test Record 2"
        }
    ]
}
```

Only needed if tests reference fixture data. Most tests can use inline dicts.

## Reference

Canonical example: `fed_prospector/api_clients/sam_opportunity_client.py`
