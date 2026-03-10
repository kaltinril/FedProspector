"""Unit tests for SAMOpportunityClient (sam_opportunity_client.py).

Tests cover:
- Date formatting and parsing
- Date range splitting for the 1-year API limit
- search_opportunities parameter construction and yielding
- get_opportunity single-record lookup
- Multi-set-aside deduplication
- Call budget enforcement
- Budget exhaustion mid-search (83-T3)
- estimate_calls_needed calculation
"""

import logging
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
    # _format_date is now an instance method inherited from BaseAPIClient.
    # SAMOpportunityClient uses MM/DD/YYYY format, so fmt="%m/%d/%Y" is passed.

    def test_format_date_from_date_object(self):
        client = _make_client()
        result = client._format_date(date(2026, 1, 15), "%m/%d/%Y")
        assert result == "01/15/2026"

    def test_format_date_from_datetime_object(self):
        client = _make_client()
        result = client._format_date(datetime(2026, 3, 5, 10, 30), "%m/%d/%Y")
        assert result == "03/05/2026"

    def test_format_date_from_string_passthrough(self):
        client = _make_client()
        result = client._format_date("01/01/2026", "%m/%d/%Y")
        assert result == "01/01/2026"

    def test_format_date_from_integer_converts_to_string(self):
        client = _make_client()
        result = client._format_date(2026, "%m/%d/%Y")
        assert result == "2026"


class TestParseDate:
    # _parse_date is now an instance method (was @staticmethod).
    # Also extended to handle YYYY-MM-DD format (HIGH bug fix).

    def test_parse_date_from_date_object(self):
        client = _make_client()
        d = date(2026, 6, 15)
        assert client._parse_date(d) == d

    def test_parse_date_from_datetime_object(self):
        client = _make_client()
        dt = datetime(2026, 6, 15, 10, 30)
        assert client._parse_date(dt) == date(2026, 6, 15)

    def test_parse_date_from_string(self):
        client = _make_client()
        result = client._parse_date("06/15/2026")
        assert result == date(2026, 6, 15)

    def test_parse_date_from_iso_string(self):
        # Regression test for HIGH bug fix: YYYY-MM-DD format now supported
        client = _make_client()
        result = client._parse_date("2026-06-15")
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


# ---------------------------------------------------------------------------
# 83-T3: Budget exhaustion mid-search
# ---------------------------------------------------------------------------

