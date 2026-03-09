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
    def __init__(self, base_url, api_key, source_name, max_daily_requests,
                 request_delay=0.1):
        self.base_url = base_url
        self.api_key = api_key
        self.source_name = source_name
        self.max_daily_requests = max_daily_requests
        self.request_delay = request_delay  # seconds between consecutive requests
        self.session = requests.Session()
        self.logger = logging.getLogger(f"fed_prospector.api.{source_name}")

    @classmethod
    def _sam_init_kwargs(cls, source_name, api_key_number=1):
        """Return kwargs dict for super().__init__() using SAM's dual-key config.

        Centralizes the SAM_API_KEY / SAM_API_KEY_2 selection logic shared by
        all four SAM search clients (Awards, Exclusions, FedHier, Subaward).

        Args:
            source_name: Source system name for rate tracking (e.g. "SAM_AWARDS").
            api_key_number: 1 (default, 10/day) or 2 (1000/day).

        Returns:
            dict: kwargs suitable for BaseAPIClient.__init__().
        """
        from config import settings
        if api_key_number == 2:
            api_key = settings.SAM_API_KEY_2
            limit = settings.SAM_DAILY_LIMIT_2
        else:
            api_key = settings.SAM_API_KEY
            limit = settings.SAM_DAILY_LIMIT
        return dict(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=limit,
        )

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
                            max_retries=3, backoff_factor=2, timeout=30,
                            stream=False):
        """Make HTTP request with rate limit check, retry, and exponential backoff.

        Args:
            method: HTTP method string (GET, POST, etc.).
            url: Full URL.
            params: Query string parameters dict.
            json_body: JSON body dict for POST requests.
            max_retries: Number of retries after the initial attempt.
            backoff_factor: Exponential backoff multiplier.
            timeout: Request timeout in seconds.
            stream: If True, response body is not downloaded immediately.
                    Caller is responsible for reading and closing the response.

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
                    stream=stream,
                )

                if response.status_code == 200:
                    # Count this as one logical request on success only.
                    # Retried attempts do not consume additional quota so that
                    # transient 429/5xx errors do not silently drain the daily
                    # budget (CRITICAL bug fix).
                    self._increment_rate_counter()
                    # Only log content length for non-streaming responses to
                    # avoid consuming the stream body before the caller reads it.
                    if not stream:
                        self.logger.debug(
                            "Response: %d (%d bytes)", response.status_code, len(response.content)
                        )
                    else:
                        self.logger.debug("Response: %d (streaming)", response.status_code)
                    # Throttle between successful requests to avoid rate limiting
                    if self.request_delay > 0:
                        time.sleep(self.request_delay)
                    return response

                if response.status_code == 429:
                    # Parse reset time from SAM.gov response body
                    msg = "429 Rate Limited"
                    try:
                        body = response.json()
                        next_access = body.get("nextAccessTime")
                        if next_access:
                            from datetime import datetime, timezone
                            # SAM.gov format: "2026-Mar-10 00:00:00+0000 UTC"
                            utc_str = next_access.replace(" UTC", "").replace("+0000", "+00:00")
                            utc_dt = datetime.strptime(
                                utc_str.replace("+00:00", ""), "%Y-%b-%d %H:%M:%S"
                            ).replace(tzinfo=timezone.utc)
                            local_dt = utc_dt.astimezone()
                            msg = f"429 Rate Limited — quota resets at {local_dt.strftime('%Y-%m-%d %I:%M %p %Z')}"
                        elif body.get("description"):
                            msg = f"429 Rate Limited — {body['description']}"
                    except Exception:
                        pass
                    self.logger.warning(msg)
                    raise requests.HTTPError(msg, response=response)

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
        if self.api_key:  # Only add if non-empty string (Win 4 fix)
            params["api_key"] = self.api_key
        return self._request_with_retry("GET", url, params=params, **kwargs)

    def post(self, endpoint, json_body=None, params=None, **kwargs):
        """Convenience method for POST requests with JSON body."""
        url = f"{self.base_url}{endpoint}"
        return self._request_with_retry("POST", url, params=params,
                                        json_body=json_body, **kwargs)

    def get_binary(self, endpoint, params=None, stream=True, **kwargs):
        """Like get() but returns the raw Response for binary/streaming downloads.

        Handles rate-limit checking and retry via _request_with_retry().
        The caller is responsible for reading and closing the response.

        Args:
            endpoint: URL path relative to base_url.
            params: Query parameters dict. api_key is added automatically if set.
            stream: If True, the response body is not downloaded immediately
                    (use response.iter_content() to stream). Default True.

        Returns:
            requests.Response: Raw response object.

        Raises:
            RateLimitExceeded: If daily limit has been reached.
            requests.HTTPError: On non-200 HTTP responses after all retries.
        """
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
        if self.api_key:
            params["api_key"] = self.api_key
        return self._request_with_retry("GET", url, params=params, stream=stream, **kwargs)

    def _format_date(self, value, fmt="%Y-%m-%d"):
        """Convert date, datetime, or string to formatted string.

        Args:
            value: A date, datetime, or string. None returns None.
            fmt: strftime format string. Default: '%Y-%m-%d'.

        Returns:
            str: Formatted date string, or None if value is None.
        """
        if value is None:
            return None
        if isinstance(value, (date, datetime)):
            return value.strftime(fmt)
        return str(value)

    def paginate(self, endpoint, params, page_size=1000,
                 pagination_style="offset",    # "offset" | "page"
                 offset_param="offset",        # query param name for offset
                 page_param="page",            # query param name for page number
                 size_param="limit",           # query param name for page size
                 page_start=0,                 # first page index (0 or 1)
                 total_key="totalRecords",     # response key for total count
                 results_key=None,             # response key for record list (None = yield full response)
                 has_next_key=None,            # if set, use response[has_next_key] to stop
                 total_pages_key=None,          # if set, use response[total_pages_key] to stop
                 offset_start=0):               # starting offset for offset-style pagination
        """Generic paginator — parameterize instead of reimplementing.

        Supports three end-of-page detection strategies:
          1. has_next_key  — stop when response[has_next_key] is falsy (USASpending)
          2. total_pages_key — stop when page >= response[total_pages_key] (Subaward)
          3. total_key — stop when offset/page*size >= response[total_key] (SAM default)

        When results_key is None (legacy behavior), yields the full parsed response
        dict for each page. When results_key is set, yields the results list for
        each page.

        Backward-compatible with existing callers: the original 3-param signature
        (endpoint, params, page_size) still works because all new params have defaults.
        Existing SAMEntityClient callers that pass positional args continue to work
        and receive full response dicts (results_key=None).
        """
        # Copy params to avoid mutating the caller's dict (HIGH bug fix)
        params = dict(params or {})
        params[size_param] = page_size

        page = page_start
        offset = offset_start

        while True:
            if pagination_style == "page":
                params[page_param] = page
            else:  # offset
                params[offset_param] = offset

            response = self.get(endpoint, params=params)
            data = response.json()

            if results_key is not None:
                results = data.get(results_key, [])
                self.logger.info(
                    "Page %s: %d results",
                    page if pagination_style == "page" else f"offset={offset}",
                    len(results),
                )
                yield results
            else:
                # Legacy behavior: yield full response dict
                total = data.get(total_key, 0)
                if pagination_style == "page":
                    self.logger.info("Page %d: total=%d", page, total)
                else:
                    self.logger.info("Page at offset %d: total=%d", offset, total)
                yield data

            # Determine whether to stop
            if results_key is not None:
                results_for_check = data.get(results_key, [])
            else:
                results_for_check = None  # legacy path uses offset math below

            if results_key is not None and not results_for_check:
                break

            # End-of-page detection
            if has_next_key is not None:
                if not data.get(has_next_key, False):
                    break
                page += 1
            elif total_pages_key is not None:
                total_pages = data.get(total_pages_key, 0)
                page += 1
                if page >= total_pages:
                    break
            else:
                total = data.get(total_key, 0)
                if pagination_style == "page":
                    page += 1
                    if page * page_size >= total:
                        break
                else:
                    offset += page_size
                    if offset >= total:
                        break
