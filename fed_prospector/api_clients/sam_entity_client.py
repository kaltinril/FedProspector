"""SAM.gov Entity Management API client.

Wraps the Entity Management v3 API for entity lookups, date-based queries,
and filtered searches. Provides convenience methods for WOSB and 8(a)
entity discovery.

API docs: https://open.gsa.gov/api/entity-api/
Endpoint: /entity-information/v3/entities
Free tier: 10 requests/day (configurable via SAM_DAILY_LIMIT env var)
"""

# OpenAPI spec: thesolution/sam_gov_api/entity-api.yaml

import logging
from datetime import date, datetime

from api_clients.base_client import BaseAPIClient, RateLimitExceeded
from config import settings


logger = logging.getLogger("fed_prospector.api.sam_entity")

# SAM.gov Entity Management API endpoint (v3)
ENTITY_ENDPOINT = "/entity-information/v3/entities"

# Business type codes (businessTypeCode query param)
# These appear in coreData.businessTypes.businessTypeList
WOSB_BUSINESS_TYPE_CODES = {
    "A2": "Woman Owned Business",
    "8W": "Woman Owned Small Business",
    "8E": "Economically Disadvantaged Women-Owned Small Business",
    "8C": "Joint Venture Women Owned Small Business",
    "8D": "Joint Venture Economically Disadvantaged Women-Owned Small Business",
}

# SBA business type codes (sbaBusinessTypeCode query param)
# These appear in coreData.businessTypes.sbaBusinessTypeList
# The 8(a) program is an SBA certification, not a general business type
SBA_8A_BUSINESS_TYPE_CODE = "A4"
SBA_8A_DESCRIPTION = "SBA Certified 8(a) Program Participant"


