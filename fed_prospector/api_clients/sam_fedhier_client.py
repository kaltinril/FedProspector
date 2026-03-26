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

from api_clients.base_client import BaseAPIClient, RateLimitExceeded


logger = logging.getLogger("fed_prospector.api.sam_fedhier")


def _walk_hierarchy_children(node, parent_fhorgid):
    """Recursively walk a hierarchy node and extract child org records.

    Used by _extract_hierarchy_children() to flatten nested hierarchy
    responses into a list of org dicts.

    Args:
        node: Dict representing a hierarchy node.
        parent_fhorgid: The fhorgid of the queried parent org.

    Returns:
        list[dict]: Flat org dicts found under this node.
    """
    children = []
    # Check common child list keys used in SAM hierarchy responses
    for key in ("subtierAgencyList", "officeList", "subordinateOrganizations",
                "childOrganizations", "children"):
        child_list = node.get(key) or []
        for child in child_list:
            children.append(child)
            # Recurse into child nodes
            children.extend(_walk_hierarchy_children(child, parent_fhorgid))
    return children


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
    HIERARCHY_ENDPOINT = "/prod/federalorganizations/v1/org/hierarchy"

    def __init__(self, api_key_number=1):
        """Initialize SAM Federal Hierarchy client. See _sam_init_kwargs() for key selection."""
        super().__init__(**self._sam_init_kwargs("sam_fedhier", api_key_number))

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
        data = response.json()
        # FedHier API uses lowercase "totalrecords" — use case-insensitive lookup
        # for validation since the key casing is inconsistent across SAM APIs
        total_key = "totalrecords" if "totalrecords" in data else "totalRecords"
        self._validate_response(
            data, [total_key, "orglist"],
            context="search_organizations",
        )
        return data

    def search_organizations_all(self, **kwargs):
        """Generator that paginates through all results from search_organizations.

        Accepts all the same keyword arguments as search_organizations except
        offset (which is managed internally). Yields individual org dicts
        from the orglist[] array.

        NOTE: The SAM FedHier API returns 'totalrecords' (lowercase), unlike
        every other SAM API that uses 'totalRecords'. We pass total_key="totalrecords"
        to handle this API inconsistency.

        Yields:
            dict: Individual organization records from the orglist.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        kwargs.pop("offset", None)
        limit = kwargs.get("limit", 100)
        for page_results in self.paginate(
            self.SEARCH_ENDPOINT,
            params=self._build_params(**kwargs),
            page_size=limit,
            pagination_style="offset",
            offset_param="offset",
            size_param="limit",
            total_key="totalrecords",  # SAM FedHier API uses lowercase — not a typo
            results_key="orglist",
        ):
            yield from page_results

    # -----------------------------------------------------------------
    # Page-level iterator (for resumable loading)
    # -----------------------------------------------------------------

    def iter_organization_pages(self, status="Active", start_offset=0, max_pages=None,
                                 **kwargs):
        """Iterate over pages of organizations, yielding one tuple per API call.

        Unlike search_organizations_all (which yields individual org dicts),
        this yields one tuple per API call giving the caller control to save
        progress after each page.

        Args:
            status: Organization status filter ('Active' or 'Inactive').
            start_offset: Offset to start from (0-based) for resumption.
            max_pages: Stop after this many API calls. None = no limit.
            **kwargs: Additional filter kwargs passed to search_organizations.

        Yields:
            tuple: (org_list, offset, total_records) per API call.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        self.logger.info(
            "Fetching organization pages (status=%s, start_offset=%d, max_pages=%s)",
            status, start_offset, max_pages or "unlimited",
        )

        offset = start_offset
        pages_fetched = 0

        while True:
            data = self.search_organizations(status=status, limit=100, offset=offset, **kwargs)

            org_list = data.get("orglist", [])
            total_records = data.get("totalrecords", 0)

            yield org_list, offset, total_records

            pages_fetched += 1

            # Stop conditions
            if not org_list or offset + 100 >= total_records:
                break
            if max_pages is not None and pages_fetched >= max_pages:
                self.logger.info("Stopping after %d pages (max_pages)", max_pages)
                break

            offset += 100

        self.logger.info("Finished: %d pages fetched", pages_fetched)

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
    # Hierarchy endpoint (Level 3 offices)
    # -----------------------------------------------------------------

    def get_org_children(self, fhorgid, limit=100, offset=0, updateddatefrom=None):
        """Fetch one page of child organizations for the given fhorgid.

        Uses the /v1/org/hierarchy endpoint which returns the hierarchical
        children of an organization. Used to retrieve Level 3 offices
        under Level 2 sub-tiers.

        Args:
            fhorgid: Federal Hierarchy org ID to get children for.
            limit: Records per page (max 100).
            offset: 0-based offset for pagination.
            updateddatefrom: Start of updated date range (YYYY-MM-DD).

        Returns:
            dict: Raw API response containing hierarchy data.
        """
        params = {
            "fhorgid": str(fhorgid),
            "limit": limit,
            "offset": offset,
        }
        if updateddatefrom is not None:
            params["updateddatefrom"] = self._format_date(updateddatefrom)

        self.logger.debug(
            "FedHier hierarchy fhorgid=%s offset=%d limit=%d", fhorgid, offset, limit
        )
        response = self.get(self.HIERARCHY_ENDPOINT, params=params)
        return response.json()

    def iter_org_children_pages(self, fhorgid, start_offset=0, max_pages=None,
                                updateddatefrom=None):
        """Iterate over pages of child orgs for a given fhorgid.

        Yields one tuple per API call, giving the caller control to save
        progress after each page. Extracts child org records from the
        hierarchy response and yields them as flat org dicts compatible
        with _normalize_org().

        Args:
            fhorgid: Federal Hierarchy org ID to get children for.
            start_offset: Offset to start from (0-based) for resumption.
            max_pages: Stop after this many API calls. None = no limit.
            updateddatefrom: Start of updated date range (YYYY-MM-DD).

        Yields:
            tuple: (child_org_list, offset, total_records) per API call.
                child_org_list contains flat org dicts extracted from the
                hierarchy response.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        self.logger.info(
            "Fetching children for fhorgid=%s (start_offset=%d, max_pages=%s)",
            fhorgid, start_offset, max_pages or "unlimited",
        )

        offset = start_offset
        pages_fetched = 0

        while True:
            data = self.get_org_children(fhorgid, limit=100, offset=offset,
                                         updateddatefrom=updateddatefrom)

            # Extract child orgs from the hierarchy response
            child_orgs = self._extract_hierarchy_children(data, str(fhorgid))
            # The hierarchy endpoint may not always report totalrecords
            # consistently; use the orglist length as a heuristic
            total_records = data.get("totalrecords", data.get("totalRecords", len(child_orgs)))

            yield child_orgs, offset, total_records

            pages_fetched += 1

            # Stop conditions
            if not child_orgs or offset + 100 >= total_records:
                break
            if max_pages is not None and pages_fetched >= max_pages:
                self.logger.info("Stopping after %d pages (max_pages)", max_pages)
                break

            offset += 100

        self.logger.info(
            "Finished children for fhorgid=%s: %d pages fetched", fhorgid, pages_fetched
        )

    @staticmethod
    def _extract_hierarchy_children(data, parent_fhorgid):
        """Extract child org records from a hierarchy API response.

        The hierarchy endpoint returns data in a nested structure rather than
        the flat orglist[] used by /v1/orgs. This method extracts child orgs
        and reshapes them into the same flat dict format that _normalize_org()
        expects.

        The hierarchy response may contain:
        - orglist[] — same flat format as the search endpoint (ideal case)
        - hierarchyDepartment with nested children
        - A single org record with sub-tier/office children

        Args:
            data: Raw JSON response from the hierarchy endpoint.
            parent_fhorgid: The fhorgid that was queried (used as fallback
                parent ID for child records).

        Returns:
            list[dict]: Flat org dicts compatible with _normalize_org().
        """
        children = []

        # Case 1: Response has orglist[] (same format as search endpoint)
        if "orglist" in data and data["orglist"]:
            for org in data["orglist"]:
                # Ensure we only return child records, not the queried org itself
                org_id = str(org.get("fhorgid", ""))
                if org_id != str(parent_fhorgid):
                    children.append(org)
                elif not children:
                    # If orglist only has the parent, check for nested children
                    pass
            if children:
                return children

        # Case 2: Nested hierarchy structure — extract from hierarchyDepartment
        # or similar nested keys
        hierarchy = data.get("orgHierarchy") or data.get("hierarchyDepartment") or {}
        if hierarchy:
            children.extend(_walk_hierarchy_children(hierarchy, parent_fhorgid))

        # Case 3: Top-level org with embedded children arrays
        # Some responses put children directly under the response
        for key in ("subtierAgencyList", "officeList", "subordinateOrganizations"):
            child_list = data.get(key) or []
            for child in child_list:
                children.append(child)

        return children

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _build_params(self, fhorgid=None, fhorgname=None, status=None,
                      fhorgtype=None, agencycode=None, cgac=None,
                      fhparentorgname=None,
                      updateddatefrom=None, updateddateto=None,
                      limit=100, **_ignored):
        """Build the query params dict for a single-page organizations search.

        Used by search_organizations_all() to pass a clean params dict into
        paginate() (without offset/limit, which paginate() manages).
        Uses base class _format_date() (default %Y-%m-%d format).

        Returns:
            dict: Query parameters ready for the SAM FedHier API.
        """
        params = {}

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

        return params
