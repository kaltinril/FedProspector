"""SAM.gov Opportunities noticedesc client.

Fetches the plain-text description for an opportunity by notice id from the
SAM.gov noticedesc endpoint. Port of the C# ``FetchDescriptionAsync`` logic in
``api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`` so the
ETL/poller side can run the same on-demand fetches that the App API runs.

This client surfaces a richer 429 signal than the base class: when SAM.gov
returns a daily-quota 429 the client raises ``DescriptionFetchRateLimited``,
a ``RateLimitExceeded`` subclass that carries a ``reset_at`` datetime so
callers (the poller, the demand loader) can persist when to retry instead of
blindly failing the request.

Endpoint: GET ``/opportunities/v1/noticedesc``
Auth: ``api_key`` query parameter (handled by BaseAPIClient.get())
Rate limit: Shares SAM.gov per-key daily quota. Key 2 (1,000/day) is the
default — Key 1's 10/day cap is too tight for on-demand description fetches.
"""

import html
import logging
import re
from datetime import datetime, time, timedelta, timezone

import requests

from api_clients.base_client import BaseAPIClient, RateLimitExceeded


logger = logging.getLogger("fed_prospector.api.sam_opportunities")


# noticedesc path on the SAM.gov host. Mirrors the URL shape the C#
# ``FetchDescriptionAsync`` consumes (the opportunity row's ``description_url``
# already points at this same endpoint, including the noticeid query param).
NOTICEDESC_ENDPOINT = "/opportunities/v1/noticedesc"

# HTML tag regex — matches the C# ``HtmlTagRegex`` ("<[^>]+>").
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Whitespace collapse regex — matches the C# ``Regex.Replace(text, @"\s+", " ")``.
_WHITESPACE_RE = re.compile(r"\s+")


class DescriptionFetchRateLimited(RateLimitExceeded):
    """Raised when SAM.gov noticedesc returns 429 (daily quota exhausted).

    Carries a ``reset_at`` (timezone-aware UTC datetime) sourced from the
    ``nextAccessTime`` field in the 429 response body, with fallback to the
    next UTC midnight (when SAM.gov Key 2's daily quota resets — see
    thesolution/phases/123-GRACEFUL-RATE-LIMIT-HANDLING.md).
    """

    def __init__(self, message: str, reset_at: datetime | None = None):
        super().__init__(message)
        self.reset_at = reset_at


