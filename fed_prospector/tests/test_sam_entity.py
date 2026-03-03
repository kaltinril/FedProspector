"""Unit tests for SAMEntityClient (sam_entity_client.py).

Tests cover:
- Entity lookup by UEI
- Date-based entity queries
- Generic search with arbitrary filters
- WOSB and 8(a) convenience searches
- Date formatting
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from api_clients.sam_entity_client import (
    SAMEntityClient,
    ENTITY_ENDPOINT,
    WOSB_BUSINESS_TYPE_CODES,
    SBA_8A_BUSINESS_TYPE_CODE,
)
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Create a SAMEntityClient with zero request_delay."""
    client = SAMEntityClient()
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_wosb_codes_include_8w_and_8e(self):
        assert "8W" in WOSB_BUSINESS_TYPE_CODES
        assert "8E" in WOSB_BUSINESS_TYPE_CODES

    def test_sba_8a_code_is_a4(self):
        assert SBA_8A_BUSINESS_TYPE_CODE == "A4"


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

class TestFormatDate:
    # _format_date is now an instance method inherited from BaseAPIClient.
    # SAMEntityClient uses MM/DD/YYYY format, so fmt="%m/%d/%Y" is passed.

    def test_format_date_from_date_object(self):
        client = _make_client()
        result = client._format_date(date(2026, 3, 15), "%m/%d/%Y")
        assert result == "03/15/2026"

    def test_format_date_from_datetime_object(self):
        client = _make_client()
        result = client._format_date(datetime(2026, 12, 1, 8, 0), "%m/%d/%Y")
        assert result == "12/01/2026"

    def test_format_date_from_string_passthrough(self):
        client = _make_client()
        result = client._format_date("03/15/2026", "%m/%d/%Y")
        assert result == "03/15/2026"


# ---------------------------------------------------------------------------
# get_entity_by_uei
# ---------------------------------------------------------------------------

class TestGetEntityByUei:
    def test_returns_entity_when_found(self):
        client = _make_client()
        fixture = load_fixture("sam_entity_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        entity = client.get_entity_by_uei("ABC123DEF456")

        assert entity is not None
        assert entity["entityRegistration"]["ueiSAM"] == "ABC123DEF456"
        assert entity["entityRegistration"]["legalBusinessName"] == "Acme Federal Solutions LLC"

    def test_returns_none_when_not_found(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "entityData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        entity = client.get_entity_by_uei("NONEXISTENT123")

        assert entity is None

    def test_returns_none_when_data_empty_despite_total(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 1,
            "entityData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        entity = client.get_entity_by_uei("GHOST000000000")

        assert entity is None

    def test_sends_uei_and_include_sections_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.get_entity_by_uei("TEST123", include_sections="entityRegistration")

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["ueiSAM"] == "TEST123"
        assert params["includeSections"] == "entityRegistration"


# ---------------------------------------------------------------------------
# get_entities_by_date
# ---------------------------------------------------------------------------

class TestGetEntitiesByDate:
    def test_yields_entities_from_paginated_response(self):
        client = _make_client()
        fixture = load_fixture("sam_entity_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        entities = list(client.get_entities_by_date(date(2026, 1, 10)))

        assert len(entities) == 1
        assert entities[0]["entityRegistration"]["ueiSAM"] == "ABC123DEF456"

    def test_accepts_string_date(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.get_entities_by_date("01/10/2026"))

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["updateDate"] == "01/10/2026"


# ---------------------------------------------------------------------------
# search_entities
# ---------------------------------------------------------------------------

class TestSearchEntities:
    def test_passes_arbitrary_filters_as_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_entities(
            physicalAddressProvinceOrStateCode="VA",
            naicsCode="541511",
            registrationStatus="A",
        ))

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["physicalAddressProvinceOrStateCode"] == "VA"
        assert params["naicsCode"] == "541511"
        assert params["registrationStatus"] == "A"
        assert params["includeSections"] == "all"


# ---------------------------------------------------------------------------
# search_wosb_entities
# ---------------------------------------------------------------------------

class TestSearchWosbEntities:
    def test_searches_with_8w_business_type_code(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_wosb_entities(include_edwosb=False))

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["businessTypeCode"] == "8W"

    def test_also_searches_edwosb_by_default(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_wosb_entities())

        # Should have made 2 calls: one for 8W and one for 8E
        assert client.session.request.call_count == 2


# ---------------------------------------------------------------------------
# search_8a_entities
# ---------------------------------------------------------------------------

class TestSearch8aEntities:
    def test_searches_with_a4_sba_business_type_code(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "entityData": []})
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_8a_entities())

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["sbaBusinessTypeCode"] == "A4"
