"""SAM.gov Contract Awards API v1 client.

Wraps the Contract Awards Search API for finding federal contract award data.
Used to populate the fpds_contract table with award-level detail not available
from USASpending or FPDS ATOM feeds.

API endpoint: GET /contract-awards/v1/search
Auth: api_key query parameter (handled by BaseAPIClient.get())
Pagination: offset-based (limit max 100, offset starts at 0)
Date format: [MM/DD/YYYY,MM/DD/YYYY] range format (with square brackets)
Rate limit: Shares daily quota with other SAM.gov APIs
"""

# OpenAPI spec: thesolution/sam_gov_api/contract-awards.yaml

import logging
from datetime import date, datetime

from api_clients.base_client import BaseAPIClient, RateLimitExceeded


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
        """Initialize SAM Awards client. See _sam_init_kwargs() for key selection."""
        super().__init__(**self._sam_init_kwargs("SAM_AWARDS", api_key_number))

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
            params["typeOfSetAsideCode"] = set_aside
        if agency_code is not None:
            params["contractingDepartmentCode"] = agency_code
        if awardee_uei is not None:
            params["awardeeUniqueEntityId"] = awardee_uei
        if psc_code is not None:
            params["productOrServiceCode"] = psc_code
        if piid is not None:
            params["piid"] = piid
        if fiscal_year is not None:
            params["fiscalYear"] = str(fiscal_year)
        if pop_state is not None:
            params["popState"] = pop_state

        # Date range filter: "[MM/DD/YYYY,MM/DD/YYYY]" format
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
        from the awardSummary[] array.

        NOTE: The SAM Awards API 'offset' parameter is a PAGE INDEX, not a
        record offset. Page 0 returns records 0-99, page 1 returns 100-199,
        etc. We use pagination_style="page" with page_param="offset" to
        match SAM's unusual naming convention.

        Yields:
            dict: Individual award records from the awardSummary list.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("offset", None)
        limit = kwargs.get("limit", 100)
        for page_results in self.paginate(
            self.SEARCH_ENDPOINT,
            params=self._build_params(**kwargs),
            page_size=limit,
            pagination_style="page",
            page_param="offset",   # SAM uses "offset" param but treats it as page index
            size_param="limit",
            page_start=0,
            total_key="totalRecords",
            results_key="awardSummary",
        ):
            yield from page_results

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

    def _build_params(self, naics_code=None, set_aside=None, agency_code=None,
                      date_signed_from=None, date_signed_to=None,
                      awardee_uei=None, psc_code=None, piid=None,
                      fiscal_year=None, pop_state=None,
                      limit=100, **_ignored):
        """Build the query params dict for a single-page awards search.

        Accepts the same keyword arguments as search_awards (minus offset/limit,
        which paginate() manages). Used by search_awards_all() to pass a clean
        params dict into paginate().

        Returns:
            dict: Query parameters ready for the SAM Awards API.
        """
        params = {}

        if naics_code is not None:
            params["naicsCode"] = naics_code
        if set_aside is not None:
            params["typeOfSetAsideCode"] = set_aside
        if agency_code is not None:
            params["contractingDepartmentCode"] = agency_code
        if awardee_uei is not None:
            params["awardeeUniqueEntityId"] = awardee_uei
        if psc_code is not None:
            params["productOrServiceCode"] = psc_code
        if piid is not None:
            params["piid"] = piid
        if fiscal_year is not None:
            params["fiscalYear"] = str(fiscal_year)
        if pop_state is not None:
            params["popState"] = pop_state

        if date_signed_from is not None or date_signed_to is not None:
            params["dateSigned"] = self._format_date_range(
                date_signed_from, date_signed_to
            )

        return params

    @staticmethod
    def _format_date_range(from_date, to_date):
        """Convert two dates to "[MM/DD/YYYY,MM/DD/YYYY]" format for the API.

        The Contract Awards API expects dates in MM/DD/YYYY format with
        square brackets for ranges, e.g. [10/01/2025,09/30/2026].

        Args:
            from_date: Start date (date, datetime, or string), or None.
            to_date: End date (date, datetime, or string), or None.

        Returns:
            str: Date range in "[MM/DD/YYYY,MM/DD/YYYY]" format, or
                single date as "MM/DD/YYYY" if only one date provided.
        """
        def fmt(d):
            if d is None:
                return ""
            if isinstance(d, (date, datetime)):
                return d.strftime("%m/%d/%Y")
            # Try to parse string dates in various formats
            s = str(d)
            for parse_fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(s, parse_fmt)
                    return parsed.strftime("%m/%d/%Y")
                except ValueError:
                    continue
            return s

        f = fmt(from_date)
        t = fmt(to_date)
        if f and t:
            return f"[{f},{t}]"
        elif f:
            return f
        elif t:
            return t
        return ""
