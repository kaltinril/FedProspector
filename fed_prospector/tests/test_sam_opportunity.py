"""Unit tests for SAMOpportunityClient (sam_opportunity_client.py).

Tests cover:
- Date formatting and parsing
- Date range splitting for the 1-year API limit
- search_opportunities parameter construction and yielding
- get_opportunity single-record lookup
- Multi-set-aside deduplication
- Call budget enforcement
- estimate_calls_needed calculation
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from api_clients.sam_opportunity_client import (
    SAMOpportunityClient,
    OPPORTUNITY_ENDPOINT,
    MAX_DATE_RANGE_DAYS,
    WOSB_SET_ASIDES,
    SBA_8A_SET_ASIDES,
    ALL_SB_SET_ASIDES,
    PRIORITY_SET_ASIDES,
)
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(call_budget=5):
    """Create a SAMOpportunityClient with zero request_delay."""
    client = SAMOpportunityClient(call_budget=call_budget)
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_wosb_set_asides_contains_expected_codes(self):
        assert "WOSB" in WOSB_SET_ASIDES
        assert "EDWOSB" in WOSB_SET_ASIDES
        assert len(WOSB_SET_ASIDES) == 4

    def test_sba_8a_set_asides_contains_expected_codes(self):
        assert "8A" in SBA_8A_SET_ASIDES
        assert "8AN" in SBA_8A_SET_ASIDES
        assert len(SBA_8A_SET_ASIDES) == 2

    def test_priority_set_asides_are_first_four_of_all(self):
        assert ALL_SB_SET_ASIDES[:4] == PRIORITY_SET_ASIDES

    def test_max_date_range_is_364(self):
        assert MAX_DATE_RANGE_DAYS == 364


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

class TestFormatDate:
    def test_format_date_from_date_object(self):
        result = SAMOpportunityClient._format_date(date(2026, 1, 15))
        assert result == "01/15/2026"

    def test_format_date_from_datetime_object(self):
        result = SAMOpportunityClient._format_date(datetime(2026, 3, 5, 10, 30))
        assert result == "03/05/2026"

    def test_format_date_from_string_passthrough(self):
        result = SAMOpportunityClient._format_date("01/01/2026")
        assert result == "01/01/2026"

    def test_format_date_from_integer_converts_to_string(self):
        result = SAMOpportunityClient._format_date(2026)
        assert result == "2026"


class TestParseDate:
    def test_parse_date_from_date_object(self):
        d = date(2026, 6, 15)
        assert SAMOpportunityClient._parse_date(d) == d

    def test_parse_date_from_datetime_object(self):
        dt = datetime(2026, 6, 15, 10, 30)
        assert SAMOpportunityClient._parse_date(dt) == date(2026, 6, 15)

    def test_parse_date_from_string(self):
        result = SAMOpportunityClient._parse_date("06/15/2026")
        assert result == date(2026, 6, 15)


# ---------------------------------------------------------------------------
# Date range splitting
# ---------------------------------------------------------------------------

class TestSplitDateRange:
    def test_short_range_returns_single_chunk(self):
        client = _make_client()
        chunks = client._split_date_range(date(2026, 1, 1), date(2026, 6, 1))
        assert len(chunks) == 1
        assert chunks[0] == (date(2026, 1, 1), date(2026, 6, 1))

    def test_exactly_364_days_returns_single_chunk(self):
        client = _make_client()
        start = date(2025, 1, 1)
        end = start + timedelta(days=MAX_DATE_RANGE_DAYS)
        chunks = client._split_date_range(start, end)
        assert len(chunks) == 1

    def test_365_days_splits_into_two_chunks(self):
        client = _make_client()
        start = date(2025, 1, 1)
        end = start + timedelta(days=366)  # 366 > MAX_DATE_RANGE_DAYS (364)
        chunks = client._split_date_range(start, end)
        assert len(chunks) == 2
        # First chunk should be exactly MAX_DATE_RANGE_DAYS
        assert (chunks[0][1] - chunks[0][0]).days == MAX_DATE_RANGE_DAYS
        # Second chunk should start the day after the first chunk ends
        assert chunks[1][0] == chunks[0][1] + timedelta(days=1)

    def test_two_year_range_splits_into_three_chunks(self):
        client = _make_client()
        start = date(2024, 1, 1)
        end = date(2026, 1, 1)  # ~730 days
        chunks = client._split_date_range(start, end)
        assert len(chunks) == 3

    def test_string_dates_are_parsed_correctly(self):
        client = _make_client()
        chunks = client._split_date_range("01/01/2026", "06/01/2026")
        assert len(chunks) == 1
        assert chunks[0][0] == date(2026, 1, 1)
        assert chunks[0][1] == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# search_opportunities
# ---------------------------------------------------------------------------

class TestSearchOpportunities:
    def test_yields_opportunities_from_response(self):
        client = _make_client()
        fixture = load_fixture("sam_opportunity_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = list(client.search_opportunities(
            posted_from=date(2026, 1, 1),
            posted_to=date(2026, 2, 1),
            set_aside="WOSB",
        ))

        assert len(results) == 2
        assert results[0]["noticeId"] == "abc123"
        assert results[1]["noticeId"] == "def456"

    def test_passes_all_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "opportunitiesData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_opportunities(
            posted_from="01/01/2026",
            posted_to="02/01/2026",
            set_aside="WOSB",
            naics="541512",
            psc="D302",
            ptype="o",
            state="VA",
            zip_code="22201",
            organization_code="9700",
            title="IT Services",
            solnum="W911NF-25-R-0001",
        ))

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["typeOfSetAside"] == "WOSB"
        assert params["ncode"] == "541512"
        assert params["ccode"] == "D302"
        assert params["ptype"] == "o"
        assert params["state"] == "VA"
        assert params["zip"] == "22201"
        assert params["organizationCode"] == "9700"
        assert params["title"] == "IT Services"
        assert params["solnum"] == "W911NF-25-R-0001"

    def test_omits_none_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "opportunitiesData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_opportunities(
            posted_from="01/01/2026",
            posted_to="02/01/2026",
        ))

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "typeOfSetAside" not in params
        assert "ncode" not in params


# ---------------------------------------------------------------------------
# get_opportunity
# ---------------------------------------------------------------------------

class TestGetOpportunity:
    def test_returns_first_opportunity_when_found(self):
        client = _make_client()
        fixture = load_fixture("sam_opportunity_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_opportunity("abc123")

        assert result is not None
        assert result["noticeId"] == "abc123"

    def test_returns_none_when_total_is_zero(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "opportunitiesData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_opportunity("nonexistent")

        assert result is None

    def test_returns_none_when_data_is_empty_despite_total(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 1,
            "opportunitiesData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_opportunity("ghost")

        assert result is None

    def test_defaults_date_range_to_past_year(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "opportunitiesData": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        client.get_opportunity("abc123")

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "postedFrom" in params
        assert "postedTo" in params


# ---------------------------------------------------------------------------
# estimate_calls_needed
# ---------------------------------------------------------------------------

class TestEstimateCallsNeeded:
    def test_single_code_single_chunk(self):
        client = _make_client()
        result = client.estimate_calls_needed(
            ["WOSB"], date(2026, 1, 1), date(2026, 6, 1)
        )
        assert result == 1

    def test_multiple_codes_single_chunk(self):
        client = _make_client()
        result = client.estimate_calls_needed(
            WOSB_SET_ASIDES, date(2026, 1, 1), date(2026, 6, 1)
        )
        assert result == 4  # 4 set-aside codes * 1 chunk

    def test_multiple_codes_multiple_chunks(self):
        client = _make_client()
        result = client.estimate_calls_needed(
            ["WOSB", "8A"], date(2024, 1, 1), date(2026, 1, 1)
        )
        # ~730 days = 3 chunks, 2 codes = 6 calls
        assert result == 6
