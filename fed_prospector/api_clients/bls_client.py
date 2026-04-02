"""Bureau of Labor Statistics (BLS) API client.

Fetches Employment Cost Index (ECI) and Consumer Price Index (CPI) data
for rate escalation benchmarking and pricing intelligence.

API docs: https://www.bls.gov/developers/
Endpoint: POST /publicAPI/v2/timeseries/data/
Auth: Optional registration key (higher rate limits with key)
Rate limits: 25 queries per 24-hour period (unregistered), 500 with key
"""

import logging

from api_clients.base_client import BaseAPIClient
from config import settings


logger = logging.getLogger("fed_prospector.api.bls")

# Key BLS series IDs for federal contracting pricing intelligence
SERIES_ECI_PROFESSIONAL = "CIU2020000000000I"  # ECI professional/business services
SERIES_ECI_ALL_CIVILIAN = "CIU2010000000000I"  # ECI all civilian workers
SERIES_CPI_ALL_URBAN = "CUUR0000SA0"           # CPI-U all urban consumers
SERIES_CPI_LESS_FOOD_ENERGY = "CUUR0000SA0L1E" # CPI-U less food and energy

ALL_SERIES = [
    SERIES_ECI_PROFESSIONAL,
    SERIES_ECI_ALL_CIVILIAN,
    SERIES_CPI_ALL_URBAN,
    SERIES_CPI_LESS_FOOD_ENERGY,
]

SERIES_NAMES = {
    SERIES_ECI_PROFESSIONAL: "ECI Professional and Business Services",
    SERIES_ECI_ALL_CIVILIAN: "ECI All Civilian Workers",
    SERIES_CPI_ALL_URBAN: "CPI-U All Urban Consumers",
    SERIES_CPI_LESS_FOOD_ENERGY: "CPI-U Less Food and Energy",
}


class BLSClient(BaseAPIClient):
    """Client for the Bureau of Labor Statistics public API v2."""

    def __init__(self):
        api_key = settings.BLS_API_KEY or ""
        daily_limit = settings.BLS_DAILY_LIMIT if api_key else 25
        super().__init__(
            base_url=settings.BLS_API_BASE_URL,
            api_key=api_key,
            source_name="BLS",
            max_daily_requests=daily_limit,
            request_delay=0.5,
            logger_name="fed_prospector.api.bls",
        )

    def fetch_series(self, series_ids, start_year, end_year):
        """Fetch time series data from BLS API.

        Args:
            series_ids: List of BLS series ID strings.
            start_year: Start year (int).
            end_year: End year (int).

        Returns:
            dict: Parsed JSON response from BLS API.
        """
        payload = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self.api_key:
            payload["registrationkey"] = self.api_key

        self.logger.info(
            "Fetching BLS series %s for years %d-%d",
            series_ids, start_year, end_year,
        )

        # BLS API uses POST to the base URL (no endpoint path)
        response = self._request_with_retry("POST", self.base_url, json_body=payload)
        data = response.json()

        status = data.get("status", "UNKNOWN")
        if status != "REQUEST_SUCCEEDED":
            msg = data.get("message", [])
            self.logger.error("BLS API returned status=%s: %s", status, msg)
            raise RuntimeError(f"BLS API error: status={status}, messages={msg}")

        results = data.get("Results", {})
        series_list = results.get("series", [])
        self.logger.info(
            "BLS response: %d series returned", len(series_list),
        )
        return data