class TestBudgetExhaustionMidSearch:
    """Verify that _search_multiple_set_asides stops when the call budget is
    exhausted partway through iteration, rather than querying all set-asides."""

    def test_stops_after_budget_exhausted(self, mock_db_connection):
        """With a budget of 2, searching 4 set-aside codes should stop after
        the budget is consumed, not after all 4 codes are queried.

        _get_remaining_requests() call sites in _search_multiple_set_asides:
        1. Line 430: calls_at_start = budget - remaining  (before loop)
        2. Line 448: calls_used check  (before each code)
        3. Line 458: remaining check   (before each code)
        4. Line 485: calls_used recalc (after each code's search)
        5. Line 448: calls_used check  (before next code -- triggers break)
        6. Line 493: calls_used final  (after loop)
        """
        client = _make_client(call_budget=2)

        # budget=2, remaining starts at 100, so calls_at_start = 2 - 100 = -98
        # After WOSB search, remaining drops to 98 => calls_used = (2-98)-(-98) = 2 >= 2 => stop
        remaining_sequence = [
            100,   # 1: calls_at_start = 2 - 100 = -98
            99,    # 2: budget check before WOSB: calls_used = (2-99)-(-98) = 1 < 2
            99,    # 3: remaining check for WOSB: 99 > 0
            98,    # 4: after WOSB search: calls_used = (2-98)-(-98) = 2
            98,    # 5: budget check before EDWOSB: calls_used = (2-98)-(-98) = 2 >= 2 => break
            98,    # 6: final calls_used after loop
        ]
        client._get_remaining_requests = MagicMock(side_effect=remaining_sequence)

        def fake_search(posted_from, posted_to, set_aside=None, **kwargs):
            yield {"noticeId": f"opp-{set_aside}", "title": f"Test {set_aside}"}

        client.search_opportunities = MagicMock(side_effect=fake_search)

        results = client._search_multiple_set_asides(
            ["WOSB", "EDWOSB", "8A", "8AN"],
            posted_from=date(2026, 1, 1),
            posted_to=date(2026, 3, 1),
        )

        # Should have only queried WOSB (first code), then stopped
        assert len(results) == 1
        assert results[0]["noticeId"] == "opp-WOSB"

        # search_opportunities should have been called only once (for WOSB)
        assert client.search_opportunities.call_count == 1
        called_set_aside = client.search_opportunities.call_args[1].get("set_aside")
        assert called_set_aside == "WOSB"

    def test_budget_exhaustion_logs_warning(self, mock_db_connection, caplog):
        """When budget is exhausted, a warning should be logged listing the
        skipped set-aside codes."""
        client = _make_client(call_budget=1)

        # budget=1, remaining starts at 100, calls_at_start = 1 - 100 = -99
        # After WOSB: remaining=99 => calls_used = (1-99)-(-99) = 1 >= 1 => break
        remaining_sequence = [
            100,   # 1: calls_at_start = 1 - 100 = -99
            100,   # 2: budget check before WOSB: calls_used = (1-100)-(-99) = 0 < 1
            100,   # 3: remaining check for WOSB: 100 > 0
            99,    # 4: after WOSB: calls_used = (1-99)-(-99) = 1
            99,    # 5: budget check before EDWOSB: calls_used = (1-99)-(-99) = 1 >= 1 => break
            99,    # 6: final calls_used after loop
        ]
        client._get_remaining_requests = MagicMock(side_effect=remaining_sequence)

        def fake_search(posted_from, posted_to, set_aside=None, **kwargs):
            yield {"noticeId": f"opp-{set_aside}", "title": f"Test {set_aside}"}

        client.search_opportunities = MagicMock(side_effect=fake_search)

        with caplog.at_level(logging.WARNING, logger="fed_prospector.api.sam_opportunity"):
            results = client._search_multiple_set_asides(
                ["WOSB", "EDWOSB", "8A"],
                posted_from=date(2026, 1, 1),
                posted_to=date(2026, 3, 1),
            )

        # Check that warning was logged about budget exhaustion
        budget_warnings = [r for r in caplog.records
                          if "budget exhausted" in r.message.lower()
                          or "budget" in r.message.lower() and "skipped" in r.message.lower()]
        assert len(budget_warnings) > 0, (
            f"Expected a budget exhaustion warning but got: "
            f"{[r.message for r in caplog.records]}"
        )

        # The skipped codes should be mentioned in the warning
        warning_text = " ".join(r.message for r in budget_warnings)
        assert "EDWOSB" in warning_text or "8A" in warning_text

    def test_daily_limit_exhaustion_stops_search(self, mock_db_connection):
        """When _get_remaining_requests returns 0, the search should stop
        even if the call budget hasn't been reached."""
        client = _make_client(call_budget=10)

        # budget=10, remaining starts at 100, calls_at_start = 10 - 100 = -90
        # After WOSB: remaining=0 => calls_used = (10-0)-(-90) = 100 >= 10 => break
        remaining_sequence = [
            100,   # 1: calls_at_start = 10 - 100 = -90
            100,   # 2: budget check before WOSB: calls_used = (10-100)-(-90) = 0 < 10
            100,   # 3: remaining check for WOSB: 100 > 0
            0,     # 4: after WOSB: calls_used = (10-0)-(-90) = 100
            0,     # 5: budget check before EDWOSB: calls_used = 100 >= 10 => break
            0,     # 6: final calls_used after loop
        ]
        client._get_remaining_requests = MagicMock(side_effect=remaining_sequence)

        def fake_search(posted_from, posted_to, set_aside=None, **kwargs):
            yield {"noticeId": f"opp-{set_aside}", "title": f"Test {set_aside}"}

        client.search_opportunities = MagicMock(side_effect=fake_search)

        results = client._search_multiple_set_asides(
            ["WOSB", "EDWOSB"],
            posted_from=date(2026, 1, 1),
            posted_to=date(2026, 3, 1),
        )

        # Only first set-aside should have been queried
        assert len(results) == 1
        assert client.search_opportunities.call_count == 1
