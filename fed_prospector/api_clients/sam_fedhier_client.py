"""SAM.gov Federal Hierarchy API v1 client.

Wraps the Federal Organizations API for retrieving the federal agency
hierarchy (departments, sub-tiers, and offices). Used to populate the
federal_organization table with the authoritative org structure.

API endpoint: GET /prod/federalorganizations/v1/orgs
Auth: api_key query parameter (handled by BaseAPIClient.get())
Pagination: offset-based (limit max 100, offset starts at 0)
Rate limit: Shares daily quota with other SAM.gov APIs
"""

# OpenAPI spec: thesolution/sam_gov_api/fh-public-hierarchy.yml, fh-public-org.yml

import logging
from datetime import date, datetime

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings


logger = logging.getLogger("fed_prospector.api.sam_fedhier")


class SAMFedHierClient(BaseAPIClient):
    """Client for the SAM.gov Federal Hierarchy API v1.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    Provides methods for retrieving and searching the federal organizational
    hierarchy (departments, sub-tier agencies, and offices).

    Usage:
        client = SAMFedHierClient(api_key_number=2)

        # Full load of all active organizations
        for org in client.get_all_organizations():
            print(org["fhorgname"])

        # Single org lookup
        org = client.get_organization(100000000)

        # Search by name
        orgs = client.search_organizations(fhorgname="Defense")
    """

    SEARCH_ENDPOINT = "/prod/federalorganizations/v1/orgs"

    def __init__(self, api_key_number=1):
        """Initialize SAM Federal Hierarchy client.

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
        source_name = "SAM_FEDHIER"

        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=daily_limit,
        )

    # -----------------------------------------------------------------
    # Core search
    # -----------------------------------------------------------------

    def search_organizations(self, fhorgid=None, fhorgname=None, status=None,
                             fhorgtype=None, agencycode=None, cgac=None,
                             fhparentorgname=None,
                             updateddatefrom=None, updateddateto=None,
                             limit=100, offset=0):
        """Search federal organizations with filters. Returns one page of results.

        Uses GET to /orgs with query parameters. All filter parameters are
        optional; omitted filters are not sent.

        Args:
            fhorgid: Unique org ID in Federal Hierarchy.
            fhorgname: Organization name (partial match).
            status: 'Active' or 'Inactive'.
            fhorgtype: 'Department/Ind. Agency' or 'Sub-Tier'.
            agencycode: FPDS agency code.
            cgac: Common Government-wide Accounting Classification code.
            fhparentorgname: Parent organization name.
            updateddatefrom: Start of updated date range (YYYY-MM-DD).
            updateddateto: End of updated date range (YYYY-MM-DD).
            limit: Records per page (max 100 per SAM API).
            offset: 0-based page index for pagination.

        Returns:
            dict with keys: totalrecords, orglist (list of org dicts).
        """
        params = {
            "limit": limit,
            "offset": offset,
        }

        if fhorgid is not None:
            params["fhorgid"] = fhorgid
        if fhorgname is not None:
            params["fhorgname"] = fhorgname
        if status is not None:
            params["status"] = status
        if fhorgtype is not None:
            params["fhorgtype"] = fhorgtype
        if agencycode is not None:
            params["agencycode"] = agencycode
        if cgac is not None:
            params["cgac"] = cgac
        if fhparentorgname is not None:
            params["fhparentorgname"] = fhparentorgname
        if updateddatefrom is not None:
            params["updateddatefrom"] = self._format_date(updateddatefrom)
        if updateddateto is not None:
            params["updateddateto"] = self._format_date(updateddateto)

        self.logger.debug(
            "FedHier search offset=%d limit=%d params=%s", offset, limit, params
        )
        response = self.get(self.SEARCH_ENDPOINT, params=params)
        return response.json()

    def search_organizations_all(self, **kwargs):
        """Generator that paginates through all results from search_organizations.

        Accepts all the same keyword arguments as search_organizations except
        offset (which is managed internally). Yields individual org dicts
        from the orglist[] array.

        Yields:
            dict: Individual organization records from the orglist.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("offset", None)
        limit = kwargs.get("limit", 100)
        offset = 0
        total_yielded = 0

        while True:
            data = self.search_organizations(offset=offset, **kwargs)
            total_records = data.get("totalrecords", 0)
            results = data.get("orglist", [])

            for org in results:
                total_yielded += 1
                yield org

            self.logger.info(
                "Page at offset %d: %d results (total available: %d, yielded so far: %d)",
                offset, len(results), total_records, total_yielded,
            )

            if not results:
                break

            offset += limit
            if offset >= total_records:
                break

        self.logger.info("FedHier search complete: %d total results", total_yielded)

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def get_all_organizations(self, status="Active"):
        """Retrieve all organizations with the given status.

        Paginates through the full result set and returns a list of all
        matching org dicts.

        Args:
            status: Filter by status ('Active' or 'Inactive'). Default 'Active'.

        Returns:
            list[dict]: All matching organization records.
        """
        self.logger.info("Fetching all %s federal organizations", status)
        return list(self.search_organizations_all(status=status))

    def get_organization(self, fh_org_id):
        """Look up a single organization by its Federal Hierarchy org ID.

        Args:
            fh_org_id: The fhorgid to look up.

        Returns:
            dict: Organization record, or None if not found.
        """
        self.logger.info("Looking up organization fhorgid=%s", fh_org_id)
        data = self.search_organizations(fhorgid=str(fh_org_id))
        orgs = data.get("orglist", [])
        if orgs:
            return orgs[0]
        return None

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _format_date(d):
        """Convert a date to YYYY-MM-DD string for the API.

        Args:
            d: date, datetime, or string.

        Returns:
            str: Date in YYYY-MM-DD format.
        """
        if d is None:
            return None
        if isinstance(d, (date, datetime)):
            return d.strftime("%Y-%m-%d")
        return str(d)
