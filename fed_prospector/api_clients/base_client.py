"""Abstract base class for all API clients.

Features:
- Automatic retry with exponential backoff
- Rate limit tracking via etl_rate_limit table
- Request logging
- Pagination support (generator-based)
- Response schema validation
- Connection pooling
"""

import logging
import time
from datetime import date, datetime, timezone

import requests
from requests.adapters import HTTPAdapter

from db.connection import get_connection

# Timeout constants (seconds) — importable by child classes
TIMEOUT_DEFAULT = 30
TIMEOUT_DOWNLOAD = 600
TIMEOUT_POLL = 120
TIMEOUT_SEARCH = 60


class RateLimitExceeded(Exception):
    """Raised when daily API rate limit has been reached."""
    pass


class BaseAPIClient:
    def __init__(self, base_url, api_key, source_name, max_daily_requests,
                 request_delay=0.1, logger_name=None):
        self.base_url = base_url
        self.api_key = api_key
        self.source_name = source_name
        self.max_daily_requests = max_daily_requests
        self.request_delay = request_delay  # seconds between consecutive requests
        self.session = requests.Session()
        # 83-11: Connection pooling — reuse TCP connections across requests
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        self.logger = logging.getLogger(
            logger_name or f"fed_prospector.api.{source_name}"
        )

    @classmethod
    def _sam_init_kwargs(cls, logger_name, api_key_number=1):
        """Return kwargs dict for super().__init__() using SAM's dual-key config.

        Centralizes the SAM_API_KEY / SAM_API_KEY_2 selection logic shared by
        all SAM.gov clients. Rate limit tracking uses a per-key source_name
        (SAM_KEY1 or SAM_KEY2) because SAM.gov shares a single daily pool
        across all endpoints for each API key.

        Args:
            logger_name: Descriptive name for the logger (e.g. "sam_awards").
                Used as ``fed_prospector.api.{logger_name}``.
            api_key_number: 1 (default, 10/day) or 2 (1000/day).

        Returns:
            dict: kwargs suitable for BaseAPIClient.__init__().
        """
        from config import settings
        if api_key_number == 2:
            api_key = settings.SAM_API_KEY_2
            limit = settings.SAM_DAILY_LIMIT_2
            source_name = "SAM_KEY2"
        else:
            api_key = settings.SAM_API_KEY
            limit = settings.SAM_DAILY_LIMIT
            source_name = "SAM_KEY1"
        return dict(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=limit,
            logger_name=f"fed_prospector.api.{logger_name}",
        )

    def _increment_rate_counter(self):
        """INSERT ... ON DUPLICATE KEY UPDATE requests_made = requests_made + 1"""
        now = datetime.now(timezone.utc)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO etl_rate_limit (source_system, request_date, requests_made, max_requests, last_request_at) "
                "VALUES (%s, %s, 1, %s, %s) "
                "ON DUPLICATE KEY UPDATE requests_made = requests_made + 1, last_request_at = %s",
                (
                    self.source_name,
                    now.date(),
                    self.max_daily_requests,
                    now,
                    now,
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
                (self.source_name, datetime.now(timezone.utc).date()),
            )
            row = cursor.fetchone()
            used = row[0] if row else 0
            return self.max_daily_requests - used
        finally:
            cursor.close()
            conn.close()

    def _validate_response(self, data, required_keys, context="", strict=False):
        """Validate that a response dict contains all required keys.

        Args:
            data: The parsed response data to validate.
            required_keys: Iterable of key names that must be present.
            context: Optional description for log messages (e.g. endpoint name).
            strict: If True, raise ValueError on validation failure.

        Returns:
            bool: True if all required keys are present, False otherwise.
        """
        if not isinstance(data, dict):
            msg = f"Response validation failed{f' ({context})' if context else ''}: expected dict, got {type(data).__name__}"
            self.logger.warning(msg)
            if strict:
                raise ValueError(msg)
            return False

        missing = [k for k in required_keys if k not in data]
        if missing:
            msg = (
                f"Response validation failed{f' ({context})' if context else ''}: "
                f"missing keys {missing}. Available keys: {list(data.keys())}"
            )
            self.logger.warning(msg)
            if strict:
                raise ValueError(msg)
            return False

        return True

    @staticmethod
    def _get_case_insensitive(data, key, default=None):
        """Case-insensitive dict key lookup.

        Handles API inconsistencies like 'totalrecords' vs 'totalRecords'.

        Args:
            data: Dict to search.
            key: Key name to look up (case-insensitive).
            default: Value to return if key not found.

        Returns:
            The value for the matching key, or default if not found.
        """
        if not isinstance(data, dict):
            return default
        key_lower = key.lower()
        for k, v in data.items():
            if k.lower() == key_lower:
                return v
        return default

    def _request_with_retry(self, method, url, params=None, json_body=None,
                            max_retries=3, backoff_factor=2, timeout=TIMEOUT_DEFAULT,
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

        Raises immediately on 429 (daily rate limit reached).
        Retries on 5xx (server error) responses.
        """

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
                    # Rate counter incremented on success. If caller crashes
                    # after increment, quota is consumed for unprocessed
                    # records. Accepted as design tradeoff — over-counting is
                    # safer than under-counting for rate-limited APIs.
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
                error_text = response.text
                self.logger.debug(
                    "Full error response body: %s", error_text
                )
                self.logger.error(
                    "Request failed: %d %s", response.status_code, error_text[:2000]
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
        params = dict(params or {})
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
        params = dict(params or {})
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
                 offset_start=0,               # starting offset for offset-style pagination
                 max_pages=1000):              # safety guard: max pages before breaking
        """Generic paginator — parameterize instead of reimplementing.

        Supports three end-of-page detection strategies:
          1. has_next_key  — stop when response[has_next_key] is falsy (USASpending)
          2. total_pages_key — stop when page >= response[total_pages_key] (Subaward)
          3. total_key — stop when offset/page*size >= response[total_key] (SAM default)

        When results_key is None (legacy behavior), yields the full parsed response
        dict for each page. When results_key is set, yields the results list for
        each page.

        Args:
            max_pages: Safety guard to prevent infinite pagination loops.
                When reached, logs a warning and stops. Default 1000.

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
        pages_fetched = 0
        total_records_fetched = 0

        while True:
            if pagination_style == "page":
                params[page_param] = page
            else:  # offset
                params[offset_param] = offset

            response = self.get(endpoint, params=params)
            data = response.json()
            pages_fetched += 1

            if results_key is not None:
                # 83-8: Warn if expected results key is missing from response
                if results_key not in data:
                    self.logger.warning(
                        "Expected results key '%s' not found in response. "
                        "Available keys: %s. Treating as empty results.",
                        results_key, list(data.keys()),
                    )
                results = data.get(results_key, [])
                total_records_fetched += len(results)
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

            # 83-5: Max pages safety guard
            if pages_fetched >= max_pages:
                self.logger.warning(
                    "Pagination stopped: reached max_pages limit (%d). "
                    "Total records fetched so far: %d",
                    max_pages, total_records_fetched,
                )
                break

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
                # Short page = end of results, even if total claims more.
                short_page = (
                    results_for_check is not None
                    and len(results_for_check) < page_size
                )
                if pagination_style == "page":
                    page += 1
                    if page * page_size >= total or short_page:
                        break
                else:
                    offset += page_size
                    if offset >= total or short_page:
                        break
