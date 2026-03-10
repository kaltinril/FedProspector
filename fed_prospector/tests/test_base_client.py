"""Unit tests for BaseAPIClient (base_client.py).

Tests cover:
- Successful GET/POST requests
- Rate limit checking and enforcement
- Immediate failure on 429 (daily rate limit) without retry
- Retry logic with exponential backoff on 5xx
- ConnectionError and Timeout retry behavior
- 4xx non-retryable error handling
- Pagination generator
- Malformed JSON response handling (83-T1)
- Concurrent rate limit counter updates (83-T2)
"""

import threading
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
    def test_request_proceeds_even_when_counter_at_limit(self, mock_db_connection):
        """Preemptive blocking removed — only a real 429 should stop requests."""
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (100,)  # at limit
        client = _make_client()

        resp_200 = make_mock_response(200, {"ok": True})
        client.session.request = MagicMock(return_value=resp_200)
        result = client.get("/test")
        assert result.status_code == 200


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------

class TestRetryBehavior:
    def test_429_raises_immediately_without_retry(self):
        """429 means daily limit reached — raise immediately, no retries."""
        client = _make_client()
        resp_429 = make_mock_response(429)
        client.session.request = MagicMock(return_value=resp_429)

        with pytest.raises(requests.HTTPError, match="429"):
            client.get("/test")

        assert client.session.request.call_count == 1

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

    def test_429_raises_on_first_attempt_ignoring_max_retries(self):
        """429 raises immediately regardless of max_retries setting."""
        client = _make_client()
        resp_429 = make_mock_response(429)
        client.session.request = MagicMock(return_value=resp_429)

        with pytest.raises(requests.HTTPError, match="429"):
            client._request_with_retry("GET", "https://api.example.com/test",
                                       max_retries=3, backoff_factor=2)

        assert client.session.request.call_count == 1

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


# ---------------------------------------------------------------------------
# 83-T1: Malformed JSON response handling
# ---------------------------------------------------------------------------

class TestMalformedJsonResponses:
    """Verify API clients handle non-JSON responses without crashing."""

    @patch("time.sleep")
    def test_html_error_page_does_not_crash_with_json_decode_error(self, mock_sleep):
        """An HTML 502 response should be treated as a 5xx server error and
        retried, not crash with an unhandled JSONDecodeError."""
        client = _make_client()
        html_body = "<html><body>502 Bad Gateway</body></html>"
        resp_502 = MagicMock()
        resp_502.status_code = 502
        resp_502.text = html_body
        resp_502.content = html_body.encode()
        resp_502.json.side_effect = ValueError("No JSON object could be decoded")
        resp_502.raise_for_status.side_effect = requests.HTTPError(
            "502 Bad Gateway", response=resp_502
        )

        # After retries exhausted, the 5xx raises HTTPError - not JSONDecodeError
        client.session.request = MagicMock(return_value=resp_502)
        with pytest.raises(requests.HTTPError, match="502"):
            client.get("/test")

        # Confirm retries happened (default max_retries=3, so 4 total attempts)
        assert client.session.request.call_count == 4

    @patch("time.sleep")
    def test_html_error_page_recovers_on_retry(self, mock_sleep):
        """A transient HTML 502 followed by a valid 200 should succeed."""
        client = _make_client()
        html_body = "<html><body>502 Bad Gateway</body></html>"
        resp_502 = MagicMock()
        resp_502.status_code = 502
        resp_502.text = html_body
        resp_502.content = html_body.encode()

        resp_200 = make_mock_response(200, {"data": "ok"})
        client.session.request = MagicMock(side_effect=[resp_502, resp_200])

        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"data": "ok"}

    def test_empty_response_body_on_200_does_not_crash(self):
        """A 200 response with an empty body should be returned successfully.
        The caller may get a JSONDecodeError when calling .json(), but the
        client itself should not crash."""
        client = _make_client()
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.content = b""
        resp_200.text = ""
        resp_200.json.side_effect = ValueError("No JSON object could be decoded")
        client.session.request = MagicMock(return_value=resp_200)

        # _request_with_retry returns the response without calling .json()
        response = client.get("/test")
        assert response.status_code == 200
        # Caller would get the error when they try to parse
        with pytest.raises(ValueError):
            response.json()

    def test_429_with_non_json_body_does_not_crash(self):
        """A 429 response with a non-JSON body (e.g. HTML from a proxy)
        should still raise HTTPError, not JSONDecodeError."""
        client = _make_client()
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.text = "<html><body>Rate Limited</body></html>"
        resp_429.content = resp_429.text.encode()
        resp_429.json.side_effect = ValueError("No JSON object could be decoded")

        client.session.request = MagicMock(return_value=resp_429)

        with pytest.raises(requests.HTTPError, match="429"):
            client.get("/test")

        # Should not retry on 429
        assert client.session.request.call_count == 1


# ---------------------------------------------------------------------------
# 83-T2: Concurrent rate limit counter updates
# ---------------------------------------------------------------------------

class TestConcurrentRateLimitUpdates:
    """Verify that concurrent _increment_rate_counter() calls don't lose updates.

    Since the real implementation uses MySQL's atomic
    ``requests_made = requests_made + 1`` (ON DUPLICATE KEY UPDATE), lost
    updates are prevented at the database level. These tests verify that the
    method is safe to call from multiple threads without Python-level errors,
    and that all calls complete successfully.
    """

    def test_concurrent_increments_all_complete(self, mock_db_connection):
        """Multiple threads calling _increment_rate_counter() simultaneously
        should all complete without errors and each should have executed the
        INSERT/UPDATE statement exactly once."""
        client = _make_client()
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value

        num_threads = 3
        errors = []
        barrier = threading.Barrier(num_threads)

        def increment_worker():
            try:
                barrier.wait(timeout=5)  # synchronize thread starts
                client._increment_rate_counter()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment_worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Threads raised errors: {errors}"
        # Each thread should have called execute() once for the INSERT/UPDATE
        assert cursor.execute.call_count == num_threads
        # Each thread should have committed
        assert conn.commit.call_count == num_threads

    def test_concurrent_increments_correct_sql_used(self, mock_db_connection):
        """Verify all concurrent calls use the atomic ON DUPLICATE KEY UPDATE
        SQL pattern, which is the database-level guarantee against lost updates."""
        client = _make_client()
        conn = mock_db_connection.return_value
        cursor = conn.cursor.return_value

        num_threads = 2
        barrier = threading.Barrier(num_threads)

        def increment_worker():
            barrier.wait(timeout=5)
            client._increment_rate_counter()

        threads = [threading.Thread(target=increment_worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # All execute calls should use the atomic SQL pattern
        for call_obj in cursor.execute.call_args_list:
            sql = call_obj[0][0]
            assert "ON DUPLICATE KEY UPDATE" in sql
            assert "requests_made = requests_made + 1" in sql
