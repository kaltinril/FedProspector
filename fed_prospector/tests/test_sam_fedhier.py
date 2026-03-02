"""Unit tests for SAMFedHierClient (sam_fedhier_client.py).

Tests cover:
- Date formatting (YYYY-MM-DD)
- search_organizations parameter construction
- search_organizations_all pagination
- get_all_organizations convenience method
- get_organization single lookup
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from api_clients.sam_fedhier_client import SAMFedHierClient
from tests.conftest import make_mock_response, load_fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key_number=1):
    """Create a SAMFedHierClient with zero request_delay."""
    client = SAMFedHierClient(api_key_number=api_key_number)
    client.request_delay = 0
    return client


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

class TestFormatDate:
    def test_format_date_from_date_object(self):
        assert SAMFedHierClient._format_date(date(2026, 1, 15)) == "2026-01-15"

    def test_format_date_from_datetime_object(self):
        assert SAMFedHierClient._format_date(datetime(2026, 1, 15, 10, 30)) == "2026-01-15"

    def test_format_date_from_string_passthrough(self):
        assert SAMFedHierClient._format_date("2026-01-15") == "2026-01-15"

    def test_format_date_none_returns_none(self):
        assert SAMFedHierClient._format_date(None) is None


# ---------------------------------------------------------------------------
# search_organizations
# ---------------------------------------------------------------------------

class TestSearchOrganizations:
    def test_returns_json_response(self):
        client = _make_client()
        fixture = load_fixture("sam_fedhier_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.search_organizations(status="Active")

        assert result["totalrecords"] == 2
        assert len(result["orglist"]) == 2

    def test_passes_all_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalrecords": 0, "orglist": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_organizations(
            fhorgid="100000000",
            fhorgname="Defense",
            status="Active",
            fhorgtype="Department/Ind. Agency",
            agencycode="9700",
            cgac="097",
            fhparentorgname="None",
            updateddatefrom=date(2025, 1, 1),
            updateddateto=date(2026, 1, 1),
        )

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert params["fhorgid"] == "100000000"
        assert params["fhorgname"] == "Defense"
        assert params["status"] == "Active"
        assert params["fhorgtype"] == "Department/Ind. Agency"
        assert params["agencycode"] == "9700"
        assert params["cgac"] == "097"
        assert params["updateddatefrom"] == "2025-01-01"
        assert params["updateddateto"] == "2026-01-01"

    def test_omits_none_filter_params(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalrecords": 0, "orglist": []})
        client.session.request = MagicMock(return_value=mock_resp)

        client.search_organizations()

        call_args = client.session.request.call_args
        params = call_args[1]["params"]
        assert "fhorgid" not in params
        assert "fhorgname" not in params


# ---------------------------------------------------------------------------
# search_organizations_all pagination
# ---------------------------------------------------------------------------

class TestSearchOrganizationsAll:
    def test_yields_all_orgs_across_pages(self):
        client = _make_client()
        page1 = make_mock_response(200, {
            "totalrecords": 3,
            "orglist": [{"fhorgid": 1}, {"fhorgid": 2}],
        })
        page2 = make_mock_response(200, {
            "totalrecords": 3,
            "orglist": [{"fhorgid": 3}],
        })
        client.session.request = MagicMock(side_effect=[page1, page2])

        results = list(client.search_organizations_all(limit=2))

        assert len(results) == 3

    def test_stops_on_empty_results(self):
        client = _make_client()
        empty = make_mock_response(200, {"totalrecords": 0, "orglist": []})
        client.session.request = MagicMock(return_value=empty)

        results = list(client.search_organizations_all())

        assert results == []


# ---------------------------------------------------------------------------
# get_all_organizations
# ---------------------------------------------------------------------------

class TestGetAllOrganizations:
    def test_returns_list_of_all_active_orgs(self):
        client = _make_client()
        fixture = load_fixture("sam_fedhier_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        orgs = client.get_all_organizations()

        assert len(orgs) == 2
        assert orgs[0]["fhorgname"] == "Department of Defense"


# ---------------------------------------------------------------------------
# get_organization
# ---------------------------------------------------------------------------

class TestGetOrganization:
    def test_returns_org_when_found(self):
        client = _make_client()
        fixture = load_fixture("sam_fedhier_response")
        mock_resp = make_mock_response(200, fixture)
        client.session.request = MagicMock(return_value=mock_resp)

        org = client.get_organization(100000000)

        assert org is not None
        assert org["fhorgid"] == 100000000

    def test_returns_none_when_not_found(self):
        client = _make_client()
        mock_resp = make_mock_response(200, {"totalrecords": 0, "orglist": []})
        client.session.request = MagicMock(return_value=mock_resp)

        org = client.get_organization(999999999)

        assert org is None
