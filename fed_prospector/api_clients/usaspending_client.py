"""USASpending.gov API v2 client.

No authentication required. No documented rate limits.
All search endpoints use POST with JSON body.

API docs: https://api.usaspending.gov
"""

import logging
from datetime import date, timedelta

from api_clients.base_client import BaseAPIClient
from config import settings


logger = logging.getLogger("fed_prospector.api.usaspending")

# Contract award type codes (exclude grants, loans, direct payments, etc.)
# A = BPA Call, B = Purchase Order, C = Delivery Order, D = Definitive Contract
CONTRACT_AWARD_TYPES = ["A", "B", "C", "D"]

# Default lookback period for incumbent searches (5 years)
DEFAULT_LOOKBACK_YEARS = 5


class USASpendingClient(BaseAPIClient):
    """USASpending.gov API v2 client. No auth, no rate limits.

    All search endpoints use POST with JSON body. Pagination uses
    page-based (page=1, page=2, ...) rather than offset-based.

    Usage:
        client = USASpendingClient()

        # Search contract awards
        for award in client.search_awards_all(naics_codes=["541512"]):
            print(award["Recipient Name"], award["Award Amount"])

        # Find incumbent for a contract
        result = client.search_incumbent(solicitation_number="W911NF-25-R-0001")
    """

    AWARD_SEARCH_ENDPOINT = "/api/v2/search/spending_by_award/"
    AWARD_DETAIL_ENDPOINT = "/api/v2/awards/"
    SPENDING_BY_CATEGORY_ENDPOINT = "/api/v2/search/spending_by_category/"
    BULK_DOWNLOAD_ENDPOINT = "/api/v2/bulk_download/awards/"
    TRANSACTION_ENDPOINT = "/api/v2/transactions/"

    # Fields to request from the award search endpoint.
    # Note: The API returns "Award ID" as the contract PIID, and
    # "generated_internal_id" as the stable unique key (which equals
    # "generated_unique_award_id" from the detail endpoint).
    # Some fields (NAICS Code, PSC Code, etc.) may be None in search
    # results and only available via the detail endpoint.
    AWARD_SEARCH_FIELDS = [
        "Award ID",
        "Recipient Name",
        "Recipient UEI",
        "Start Date",
        "End Date",
        "Award Amount",
        "Total Outlays",
        "Description",
        "Contract Award Type",
        "recipient_id",
        "prime_award_recipient_id",
        "Awarding Agency",
        "Awarding Sub Agency",
        "Funding Agency",
        "NAICS Code",
        "NAICS Description",
        "PSC Code",
        "Type of Set Aside",
        "Place of Performance State Code",
        "Place of Performance Country Code",
        "Place of Performance Zip5",
        "Place of Performance City Code",
        "Last Date to Order",
        "Base and All Options Value",
        "generated_unique_award_id",
    ]

    def __init__(self, db_connection=None):
        """Initialize USASpending client.

        Args:
            db_connection: Not used. Kept for interface compatibility.
        """
        super().__init__(
            base_url=settings.USASPENDING_API_BASE_URL,
            api_key="",  # No API key needed
            source_name="USASPENDING",
            max_daily_requests=999999,  # No rate limit
        )

    # -----------------------------------------------------------------
    # Core API methods
    # -----------------------------------------------------------------

    def search_awards(self, naics_codes=None, psc_codes=None, agencies=None,
                      start_date=None, end_date=None, set_aside_codes=None,
                      recipient_name=None, keyword=None, limit=100, page=1):
        """Search contract awards with filters. Returns one page of results.

        Uses POST to /api/v2/search/spending_by_award/.
        All filter parameters are optional; omitted filters are not sent.

        Args:
            naics_codes: List of NAICS code strings (e.g. ["541512"]).
            psc_codes: List of PSC code strings.
            agencies: List of agency filter dicts, each with
                {"type": "awarding", "tier": "toptier", "name": "..."}.
            start_date: Start date (date, datetime, or YYYY-MM-DD string).
            end_date: End date (date, datetime, or YYYY-MM-DD string).
            set_aside_codes: List of set-aside type codes.
            recipient_name: Recipient/vendor name search string.
            keyword: Free-text keyword search.
            limit: Records per page (max 100 per USASpending API).
            page: 1-based page number.

        Returns:
            dict with keys: results (list), page_metadata (dict with
            page, hasNext, total, limit).
        """
        filters = {
            "award_type_codes": CONTRACT_AWARD_TYPES,
        }

        if naics_codes:
            filters["naics_codes"] = naics_codes
        if psc_codes:
            filters["psc_codes"] = psc_codes
        if agencies:
            filters["agencies"] = agencies
        if set_aside_codes:
            filters["set_aside_type_codes"] = set_aside_codes
        if recipient_name:
            filters["recipient_search_text"] = [recipient_name]
        if keyword:
            filters["keywords"] = [keyword]

        if start_date or end_date:
            sd = self._format_date(start_date) if start_date else "2000-01-01"
            ed = self._format_date(end_date) if end_date else self._format_date(date.today())
            filters["time_period"] = [{"start_date": sd, "end_date": ed}]

        body = {
            "filters": filters,
            "fields": self.AWARD_SEARCH_FIELDS,
            "limit": limit,
            "page": page,
            "sort": "Award Amount",
            "order": "desc",
        }

        self.logger.debug("Award search page=%d limit=%d filters=%s", page, limit, filters)
        response = self.post(self.AWARD_SEARCH_ENDPOINT, json_body=body, timeout=60)
        return response.json()

    def search_awards_all(self, **kwargs):
        """Generator that paginates through all results from search_awards.

        Accepts all the same keyword arguments as search_awards except
        page (which is managed internally). Yields individual award dicts.

        Yields:
            dict: Individual award records from the results list.
        """
        kwargs.pop("page", None)
        page = 1
        total_yielded = 0

        while True:
            data = self.search_awards(page=page, **kwargs)
            results = data.get("results", [])

            for award in results:
                total_yielded += 1
                yield award

            metadata = data.get("page_metadata", {})
            has_next = metadata.get("hasNext", False)

            self.logger.info(
                "Page %d: %d results (total yielded: %d, hasNext: %s)",
                page, len(results), total_yielded, has_next,
            )

            if not has_next or not results:
                break

            page += 1

        self.logger.info("Award search complete: %d total results", total_yielded)

    def get_award(self, award_id):
        """Get full award details by generated_unique_award_id.

        Args:
            award_id: The generated_unique_award_id string.

        Returns:
            dict: Full award details, or None on 404.
        """
        endpoint = f"{self.AWARD_DETAIL_ENDPOINT}{award_id}/"
        self.logger.info("Fetching award detail: %s", award_id)
        try:
            response = self.get(endpoint)
            return response.json()
        except Exception as e:
            self.logger.warning("Failed to fetch award %s: %s", award_id, e)
            return None

    def get_award_detail(self, award_id):
        """Alias for get_award. Kept for naming clarity."""
        return self.get_award(award_id)

    # -----------------------------------------------------------------
    # Convenience: Incumbent search
    # -----------------------------------------------------------------

    def search_incumbent(self, solicitation_number=None, naics_code=None,
                         agency=None, place_of_performance_state=None,
                         lookback_years=None):
        """Find the incumbent (previous winner) for a contract opportunity.

        Strategy:
        1. If solicitation_number provided, search by keyword match
        2. Otherwise search by naics_code + agency + place_of_performance
        3. Return the most recent matching award (sorted by amount desc)

        Args:
            solicitation_number: Solicitation or contract number to search.
            naics_code: NAICS code string (e.g. "541512").
            agency: Agency name string for awarding_agency filter.
            place_of_performance_state: 2-letter state code.
            lookback_years: How many years back to search. Default 5.

        Returns:
            dict: Most recent matching award, or None if no match.
        """
        years = lookback_years or DEFAULT_LOOKBACK_YEARS
        end = date.today()
        start = end - timedelta(days=365 * years)

        kwargs = {
            "start_date": start,
            "end_date": end,
            "limit": 10,
            "page": 1,
        }

        if solicitation_number:
            # Search by keyword to catch solicitation number in descriptions/PIID
            kwargs["keyword"] = solicitation_number

        if naics_code:
            kwargs["naics_codes"] = [naics_code]

        if agency:
            kwargs["agencies"] = [
                {"type": "awarding", "tier": "toptier", "name": agency}
            ]

        self.logger.info(
            "Incumbent search: sol=%s naics=%s agency=%s state=%s",
            solicitation_number, naics_code, agency, place_of_performance_state,
        )

        data = self.search_awards(**kwargs)
        results = data.get("results", [])

        if not results:
            self.logger.info("No incumbent found")
            return None

        # Return the top result (sorted by award amount descending)
        top = results[0]
        self.logger.info(
            "Incumbent found: %s (Award: %s, Amount: %s)",
            top.get("Recipient Name"),
            top.get("Award ID"),
            top.get("Award Amount"),
        )
        return top

    # -----------------------------------------------------------------
    # Aggregate spending
    # -----------------------------------------------------------------

    def get_spending_by_category(self, category, filters, limit=10, page=1):
        """Get aggregate spending by category.

        Args:
            category: Category name (e.g. "recipient", "awarding_agency",
                "naics", "psc", "awarding_subagency").
            filters: Filters dict matching USASpending filter schema.
            limit: Results per page.
            page: 1-based page number.

        Returns:
            dict: API response with results and page_metadata.
        """
        endpoint = f"{self.SPENDING_BY_CATEGORY_ENDPOINT}{category}/"
        body = {
            "filters": filters,
            "limit": limit,
            "page": page,
        }

        self.logger.debug("Spending by %s: page=%d", category, page)
        response = self.post(endpoint, json_body=body, timeout=60)
        return response.json()

    def get_top_recipients(self, naics_code=None, agency=None,
                           set_aside=None, start_date=None, end_date=None,
                           limit=20):
        """Find who wins the most contracts for given criteria.

        Uses spending_by_category/recipient endpoint for aggregate data.

        Args:
            naics_code: Optional NAICS code filter.
            agency: Optional awarding agency name.
            set_aside: Optional set-aside type code.
            start_date: Start date for time filter.
            end_date: End date for time filter.
            limit: Number of top recipients to return.

        Returns:
            list[dict]: Top recipients with name and aggregate amount.
        """
        filters = {
            "award_type_codes": CONTRACT_AWARD_TYPES,
        }

        if naics_code:
            filters["naics_codes"] = [naics_code]
        if agency:
            filters["agencies"] = [
                {"type": "awarding", "tier": "toptier", "name": agency}
            ]
        if set_aside:
            filters["set_aside_type_codes"] = [set_aside]
        if start_date or end_date:
            sd = self._format_date(start_date) if start_date else "2000-01-01"
            ed = self._format_date(end_date) if end_date else self._format_date(date.today())
            filters["time_period"] = [{"start_date": sd, "end_date": ed}]

        self.logger.info(
            "Top recipients: naics=%s agency=%s set_aside=%s limit=%d",
            naics_code, agency, set_aside, limit,
        )

        data = self.get_spending_by_category("recipient", filters, limit=limit)
        results = data.get("results", [])

        self.logger.info("Found %d top recipients", len(results))
        return results

    # -----------------------------------------------------------------
    # Transaction history (for burn rate analysis)
    # -----------------------------------------------------------------

    def get_award_transactions(self, award_id, page=1, limit=5000,
                               sort="action_date", order="asc"):
        """Get transaction history for a specific award.

        POST to /api/v2/transactions/. Returns the per-modification
        funding timeline needed for burn rate analysis.

        Args:
            award_id: The generated_unique_award_id (e.g. "CONT_AWD_...").
            page: 1-based page number (default 1).
            limit: Records per page, 1-5000 (default 5000).
            sort: Sort field (default "action_date").
            order: "asc" or "desc" (default "asc" for chronological).

        Returns:
            dict with keys: results (list of transaction dicts),
            page_metadata (dict with page, hasNext, total, limit).
        """
        body = {
            "award_id": award_id,
            "page": page,
            "limit": limit,
            "sort": sort,
            "order": order,
        }
        self.logger.debug("Transactions for %s page=%d", award_id, page)
        response = self.post(self.TRANSACTION_ENDPOINT, json_body=body, timeout=60)
        return response.json()

    def get_all_transactions(self, award_id, **kwargs):
        """Generator yielding all transactions for an award.

        Paginates automatically through all pages. Used to build
        complete funding timeline for burn rate calculation.

        Args:
            award_id: The generated_unique_award_id.
            **kwargs: Passed to get_award_transactions (sort, order, limit).

        Yields:
            dict: Individual transaction records.
        """
        kwargs.pop("page", None)
        page = 1
        total_yielded = 0

        while True:
            data = self.get_award_transactions(award_id, page=page, **kwargs)
            results = data.get("results", [])

            for txn in results:
                total_yielded += 1
                yield txn

            metadata = data.get("page_metadata", {})
            has_next = metadata.get("hasNext", False)

            self.logger.info(
                "Award %s transactions page %d: %d records (total: %d, hasNext: %s)",
                award_id, page, len(results), total_yielded, has_next,
            )

            if not has_next or not results:
                break

            page += 1

        self.logger.info("Award %s: %d total transactions", award_id, total_yielded)

    # -----------------------------------------------------------------
    # Bulk download
    # -----------------------------------------------------------------

    def request_bulk_download(self, fiscal_year, award_types=None):
        """Request a bulk CSV download for a fiscal year.

        Args:
            fiscal_year: Federal fiscal year (e.g. 2025).
            award_types: List of award type codes. Defaults to CONTRACT_AWARD_TYPES.

        Returns:
            dict: API response with file_url for download, or status_url
                for pending downloads.
        """
        body = {
            "filters": {
                "prime_award_types": award_types or CONTRACT_AWARD_TYPES,
                "date_type": "action_date",
                "date_range": {
                    "start_date": f"{fiscal_year - 1}-10-01",
                    "end_date": f"{fiscal_year}-09-30",
                },
            },
        }

        self.logger.info("Requesting bulk download for FY%d", fiscal_year)
        response = self.post(self.BULK_DOWNLOAD_ENDPOINT, json_body=body, timeout=120)
        data = response.json()

        if data.get("file_url"):
            self.logger.info("Bulk download ready: %s", data["file_url"])
        elif data.get("status_url"):
            self.logger.info("Bulk download queued: %s", data["status_url"])
        else:
            self.logger.warning("Unexpected bulk download response: %s", data)

        return data

    # -----------------------------------------------------------------
    # Note: get() and _format_date() are inherited from BaseAPIClient.
    # BaseAPIClient.get() skips api_key injection when self.api_key is
    # falsy (empty string), so no override is needed for USASpending.
    # BaseAPIClient._format_date() uses %Y-%m-%d by default, which
    # matches USASpending's expected date format.
    # -----------------------------------------------------------------
