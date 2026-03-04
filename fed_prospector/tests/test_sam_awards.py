"""Unit tests for SAMAwardsClient (sam_awards_client.py).

Tests cover:
- Date range formatting ("[MM/DD/YYYY,MM/DD/YYYY]")
- search_awards parameter construction
- search_awards_all pagination
- Convenience methods: search_by_naics, search_by_awardee, search_by_solicitation
- estimate_calls_needed
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from api_clients.sam_awards_client import SAMAwardsClient
from api_clients.base_client import RateLimitExceeded
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key_number=1):
    """Create a SAMAwardsClient with zero request_delay."""
    client = SAMAwardsClient(api_key_number=api_key_number)
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Date range formatting
# ---------------------------------------------------------------------------

class TestFormatDateRange:
    def test_both_dates_as_date_objects(self):
        result = SAMAwardsClient._format_date_range(
            date(2025, 10, 1), date(2026, 9, 30)
        )
        assert result == "[10/01/2025,09/30/2026]"

    def test_both_dates_as_datetime_objects(self):
        result = SAMAwardsClient._format_date_range(
            datetime(2025, 10, 1, 12, 0), datetime(2026, 9, 30, 12, 0)
        )
        assert result == "[10/01/2025,09/30/2026]"

    def test_dates_as_yyyymmdd_strings(self):
        result = SAMAwardsClient._format_date_range("20251001", "20260930")
        assert result == "[10/01/2025,09/30/2026]"

    def test_dates_as_iso_strings(self):
        result = SAMAwardsClient._format_date_range("2025-10-01", "2026-09-30")
        assert result == "[10/01/2025,09/30/2026]"

    def test_only_from_date(self):
        result = SAMAwardsClient._format_date_range(date(2025, 10, 1), None)
        assert result == "10/01/2025"

    def test_only_to_date(self):
        result = SAMAwardsClient._format_date_range(None, date(2026, 9, 30))
        assert result == "09/30/2026"

    def test_both_none_returns_empty(self):
        result = SAMAwardsClient._format_date_range(None, None)
        assert result == ""


# ---------------------------------------------------------------------------
# search_awards
# ---------------------------------------------------------------------------

class TestSearchAwards:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("sam_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_awards(naics_code="541512")

        assert result["totalRecords"] == 2
        assert len(result["awardSummary"]) == 2

    def test_passes_all_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "awardSummary": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_awards(
            naics_code="541512",
            set_aside="WOSB",
            agency_code="9700",
            awardee_uei="ABC123",
            psc_code="D302",
            piid="W911NF-25-C-0001",
            fiscal_year=2026,
            pop_state="VA",
            date_signed_from=date(2025, 10, 1),
            date_signed_to=date(2026, 9, 30),
        )

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["naicsCode"] == "541512"
        assert params["typeOfSetAsideCode"] == "WOSB"
        assert params["contractingDepartmentCode"] == "9700"
        assert params["awardeeUniqueEntityId"] == "ABC123"
        assert params["productOrServiceCode"] == "D302"
        assert params["piid"] == "W911NF-25-C-0001"
        assert params["fiscalYear"] == "2026"
        assert params["popState"] == "VA"
        assert params["dateSigned"] == "[10/01/2025,09/30/2026]"

    def test_omits_none_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "awardSummary": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_awards()

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "naicsCode" not in params
        assert "dateSigned" not in params


# ---------------------------------------------------------------------------
# search_awards_all pagination
# ---------------------------------------------------------------------------

class TestSearchAwardsAll:
    def test_yields_all_awards_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "totalRecords": 3,
            "awardSummary": [{"id": 1}, {"id": 2}],
        })
        page2 = make_mock_response(200, {
            "totalRecords": 3,
            "awardSummary": [{"id": 3}],
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.search_awards_all(limit=2))

        assert len(results) == 3
        assert results[0]["id"] == 1
        assert results[2]["id"] == 3

    def test_stops_on_empty_results(self):
        client = _make_client()
        empty = make_mock_response(200, {
            "totalRecords": 0,
            "awardSummary": [],
        })
        client.session.request = MagicMock(return_value=empty)

        results = list(client.search_awards_all())

        assert results == []
        assert client.session.request.call_count == 1


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------

class TestSearchByNaics:
    def test_single_naics_code(self):
        client = _make_client()
        fixture = load_fixture("sam_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_naics("541512")

        assert len(results) == 2

    def test_multiple_naics_codes(self):
        client = _make_client()
        resp = make_mock_response(200, {
            "totalRecords": 1,
            "awardSummary": [{"id": 1}],
        })
        client.session.request = MagicMock(return_value=resp)

        results = client.search_by_naics(["541512", "541519"])

        assert len(results) == 2  # 1 per NAICS code

    def test_string_naics_code_converted_to_list(self):
        client = _make_client()
        resp = make_mock_response(200, {
            "totalRecords": 1,
            "awardSummary": [{"id": 1}],
        })
        client.session.request = MagicMock(return_value=resp)

        results = client.search_by_naics("541512")

        assert len(results) == 1


class TestSearchByAwardee:
    def test_returns_awards_for_uei(self):
        client = _make_client()
        fixture = load_fixture("sam_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_awardee("ABC123DEF456")

        assert len(results) == 2


class TestSearchBySolicitation:
    def test_returns_awards_for_piid(self):
        client = _make_client()
        fixture = load_fixture("sam_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_solicitation("W911NF-25-C-0001")

        assert len(results) == 2


# ---------------------------------------------------------------------------
# estimate_calls_needed
# ---------------------------------------------------------------------------

class TestEstimateCallsNeeded:
    def test_single_code(self):
        client = _make_client()
        assert client.estimate_calls_needed(["541512"], None, None) == 1

    def test_multiple_codes(self):
        client = _make_client()
        assert client.estimate_calls_needed(
            ["541512", "541519", "541511"], None, None
        ) == 3

    def test_string_input_treated_as_single(self):
        client = _make_client()
        assert client.estimate_calls_needed("541512", None, None) == 1
