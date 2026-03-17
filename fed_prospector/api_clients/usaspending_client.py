"""USASpending.gov API v2 client.

No authentication required. No documented rate limits.
All search endpoints use POST with JSON body.

API docs: https://api.usaspending.gov
"""

import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import click
import requests

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
    # Raw HTTP helper (bypasses rate counters, used for polls/downloads)
    # -----------------------------------------------------------------

    def _raw_get(self, url, **kwargs):
        """HTTP GET via session with retry logic but no rate-limit tracking.

        Used for polling and download requests that should not count
        against API quotas. Retries up to 3 times on connection errors
        with exponential backoff.

        Args:
            url: Full URL to GET.
            **kwargs: Passed to session.get() (timeout, stream, etc.).

        Returns:
            requests.Response: The HTTP response.

        Raises:
            requests.ConnectionError: After all retries exhausted.
        """
        kwargs.setdefault("timeout", (30, 600))
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.debug("_raw_get attempt %d: %s", attempt, url)
                response = self.session.get(url, **kwargs)
                return response
            except requests.ConnectionError as exc:
                if attempt < max_attempts:
                    delay = 2 ** attempt
                    self.logger.warning(
                        "_raw_get connection error (attempt %d/%d), "
                        "retrying in %ds: %s",
                        attempt, max_attempts, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        "_raw_get failed after %d attempts: %s",
                        max_attempts, exc,
                    )
                    raise

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
        data = response.json()
        self._validate_response(
            data, ["results", "page_metadata"],
            context="search_awards",
        )
        return data

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
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self.logger.info("Award not found (404): %s", award_id)
                return None
            raise
        except requests.RequestException as e:
            self.logger.warning("Network error fetching award %s: %s", award_id, e)
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
        data = response.json()
        self._validate_response(
            data, ["results", "page_metadata"],
            context="get_award_transactions",
        )
        return data

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

    def request_bulk_download(self, fiscal_year, award_types=None,
                              start_date=None, end_date=None):
        """Request a bulk CSV download for a fiscal year or custom date range.

        Args:
            fiscal_year: Federal fiscal year (e.g. 2025). Ignored when
                start_date/end_date are provided.
            award_types: List of award type codes. Defaults to CONTRACT_AWARD_TYPES.
            start_date: Optional start date string (YYYY-MM-DD). When provided
                with end_date, overrides the fiscal_year date range.
            end_date: Optional end date string (YYYY-MM-DD).

        Returns:
            dict: API response with file_url for download, or status_url
                for pending downloads.
        """
        if start_date and end_date:
            sd = self._format_date(start_date) if not isinstance(start_date, str) else start_date
            ed = self._format_date(end_date) if not isinstance(end_date, str) else end_date
            date_range = {"start_date": sd, "end_date": ed}
            log_label = f"{start_date} to {end_date}"
        else:
            date_range = {
                "start_date": f"{fiscal_year - 1}-10-01",
                "end_date": f"{fiscal_year}-09-30",
            }
            log_label = f"FY{fiscal_year}"

        body = {
            "filters": {
                "prime_award_types": award_types or CONTRACT_AWARD_TYPES,
                "date_type": "action_date",
                "date_range": date_range,
            },
        }

        self.logger.info("Requesting bulk download for %s", log_label)
        response = self.post(self.BULK_DOWNLOAD_ENDPOINT, json_body=body, timeout=120)
        data = response.json()
        self._validate_response(
            data, [],
            context="request_bulk_download",
        )

        if data.get("file_url"):
            self.logger.info("Bulk download ready: %s", data["file_url"])
        elif data.get("status_url"):
            self.logger.info("Bulk download queued: %s", data["status_url"])
        else:
            self.logger.warning("Unexpected bulk download response: %s", data)

        return data

    # -----------------------------------------------------------------
    # Bulk download polling and file retrieval
    # -----------------------------------------------------------------

    def poll_bulk_download(self, status_url, timeout=600, interval=10):
        """Poll a bulk download status URL until the file is ready.

        Args:
            status_url: URL returned by request_bulk_download() to check status.
            timeout: Maximum seconds to wait (default 600).
            interval: Seconds between polls (default 10).

        Returns:
            dict: Response JSON containing file_url.

        Raises:
            TimeoutError: If file not ready within timeout.
        """
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError(
                    f"Bulk download not ready after {timeout}s: {status_url}"
                )

            self.logger.info(
                "Polling bulk download (%.0fs elapsed): %s", elapsed, status_url
            )
            response = self._raw_get(status_url, timeout=(30, 60))

            if response.status_code != 200:
                body_preview = (response.text or "")[:500]
                self.logger.error(
                    "Poll returned HTTP %d: %s", response.status_code, body_preview
                )
                response.raise_for_status()

            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                body_preview = (response.text or "")[:500]
                raise RuntimeError(
                    f"Poll response was not valid JSON: {body_preview}"
                ) from exc

            if data.get("file_url"):
                self.logger.info("Bulk download ready: %s", data["file_url"])
                return data
            if data.get("status") == "finished":
                self.logger.info("Bulk download finished: %s", data)
                return data

            self.logger.info(
                "Bulk download status: %s", data.get("status", "unknown")
            )
            time.sleep(interval)

    def download_bulk_file(self, file_url, dest_dir=None, max_retries=5):
        """Stream-download a bulk file to local disk.

        Retries on HTTP 403 with exponential backoff, since USASpending's
        CDN intermittently returns 403 for valid files that are still
        propagating.

        Args:
            file_url: URL of the file to download.
            dest_dir: Local directory to save to. Defaults to
                settings.DOWNLOAD_DIR / "usaspending".
            max_retries: Maximum number of retries on 403 responses.

        Returns:
            Path: Local file path of the downloaded file.
        """
        if dest_dir is None:
            dest_dir = settings.DOWNLOAD_DIR / "usaspending"
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Extract filename from URL
        filename = file_url.rsplit("/", 1)[-1]
        if not filename:
            filename = "bulk_download.zip"

        dest_path = dest_dir / filename
        self.logger.info("Downloading %s -> %s", file_url, dest_path)

        retry_delay = 10
        for attempt in range(max_retries + 1):
            response = self._raw_get(file_url, stream=True, timeout=(30, 600))
            if response.status_code == 403 and attempt < max_retries:
                self.logger.warning(
                    "Download returned 403 (attempt %d/%d), retrying in %ds...",
                    attempt + 1, max_retries, retry_delay,
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue
            if response.status_code != 200:
                body = getattr(response, "text", "")
                self.logger.error(
                    "Download failed: %s %s", response.status_code, body[:500]
                )
            response.raise_for_status()
            break

        content_length = response.headers.get("Content-Length")
        total_size_mb = int(content_length) / (1024 * 1024) if content_length else None
        next_report_bytes = 50 * 1024 * 1024  # Report every 50MB

        total_bytes = 0
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                total_bytes += len(chunk)
                if total_bytes >= next_report_bytes:
                    dl_mb = total_bytes / (1024 * 1024)
                    if total_size_mb:
                        pct = total_bytes * 100 / int(content_length)
                        click.echo(f"  Downloaded {dl_mb:,.0f}MB / {total_size_mb:,.0f}MB ({pct:.0f}%)")
                    else:
                        click.echo(f"  Downloaded {dl_mb:,.0f}MB")
                    next_report_bytes += 50 * 1024 * 1024

        size_mb = total_bytes / (1024 * 1024)
        self.logger.info("Downloaded %.1f MB to %s", size_mb, dest_path)
        return dest_path

    # -----------------------------------------------------------------
    # Archive downloads (pre-built fiscal year files)
    # -----------------------------------------------------------------

    ARCHIVE_LIST_ENDPOINT = "/api/v2/bulk_download/list_monthly_files/"

    def list_archive_files(self, fiscal_year):
        """List available archive files for a fiscal year.

        Args:
            fiscal_year: Federal fiscal year (e.g. 2025).

        Returns:
            dict: API response with monthly_files list containing
                file_name, url, updated_date, etc.
        """
        body = {
            "agency": "all",
            "fiscal_year": fiscal_year,
            "type": "contracts",
        }

        self.logger.info("Listing archive files for FY%d", fiscal_year)
        response = self.post(self.ARCHIVE_LIST_ENDPOINT, json_body=body, timeout=60)
        data = response.json()
        self._validate_response(
            data, ["monthly_files"],
            context="list_archive_files",
        )
        return data

    def download_archive_file(self, fiscal_year):
        """Download the full archive file for a fiscal year.

        Finds the "Full" file from the archive listing and streams it
        to the local download directory. Skips download if the file
        already exists locally.

        Args:
            fiscal_year: Federal fiscal year (e.g. 2025).

        Returns:
            Path: Local file path of the downloaded archive.

        Raises:
            RuntimeError: If no Full archive file is found for the year.
        """
        data = self.list_archive_files(fiscal_year)
        monthly_files = data.get("monthly_files", [])

        # Find the "Full" file
        full_file = None
        for entry in monthly_files:
            if "_Full_" in entry.get("file_name", ""):
                full_file = entry
                break

        if not full_file:
            raise RuntimeError(
                f"No Full archive file found for FY{fiscal_year}. "
                f"Available files: {[f.get('file_name') for f in monthly_files]}"
            )

        file_name = full_file["file_name"]
        file_url = full_file["url"]

        dest_dir = Path(settings.DOWNLOAD_DIR) / "usaspending"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name

        if dest_path.exists():
            self.logger.info("Already downloaded: %s", dest_path)
            return dest_path

        self.logger.info("Downloading archive %s -> %s", file_url, dest_path)
        response = self._raw_get(file_url, stream=True, timeout=(30, 600))
        response.raise_for_status()

        content_length = response.headers.get("Content-Length")
        total_size_mb = int(content_length) / (1024 * 1024) if content_length else None
        next_report_bytes = 50 * 1024 * 1024  # Report every 50MB

        total_bytes = 0
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                total_bytes += len(chunk)
                if total_bytes >= next_report_bytes:
                    dl_mb = total_bytes / (1024 * 1024)
                    if total_size_mb:
                        pct = total_bytes * 100 / int(content_length)
                        click.echo(f"  Downloaded {dl_mb:,.0f}MB / {total_size_mb:,.0f}MB ({pct:.0f}%)")
                    else:
                        click.echo(f"  Downloaded {dl_mb:,.0f}MB")
                    next_report_bytes += 50 * 1024 * 1024

        size_mb = total_bytes / (1024 * 1024)
        self.logger.info("Downloaded %.1f MB to %s", size_mb, dest_path)
        return dest_path

    def download_delta_file(self, download_dir=None):
        """Download the latest delta file for all fiscal years.

        Discovers the most recent delta file from the archive listing
        endpoint and streams it to the local download directory. Skips
        download if the file already exists locally.

        Delta files cover all fiscal years (FY "All") and contain
        incremental changes since the last full archive. The archive
        listing returns them with "_Delta_" in the filename.

        Args:
            download_dir: Local directory to save to. Defaults to
                settings.DOWNLOAD_DIR / "usaspending".

        Returns:
            Path: Local file path of the downloaded delta ZIP.

        Raises:
            RuntimeError: If no delta file is found in the archive listing.
        """
        # Delta files use fiscal_year=0 to represent "All" in the listing API
        # Try current FY first, then fall back — the API returns delta files
        # alongside full files in the monthly listing
        current_fy = self._current_fiscal_year()
        data = self.list_archive_files(current_fy)
        monthly_files = data.get("monthly_files", [])

        # Find all delta files and pick the most recent one
        delta_files = [
            entry for entry in monthly_files
            if "_Delta_" in entry.get("file_name", "")
        ]

        if not delta_files:
            raise RuntimeError(
                f"No Delta file found in FY{current_fy} archive listing. "
                f"Available files: {[f.get('file_name') for f in monthly_files]}"
            )

        # Sort by updated_date descending to get the latest
        delta_files.sort(
            key=lambda f: f.get("updated_date", ""), reverse=True
        )
        latest_delta = delta_files[0]

        file_name = latest_delta["file_name"]
        file_url = latest_delta["url"]

        if download_dir is None:
            dest_dir = Path(settings.DOWNLOAD_DIR) / "usaspending"
        else:
            dest_dir = Path(download_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name

        if dest_path.exists():
            self.logger.info("Already downloaded: %s", dest_path)
            return dest_path

        self.logger.info("Downloading delta %s -> %s", file_url, dest_path)
        return self.download_bulk_file(file_url, dest_dir=dest_dir)

    def _current_fiscal_year(self):
        """Return the current federal fiscal year.

        Federal FY starts October 1, so Oct-Dec of calendar year N
        is FY N+1.
        """
        today = date.today()
        if today.month >= 10:
            return today.year + 1
        return today.year

    # -----------------------------------------------------------------
    # Note: get() and _format_date() are inherited from BaseAPIClient.
    # BaseAPIClient.get() skips api_key injection when self.api_key is
    # falsy (empty string), so no override is needed for USASpending.
    # BaseAPIClient._format_date() uses %Y-%m-%d by default, which
    # matches USASpending's expected date format.
    # -----------------------------------------------------------------
