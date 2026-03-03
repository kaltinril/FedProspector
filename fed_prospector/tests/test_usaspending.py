"""Unit tests for USASpendingClient (usaspending_client.py).

Tests cover:
- Date formatting (YYYY-MM-DD)
- search_awards POST body construction
- search_awards_all pagination via hasNext
- get_award detail retrieval
- search_incumbent convenience method
- get_spending_by_category
- get_top_recipients
- get_award_transactions and get_all_transactions pagination
- get() override (no api_key)
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from api_clients.usaspending_client import (
    USASpendingClient,
    CONTRACT_AWARD_TYPES,
    DEFAULT_LOOKBACK_YEARS,
)
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Create a USASpendingClient with zero request_delay."""
    client = USASpendingClient()
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_contract_award_types_are_abcd(self):
        assert CONTRACT_AWARD_TYPES == ["A", "B", "C", "D"]

    def test_default_lookback_is_5_years(self):
        assert DEFAULT_LOOKBACK_YEARS == 5


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

class TestFormatDate:
    # _format_date is now an instance method inherited from BaseAPIClient.
    # USASpending uses YYYY-MM-DD (the base class default fmt).

    def test_format_date_from_date_object(self):
        client = _make_client()
        result = client._format_date(date(2026, 3, 15))
        assert result == "2026-03-15"

    def test_format_date_from_string_passthrough(self):
        client = _make_client()
        result = client._format_date("2026-03-15")
        assert result == "2026-03-15"


# ---------------------------------------------------------------------------
# get() — no api_key injection for clients with empty api_key=""
# (Win 4 fix: BaseAPIClient.get() skips api_key when self.api_key is falsy)
# ---------------------------------------------------------------------------

class TestGetNoApiKey:
    def test_get_does_not_add_api_key(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"data": "ok"})
        client.session.request = MagicMock(return_value=mock_resp)

        client.get("/api/v2/test", params={"q": "hello"})

        call_args = client.session.request.call_args
        params = call_args[1].get("params", {})
        assert "api_key" not in params


# ---------------------------------------------------------------------------
# search_awards
# ---------------------------------------------------------------------------

class TestSearchAwards:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("usaspending_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_awards(naics_codes=["541512"])

        assert len(result["results"]) == 1
        assert result["results"][0]["Award ID"] == "W911NF-25-C-0001"

    def test_builds_correct_post_body(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "results": [], "page_metadata": {"hasNext": False},
        })
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_awards(
            naics_codes=["541512"],
            psc_codes=["D302"],
            set_aside_codes=["WOSB"],
            recipient_name="Acme",
            keyword="IT Services",
            start_date=date(2025, 10, 1),
            end_date=date(2026, 9, 30),
            limit=50,
            page=2,
        )

        call_args = client.session.request.call_args
        body = call_args[1]["json"]
        assert body["filters"]["naics_codes"] == ["541512"]
        assert body["filters"]["psc_codes"] == ["D302"]
        assert body["filters"]["set_aside_type_codes"] == ["WOSB"]
        assert body["filters"]["recipient_search_text"] == ["Acme"]
        assert body["filters"]["keywords"] == ["IT Services"]
        assert body["filters"]["time_period"] == [
            {"start_date": "2025-10-01", "end_date": "2026-09-30"}
        ]
        assert body["filters"]["award_type_codes"] == CONTRACT_AWARD_TYPES
        assert body["limit"] == 50
        assert body["page"] == 2

    def test_omits_none_filters(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "results": [], "page_metadata": {"hasNext": False},
        })
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_awards()

        call_args = client.session.request.call_args
        body = call_args[1]["json"]
        assert "naics_codes" not in body["filters"]
        assert "time_period" not in body["filters"]


# ---------------------------------------------------------------------------
# search_awards_all pagination
# ---------------------------------------------------------------------------

