"""Unit tests for BaseAPIClient (base_client.py).

Tests cover:
- Successful GET/POST requests
- Rate limit checking and enforcement
- Retry logic with exponential backoff on 429 and 5xx
- ConnectionError and Timeout retry behavior
- 4xx non-retryable error handling
- Pagination generator
"""

import time
from unittest.mock import MagicMock, patch, call

import pytest
import requests

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from tests.conftest import make_mock_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**kwargs):
    """Create a BaseAPIClient with test defaults and zero request_delay."""
    defaults = dict(
        base_url="https://api.example.com",
        api_key="test-key",
        source_name="TEST_SOURCE",
        max_daily_requests=100,
        request_delay=0,  # no sleep between requests in tests
    )
    defaults.update(kwargs)
    return BaseAPIClient(**defaults)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestBaseClientInit:
    def test_init_sets_attributes(self):
        client = _make_client()
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.source_name == "TEST_SOURCE"
        assert client.max_daily_requests == 100
        assert client.request_delay == 0

    def test_init_creates_session(self):
        client = _make_client()
        assert client.session is not None


# ---------------------------------------------------------------------------
# Rate limit checking
# ---------------------------------------------------------------------------

class TestRateLimitCheck:
    def test_check_rate_limit_returns_true_when_no_record(self, mock_db_connection):
        """No record in etl_rate_limit means 0 requests made."""
        client = _make_client()
        assert client._check_rate_limit() is True

    def test_check_rate_limit_returns_true_when_under_limit(self, mock_db_connection):
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (5,)  # 5 < 100
        client = _make_client()
        assert client._check_rate_limit() is True

    def test_check_rate_limit_returns_false_when_at_limit(self, mock_db_connection):
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (100,)  # 100 == max
        client = _make_client()
        assert client._check_rate_limit() is False

    def test_get_remaining_requests_returns_correct_count(self, mock_db_connection):
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (30,)
        client = _make_client()
        assert client._get_remaining_requests() == 70  # 100 - 30


# ---------------------------------------------------------------------------
# Successful requests
# ---------------------------------------------------------------------------

class TestSuccessfulRequests:
    def test_get_returns_response_on_200(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"data": "ok"})
        client.session.request = MagicMock(return_value=mock_resp)

        response = client.get("/test", params={"q": "hello"})

        assert response.status_code == 200
        assert response.json() == {"data": "ok"}

    def test_get_adds_api_key_to_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {})
        client.session.request = MagicMock(return_value=mock_resp)

        client.get("/test", params={"q": "hello"})

        call_args = client.session.request.call_args
        params = call_args.kwargs["params"]
        assert params["api_key"] == "test-key"
        assert params["q"] == "hello"

    def test_post_sends_json_body(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"result": "created"})
        client.session.request = MagicMock(return_value=mock_resp)

        response = client.post("/create", json_body={"name": "test"})

        assert response.status_code == 200
        call_args = client.session.request.call_args
        assert call_args.kwargs["json"] == {"name": "test"}


# ---------------------------------------------------------------------------
# Rate limit enforcement
# ---------------------------------------------------------------------------

class TestRateLimitEnforcement:
    def test_request_raises_rate_limit_exceeded_when_at_limit(self, mock_db_connection):
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (100,)  # at limit
        client = _make_client()

        with pytest.raises(RateLimitExceeded, match="Daily rate limit"):
            client.get("/test")


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------

