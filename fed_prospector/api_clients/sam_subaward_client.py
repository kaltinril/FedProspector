"""SAM.gov Acquisition Subaward Reporting API v1 client.

Wraps the Acquisition Subaward Reporting API for finding which large primes
subcontract to WOSB/8(a) firms. Used for teaming partner identification.

API endpoint: GET /prod/contract/v1/subcontracts/search
Auth: api_key query parameter (handled by BaseAPIClient.get())
Pagination: page-based (pageNumber starts at 0, pageSize max 1,000)
Rate limit: Shares daily quota with other SAM.gov APIs
"""

# OpenAPI spec: thesolution/sam_gov_api/subawardreportingpublicapi.yaml

import logging

from api_clients.base_client import BaseAPIClient, RateLimitExceeded


logger = logging.getLogger("fed_prospector.api.sam_subaward")


class SAMSubawardClient(BaseAPIClient):
    """Client for the SAM.gov Acquisition Subaward Reporting API v1.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.

    Working filters:
        - PIID (Procurement Instrument Identifier)
        - agencyId (four-digit contracting agency code)
        - fromDate / toDate (date range)
        - primeAwardType (type of prime award)
        - status ("Published" or "Deleted")

    Note: primeNaics, primeEntityUei, and subEntityUei are accepted by the
    API without error but are SILENTLY IGNORED -- they have no effect on
    results (Phase 15 finding).

    Usage:
        client = SAMSubawardClient(api_key_number=2)

        # Single page search
        result = client.search_subcontracts(agency_id="9700")

        # Paginate through all results
        for sub in client.search_subcontracts_all(agency_id="9700"):
            print(sub["piid"], sub["subEntityLegalBusinessName"])

        # Find subcontracts under a specific prime contract
        subs = client.search_by_piid("W911NF-25-C-0001")
    """

    SEARCH_ENDPOINT = "/prod/contract/v1/subcontracts/search"

    def __init__(self, api_key_number=1):
        """Initialize SAM Subaward client. See _sam_init_kwargs() for key selection."""
        super().__init__(**self._sam_init_kwargs("SAM_SUBAWARD", api_key_number))

    # -----------------------------------------------------------------
    # Core search
    # -----------------------------------------------------------------

    def search_subcontracts(self, piid=None, agency_id=None,
                            from_date=None, to_date=None,
                            prime_award_type=None, status="Published",
                            page_number=0, page_size=100):
        """Search subcontracts with filters. Returns one page of results.

        Uses GET to /prod/contract/v1/subcontracts/search with query params.
        All filter parameters are optional; omitted filters are not sent.

        Args:
            piid: Procurement Instrument Identifier for the prime contract.
            agency_id: Four-digit contracting agency code.
            from_date: Start date (date, datetime, or yyyy-MM-dd string).
            to_date: End date (date, datetime, or yyyy-MM-dd string).
            prime_award_type: Type of prime award.
            status: Record status ("Published" or "Deleted"). Default: "Published".
            page_number: 0-based page index.
            page_size: Records per page (max 1,000).

        Returns:
            dict with keys: totalRecords, totalPages, pageNumber,
            nextPageLink, previousPageLink, data (list of subaward dicts).
        """
        params = {
            "pageNumber": page_number,
            "pageSize": page_size,
        }

        if piid is not None:
            params["piid"] = piid
        if agency_id is not None:
            params["agencyId"] = agency_id
        if from_date is not None:
            params["fromDate"] = self._format_date(from_date)
        if to_date is not None:
            params["toDate"] = self._format_date(to_date)
        if prime_award_type is not None:
            params["primeAwardType"] = prime_award_type
        if status is not None:
            params["status"] = status

        self.logger.debug(
            "Subaward search page=%d size=%d params=%s",
            page_number, page_size, params,
        )
        response = self.get(self.SEARCH_ENDPOINT, params=params)
        return response.json()

    def search_subcontracts_all(self, max_pages=None, **kwargs):
        """Generator that paginates through all results from search_subcontracts.

        Accepts all the same keyword arguments as search_subcontracts except
        page_number (which is managed internally). Yields individual subaward
        dicts from the data[] array.

        Args:
            max_pages: Optional maximum number of pages to fetch. None = all.
            **kwargs: Passed through to search_subcontracts.

        Yields:
            dict: Individual subaward records from the data list.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("page_number", None)
        page_size = kwargs.get("page_size", 100)
        pages_fetched = 0
        for page_results in self.paginate(
            self.SEARCH_ENDPOINT,
            params=self._build_params(**kwargs),
            page_size=page_size,
            pagination_style="page",
            page_param="pageNumber",
            size_param="pageSize",
            page_start=0,
            results_key="data",
            total_pages_key="totalPages",
        ):
            yield from page_results
            pages_fetched += 1
            if max_pages is not None and pages_fetched >= max_pages:
                break

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def search_by_piid(self, piid, **kwargs):
        """Find subcontracts under a specific prime contract by PIID.

        Args:
            piid: Prime contract Procurement Instrument Identifier.
            **kwargs: Additional filters passed to search_subcontracts_all.

        Returns:
            list[dict]: All matching subaward records.
        """
        self.logger.info("Searching subcontracts for PIID %s", piid)
        return list(self.search_subcontracts_all(piid=piid, **kwargs))

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _build_params(self, piid=None, agency_id=None,
                      from_date=None, to_date=None,
                      prime_award_type=None, status="Published",
                      page_size=100, **_ignored):
        """Build the query params dict for a single-page subcontracts search.

        Used by search_subcontracts_all() to pass a clean params dict into
        paginate() (without page_number/pageSize, which paginate() manages).
        Uses base class _format_date() (default %Y-%m-%d format).

        Returns:
            dict: Query parameters ready for the SAM Subaward API.
        """
        params = {}

        if piid is not None:
            params["piid"] = piid
        if agency_id is not None:
            params["agencyId"] = agency_id
        if from_date is not None:
            params["fromDate"] = self._format_date(from_date)
        if to_date is not None:
            params["toDate"] = self._format_date(to_date)
        if prime_award_type is not None:
            params["primeAwardType"] = prime_award_type
        if status is not None:
            params["status"] = status

        return params
