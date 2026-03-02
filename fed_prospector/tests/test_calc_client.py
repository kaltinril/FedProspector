"""Unit tests for CalcPlusClient (calc_client.py).

Tests cover:
- ES response parsing (_extract_hits, _get_total_count)
- search_rates parameter construction
- search_rates_all pagination with ES max window
- get_all_rates multi-strategy deduplication
- get_rate_summary statistics calculation
- get() override (no api_key)
"""

from unittest.mock import MagicMock

import pytest

from api_clients.calc_client import CalcPlusClient, _ES_MAX_WINDOW, _SORT_STRATEGIES
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Create a CalcPlusClient with zero request_delay."""
    client = CalcPlusClient()
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# ES response helpers
# ---------------------------------------------------------------------------

class TestExtractHits:
    def test_extracts_source_with_es_id(self):
        data = {
            "hits": {
                "hits": [
                    {"_id": "abc", "_source": {"vendor_name": "Acme", "current_price": 100.0}},
                    {"_id": "def", "_source": {"vendor_name": "Corp", "current_price": 200.0}},
                ]
            }
        }
        results = CalcPlusClient._extract_hits(data)

        assert len(results) == 2
        assert results[0]["vendor_name"] == "Acme"
        assert results[0]["_es_id"] == "abc"
        assert results[1]["current_price"] == 200.0

    def test_returns_empty_list_for_no_hits(self):
        data = {"hits": {"hits": []}}
        results = CalcPlusClient._extract_hits(data)
        assert results == []

    def test_handles_missing_hits_key(self):
        results = CalcPlusClient._extract_hits({})
        assert results == []


class TestGetTotalCount:
    def test_uses_aggregation_count_when_available(self):
        data = {
            "hits": {"total": {"value": 10000, "relation": "gte"}},
            "aggregations": {"wage_stats": {"count": 230000}},
        }
        assert CalcPlusClient._get_total_count(data) == 230000

    def test_falls_back_to_hits_total_dict(self):
        data = {
            "hits": {"total": {"value": 5000, "relation": "eq"}},
            "aggregations": {"wage_stats": {}},
        }
        assert CalcPlusClient._get_total_count(data) == 5000

    def test_falls_back_to_hits_total_int(self):
        data = {"hits": {"total": 42}}
        assert CalcPlusClient._get_total_count(data) == 42

    def test_returns_zero_for_empty_data(self):
        assert CalcPlusClient._get_total_count({}) == 0


# ---------------------------------------------------------------------------
# get() override
# ---------------------------------------------------------------------------

class TestGetOverride:
    def test_get_does_not_add_api_key(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"hits": {"hits": []}})
        client.session.request = MagicMock(return_value=mock_resp)

        client.get("/ceilingrates/", params={"keyword": "test"})

        call_args = client.session.request.call_args
        params = call_args[1].get("params", {})
        assert "api_key" not in params


# ---------------------------------------------------------------------------
# search_rates
# ---------------------------------------------------------------------------

class TestSearchRates:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("calc_rates_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_rates(keyword="software developer")

        assert "hits" in result
        assert len(result["hits"]["hits"]) == 3

    def test_passes_keyword_and_pagination_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"hits": {"hits": []}})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_rates(
            keyword="project manager",
            page=2,
            page_size=50,
            sort="desc",
            ordering="vendor_name",
        )

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["keyword"] == "project manager"
        assert params["page"] == 2
        assert params["page_size"] == 50
        assert params["sort"] == "desc"
        assert params["ordering"] == "vendor_name"

    def test_omits_none_keyword_and_ordering(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"hits": {"hits": []}})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_rates()

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "keyword" not in params
        assert "ordering" not in params


# ---------------------------------------------------------------------------
# search_rates_all pagination
# ---------------------------------------------------------------------------

class TestSearchRatesAll:
    def test_yields_all_rates(self):
        client = _make_client()
        fixture = load_fixture("calc_rates_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = list(client.search_rates_all(keyword="software"))

        assert len(results) == 3
        assert results[0]["vendor_name"] == "Acme Consulting LLC"

    def test_stops_when_fewer_than_page_size_results(self):
        client = _make_client()
        # 3 results but page_size is 1000, so only 1 page
        fixture = load_fixture("calc_rates_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        list(client.search_rates_all())

        assert client.session.request.call_count == 1

    def test_stops_at_es_max_window(self):
        """Verify we do not request beyond the 10000 ES window."""
        client = _make_client()
        # Return full pages of 1000 to force multiple pages
        full_page_hits = [
            {"_id": f"r{i}", "_source": {"current_price": 100.0}}
            for i in range(1000)
        ]
        full_page = make_mock_response(200, {
            "hits": {"total": {"value": 10000, "relation": "gte"}, "hits": full_page_hits},
        })
        client.session.request = MagicMock(return_value=full_page)

        list(client.search_rates_all())

        # page_size=1000, so 10 pages max (10*1000 = 10000)
        assert client.session.request.call_count == 10


# ---------------------------------------------------------------------------
# get_all_rates deduplication
# ---------------------------------------------------------------------------

class TestGetAllRates:
    def test_deduplicates_by_es_id(self):
        client = _make_client()
        # Two strategies return overlapping records
        data_with_overlap = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "r1", "_source": {"current_price": 100.0}},
                    {"_id": "r2", "_source": {"current_price": 200.0}},
                ],
            },
        }
        mock_resp = make_mock_response(200, data_with_overlap)
        client.session.request = MagicMock(return_value=mock_resp)

        results = list(client.get_all_rates())

        # Even though many strategies are used, r1 and r2 only appear once each
        assert len(results) == 2
        ids = [r["_es_id"] for r in results]
        assert "r1" in ids
        assert "r2" in ids

    def test_calls_progress_callback(self):
        client = _make_client()
        data = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_id": "r1", "_source": {"current_price": 100.0}}],
            },
        }
        mock_resp = make_mock_response(200, data)
        client.session.request = MagicMock(return_value=mock_resp)

        callback = MagicMock()
        list(client.get_all_rates(progress_callback=callback))

        assert callback.call_count == len(_SORT_STRATEGIES)


# ---------------------------------------------------------------------------
# get_rate_summary
# ---------------------------------------------------------------------------

class TestGetRateSummary:
    def test_returns_summary_statistics(self):
        client = _make_client()
        fixture = load_fixture("calc_rates_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        summary = client.get_rate_summary("software developer")

        assert summary is not None
        assert summary["keyword"] == "software developer"
        assert summary["count"] == 3
        assert summary["min"] == 125.50
        assert summary["max"] == 175.00
        assert 145.0 < summary["avg"] < 147.5  # ~146.92

    def test_returns_none_when_no_rates_found(self):
        client = _make_client()
        empty = make_mock_response(200, {"hits": {"hits": []}})
        client.session.request = MagicMock(return_value=empty)

        summary = client.get_rate_summary("nonexistent category")

        assert summary is None

    def test_filters_by_business_size(self):
        client = _make_client()
        fixture = load_fixture("calc_rates_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        summary = client.get_rate_summary("software", business_size="SMALL")

        assert summary is not None
        # Only 2 SMALL records in fixture (Acme 125.50, Federal IT 140.25)
        assert summary["count"] == 2
        assert summary["min"] == 125.50
        assert summary["max"] == 140.25

    def test_returns_none_when_no_valid_prices(self):
        client = _make_client()
        data = {
            "hits": {
                "hits": [
                    {"_id": "r1", "_source": {"vendor_name": "Test", "current_price": None}},
                ]
            }
        }
        mock_resp = make_mock_response(200, data)
        client.session.request = MagicMock(return_value=mock_resp)

        summary = client.get_rate_summary("test")

        assert summary is None
