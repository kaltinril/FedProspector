"""SAM.gov Opportunities API v2 client.

Wraps the Opportunities Search API for finding federal contract opportunities.
Provides convenience methods for WOSB and 8(a) set-aside searches, which are
the primary prospecting use case for this system.

Public API docs: https://open.gsa.gov/api/get-opportunities-public-api/
Auth API docs (not used - requires System Account): https://open.gsa.gov/api/opportunities-api/
Endpoint: /opportunities/v2/search
Free tier: 10 requests/day (shared with entity API, configurable via SAM_DAILY_LIMIT)
"""

# OpenAPI spec: thesolution/sam_gov_api/get-opportunities-v2.yaml

import logging
from datetime import date, datetime, timedelta

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings


logger = logging.getLogger("fed_prospector.api.sam_opportunity")

# SAM.gov Opportunities API endpoint (v2)
OPPORTUNITY_ENDPOINT = "/opportunities/v2/search"

# Maximum date range allowed per API call.
# SAM.gov rejects ranges of exactly 365 days ("Date range must be null year(s) apart"),
# so we use 364 to stay safely under the 1-year limit.
MAX_DATE_RANGE_DAYS = 364

# Set-aside codes relevant to WOSB prospecting
WOSB_SET_ASIDES = ["WOSB", "EDWOSB", "WOSBSS", "EDWOSBSS"]

# Set-aside codes relevant to 8(a) prospecting
SBA_8A_SET_ASIDES = ["8A", "8AN"]

# All small business set-aside codes, ordered by priority for WOSB/8(a) prospecting.
# The top 4 (WOSB, EDWOSB, 8A, 8AN) are the highest-value targets and are queried
# first so they fit within a tight API call budget.
ALL_SB_SET_ASIDES = [
    "WOSB", "EDWOSB", "8A", "8AN",          # Priority tier 1: core WOSB/8(a)
    "SBA", "HZC", "SDVOSBC", "SBP",          # Priority tier 2: other SB programs
    "WOSBSS", "EDWOSBSS", "HZS", "SDVOSBS",  # Priority tier 3: sole-source variants
]

# The top 4 priority set-asides most relevant to WOSB/8(a) prospecting
PRIORITY_SET_ASIDES = ["WOSB", "EDWOSB", "8A", "8AN"]


