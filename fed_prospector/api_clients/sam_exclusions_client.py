"""SAM.gov Exclusions API v4 client.

Wraps the Entity Information Exclusions API for checking whether entities
(vendors, individuals) are excluded from federal contracting.
Used for due diligence on teaming partners and competitors.

API endpoint: GET /entity-information/v4/exclusions
Auth: api_key query parameter (handled by BaseAPIClient.get())
Pagination: page-based (page starts at 0, size max 10)
Rate limit: Shares daily quota with other SAM.gov APIs
"""

# OpenAPI spec: thesolution/sam_gov_api/exclusions-api.yaml

import logging

from api_clients.base_client import BaseAPIClient, RateLimitExceeded


logger = logging.getLogger("fed_prospector.api.sam_exclusions")


class SAMExclusionsClient(BaseAPIClient):
    """Client for the SAM.gov Exclusions API v4.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    Provides methods for searching exclusions and checking specific entities.

    Usage:
        client = SAMExclusionsClient(api_key_number=2)

        # Search exclusions
        result = client.search_exclusions(exclusionType="Ineligible")

        # Check a specific UEI
        exclusions = client.check_entity("ABC123DEF456")

        # Batch check multiple UEIs
        results = client.check_entities(["UEI1", "UEI2", "UEI3"])
    """

    SEARCH_ENDPOINT = "/entity-information/v4/exclusions"

    def __init__(self, api_key_number=1):
        """Initialize SAM Exclusions client. See _sam_init_kwargs() for key selection."""
        super().__init__(**self._sam_init_kwargs("sam_exclusions", api_key_number))

    # -----------------------------------------------------------------
    # Core search
    # -----------------------------------------------------------------

    def search_exclusions(self, uei=None, q=None, excluding_agency_code=None,
                          exclusion_type=None, exclusion_program=None,
                          size=10, page=0):
        """Search exclusions with filters. Returns one page of results.

        Uses GET to /entity-information/v4/exclusions with query parameters.
        All filter parameters are optional; omitted filters are not sent.

        Args:
            uei: UEI SAM identifier to search.
            q: Free-text name search (entity or individual name).
            excluding_agency_code: Agency code that issued the exclusion.
            exclusion_type: Type of exclusion (e.g. "Ineligible (Proceedings Completed)").
            exclusion_program: Exclusion program (e.g. "Reciprocal", "Nonprescribed").
            size: Records per page (max 10 per SAM API).
            page: 0-based page number for pagination.

        Returns:
            dict with keys: totalRecords, excludedEntity (list of
            exclusion dicts).
        """
        params = {
            "size": size,
            "page": page,
        }

        if uei is not None:
            params["ueiSAM"] = uei
        if q is not None:
            params["q"] = q
        if excluding_agency_code is not None:
            params["excludingAgencyCode"] = excluding_agency_code
        if exclusion_type is not None:
            params["exclusionType"] = exclusion_type
        if exclusion_program is not None:
            params["exclusionProgram"] = exclusion_program

        self.logger.debug(
            "Exclusion search page=%d size=%d params=%s", page, size, params
        )
        response = self.get(self.SEARCH_ENDPOINT, params=params)
        return response.json()

    def search_exclusions_all(self, **kwargs):
        """Generator that paginates through all results from search_exclusions.

        Accepts all the same keyword arguments as search_exclusions except
        page (which is managed internally). Yields individual exclusion dicts
        from the excludedEntity[] array.

        Yields:
            dict: Individual exclusion records from the excludedEntity list.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("page", None)
        size = kwargs.get("size", 10)
        for page_results in self.paginate(
            self.SEARCH_ENDPOINT,
            params=self._build_params(**kwargs),
            page_size=size,
            pagination_style="page",
            page_param="page",
            size_param="size",
            page_start=0,
            total_key="totalRecords",
            results_key="excludedEntity",
        ):
            yield from page_results

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def check_entity(self, uei):
        """Check if a specific UEI is excluded.

        Args:
            uei: UEI SAM identifier string.

        Returns:
            list[dict]: All exclusion records for this UEI (empty if not excluded).
        """
        self.logger.info("Checking exclusions for UEI %s", uei)
        return list(self.search_exclusions_all(uei=uei))

    def check_entities(self, uei_list):
        """Batch check multiple UEIs for exclusions.

        Makes a separate API call for each UEI. Returns a dict mapping
        each UEI to its list of exclusion records (empty list if clean).

        Args:
            uei_list: List of UEI SAM identifier strings.

        Returns:
            dict[str, list[dict]]: Mapping of UEI -> exclusion records.
                Only UEIs with exclusions are included in the result.
        """
        results = {}
        for uei in uei_list:
            try:
                exclusions = self.check_entity(uei)
                if exclusions:
                    results[uei] = exclusions
            except RateLimitExceeded:
                self.logger.warning(
                    "Rate limit reached during batch check. "
                    "Checked %d of %d UEIs so far.",
                    len(results), len(uei_list),
                )
                break

        self.logger.info(
            "Batch exclusion check complete: %d UEIs checked, %d excluded",
            len(uei_list), len(results),
        )
        return results

    def search_by_name(self, name):
        """Search exclusions by entity or individual name.

        Args:
            name: Name string to search (partial match supported).

        Returns:
            list[dict]: All matching exclusion records.
        """
        self.logger.info("Searching exclusions for name '%s'", name)
        return list(self.search_exclusions_all(q=name))

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _build_params(self, uei=None, q=None, excluding_agency_code=None,
                      exclusion_type=None, exclusion_program=None,
                      size=10, **_ignored):
        """Build the query params dict for a single-page exclusions search.

        Used by search_exclusions_all() to pass a clean params dict into
        paginate() (without page/size, which paginate() manages).

        Returns:
            dict: Query parameters ready for the SAM Exclusions API.
        """
        params = {}

        if uei is not None:
            params["ueiSAM"] = uei
        if q is not None:
            params["q"] = q
        if excluding_agency_code is not None:
            params["excludingAgencyCode"] = excluding_agency_code
        if exclusion_type is not None:
            params["exclusionType"] = exclusion_type
        if exclusion_program is not None:
            params["exclusionProgram"] = exclusion_program

        return params
