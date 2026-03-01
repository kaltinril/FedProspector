"""SAM.gov Contract Awards API v1 client.

Wraps the Contract Awards Search API for finding federal contract award data.
Used to populate the fpds_contract table with award-level detail not available
from USASpending or FPDS ATOM feeds.

API endpoint: GET /contract-awards/v1/search
Auth: api_key query parameter (handled by BaseAPIClient.get())
Pagination: offset-based (limit max 100, offset starts at 0)
Date format: YYYYMMDD,YYYYMMDD range format (no separators)
Rate limit: Shares daily quota with other SAM.gov APIs
"""

import logging
from datetime import date, datetime

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings


logger = logging.getLogger("fed_prospector.api.sam_awards")


class SAMAwardsClient(BaseAPIClient):
    """Client for the SAM.gov Contract Awards API v1.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    Provides convenience methods for searching contract awards by NAICS,
    awardee UEI, or contract PIID.

    Usage:
        client = SAMAwardsClient(api_key_number=2)

        # Single search
        result = client.search_awards(naics_code="541511", set_aside="WOSB")

        # Paginate through all results
        for award in client.search_awards_all(naics_code="541511"):
            print(award["contractId"]["contractNumber"])

        # Convenience: search by NAICS codes
        awards = client.search_by_naics(["541511", "541512"])
    """

    SEARCH_ENDPOINT = "/contract-awards/v1/search"

    def __init__(self, api_key_number=1):
        """Initialize SAM Awards client.

        Args:
            api_key_number: Which API key to use (1 or 2). Key 2 has
                1000/day limit vs 10/day for key 1.
        """
        if api_key_number == 2:
            api_key = settings.SAM_API_KEY_2
            daily_limit = settings.SAM_DAILY_LIMIT_2
        else:
            api_key = settings.SAM_API_KEY
            daily_limit = settings.SAM_DAILY_LIMIT

        # Separate source_name from SAM_OPPORTUNITY for independent rate tracking
        source_name = "SAM_AWARDS"

        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=daily_limit,
        )

    # -----------------------------------------------------------------
    # Core search
    # -----------------------------------------------------------------

    def search_awards(self, naics_code=None, set_aside=None, agency_code=None,
                      date_signed_from=None, date_signed_to=None,
                      awardee_uei=None, psc_code=None, piid=None,
                      fiscal_year=None, pop_state=None,
                      limit=100, offset=0):
        """Search contract awards with filters. Returns one page of results.

        Uses GET to /contract-awards/v1/search with query parameters.
        All filter parameters are optional; omitted filters are not sent.

        Args:
            naics_code: NAICS code string (e.g. "541511").
            set_aside: Set-aside type code (e.g. "WOSB", "8A").
            agency_code: Awarding agency code.
            date_signed_from: Start of date signed range (date, datetime,
                or YYYYMMDD string).
            date_signed_to: End of date signed range.
            awardee_uei: Awardee UEI identifier.
            psc_code: Product or Service Code.
            piid: Contract PIID (Procurement Instrument Identifier).
            fiscal_year: Federal fiscal year (e.g. 2025).
            pop_state: Place of performance state code.
            limit: Records per page (max 100 per SAM API).
            offset: 0-based record offset for pagination.

        Returns:
            dict with keys: totalRecords, limit, offset, data (list of
            award dicts).
        """
        params = {
            "limit": limit,
            "offset": offset,
        }

        if naics_code is not None:
            params["naicsCode"] = naics_code
        if set_aside is not None:
            params["typeOfSetAside"] = set_aside
        if agency_code is not None:
            params["agencyCode"] = agency_code
        if awardee_uei is not None:
            params["awardeeUEI"] = awardee_uei
        if psc_code is not None:
            params["productOrServiceCode"] = psc_code
        if piid is not None:
            params["piid"] = piid
        if fiscal_year is not None:
            params["fiscalYear"] = str(fiscal_year)
        if pop_state is not None:
            params["popState"] = pop_state

        # Date range filter: "YYYYMMDD,YYYYMMDD" format
        if date_signed_from is not None or date_signed_to is not None:
            params["dateSigned"] = self._format_date_range(
                date_signed_from, date_signed_to
            )

        self.logger.debug(
            "Award search offset=%d limit=%d params=%s", offset, limit, params
        )
        response = self.get(self.SEARCH_ENDPOINT, params=params)
        return response.json()

    def search_awards_all(self, **kwargs):
        """Generator that paginates through all results from search_awards.

        Accepts all the same keyword arguments as search_awards except
        offset (which is managed internally). Yields individual award dicts
        from the data[] array.

        Yields:
            dict: Individual award records from the data list.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("offset", None)
        limit = kwargs.get("limit", 100)
        offset = 0
        total_yielded = 0

        while True:
            data = self.search_awards(offset=offset, **kwargs)
            total_records = data.get("totalRecords", 0)
            results = data.get("data", [])

            for award in results:
                total_yielded += 1
                yield award

            self.logger.info(
                "Page at offset %d: %d results (total available: %d, yielded so far: %d)",
                offset, len(results), total_records, total_yielded,
            )

            if not results:
                break

            offset += limit
            if offset >= total_records:
                break

        self.logger.info("Award search complete: %d total results", total_yielded)

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def search_by_naics(self, naics_codes, date_from=None, date_to=None,
                        set_aside=None):
        """Search for awards by one or more NAICS codes.

        Makes a separate paginated search for each NAICS code and returns
        all results combined. Results are not deduplicated (different NAICS
        codes should not return overlapping contracts).

        Args:
            naics_codes: Single NAICS code string or list of strings.
            date_from: Optional start date for date_signed range.
            date_to: Optional end date for date_signed range.
            set_aside: Optional set-aside type filter.

        Returns:
            list[dict]: All matching award records.
        """
        if isinstance(naics_codes, str):
            naics_codes = [naics_codes]

        all_awards = []
        for code in naics_codes:
            self.logger.info("Searching awards for NAICS %s", code)
            try:
                for award in self.search_awards_all(
                    naics_code=code,
                    date_signed_from=date_from,
                    date_signed_to=date_to,
                    set_aside=set_aside,
                ):
                    all_awards.append(award)
            except RateLimitExceeded:
                self.logger.warning(
                    "Rate limit reached during NAICS %s search. "
                    "Returning %d results collected so far.",
                    code, len(all_awards),
                )
                break

        self.logger.info(
            "NAICS search complete: %d codes, %d total awards",
            len(naics_codes), len(all_awards),
        )
        return all_awards

    def search_by_awardee(self, uei, date_from=None, date_to=None):
        """Find all awards for a specific vendor by UEI.

        Args:
            uei: Awardee UEI string.
            date_from: Optional start date for date_signed range.
            date_to: Optional end date for date_signed range.

        Returns:
            list[dict]: All matching award records.
        """
        self.logger.info("Searching awards for awardee UEI %s", uei)
        return list(self.search_awards_all(
            awardee_uei=uei,
            date_signed_from=date_from,
            date_signed_to=date_to,
        ))

    def search_by_solicitation(self, piid):
        """Find awards by contract PIID.

        Args:
            piid: Contract PIID (Procurement Instrument Identifier).

        Returns:
            list[dict]: All matching award records.
        """
        self.logger.info("Searching awards for PIID %s", piid)
        return list(self.search_awards_all(piid=piid))

    def estimate_calls_needed(self, naics_codes, date_from, date_to):
        """Rough estimate of API calls needed for a multi-NAICS search.

        Each NAICS code requires at least 1 API call. Additional calls are
        needed for pagination (1 per 100 results). This estimate assumes
        1 call per NAICS code as a minimum baseline for budgeting.

        Args:
            naics_codes: List of NAICS code strings.
            date_from: Start date (not used in calculation, kept for interface).
            date_to: End date (not used in calculation, kept for interface).

        Returns:
            int: Minimum number of API calls needed.
        """
        if isinstance(naics_codes, str):
            naics_codes = [naics_codes]
        return len(naics_codes)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _format_date_range(from_date, to_date):
        """Convert two dates to "YYYYMMDD,YYYYMMDD" format for the API.

        Handles date objects, datetime objects, and strings. If a date is
        None, it is omitted from the range (producing ",YYYYMMDD" or
        "YYYYMMDD,").

        Args:
            from_date: Start date (date, datetime, or YYYYMMDD string), or None.
            to_date: End date (date, datetime, or YYYYMMDD string), or None.

        Returns:
            str: Date range in "YYYYMMDD,YYYYMMDD" format.
        """
        def fmt(d):
            if d is None:
                return ""
            if isinstance(d, (date, datetime)):
                return d.strftime("%Y%m%d")
            # Already a string -- strip any separators just in case
            s = str(d).replace("-", "").replace("/", "")
            return s

        return f"{fmt(from_date)},{fmt(to_date)}"