class SAMEntityClient(BaseAPIClient):
    """Client for the SAM.gov Entity Management API v3.

    Inherits rate limiting, retries, and pagination from BaseAPIClient.
    All methods default to includeSections=all to retrieve full entity data.

    Usage:
        client = SAMEntityClient()
        entity = client.get_entity_by_uei("ABC123DEF456")
        for entity in client.search_wosb_entities(stateCode="VA"):
            print(entity["entityRegistration"]["legalBusinessName"])
    """

    def __init__(self):
        super().__init__(
            base_url=settings.SAM_API_BASE_URL,
            api_key=settings.SAM_API_KEY,
            source_name="SAM_ENTITY",
            max_daily_requests=settings.SAM_DAILY_LIMIT,
        )

    def get_entity_by_uei(self, uei_sam, include_sections="all"):
        """Look up a single entity by its Unique Entity Identifier (UEI).

        Args:
            uei_sam: 12-character SAM UEI (e.g. "ABC123DEF456").
            include_sections: Comma-separated sections to include. Default "all".
                Valid values: entityRegistration, coreData, assertions,
                repsAndCerts, mandatoryPOCs, optionalPOCs, all.

        Returns:
            dict: The entity record from entityData, or None if not found.

        Raises:
            RateLimitExceeded: If daily API limit has been reached.
            requests.HTTPError: On non-retryable HTTP errors.
        """
        params = {
            "ueiSAM": uei_sam,
            "includeSections": include_sections,
        }
        self.logger.info("Looking up entity by UEI: %s", uei_sam)
        response = self.get(ENTITY_ENDPOINT, params=params)
        data = response.json()

        total = data.get("totalRecords", 0)
        if total == 0:
            self.logger.info("No entity found for UEI: %s", uei_sam)
            return None

        entities = data.get("entityData", [])
        if not entities:
            self.logger.warning(
                "totalRecords=%d but entityData is empty for UEI: %s",
                total, uei_sam,
            )
            return None

        self.logger.info("Found entity for UEI: %s", uei_sam)
        return entities[0]

    def get_entities_by_date(self, update_date, registration_status="A",
                             include_sections="all"):
        """Get all entities updated on a specific date.

        Uses pagination to retrieve all matching records. Returns a generator
        that yields individual entity records.

        Args:
            update_date: Date to query. Accepts date object, datetime object,
                or string in MM/DD/YYYY format.
            registration_status: "A" for Active (default) or "E" for Expired.
            include_sections: Sections to include. Default "all".

        Yields:
            dict: Individual entity records from entityData.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.
        """
        date_str = self._format_date(update_date)

        params = {
            "registrationStatus": registration_status,
            "updateDate": date_str,
            "includeSections": include_sections,
        }

        self.logger.info(
            "Fetching entities updated on %s (status=%s)",
            date_str, registration_status,
        )

        total_yielded = 0
        for page_data in self.paginate(ENTITY_ENDPOINT, params=params):
            entities = page_data.get("entityData", [])
            for entity in entities:
                total_yielded += 1
                yield entity

        self.logger.info(
            "Finished date query for %s: %d entities yielded",
            date_str, total_yielded,
        )

    def search_entities(self, include_sections="all", **filters):
        """Search entities with arbitrary filters. Returns a generator.

        Passes all keyword arguments directly as SAM.gov API query parameters.
        See the OpenAPI spec (thesolution/sam_gov_api/entity-api.yaml) for valid parameter names.

        Common filter parameters:
            ueiSAM, legalBusinessName, dbaName, registrationStatus,
            physicalAddressCity, physicalAddressProvinceOrStateCode,
            physicalAddressCountryCode, physicalAddressZipPostalCode,
            naicsCode, primaryNaics, pscCode, businessTypeCode,
            sbaBusinessTypeCode, entityStructureCode, updateDate,
            registrationDate, exclusionStatusFlag, cageCode, dodaac

        Args:
            include_sections: Sections to include. Default "all".
            **filters: SAM.gov API query parameters.

        Yields:
            dict: Individual entity records from entityData.

        Raises:
            RateLimitExceeded: If daily API limit is reached during pagination.

        Example:
            for entity in client.search_entities(
                physicalAddressProvinceOrStateCode="VA",
                naicsCode="541511",
                registrationStatus="A",
            ):
                print(entity["entityRegistration"]["legalBusinessName"])
        """
        params = dict(filters)
        params["includeSections"] = include_sections

        filter_summary = ", ".join(f"{k}={v}" for k, v in filters.items())
        self.logger.info("Searching entities with filters: %s", filter_summary)

        total_yielded = 0
        for page_data in self.paginate(ENTITY_ENDPOINT, params=params):
            entities = page_data.get("entityData", [])
            for entity in entities:
                total_yielded += 1
                yield entity

        self.logger.info(
            "Search complete: %d entities yielded (filters: %s)",
            total_yielded, filter_summary,
        )

    def search_wosb_entities(self, include_edwosb=True, **kwargs):
        """Search for Women-Owned Small Business (WOSB) entities.

        Convenience method that sets the businessTypeCode filter to the
        WOSB code (8W). Pass additional filters as keyword arguments.

        Args:
            include_edwosb: If True (default), also search for Economically
                Disadvantaged WOSB (8E) entities in a separate query. Note
                that the SAM API accepts only one businessTypeCode value per
                request, so multiple codes require separate API calls.
            **kwargs: Additional SAM.gov API query parameters
                (e.g. stateCode, naicsCode, registrationStatus).

        Yields:
            dict: Individual entity records matching WOSB criteria.

        Note:
            Each business type code requires a separate API call. With the
            free-tier limit of 10 calls/day, use filters to narrow results
            and be mindful of remaining daily requests.
        """
        # Primary search: Woman Owned Small Business (8W)
        self.logger.info("Searching for WOSB (8W) entities")
        yield from self.search_entities(businessTypeCode="8W", **kwargs)

        # Optional: also search for EDWOSB (8E)
        if include_edwosb:
            remaining = self._get_remaining_requests()
            if remaining > 0:
                self.logger.info("Searching for EDWOSB (8E) entities")
                yield from self.search_entities(businessTypeCode="8E", **kwargs)
            else:
                self.logger.warning(
                    "Skipping EDWOSB (8E) search: no API requests remaining today"
                )

    def search_8a_entities(self, **kwargs):
        """Search for SBA 8(a) certified entities.

        Convenience method that sets the sbaBusinessTypeCode filter to the
        8(a) program code (A4). The 8(a) Business Development Program is
        an SBA certification, so it uses sbaBusinessTypeCode rather than
        businessTypeCode.

        Args:
            **kwargs: Additional SAM.gov API query parameters
                (e.g. stateCode, naicsCode, registrationStatus).

        Yields:
            dict: Individual entity records with 8(a) certification.
        """
        self.logger.info("Searching for SBA 8(a) certified entities")
        yield from self.search_entities(sbaBusinessTypeCode=SBA_8A_BUSINESS_TYPE_CODE,
                                        **kwargs)

    @staticmethod
    def _format_date(value):
        """Convert a date value to MM/DD/YYYY format expected by SAM.gov API.

        Args:
            value: A date object, datetime object, or string. If string,
                it is returned as-is (caller is responsible for format).

        Returns:
            str: Date in MM/DD/YYYY format, or the original string.
        """
        if isinstance(value, datetime):
            return value.strftime("%m/%d/%Y")
        if isinstance(value, date):
            return value.strftime("%m/%d/%Y")
        # Assume string is already formatted
        return str(value)
