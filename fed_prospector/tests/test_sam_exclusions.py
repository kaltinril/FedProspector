"""Unit tests for SAMExclusionsClient (sam_exclusions_client.py).

Tests cover:
- search_exclusions parameter construction
- search_exclusions_all pagination
- check_entity single UEI lookup
- check_entities batch check
- search_by_name convenience method
"""

from unittest.mock import MagicMock

import pytest

from api_clients.sam_exclusions_client import SAMExclusionsClient
from api_clients.base_client import RateLimitExceeded
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key_number=1):
    """Create a SAMExclusionsClient with zero request_delay."""
    client = SAMExclusionsClient(api_key_number=api_key_number)
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# search_exclusions
# ---------------------------------------------------------------------------

class TestSearchExclusions:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("sam_exclusions_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_exclusions(uei="XYZ789GHI012")

        assert result["totalRecords"] == 1
        assert len(result["excludedEntity"]) == 1

    def test_passes_all_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "excludedEntity": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_exclusions(
            uei="XYZ789GHI012",
            q="Bad Actor",
            excluding_agency_code="9700",
            exclusion_type="Ineligible",
            exclusion_program="Reciprocal",
            size=5,
            page=2,
        )

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["ueiSAM"] == "XYZ789GHI012"
        assert params["q"] == "Bad Actor"
        assert params["excludingAgencyCode"] == "9700"
        assert params["exclusionType"] == "Ineligible"
        assert params["exclusionProgram"] == "Reciprocal"
        assert params["size"] == 5
        assert params["page"] == 2

    def test_omits_none_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalRecords": 0, "excludedEntity": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_exclusions()

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "ueiSAM" not in params
        assert "q" not in params


# ---------------------------------------------------------------------------
# search_exclusions_all pagination
# ---------------------------------------------------------------------------

class TestSearchExclusionsAll:
    def test_yields_all_exclusions_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "totalRecords": 12,
            "excludedEntity": [{"id": i} for i in range(10)],
        })
        page2 = make_mock_response(200, {
            "totalRecords": 12,
            "excludedEntity": [{"id": 10}, {"id": 11}],
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.search_exclusions_all(size=10))

        assert len(results) == 12

    def test_stops_on_empty_results(self):
        client = _make_client()
        empty = make_mock_response(200, {
            "totalRecords": 0,
            "excludedEntity": [],
        })
        client.session.request = MagicMock(return_value=empty)

        results = list(client.search_exclusions_all())

        assert results == []
        assert client.session.request.call_count == 1


# ---------------------------------------------------------------------------
# check_entity
# ---------------------------------------------------------------------------

class TestCheckEntity:
    def test_returns_exclusions_for_excluded_uei(self):
        client = _make_client()
        fixture = load_fixture("sam_exclusions_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        exclusions = client.check_entity("XYZ789GHI012")

        assert len(exclusions) == 1
        assert exclusions[0]["exclusionIdentification"]["entityName"] == "Bad Actor Corp"

    def test_returns_empty_list_for_clean_uei(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {
            "totalRecords": 0,
            "excludedEntity": [],
        })
        client.session.request = MagicMock(return_value=mock_resp)

        exclusions = client.check_entity("CLEAN123UEI456")

        assert exclusions == []


# ---------------------------------------------------------------------------
# check_entities (batch)
# ---------------------------------------------------------------------------

class TestCheckEntities:
    def test_returns_dict_of_excluded_ueis_only(self):
        client = _make_client()

        excluded_resp = make_mock_response(200, {
            "totalRecords": 1,
            "excludedEntity": [{"exclusionIdentification": {"entityName": "Bad Actor"}}],
        })
        clean_resp = make_mock_response(200, {
            "totalRecords": 0,
            "excludedEntity": [],
        })
        client.session.request = MagicMock(
            side_effect=[excluded_resp, clean_resp]
        )

        results = client.check_entities(["BAD_UEI", "CLEAN_UEI"])

        assert "BAD_UEI" in results
        assert "CLEAN_UEI" not in results
        assert len(results["BAD_UEI"]) == 1


# ---------------------------------------------------------------------------
# search_by_name
# ---------------------------------------------------------------------------

class TestSearchByName:
    def test_returns_matching_exclusions(self):
        client = _make_client()
        fixture = load_fixture("sam_exclusions_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        results = client.search_by_name("Bad Actor")

        assert len(results) == 1
        assert results[0]["exclusionIdentification"]["entityName"] == "Bad Actor Corp"