class TestRetryBehavior:
    @patch("time.sleep")
    def test_retries_on_429_then_succeeds(self, mock_sleep):
        client = _make_client()
        resp_429 = make_mock_response(429)
        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(side_effect=[resp_429, resp_200])

        response = client.get("/test")

        assert response.status_code == 200
        assert client.session.request.call_count == 2
        # Backoff: 2^0 = 1 second
        mock_sleep.assert_any_call(1)

    @patch("time.sleep")
    def test_retries_on_500_then_succeeds(self, mock_sleep):
        client = _make_client()
        resp_500 = make_mock_response(500)
        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(side_effect=[resp_500, resp_200])

        response = client.get("/test")

        assert response.status_code == 200
        assert client.session.request.call_count == 2

    @patch("time.sleep")
    def test_retries_on_connection_error_then_succeeds(self, mock_sleep):
        client = _make_client()
        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(
            side_effect=[requests.ConnectionError("Connection refused"), resp_200]
        )

        response = client.get("/test")

        assert response.status_code == 200

    @patch("time.sleep")
    def test_retries_on_timeout_then_succeeds(self, mock_sleep):
        client = _make_client()
        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(
            side_effect=[requests.Timeout("Timed out"), resp_200]
        )

        response = client.get("/test")

        assert response.status_code == 200

    @patch("time.sleep")
    def test_raises_after_all_retries_exhausted_on_429(self, mock_sleep):
        client = _make_client()
        resp_429 = make_mock_response(429)
        # 4 attempts: initial + 3 retries
        client.session.request = MagicMock(return_value=resp_429)

        with pytest.raises(requests.HTTPError):
            client._request_with_retry("GET", "https://api.example.com/test",
                                       max_retries=3, backoff_factor=2)

        assert client.session.request.call_count == 4

    @patch("time.sleep")
    def test_raises_after_all_retries_exhausted_on_connection_error(self, mock_sleep):
        client = _make_client()
        client.session.request = MagicMock(
            side_effect=requests.ConnectionError("Connection refused")
        )

        with pytest.raises(requests.ConnectionError):
            client._request_with_retry("GET", "https://api.example.com/test",
                                       max_retries=2, backoff_factor=2)

        assert client.session.request.call_count == 3


# ---------------------------------------------------------------------------
# Non-retryable errors (4xx except 429)
# ---------------------------------------------------------------------------

class TestNonRetryableErrors:
    def test_400_raises_immediately_without_retry(self):
        client = _make_client()
        resp_400 = make_mock_response(400, text="Bad Request")
        resp_400.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        client.session.request = MagicMock(return_value=resp_400)

        with pytest.raises(requests.HTTPError):
            client.get("/test")

        # Only 1 attempt - no retries for 400
        assert client.session.request.call_count == 1

    def test_403_raises_immediately_without_retry(self):
        client = _make_client()
        resp_403 = make_mock_response(403, text="Forbidden")
        resp_403.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        client.session.request = MagicMock(return_value=resp_403)

        with pytest.raises(requests.HTTPError):
            client.get("/test")

        assert client.session.request.call_count == 1


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    def test_paginate_yields_all_pages(self):
        client = _make_client()

        page1 = make_mock_response(200, {
            "totalRecords": 3,
            "data": [{"id": 1}, {"id": 2}],
        })
        page2 = make_mock_response(200, {
            "totalRecords": 3,
            "data": [{"id": 3}],
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        pages = list(client.paginate("/items", params={}, page_size=2))

        assert len(pages) == 2
        assert pages[0]["data"] == [{"id": 1}, {"id": 2}]
        assert pages[1]["data"] == [{"id": 3}]

    def test_paginate_stops_when_all_records_fetched(self):
        client = _make_client()

        single_page = make_mock_response(200, {
            "totalRecords": 2,
            "data": [{"id": 1}, {"id": 2}],
        })
        client.session.request = MagicMock(return_value=single_page)

        pages = list(client.paginate("/items", params={}, page_size=100))

        # Only 1 page needed (2 records < 100 page_size)
        assert len(pages) == 1

    def test_paginate_uses_custom_keys(self):
        client = _make_client()

        resp = make_mock_response(200, {
            "total": 1,
            "items": [{"id": 1}],
        })
        client.session.request = MagicMock(return_value=resp)

        # Note: offset_key/limit_key were renamed to offset_param/size_param
        # in Phase 14.12 to match the expanded parameter set.
        pages = list(client.paginate(
            "/items", params={}, page_size=10,
            offset_param="start", size_param="count", total_key="total",
        ))

        assert len(pages) == 1
        # Verify custom offset/limit keys were set in params
        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "count" in params
        assert "start" in params
