"""SCA Wage Determination client — downloads WD text files from SAM.gov.

Data sources:
- Search API: sam.gov/api/prod/sgs/v1/search/?index=sca
  Returns all active WD numbers WITH revision numbers. Primary discovery source.
- WD download: sam.gov/api/prod/wdol/v1/wd/{WD_NUMBER}/{REVISION}/download
  Returns fixed-width plain text. S3-backed, no rate limiting, no API key.
- Crosswalk XLSX (legacy, kept as fallback): maps counties to WD numbers.
- GSA Non-Standard WD PDF: lists ~94 non-standard WD numbers for GSA MAS contracts.

No API key needed for any endpoint.
"""

import io
import logging
import re

from api_clients.base_client import BaseAPIClient, TIMEOUT_DOWNLOAD

logger = logging.getLogger("fed_prospector.api.sca_wd")

CROSSWALK_PATH = "/sites/default/files/2024-11/sca-2015-crosswalk.xlsx"
WD_DOWNLOAD_PATH = "/api/prod/wdol/v1/wd/{wd_number}/{revision}/download"
GSA_NONSTANDARD_PDF_URL = (
    "https://www.gsa.gov/system/files/"
    "Non-Standard%20Wage%20Determinations%202022-0042%20to%202025-0077"
    "%20MAS%20Refresh%20%2327%20June%202025_0.pdf"
)


