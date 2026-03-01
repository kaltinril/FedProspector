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
from datetime import date, datetime

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings


logger = logging.getLogger("fed_prospector.api.sam_subaward")


class SAMSubawardClient(BaseAPIClient):
    """Client for the SAM.gov Acquisition Subaward Reporting API v1.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    Provides methods for searching subcontracts by prime, subcontractor,
    NAICS code, or agency.

    Usage:
        client = SAMSubawardClient(api_key_number=2)

        # Single page search
        result = client.search_subcontracts(agencyId="9700")

        # Paginate through all results
        for sub in client.search_subcontracts_all(agencyId="9700"):
            print(sub["piid"], sub["subEntityLegalBusinessName"])

        # Find subcontracts under a specific prime
        subs = client.search_by_prime("ABC123DEF456")
    """

    SEARCH_ENDPOINT = "/prod/contract/v1/subcontracts/search"

    def __init__(self, api_key_number=1):
        """Initialize SAM Subaward client.

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

        # Separate source_name for independent rate tracking
        source_name = "SAM_SUBAWARD"

        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=daily_limit,
        )

    # -----------------------------------------------------------------
    # Core search
    # -----------------------------------------------------------------

    def search_subcontracts(self, piid=None, agency_id=None,
                            prime_uei=None, sub_uei=None,
                            naics_code=None, from_date=None, to_date=None,
                            prime_award_type=None, status="Published",
                            page_number=0, page_size=100):
        """Search subcontracts with filters. Returns one page of results.

        Uses GET to /prod/contract/v1/subcontracts/search with query params.
        All filter parameters are optional; omitted filters are not sent.

        Args:
            piid: Procurement Instrument Identifier for the prime contract.
            agency_id: Four-digit contracting agency code.
            prime_uei: Prime contractor UEI identifier.
            sub_uei: Subcontractor UEI identifier.
            naics_code: NAICS code filter (searches primeNaics field).
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
            params["PIID"] = piid
        if agency_id is not None:
            params["agencyId"] = agency_id
        if prime_uei is not None:
            params["primeEntityUei"] = prime_uei
        if sub_uei is not None:
            params["subEntityUei"] = sub_uei
        if naics_code is not None:
            params["primeNaics"] = naics_code
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
        page_number = 0
        total_yielded = 0
        pages_fetched = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                break

            data = self.search_subcontracts(page_number=page_number, **kwargs)
            total_records = data.get("totalRecords", 0)
            total_pages = data.get("totalPages", 0)
            results = data.get("data", [])
            pages_fetched += 1

            for sub in results:
                total_yielded += 1
                yield sub

            self.logger.info(
                "Page %d/%d: %d results (total available: %d, yielded so far: %d)",
                page_number + 1, total_pages, len(results),
                total_records, total_yielded,
            )

            if not results:
                break

            page_number += 1
            if page_number >= total_pages:
                break

        self.logger.info("Subaward search complete: %d total results", total_yielded)

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def search_by_prime(self, prime_uei, **kwargs):
        """Find subcontracts under a specific prime contractor.

        Args:
            prime_uei: Prime contractor UEI identifier.
            **kwargs: Additional filters passed to search_subcontracts_all.

        Returns:
            list[dict]: All matching subaward records.
        """
        self.logger.info("Searching subcontracts for prime UEI %s", prime_uei)
        return list(self.search_subcontracts_all(prime_uei=prime_uei, **kwargs))

    def search_by_sub(self, sub_uei, **kwargs):
        """Find all subcontracts awarded TO a specific entity.

        Args:
            sub_uei: Subcontractor UEI identifier.
            **kwargs: Additional filters passed to search_subcontracts_all.

        Returns:
            list[dict]: All matching subaward records.
        """
        self.logger.info("Searching subcontracts for sub UEI %s", sub_uei)
        return list(self.search_subcontracts_all(sub_uei=sub_uei, **kwargs))

    def search_by_naics(self, naics_code, **kwargs):
        """Find subcontracts in a specific NAICS code.

        Args:
            naics_code: NAICS code string (e.g. "541511").
            **kwargs: Additional filters passed to search_subcontracts_all.

        Returns:
            list[dict]: All matching subaward records.
        """
        self.logger.info("Searching subcontracts for NAICS %s", naics_code)
        return list(self.search_subcontracts_all(naics_code=naics_code, **kwargs))

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

    @staticmethod
    def _format_date(d):
        """Convert a date to yyyy-MM-dd format for the API.

        Args:
            d: date object, datetime object, or string.

        Returns:
            str: Date in yyyy-MM-dd format.
        """
        if isinstance(d, (date, datetime)):
            return d.strftime("%Y-%m-%d")
        # Already a string -- ensure yyyy-MM-dd format
        s = str(d).strip()
        # Handle MM/DD/YYYY
        if len(s) == 10 and s[2] == "/" and s[5] == "/":
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}"
        return s