class SAMOpportunityClient(BaseAPIClient):
    """Client for the SAM.gov Opportunities API v2.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    The Opportunities API uses typeOfSetAside to filter by set-aside type,
    but only accepts ONE value per request. Convenience methods handle
    querying across multiple set-aside types with deduplication.

    A per-invocation call budget (default 5) limits how many API calls the
    multi-set-aside convenience methods (load_all_set_asides, etc.) will
    make. This reserves half of the 10/day free-tier quota for entity and
    other API work. Individual search_opportunities() calls are not subject
    to the budget.

    Usage:
        client = SAMOpportunityClient()

        # Single set-aside search
        for opp in client.search_opportunities(
            posted_from="01/01/2026", posted_to="02/01/2026",
            set_aside="WOSB",
        ):
            print(opp["title"])

        # All WOSB set-asides (auto-deduplicates, respects call budget)
        opps = client.get_wosb_opportunities(
            posted_from=date(2026, 1, 1), posted_to=date(2026, 2, 1),
        )
        for opp in opps:
            print(opp["title"])
    """

    DEFAULT_CALL_BUDGET = 5

    def __init__(self, call_budget=None, api_key_number=1):
        if api_key_number == 2:
            api_key = settings.SAM_API_KEY_2
            daily_limit = settings.SAM_DAILY_LIMIT_2
            source_name = "SAM_OPPORTUNITY_KEY2"
        else:
            api_key = settings.SAM_API_KEY
            daily_limit = settings.SAM_DAILY_LIMIT
            source_name = "SAM_OPPORTUNITY"

        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key,
            source_name=source_name,
            max_daily_requests=daily_limit,
        )
        self.call_budget = call_budget if call_budget is not None else self.DEFAULT_CALL_BUDGET

    def search_opportunities(self, posted_from, posted_to, set_aside=None,
                             naics=None, psc=None, ptype=None, state=None,
                             zip_code=None, organization_code=None,
                             title=None, solnum=None, limit=1000):
        """Search opportunities with the given filters. Generator yielding
        individual opportunity dicts.

        Automatically splits date ranges longer than 1 year into multiple
        API calls, and paginates within each date chunk.

        Args:
            posted_from: Start date. Accepts date, datetime, or string
                in MM/dd/yyyy format.
            posted_to: End date. Same types accepted.
            set_aside: Single set-aside code (e.g. "WOSB", "8A").
                Only ONE value per request.
            naics: 6-digit NAICS code string.
            psc: PSC classification code string.
            ptype: Procurement type code. One of:
                o=solicitation, k=combined, p=presolicitation, r=sources sought.
            state: Place of performance state code.
            zip_code: Place of performance ZIP code.
            organization_code: Agency code.
            title: Opportunity title search string.
            solnum: Solicitation number.
            limit: Records per page (max 1000, default 1000).

        Yields:
            dict: Individual opportunity records from opportunitiesData.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
            requests.HTTPError: On non-retryable HTTP errors.
        """
        date_chunks = self._split_date_range(posted_from, posted_to)

        set_aside_label = set_aside or "all"
        self.logger.info(
            "Searching opportunities: set_aside=%s, posted %s to %s (%d date chunk(s))",
            set_aside_label,
            self._format_date(posted_from, "%m/%d/%Y"),
            self._format_date(posted_to, "%m/%d/%Y"),
            len(date_chunks),
        )

        total_yielded = 0
        for chunk_from, chunk_to in date_chunks:
            params = {
                "postedFrom": self._format_date(chunk_from, "%m/%d/%Y"),
                "postedTo": self._format_date(chunk_to, "%m/%d/%Y"),
            }

            if set_aside is not None:
                params["typeOfSetAside"] = set_aside
            if naics is not None:
                params["ncode"] = naics
            if psc is not None:
                params["ccode"] = psc
            if ptype is not None:
                params["ptype"] = ptype
            if state is not None:
                params["state"] = state
            if zip_code is not None:
                params["zip"] = zip_code
            if organization_code is not None:
                params["organizationCode"] = organization_code
            if title is not None:
                params["title"] = title
            if solnum is not None:
                params["solnum"] = solnum

            self.logger.info(
                "Querying chunk: %s to %s (set_aside=%s)",
                params["postedFrom"], params["postedTo"], set_aside_label,
            )

            for page_data in self.paginate(
                OPPORTUNITY_ENDPOINT, params=params, page_size=limit,
            ):
                opportunities = page_data.get("opportunitiesData", [])
                for opp in opportunities:
                    total_yielded += 1
                    yield opp

        self.logger.info(
            "Search complete: %d opportunities yielded (set_aside=%s)",
            total_yielded, set_aside_label,
        )

    def get_opportunity(self, notice_id, posted_from=None, posted_to=None):
        """Fetch a single opportunity by notice ID.

        The Opportunities API requires postedFrom and postedTo even for
        single-record lookups. If not provided, defaults to the past year.

        Args:
            notice_id: The unique notice ID string.
            posted_from: Optional start date. Defaults to 1 year ago.
            posted_to: Optional end date. Defaults to today.

        Returns:
            dict: The opportunity record, or None if not found.

        Raises:
            RateLimitExceeded: If daily API limit has been reached.
            requests.HTTPError: On non-retryable HTTP errors.
        """
        if posted_to is None:
            posted_to = date.today()
        if posted_from is None:
            posted_from = date.today() - timedelta(days=365)

        params = {
            "noticeid": notice_id,
            "postedFrom": self._format_date(posted_from, "%m/%d/%Y"),
            "postedTo": self._format_date(posted_to, "%m/%d/%Y"),
        }

        self.logger.info("Looking up opportunity by notice ID: %s", notice_id)
        response = self.get(OPPORTUNITY_ENDPOINT, params=params)
        data = response.json()

        total = data.get("totalRecords", 0)
        if total == 0:
            self.logger.info("No opportunity found for notice ID: %s", notice_id)
            return None

        opportunities = data.get("opportunitiesData", [])
        if not opportunities:
            self.logger.warning(
                "totalRecords=%d but opportunitiesData is empty for notice ID: %s",
                total, notice_id,
            )
            return None

        self.logger.info("Found opportunity for notice ID: %s", notice_id)
        return opportunities[0]

    def get_wosb_opportunities(self, posted_from, posted_to, naics=None,
                               **kwargs):
        """Search across all WOSB set-aside types with deduplication.

        Makes separate API calls for each WOSB-related set-aside code:
        WOSB, EDWOSB, WOSBSS, EDWOSBSS. Results are deduplicated by
        noticeId.

        Args:
            posted_from: Start date.
            posted_to: End date.
            naics: Optional NAICS code filter.
            **kwargs: Additional keyword arguments passed to search_opportunities.

        Returns:
            list[dict]: Deduplicated list of opportunity records.
        """
        return self._search_multiple_set_asides(
            WOSB_SET_ASIDES, posted_from, posted_to, naics=naics, **kwargs,
        )

    def get_8a_opportunities(self, posted_from, posted_to, naics=None,
                             **kwargs):
        """Search across all 8(a) set-aside types with deduplication.

        Makes separate API calls for each 8(a)-related set-aside code:
        8A, 8AN. Results are deduplicated by noticeId.

        Args:
            posted_from: Start date.
            posted_to: End date.
            naics: Optional NAICS code filter.
            **kwargs: Additional keyword arguments passed to search_opportunities.

        Returns:
            list[dict]: Deduplicated list of opportunity records.
        """
        return self._search_multiple_set_asides(
            SBA_8A_SET_ASIDES, posted_from, posted_to, naics=naics, **kwargs,
        )

    def load_all_set_asides(self, posted_from, posted_to, naics=None,
                            set_aside_codes=None, **kwargs):
        """Load opportunities for small business set-aside types.

        Makes separate API calls for each set-aside code. Results are
        deduplicated by noticeId. Respects the instance call_budget;
        set-aside types are queried in priority order so the most
        important ones are fetched first if the budget runs out.

        Args:
            posted_from: Start date.
            posted_to: End date.
            naics: Optional NAICS code filter.
            set_aside_codes: Optional list of set-aside codes to query.
                Defaults to ALL_SB_SET_ASIDES (12 codes, priority-ordered).
            **kwargs: Additional keyword arguments passed to search_opportunities.

        Returns:
            list[dict]: Deduplicated list of all unique opportunity records.
        """
        codes = set_aside_codes if set_aside_codes is not None else ALL_SB_SET_ASIDES
        return self._search_multiple_set_asides(
            codes, posted_from, posted_to, naics=naics, **kwargs,
        )

    def _search_multiple_set_asides(self, set_aside_codes, posted_from,
                                    posted_to, naics=None, **kwargs):
        """Search across multiple set-aside types and deduplicate results.

        The SAM.gov API only accepts one typeOfSetAside value per request,
        so this method issues a separate search per code. Results are
        deduplicated by noticeId.

        Tracks API calls made during this invocation and stops when the
        instance call_budget is reached, logging a warning with the
        remaining set-aside types that were skipped.

        Args:
            set_aside_codes: List of set-aside code strings.
            posted_from: Start date.
            posted_to: End date.
            naics: Optional NAICS code filter.
            **kwargs: Additional keyword arguments passed to search_opportunities.

        Returns:
            list[dict]: Deduplicated list of opportunity records.
        """
        seen_ids = set()
        results = []
        budget = self.call_budget
        # Track calls by reading the rate counter before and after each
        # set-aside search so pagination calls are counted accurately
        # (MEDIUM bug fix: old code only counted date chunks, not pages).
        calls_at_start = budget - self._get_remaining_requests()

        self.logger.info(
            "Searching %d set-aside types: %s (call budget: %d)",
            len(set_aside_codes), ", ".join(set_aside_codes), budget,
        )

        for idx, code in enumerate(set_aside_codes):
            # Check call budget before starting a new set-aside type.
            # Re-read the rate counter so pagination calls are included.
            calls_used = (budget - self._get_remaining_requests()) - calls_at_start
            if calls_used >= budget:
                skipped = set_aside_codes[idx:]
                self.logger.warning(
                    "API call budget exhausted (%d calls). "
                    "Remaining set-aside types skipped: %s",
                    budget, ", ".join(skipped),
                )
                break

            remaining = self._get_remaining_requests()
            if remaining <= 0:
                self.logger.warning(
                    "No API requests remaining today. Stopping at set-aside "
                    "code '%s' (%d of %d codes queried).",
                    code, idx, len(set_aside_codes),
                )
                break

            count_before = len(results)
            try:
                for opp in self.search_opportunities(
                    posted_from, posted_to,
                    set_aside=code, naics=naics, **kwargs,
                ):
                    notice_id = opp.get("noticeId")
                    if notice_id and notice_id not in seen_ids:
                        seen_ids.add(notice_id)
                        results.append(opp)
            except RateLimitExceeded:
                self.logger.warning(
                    "Rate limit reached during set-aside '%s' search. "
                    "Returning %d results collected so far.",
                    code, len(results),
                )
                break

            calls_used = (budget - self._get_remaining_requests()) - calls_at_start
            new_count = len(results) - count_before
            self.logger.info(
                "Set-aside '%s': %d new opportunities (total unique so far: %d, "
                "budget used: %d/%d)",
                code, new_count, len(results), calls_used, budget,
            )

        calls_used = (budget - self._get_remaining_requests()) - calls_at_start
        self.logger.info(
            "Multi-set-aside search complete: %d unique opportunities "
            "(%d API calls used of %d budget)",
            len(results), calls_used, budget,
        )
        return results

    def _parse_date(self, value):
        """Parse a date value into a date object.

        Args:
            value: A date object, datetime object, or string in MM/dd/yyyy
                or YYYY-MM-DD format.

        Returns:
            date: A date object.
        """
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        # Try MM/dd/yyyy first (SAM API native format), then YYYY-MM-DD
        # (ISO 8601 format passed by ETL callers). Raises ValueError if
        # neither format matches (HIGH bug fix).
        s = str(value)
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise ValueError(
            f"Cannot parse date {value!r}: expected MM/DD/YYYY or YYYY-MM-DD"
        )

    # _format_date is inherited from BaseAPIClient. SAM Opportunities API
    # uses MM/DD/YYYY format, so all call sites pass fmt="%m/%d/%Y".

    def _split_date_range(self, posted_from, posted_to):
        """Split a date range into chunks of at most 1 year (365 days).

        The SAM.gov Opportunities API enforces a maximum of 1 year between
        postedFrom and postedTo. If the requested range exceeds this limit,
        it is split into consecutive 365-day chunks.

        Args:
            posted_from: Start date (date, datetime, or MM/dd/yyyy string).
            posted_to: End date (date, datetime, or MM/dd/yyyy string).

        Returns:
            list[tuple[date, date]]: List of (from_date, to_date) tuples,
                each spanning at most 365 days.
        """
        start = self._parse_date(posted_from)
        end = self._parse_date(posted_to)

        if (end - start).days <= MAX_DATE_RANGE_DAYS:
            return [(start, end)]

        chunks = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=MAX_DATE_RANGE_DAYS), end)
            chunks.append((chunk_start, chunk_end))
            chunk_start = chunk_end + timedelta(days=1)

        self.logger.info(
            "Date range %s to %s split into %d chunks of <= %d days",
            self._format_date(start, "%m/%d/%Y"), self._format_date(end, "%m/%d/%Y"),
            len(chunks), MAX_DATE_RANGE_DAYS,
        )
        return chunks

    def estimate_calls_needed(self, set_asides, posted_from, posted_to):
        """Estimate how many API calls would be needed for a multi-set-aside search.

        Each set-aside type requires one API call per date chunk (365-day
        max per chunk). Pagination within a chunk may add additional calls,
        but this estimate counts only the minimum (1 call per chunk per
        set-aside type).

        Args:
            set_asides: List of set-aside code strings to query.
            posted_from: Start date (date, datetime, or MM/dd/yyyy string).
            posted_to: End date (date, datetime, or MM/dd/yyyy string).

        Returns:
            int: Minimum number of API calls needed.
        """
        num_chunks = len(self._split_date_range(posted_from, posted_to))
        return len(set_asides) * num_chunks
