"""SAM.gov bulk extract download client.

Downloads monthly and daily entity extract files from SAM.gov's
data-services API. This is the primary mechanism for loading entity
data because it bypasses the 10/day API rate limit by downloading
complete datasets as single files.

Extract files are ZIP archives containing either pipe-delimited DAT
files (V1) or JSON files (V2).
"""

# OpenAPI spec: thesolution/sam_gov_api/sam-entity-extracts-api.yaml

import json
import logging
import zipfile
from datetime import date
from pathlib import Path

import requests
from tqdm import tqdm

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings

logger = logging.getLogger("fed_prospector.api.sam_extract")


class SAMExtractClient(BaseAPIClient):
    """Client for downloading SAM.gov bulk entity extract files."""

    EXTRACT_ENDPOINT = "/data-services/v1/extracts"

    def __init__(self, api_key=None):
        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=api_key or settings.SAM_API_KEY,
            source_name="SAM_KEY1",
            max_daily_requests=settings.SAM_DAILY_LIMIT,
            logger_name="fed_prospector.api.sam_extract",
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def download_monthly_extract(
        self,
        year,
        month,
        output_dir=None,
        sensitivity="PUBLIC",
        version="V2",
    ):
        """Download a monthly entity extract ZIP from SAM.gov.

        SAM.gov publishes monthly extracts on the first Sunday of each
        month.  The exact date varies, so we probe dates from the 1st
        through the 7th until we get a successful download.

        Args:
            year: 4-digit year (e.g. 2026)
            month: 1-12
            output_dir: Where to save the ZIP. Defaults to settings.DOWNLOAD_DIR.
            sensitivity: 'PUBLIC' or 'FOUO'
            version: 'V1' or 'V2'

        Returns:
            List of Path objects for the extracted files.

        Raises:
            FileNotFoundError: If no extract file found for any date in range.
            RateLimitExceeded: If daily API limit has been reached.
        """
        output_dir = Path(output_dir) if output_dir else settings.DOWNLOAD_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Try each day 1-7 of the month (the first Sunday varies)
        candidate_dates = self._first_week_dates(year, month)

        # Try both filename formats: V2 with version prefix, and legacy without
        filename_templates = [
            f"SAM_{sensitivity}_MONTHLY_{version}_{{date}}.ZIP",
            f"SAM_{sensitivity}_MONTHLY_{{date}}.ZIP",
        ]

        for candidate in candidate_dates:
            date_str = candidate.strftime("%Y%m%d")
            for template in filename_templates:
                filename = template.format(date=date_str)
                self.logger.info("Trying monthly extract: %s", filename)

                zip_path = self._download_extract_file(filename, output_dir)
                if zip_path is not None:
                    self.logger.info(
                        "Monthly extract downloaded: %s (%s bytes)",
                        zip_path,
                        zip_path.stat().st_size,
                    )
                    return self.extract_zip(zip_path, output_dir)

        raise FileNotFoundError(
            f"No monthly extract found for {year}-{month:02d} "
            f"(tried dates 01-07, sensitivity={sensitivity}, version={version})"
        )

    def download_daily_extract(
        self,
        date_obj,
        output_dir=None,
        sensitivity="PUBLIC",
    ):
        """Download a daily entity extract ZIP from SAM.gov.

        Daily extracts are published Tuesday through Saturday.

        Args:
            date_obj: A datetime.date for the desired extract.
            output_dir: Where to save the ZIP. Defaults to settings.DOWNLOAD_DIR.
            sensitivity: 'PUBLIC' or 'FOUO'

        Returns:
            List of Path objects for the extracted files.

        Raises:
            ValueError: If date_obj falls on a Sunday or Monday.
            FileNotFoundError: If the extract file is not found.
            RateLimitExceeded: If daily API limit has been reached.
        """
        weekday = date_obj.weekday()  # 0=Mon, 6=Sun
        if weekday in (0, 6):  # Monday or Sunday
            raise ValueError(
                f"Daily extracts are only available Tue-Sat. "
                f"{date_obj.isoformat()} is a {date_obj.strftime('%A')}."
            )

        output_dir = Path(output_dir) if output_dir else settings.DOWNLOAD_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = date_obj.strftime("%Y%m%d")
        filename = f"SAM_{sensitivity}_DAILY_V2_{date_str}.ZIP"
        self.logger.info("Downloading daily extract: %s", filename)

        zip_path = self._download_extract_file(filename, output_dir)
        if zip_path is None:
            raise FileNotFoundError(
                f"Daily extract not found: {filename}"
            )

        self.logger.info(
            "Daily extract downloaded: %s (%s bytes)",
            zip_path,
            zip_path.stat().st_size,
        )
        return self.extract_zip(zip_path, output_dir)

    def list_available_extracts(self, sensitivity="PUBLIC", file_type=None):
        """List available extract files on SAM.gov.

        Args:
            sensitivity: 'PUBLIC' or 'FOUO'
            file_type: Optional filter, e.g. 'ENTITY'

        Returns:
            Parsed JSON response (dict) from the API.
        """
        params = {"sensitivity": sensitivity}
        if file_type:
            params["fileType"] = file_type

        response = self.get(self.EXTRACT_ENDPOINT, params=params)
        return response.json()

    def extract_zip(self, zip_path, output_dir=None):
        """Extract a ZIP file, handling nested ZIPs.

        Args:
            zip_path: Path to the ZIP file.
            output_dir: Extraction target. Defaults to same directory as ZIP.

        Returns:
            List of Path objects for all extracted (non-ZIP) files.
        """
        zip_path = Path(zip_path)
        output_dir = Path(output_dir) if output_dir else zip_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted_files = []
        self.logger.info("Extracting %s to %s", zip_path.name, output_dir)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)
            for member in zf.namelist():
                member_path = output_dir / member
                if member_path.is_file():
                    if member_path.suffix.upper() == ".ZIP":
                        # Recursively extract nested ZIPs
                        self.logger.info(
                            "Found nested ZIP: %s", member_path.name
                        )
                        nested = self.extract_zip(member_path, output_dir)
                        extracted_files.extend(nested)
                    else:
                        extracted_files.append(member_path)

        self.logger.info(
            "Extracted %d file(s) from %s", len(extracted_files), zip_path.name
        )
        return extracted_files

    def stream_json_entities(self, json_file_path):
        """Generator yielding one entity dict at a time from a JSON extract.

        The JSON format is: {"entityData": [{...}, {...}, ...]}
        Files can be 55MB+, so we use ijson for streaming when available.
        Falls back to loading the full file if ijson is not installed.

        Args:
            json_file_path: Path to the JSON extract file.

        Yields:
            dict -- A single entity record from the entityData array.
        """
        json_file_path = Path(json_file_path)
        self.logger.info("Streaming entities from %s", json_file_path.name)

        try:
            import ijson

            self.logger.debug("Using ijson for streaming JSON parse")
            yield from self._stream_with_ijson(json_file_path, ijson)
        except ImportError:
            self.logger.warning(
                "ijson not installed -- loading entire JSON file into memory. "
                "Install ijson for better memory usage: pip install ijson"
            )
            yield from self._stream_with_json_fallback(json_file_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _download_extract_file(self, filename, output_dir):
        """Download a single extract file by name.

        If the file already exists locally with a matching size, the
        download is skipped.  The size check uses a streaming GET with
        ``stream=True`` so that only the headers are fetched; if sizes
        match the response body is discarded without consuming
        bandwidth or an extra API call.

        Uses streaming download with progress bar. Routes through
        get_binary() so rate-limit checking and retry logic are handled
        by BaseAPIClient._request_with_retry().

        Args:
            filename: The SAM.gov extract filename (e.g. SAM_PUBLIC_...).
            output_dir: Directory to save the file.

        Returns:
            Path to the downloaded ZIP, or None if not found (404).

        Raises:
            RateLimitExceeded: If daily limit reached.
            requests.HTTPError: On unexpected HTTP errors (non-404 4xx or 5xx).
        """
        self.logger.debug("GET %s?fileName=%s (stream=True)",
                          self.EXTRACT_ENDPOINT, filename)

        try:
            response = self.get_binary(
                self.EXTRACT_ENDPOINT,
                params={"fileName": filename},
                stream=True,
                timeout=60,
            )
        except requests.HTTPError as exc:
            # _request_with_retry raises HTTPError for 4xx (not 429) responses.
            # 404 means the file doesn't exist for this date — a normal condition.
            if exc.response is not None and exc.response.status_code == 404:
                self.logger.debug("Not found: %s", filename)
                return None
            self.logger.error("HTTP error downloading %s: %s", filename, exc)
            raise

        # --- Skip download if local file already matches remote size ---
        dest = output_dir / filename
        remote_size = int(response.headers.get("content-length", 0))

        if dest.exists() and remote_size > 0:
            local_size = dest.stat().st_size
            if local_size == remote_size:
                self.logger.info(
                    "File already exists with matching size (%s bytes), "
                    "skipping download: %s",
                    local_size, dest.name,
                )
                response.close()
                return dest

        # Stream the file to disk with progress bar
        total_size = remote_size
        chunk_size = 8192  # 8 KB

        with (
            open(dest, "wb") as f,
            tqdm(
                total=total_size or None,
                unit="B",
                unit_scale=True,
                desc=filename,
                disable=(total_size == 0),
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    progress.update(len(chunk))

        response.close()
        return dest

    @staticmethod
    def _first_week_dates(year, month):
        """Return date objects for the 1st through 7th of the given month.

        Sorted so the first Sunday comes first, then remaining days in
        order.  This maximizes the chance of hitting the correct file on
        the first attempt.
        """
        dates = [date(year, month, day) for day in range(1, 8)]
        # Sort: Sundays first (weekday 6), then by day
        dates.sort(key=lambda d: (d.weekday() != 6, d.day))
        return dates

    @staticmethod
    def _stream_with_ijson(json_file_path, ijson):
        """Yield entities one at a time using ijson streaming parser."""
        with open(json_file_path, "rb") as f:
            for entity in ijson.items(f, "entityData.item"):
                yield entity

    @staticmethod
    def _stream_with_json_fallback(json_file_path):
        """Yield entities by loading the entire JSON file (fallback)."""
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entities = data.get("entityData", [])
        yield from entities
