"""Abstract base class for all API clients.

Features:
- Automatic retry with exponential backoff
- Rate limit tracking via etl_rate_limit table
- Request logging
- Pagination support (generator-based)
"""

import logging
import time
from datetime import date, datetime

import requests

from db.connection import get_connection


class RateLimitExceeded(Exception):
    """Raised when daily API rate limit has been reached."""
    pass


class BaseAPIClient:
    def __init__(self, base_url, api_key, source_name, max_daily_requests):
        self.base_url = base_url
        self.api_key = api_key
        self.source_name = source_name
        self.max_daily_requests = max_daily_requests
        self.session = requests.Session()
        self.logger = logging.getLogger(f"fed_prospector.api.{source_name}")

    def _check_rate_limit(self):
        """Query etl_rate_limit for today's count. Return True if under limit."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT requests_made FROM etl_rate_limit "
                "WHERE source_system = %s AND request_date = %s",
                (self.source_name, date.today()),
            )
            row = cursor.fetchone()
            if row is None:
                return True  # No record yet = 0 requests made
            return row[0] < self.max_daily_requests
        finally:
            cursor.close()
            conn.close()

    def _increment_rate_counter(self):
        """INSERT ... ON DUPLICATE KEY UPDATE requests_made = requests_made + 1"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO etl_rate_limit (source_system, request_date, requests_made, max_requests, last_request_at) "
                "VALUES (%s, %s, 1, %s, %s) "
                "ON DUPLICATE KEY UPDATE requests_made = requests_made + 1, last_request_at = %s",
                (
                    self.source_name,
                    date.today(),
                    self.max_daily_requests,
                    datetime.now(),
                    datetime.now(),
                ),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _get_remaining_requests(self):
        """Return how many API requests remain for today."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT requests_made FROM etl_rate_limit "
                "WHERE source_system = %s AND request_date = %s",
                (self.source_name, date.today()),
            )
            row = cursor.fetchone()
            used = row[0] if row else 0
            return self.max_daily_requests - used
        finally:
            cursor.close()
            conn.close()

    def _request_with_retry(self, method, url, params=None, json_body=None,
                            max_retries=3, backoff_factor=2, timeout=30):
        """Make HTTP request with rate limit check, retry, and exponential backoff.

        Args:
            method: HTTP method string (GET, POST, etc.).
            url: Full URL.
            params: Query string parameters dict.
            json_body: JSON body dict for POST requests.
            max_retries: Number of retries after the initial attempt.
            backoff_factor: Exponential backoff multiplier.
            timeout: Request timeout in seconds.

        Raises RateLimitExceeded if daily limit reached.
        Retries on 429 (rate limited) and 5xx (server error) responses.
        """
        if not self._check_rate_limit():
            raise RateLimitExceeded(
                f"{self.source_name}: Daily rate limit of {self.max_daily_requests} reached. "
                f"No requests remaining for today."
            )

        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    "Request %s %s (attempt %d/%d)",
                    method, url, attempt + 1, max_retries + 1,
                )
                response = self.session.request(
                    method, url, params=params, json=json_body, timeout=timeout,
                )

                # Count this request
                self._increment_rate_counter()

                if response.status_code == 200:
                    self.logger.debug("Response: %d (%d bytes)", response.status_code, len(response.content))
                    return response

                if response.status_code == 429:
                    wait = backoff_factor ** attempt
                    self.logger.warning(
                        "Rate limited (429). Waiting %ds before retry...", wait
                    )
                    time.sleep(wait)
                    last_exception = requests.HTTPError(f"429 Rate Limited", response=response)
                    continue

                if response.status_code >= 500:
                    wait = backoff_factor ** attempt
                    self.logger.warning(
                        "Server error (%d). Waiting %ds before retry...",
                        response.status_code, wait,
                    )
                    time.sleep(wait)
                    last_exception = requests.HTTPError(
                        f"{response.status_code} Server Error", response=response
                    )
                    continue

                # 4xx (not 429) - don't retry
                self.logger.error(
                    "Request failed: %d %s", response.status_code, response.text[:500]
                )
                response.raise_for_status()

            except requests.ConnectionError as e:
                wait = backoff_factor ** attempt
                self.logger.warning("Connection error: %s. Waiting %ds...", e, wait)
                time.sleep(wait)
                last_exception = e
            except requests.Timeout as e:
                wait = backoff_factor ** attempt
                self.logger.warning("Timeout: %s. Waiting %ds...", e, wait)
                time.sleep(wait)
                last_exception = e

        # All retries exhausted
        self.logger.error("All %d retries exhausted for %s %s", max_retries + 1, method, url)
        if last_exception:
            raise last_exception
        raise requests.HTTPError(f"Request failed after {max_retries + 1} attempts")

    def get(self, endpoint, params=None, **kwargs):
        """Convenience method for GET requests."""
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        return self._request_with_retry("GET", url, params=params, **kwargs)

    def post(self, endpoint, json_body=None, params=None, **kwargs):
        """Convenience method for POST requests with JSON body."""
        url = f"{self.base_url}{endpoint}"
        return self._request_with_retry("POST", url, params=params,
                                        json_body=json_body, **kwargs)

    def paginate(self, endpoint, params, page_size=1000,
                 offset_key="offset", limit_key="limit",
                 total_key="totalRecords"):
        """Generator that yields pages of results.

        Handles pagination math and stops when all records retrieved.
        Each yield returns the parsed JSON response for that page.
        """
        offset = 0
        if params is None:
            params = {}
        params[limit_key] = page_size

        while True:
            params[offset_key] = offset
            response = self.get(endpoint, params=params)
            data = response.json()

            total = data.get(total_key, 0)
            self.logger.info(
                "Page at offset %d: total=%d", offset, total
            )

            yield data

            offset += page_size
            if offset >= total:
                break