class SCAWDClient(BaseAPIClient):
    """Client for downloading SCA wage determinations from SAM.gov."""

    def __init__(self):
        super().__init__(
            base_url="https://sam.gov",
            api_key="",
            source_name="SCA_WD",
            max_daily_requests=999999,  # No rate limit (S3-backed)
            request_delay=0.05,  # Minimal politeness delay
            logger_name="fed_prospector.api.sca_wd",
        )

    def load_active_wd_list(self) -> list[dict]:
        """Load the active WD reference file (data/sca_active_wds.tsv).

        This file contains WD numbers and revision numbers extracted from
        SAM.gov's search results. It is the primary discovery source —
        no revision probing needed when revisions are known.

        To refresh this file, download all active SCA WDs from:
        https://sam.gov/search/?index=sca&pageSize=1100&sfm[status][is_active]=true
        Then extract WD numbers and revision numbers.

        Returns:
            List of dicts with keys: wd_number, revision
        """
        import os

        tsv_path = os.path.join(os.path.dirname(__file__), "..", "data", "sca_active_wds.tsv")
        tsv_path = os.path.normpath(tsv_path)

        if not os.path.exists(tsv_path):
            self.logger.warning("Active WD list not found at %s", tsv_path)
            return []

        results = []
        with open(tsv_path, "r") as f:
            header = f.readline()  # skip header
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[1].isdigit():
                    results.append({
                        "wd_number": parts[0],
                        "revision": int(parts[1]),
                    })

        self.logger.info("Loaded %d active WDs from reference file", len(results))
        return results

    def download_crosswalk(self) -> list[dict]:
        """Download the SCA crosswalk XLSX and parse to list of dicts.

        Returns:
            List of dicts with keys: state, county, wd_number, msa_code, area_name
        """
        import openpyxl

        self.logger.info("Downloading SCA crosswalk XLSX from %s%s", self.base_url, CROSSWALK_PATH)
        response = self.get_binary(CROSSWALK_PATH, stream=False)
        wb = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True, data_only=True)
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        # Read header row and normalize to lowercase
        header = [str(h).strip().lower() if h else "" for h in next(rows_iter)]
        self.logger.info("Crosswalk header columns: %s", header)

        # Map expected columns — flexible matching
        col_map = {}
        for i, col_name in enumerate(header):
            if "state" in col_name:
                col_map["state"] = i
            elif "county" in col_name and "wd" not in col_name:
                col_map["county"] = i
            elif "wd" in col_name and "num" in col_name:
                col_map["wd_number"] = i
            elif col_name in ("wd", "wd #", "wd#"):
                col_map["wd_number"] = i
            elif "msa" in col_name:
                col_map["msa_code"] = i
            elif "area" in col_name:
                col_map["area_name"] = i

        if "wd_number" not in col_map:
            # Fallback: try to find any column with "wd" or "wage determination"
            for i, col_name in enumerate(header):
                if "wd" in col_name or "wage" in col_name:
                    col_map["wd_number"] = i
                    break

        if "wd_number" not in col_map:
            raise ValueError(
                f"Could not find WD number column in crosswalk. Headers: {header}"
            )

        results = []
        for row in rows_iter:
            if not row or all(cell is None for cell in row):
                continue
            wd_num = row[col_map["wd_number"]] if col_map.get("wd_number") is not None else None
            if not wd_num:
                continue
            # XLSX stores WD suffix as float (e.g. 4587.0). Convert to "2015-4587".
            if isinstance(wd_num, float):
                wd_num = int(wd_num)
            wd_str = str(wd_num).strip()
            if not wd_str or wd_str.lower() in ("none", ""):
                continue
            # If it's just a number (the suffix), prepend the series prefix
            if wd_str.isdigit():
                wd_str = f"2015-{wd_str}"
            record = {
                "state": str(row[col_map["state"]]).strip() if col_map.get("state") is not None and row[col_map["state"]] else None,
                "county": str(row[col_map["county"]]).strip() if col_map.get("county") is not None and row[col_map["county"]] else None,
                "wd_number": wd_str,
                "msa_code": str(row[col_map["msa_code"]]).strip() if col_map.get("msa_code") is not None and row[col_map["msa_code"]] else None,
                "area_name": str(row[col_map["area_name"]]).strip() if col_map.get("area_name") is not None and row[col_map["area_name"]] else None,
            }
            results.append(record)

        wb.close()
        self.logger.info("Parsed %d crosswalk rows, %d unique WD numbers",
                         len(results), len({r["wd_number"] for r in results}))
        return results

    def download_nonstandard_wd_list(self, exclude_wd_numbers: set[str] | None = None) -> list[str]:
        """Download the GSA Non-Standard Wage Determinations PDF and extract WD numbers.

        The PDF lists ~94 non-standard WDs used on GSA MAS contracts.
        WD numbers are extracted via regex (YYYY-NNNN format) and deduplicated.

        Args:
            exclude_wd_numbers: Set of WD numbers to exclude (e.g. from crosswalk).

        Returns:
            Sorted list of unique non-standard WD number strings.
        """
        import pdfplumber
        import requests

        exclude = exclude_wd_numbers or set()
        self.logger.info("Downloading GSA non-standard WD PDF from %s", GSA_NONSTANDARD_PDF_URL)

        # Download from GSA directly (different domain from base_url)
        resp = requests.get(GSA_NONSTANDARD_PDF_URL, timeout=60)
        resp.raise_for_status()

        # Extract text from all pages
        all_text = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

        full_text = "\n".join(all_text)

        # Extract WD numbers matching YYYY-NNNN pattern
        wd_pattern = re.compile(r'\b(\d{4}-\d{4})\b')
        found = set(wd_pattern.findall(full_text))

        # Filter out anything that doesn't look like a real WD number
        # (year part should be 2015-2099 range)
        valid = set()
        for wd in found:
            year = int(wd.split("-")[0])
            if 2015 <= year <= 2099:
                valid.add(wd)

        # Remove any already covered by the crosswalk
        nonstandard = sorted(valid - exclude)

        self.logger.info(
            "Extracted %d WD numbers from PDF, %d after excluding %d crosswalk WDs",
            len(valid), len(nonstandard), len(valid) - len(nonstandard),
        )
        return nonstandard

    def download_wd(self, wd_number: str, revision: int) -> tuple[str | None, int]:
        """Download a single WD text file.

        Args:
            wd_number: e.g. "2015-4001"
            revision: Revision number (0 = original)

        Returns:
            Tuple of (text_content, http_status).
            text_content is None on non-200 responses.
        """
        import requests as req

        url = f"{self.base_url}{WD_DOWNLOAD_PATH.format(wd_number=wd_number, revision=revision)}"
        try:
            # Use requests directly (not base class) because 404 is expected
            # during revision probing and _request_with_retry logs 404 as ERROR.
            response = self.session.get(url, timeout=TIMEOUT_DOWNLOAD)
            if response.status_code == 200:
                return response.text, 200
            return None, response.status_code
        except Exception as exc:
            self.logger.debug("WD download failed for %s rev %d: %s", wd_number, revision, exc)
            return None, 0

    def _head_check(self, wd_number: str, revision: int) -> bool:
        """Quick HEAD request to check if a revision exists (303=yes, 404=no)."""
        url = f"{self.base_url}{WD_DOWNLOAD_PATH.format(wd_number=wd_number, revision=revision)}"
        try:
            response = self.session.head(url, timeout=10, allow_redirects=False)
            return response.status_code in (200, 303)
        except Exception:
            return False

    def find_latest_revision(self, wd_number: str, start_revision: int = 1) -> tuple[str | None, int]:
        """Find the latest revision using doubling + bisect, then download it.

        Strategy:
        1. Doubling phase: from start_revision, double the step until we hit a 404.
           This finds an upper bound in O(log N) requests.
        2. Bisect phase: binary search between last-known-good and upper bound.
           This pinpoints the exact latest revision in O(log N) requests.
        3. Single GET to download the content of the latest revision.

        Uses HEAD requests for probing (fast, no body download).
        """
        # Verify start_revision exists
        if not self._head_check(wd_number, start_revision):
            if start_revision > 1:
                # Cached revision no longer valid, fall back to 1
                start_revision = 1
                if not self._head_check(wd_number, 1):
                    return None, -1
            else:
                return None, -1

        # Phase 1: Doubling — find upper bound
        lo = start_revision
        step = 1
        while True:
            probe = lo + step
            if self._head_check(wd_number, probe):
                lo = probe
                step *= 2
            else:
                hi = probe
                break
            # Safety cap — no WD has 1000+ revisions
            if step > 512:
                hi = lo + 512
                break

        # Phase 2: Bisect — find exact latest between lo and hi
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self._head_check(wd_number, mid):
                lo = mid
            else:
                hi = mid

        # lo is now the latest revision. Download the content.
        text, status = self.download_wd(wd_number, lo)
        if text and status == 200:
            self.logger.debug("WD %s latest revision: %d", wd_number, lo)
            return text, lo

        return None, -1

        if latest_rev >= 0:
            self.logger.debug("WD %s latest revision: %d", wd_number, latest_rev)
        return latest_text, latest_rev