class SamOpportunitiesClient(BaseAPIClient):
    """Client for SAM.gov's opportunity description endpoint.

    Inherits API key handling and rate-counter bookkeeping from BaseAPIClient,
    but bypasses ``_request_with_retry`` for the 429 path so we can attach the
    reset-time signal callers need.

    Usage:
        client = SamOpportunitiesClient()  # key 2 by default
        try:
            text = client.fetch_description_text(notice_id)
        except DescriptionFetchRateLimited as e:
            queue_for_retry_after(e.reset_at)
    """

    def __init__(self, api_key_number: int = 2):
        """Initialize the noticedesc client.

        Args:
            api_key_number: 1 (10/day) or 2 (1,000/day). Defaults to 2 because
                on-demand description fetches would exhaust Key 1's daily
                quota almost immediately.
        """
        super().__init__(
            **self._sam_init_kwargs("sam_opportunities", api_key_number)
        )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def fetch_description_text(self, notice_id: str) -> str:
        """Fetch and HTML-strip the description for ``notice_id``.

        Args:
            notice_id: SAM.gov notice id (UUID-like string).

        Returns:
            Plain-text description with HTML tags removed, entities decoded,
            and runs of whitespace collapsed to single spaces.

        Raises:
            DescriptionFetchRateLimited: SAM.gov returned 429. ``reset_at`` on
                the exception indicates when the daily quota resets.
            ValueError: ``notice_id`` is empty, or the response had no
                ``description`` field / it was empty.
            requests.HTTPError: Non-200 / non-429 HTTP error.
            requests.RequestException: Network / timeout error.
        """
        if not notice_id or not notice_id.strip():
            raise ValueError("notice_id must be a non-empty string")

        params = {"noticeid": notice_id}
        # We can't use BaseAPIClient.get() here because its retry path raises a
        # plain HTTPError on 429, losing the nextAccessTime. Instead, drive the
        # session directly and intercept 429 ourselves.
        url = f"{self.base_url}{NOTICEDESC_ENDPOINT}"
        request_params = dict(params)
        if self.api_key:
            request_params["api_key"] = self.api_key

        self.logger.debug("Fetching noticedesc for notice_id=%s", notice_id)
        response = self.session.get(url, params=request_params, timeout=30)

        if response.status_code == 429:
            reset_at = self._parse_reset_at(response)
            msg = self._format_429_message(reset_at)
            self.logger.warning(
                "noticedesc 429 for notice_id=%s — reset_at=%s",
                notice_id, reset_at.isoformat() if reset_at else "unknown",
            )
            raise DescriptionFetchRateLimited(msg, reset_at=reset_at)

        if response.status_code != 200:
            self.logger.error(
                "noticedesc failed for notice_id=%s: %d %s",
                notice_id, response.status_code, response.text[:500],
            )
            # raise_for_status() produces an HTTPError with the response
            # attached — matches what _request_with_retry surfaces.
            response.raise_for_status()

        # Success — bookkeep against the daily quota like other endpoints do.
        self._increment_rate_counter()

        body = response.json()
        html_description = body.get("description") if isinstance(body, dict) else None
        if not html_description or not html_description.strip():
            raise ValueError(
                f"SAM.gov returned empty description for notice_id={notice_id}"
            )

        plain_text = self._strip_html_tags(html_description)
        self.logger.debug(
            "noticedesc ok for notice_id=%s (%d chars)",
            notice_id, len(plain_text),
        )
        return plain_text

    # -----------------------------------------------------------------
    # Helpers — ported from C# OpportunityService
    # -----------------------------------------------------------------

    @staticmethod
    def _strip_html_tags(text: str) -> str:
        """Port of C# ``StripHtmlTags``.

        1. Remove all HTML tags via ``<[^>]+>`` regex.
        2. Decode common HTML entities (``html.unescape`` covers the explicit
           list the C# does — ``&nbsp;`` ``&amp;`` ``&lt;`` ``&gt;`` ``&quot;``
           ``&#39;`` ``&apos;`` — plus everything else).
        3. Collapse runs of whitespace/newlines into single spaces and trim.
        """
        stripped = _HTML_TAG_RE.sub("", text)
        decoded = html.unescape(stripped)
        # C# does .Replace("&nbsp;", " ") which yields a regular space.
        # html.unescape turns &nbsp; into U+00A0 (non-breaking space); fold it
        # into a regular space so the \s+ collapse below catches it.
        decoded = decoded.replace(" ", " ")
        collapsed = _WHITESPACE_RE.sub(" ", decoded).strip()
        return collapsed

    @staticmethod
    def _parse_reset_at(response: requests.Response) -> datetime | None:
        """Pull ``nextAccessTime`` from a 429 body. Fall back to next UTC midnight.

        SAM.gov Key 2's 1,000/day quota resets at UTC midnight (per Phase 123
        plan), so a fresh midnight is the correct fallback when the body
        doesn't include the field.
        """
        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            next_access = body.get("nextAccessTime")
            if next_access:
                parsed = SamOpportunitiesClient._parse_next_access_time(next_access)
                if parsed is not None:
                    return parsed

        # Fallback: SAM Key 2 daily quota resets at UTC midnight.
        return SamOpportunitiesClient._next_utc_midnight()

    @staticmethod
    def _parse_next_access_time(value: str) -> datetime | None:
        """Best-effort parse of SAM's ``nextAccessTime`` string.

        Known formats observed in production:
          * ISO 8601 with Z suffix: ``2026-05-29T00:00:00Z``
          * SAM custom: ``2026-Mar-10 00:00:00+0000 UTC`` (matches the format
            ``base_client._request_with_retry`` already parses for logging).
        """
        if not isinstance(value, str) or not value.strip():
            return None

        candidate = value.strip()

        # ISO 8601 — fromisoformat handles "+00:00" but historically not "Z".
        iso_candidate = candidate.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

        # SAM custom: "2026-Mar-10 00:00:00+0000 UTC"
        try:
            cleaned = candidate.replace(" UTC", "").replace("+0000", "")
            dt = datetime.strptime(cleaned.strip(), "%Y-%b-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _next_utc_midnight(now: datetime | None = None) -> datetime:
        """Return the next UTC midnight after ``now`` (default: current UTC)."""
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        return datetime.combine(tomorrow, time(0, 0, 0), tzinfo=timezone.utc)

    @staticmethod
    def _format_429_message(reset_at: datetime | None) -> str:
        if reset_at is None:
            return "SAM.gov noticedesc 429 — daily quota exhausted"
        return (
            f"SAM.gov noticedesc 429 — daily quota exhausted, "
            f"resets at {reset_at.isoformat()}"
        )


# ---------------------------------------------------------------------------
# Smoke test: ``python -m api_clients.sam_opportunities_client``
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import json
    from unittest.mock import MagicMock, patch

    print("Smoke test: 429 with nextAccessTime -> DescriptionFetchRateLimited")

    # Patch settings + DB so construction doesn't need a real env.
    with patch("api_clients.base_client.get_connection", MagicMock()):
        from config import settings as _s
        _s.SAM_API_KEY = "test-key-1"
        _s.SAM_API_KEY_2 = "test-key-2"
        _s.SAM_API_BASE_URL = "https://api.sam.gov"
        _s.SAM_DAILY_LIMIT = 10
        _s.SAM_DAILY_LIMIT_2 = 1000

        client = SamOpportunitiesClient(api_key_number=2)

        fake_response = MagicMock()
        fake_response.status_code = 429
        fake_response.json.return_value = {"nextAccessTime": "2026-05-29T00:00:00Z"}
        fake_response.text = json.dumps(fake_response.json.return_value)
        client.session = MagicMock()
        client.session.get.return_value = fake_response

        try:
            client.fetch_description_text("abc123")
        except DescriptionFetchRateLimited as e:
            assert e.reset_at is not None, "reset_at should be populated"
            assert e.reset_at == datetime(2026, 5, 29, tzinfo=timezone.utc), (
                f"unexpected reset_at: {e.reset_at!r}"
            )
            print(f"  OK — reset_at={e.reset_at.isoformat()}")
        else:
            raise AssertionError("expected DescriptionFetchRateLimited")

    print("Smoke test: HTML stripping matches C# semantics")
    sample = "<p>Hello&nbsp;<b>world</b>&amp;&#39;friends&#39;</p>\n<br/>\n  spaces"
    expected = "Hello world&'friends' spaces"
    actual = SamOpportunitiesClient._strip_html_tags(sample)
    assert actual == expected, f"got {actual!r}, expected {expected!r}"
    print(f"  OK — {actual!r}")

    print("Smoke test: _next_utc_midnight")
    now = datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc)
    nxt = SamOpportunitiesClient._next_utc_midnight(now=now)
    assert nxt == datetime(2026, 5, 29, 0, 0, tzinfo=timezone.utc)
    print(f"  OK — {nxt.isoformat()}")

    print("All smoke tests passed.")