class TestSearchAwardsAll:
    def test_yields_all_awards_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "results": [{"Award ID": "A"}, {"Award ID": "B"}],
            "page_metadata": {"page": 1, "hasNext": True, "total": 3, "limit": 2},
        })
        page2 = make_mock_response(200, {
            "results": [{"Award ID": "C"}],
            "page_metadata": {"page": 2, "hasNext": False, "total": 3, "limit": 2},
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.search_awards_all(limit=2))

        assert len(results) == 3
        assert results[2]["Award ID"] == "C"

    def test_stops_when_has_next_is_false(self):
        client = _make_client()
        resp = make_mock_response(200, {
            "results": [{"Award ID": "A"}],
            "page_metadata": {"page": 1, "hasNext": False, "total": 1, "limit": 100},
        })
        client.session.request = MagicMock(return_value=resp)

        results = list(client.search_awards_all())

        assert len(results) == 1
        assert client.session.request.call_count == 1


# ---------------------------------------------------------------------------
# get_award
# ---------------------------------------------------------------------------

class TestGetAward:
    def test_returns_award_detail(self):
        client = _make_client()
        detail = {"id": "CONT_AWD_123", "total_obligation": 3000000}
        mock_resp = make_mock_response(200, detail)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_award("CONT_AWD_123")

        assert result["id"] == "CONT_AWD_123"

    def test_returns_none_on_error(self):
        client = _make_client()
        client.session.request = MagicMock(side_effect=Exception("404 Not Found"))

        result = client.get_award("NONEXISTENT")

        assert result is None

    def test_get_award_detail_is_alias(self):
        client = _make_client()
        detail = {"id": "CONT_AWD_123"}
        mock_resp = make_mock_response(200, detail)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_award_detail("CONT_AWD_123")

        assert result["id"] == "CONT_AWD_123"


# ---------------------------------------------------------------------------
# search_incumbent
# ---------------------------------------------------------------------------

class TestSearchIncumbent:
    def test_returns_top_result(self):
        client = _make_client()
        fixture = load_fixture("usaspending_awards_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_incumbent(solicitation_number="W911NF-25-R-0001")

        assert result is not None
        assert result["Recipient Name"] == "Acme Federal Solutions LLC"

    def test_returns_none_when_no_results(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "results": [],
            "page_metadata": {"page": 1, "hasNext": False, "total": 0, "limit": 10},
        })
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_incumbent(naics_code="999999")

        assert result is None


# ---------------------------------------------------------------------------
# get_spending_by_category
# ---------------------------------------------------------------------------

class TestGetSpendingByCategory:
    def test_posts_with_correct_endpoint(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"results": [], "page_metadata": {}})
        client.session.request = MagicMock(return_value=mock_resp)

        client.get_spending_by_category(
            "recipient",
            {"award_type_codes": CONTRACT_AWARD_TYPES},
            limit=10,
        )

        call_args = client.session.request.call_args
        url = call_args[0][1]
        assert "spending_by_category/recipient/" in url


# ---------------------------------------------------------------------------
# get_award_transactions pagination
# ---------------------------------------------------------------------------

class TestGetAwardTransactions:
    def test_returns_transaction_page(self):
        client = _make_client()
        txn_data = {
            "results": [{"id": 1, "action_date": "2025-10-15"}],
            "page_metadata": {"page": 1, "hasNext": False, "total": 1, "limit": 5000},
        }
        mock_resp = make_mock_response(200, txn_data)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.get_award_transactions("CONT_AWD_123")

        assert len(result["results"]) == 1


class TestGetAllTransactions:
    def test_yields_all_transactions_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "results": [{"id": 1}, {"id": 2}],
            "page_metadata": {"page": 1, "hasNext": True, "total": 3, "limit": 2},
        })
        page2 = make_mock_response(200, {
            "results": [{"id": 3}],
            "page_metadata": {"page": 2, "hasNext": False, "total": 3, "limit": 2},
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.get_all_transactions("CONT_AWD_123"))

        assert len(results) == 3
