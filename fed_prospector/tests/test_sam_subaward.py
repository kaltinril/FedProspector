"""Unit tests for SAMSubawardClient (sam_subaward_client.py).

Tests cover:
- Date formatting (yyyy-MM-dd) and MM/DD/YYYY conversion
- search_subcontracts parameter construction
- search_subcontracts_all pagination with max_pages
- Convenience methods: search_by_prime, search_by_sub, search_by_naics, search_by_piid
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from api_clients.sam_subaward_client import SAMSubawardClient
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key_number=1):
    """Create a SAMSubawardClient with zero request_delay."""
    client = SAMSubawardClient(api_key_number=api_key_number)
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

class TestFormatDate:
    # _format_date is now an instance method inherited from BaseAPIClient.
    # The base class converts date/datetime objects to YYYY-MM-DD (default fmt).
    # Strings are returned as-is (str(value)). The old client-level special
    # MM/DD/YYYY → YYYY-MM-DD string conversion has been removed; callers are
    # expected to pass date/datetime objects or ISO strings.

    def test_format_date_from_date_object(self):
        client = _make_client()
        result = client._format_date(date(2025, 11, 1))
        assert result == "2025-11-01"

    def test_format_date_from_datetime_object(self):
        client = _make_client()
        result = client._format_date(datetime(2025, 11, 1, 12, 0))
        assert result == "2025-11-01"

    def test_format_date_from_iso_string_passthrough(self):
        client = _make_client()
        result = client._format_date("2025-11-01")
        assert result == "2025-11-01"

    def test_format_date_from_other_string_passthrough(self):
        client = _make_client()
        result = client._format_date("Nov 1 2025")
        assert result == "Nov 1 2025"


# ---------------------------------------------------------------------------
# search_subcontracts
# ---------------------------------------------------------------------------

class TestSearchSubcontracts:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("sam_subaward_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_subcontracts(agency_id="9700")

        assert result["totalRecords"] == 2
        assert len(result["data"]) == 2

    def test_passes_all_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0, "totalPages": 0,
            "pageNumber": 0, "data": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_subcontracts(
            piid="W911NF-25-C-0001",
            agency_id="9700",
            prime_uei="PRIME123UEI456",
            sub_uei="SUB789UEI012",
            naics_code="541512",
            from_date=date(2025, 1, 1),
            to_date=date(2025, 12, 31),
            prime_award_type="Contract",
            status="Published",
            page_number=0,
            page_size=100,
        )

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["PIID"] == "W911NF-25-C-0001"
        assert params["agencyId"] == "9700"
        assert params["primeEntityUei"] == "PRIME123UEI456"
        assert params["subEntityUei"] == "SUB789UEI012"
        assert params["primeNaics"] == "541512"
        assert params["fromDate"] == "2025-01-01"
        assert params["toDate"] == "2025-12-31"
        assert params["primeAwardType"] == "Contract"
        assert params["status"] == "Published"

    def test_omits_none_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0, "totalPages": 0,
            "pageNumber": 0, "data": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_subcontracts()

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "PIID" not in params
        assert "agencyId" not in params
        assert "fromDate" not in params


# ---------------------------------------------------------------------------
# search_subcontracts_all pagination
# ---------------------------------------------------------------------------

class TestSearchSubcontractsAll:
    def test_yields_all_subcontracts_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "totalRecords": 3, "totalPages": 2,
            "pageNumber": 0, "data": [{"id": 1}, {"id": 2}],
        })
        page2 = make_mock_response(200, {
            "totalRecords": 3, "totalPages": 2,
            "pageNumber": 1, "data": [{"id": 3}],
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.search_subcontracts_all(page_size=2))

        assert len(results) == 3

    def test_stops_on_empty_results(self):
        client = _make_client()
        empty = make_mock_response(200, {
            "totalRecords": 0, "totalPages": 0,
            "pageNumber": 0, "data": [],
        })
        client.session.request = MagicMock(return_value=empty)

        results = list(client.search_subcontracts_all())

        assert results == []

    def test_respects_max_pages_limit(self):
        client = _make_client()
        page = make_mock_response(200, {
            "totalRecords": 1000, "totalPages": 10,
            "pageNumber": 0, "data": [{"id": i} for i in range(100)],
        })
        client.session.request = MagicMock(return_value=page)

        results = list(client.search_subcontracts_all(max_pages=2, page_size=100))

        # Should stop after 2 pages even though 10 pages available
        assert client.session.request.call_count == 2


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------

class TestSearchByPrime:
    def test_returns_subcontracts_for_prime_uei(self):
        client = _make_client()
        fixture = load_fixture("sam_subaward_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_prime("PRIME123UEI456")

        assert len(results) == 2


class TestSearchBySub:
    def test_returns_subcontracts_for_sub_uei(self):
        client = _make_client()
        fixture = load_fixture("sam_subaward_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_sub("SUB789UEI012")

        assert len(results) == 2


class TestSearchByNaics:
    def test_returns_subcontracts_for_naics(self):
        client = _make_client()
        fixture = load_fixture("sam_subaward_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_naics("541512")

        assert len(results) == 2


class TestSearchByPiid:
    def test_returns_subcontracts_for_piid(self):
        client = _make_client()
        fixture = load_fixture("sam_subaward_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_piid("W911NF-25-C-0001")

        assert len(results) == 2
