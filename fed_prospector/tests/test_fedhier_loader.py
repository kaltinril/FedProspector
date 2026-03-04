"""Tests for etl.fedhier_loader -- normalisation, parent extraction, upsert."""

import pytest
from unittest.mock import MagicMock, patch

from etl.fedhier_loader import FedHierLoader, _ORG_HASH_FIELDS, _ORG_TYPE_LEVELS


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_org(**overrides):
    """Return a minimal raw Federal Hierarchy API org dict."""
    base = {
        "fhorgid": 100123456,
        "fhorgname": "Test Department",
        "fhorgtype": "Department/Ind. Agency",
        "status": "ACTIVE",
        "agencycode": "4700",
        "oldfpdsofficecode": "47PA",
        "cgaclist": [{"cgac": "047"}],
        "fhorgparenthistory": [],
        "fhdeptindagencyorgid": None,
        "createddate": "2020-01-15",
        "lastupdateddate": "2026-01-10",
    }
    base.update(overrides)
    return base


def _make_subtier_org(**overrides):
    """Return a raw sub-tier org dict with parent reference."""
    base = _make_raw_org(
        fhorgid=100234567,
        fhorgname="Test Sub-Tier",
        fhorgtype="Sub-Tier",
        fhorgparenthistory=[
            {"fhfullparentpathid": "100123456"}
        ],
        fhdeptindagencyorgid=100123456,
    )
    base.update(overrides)
    return base


def _make_office_org(**overrides):
    """Return a raw office org dict with full parent path."""
    base = _make_raw_org(
        fhorgid=100345678,
        fhorgname="Test Office",
        fhorgtype="Office",
        fhorgparenthistory=[
            {"fhfullparentpathid": "100123456.100234567"}
        ],
    )
    base.update(overrides)
    return base


# ===================================================================
# _normalize_org tests
# ===================================================================

class TestNormalizeOrg:

    def _loader(self):
        with patch("etl.fedhier_loader.get_connection"), \
             patch("etl.staging_mixin.get_connection"):
            return FedHierLoader()

    def test_normalize_department(self):
        loader = self._loader()
        result = loader._normalize_org(_make_raw_org())

        assert result["fh_org_id"] == 100123456
        assert result["fh_org_name"] == "Test Department"
        assert result["fh_org_type"] == "Department/Ind. Agency"
        assert result["status"] == "ACTIVE"
        assert result["agency_code"] == "4700"
        assert result["oldfpds_office_code"] == "47PA"
        assert result["cgac"] == "047"
        assert result["parent_org_id"] is None  # Top-level
        assert result["level"] == 1
        assert result["created_date"] == "2020-01-15"
        assert result["last_modified_date"] == "2026-01-10"

    def test_normalize_subtier(self):
        loader = self._loader()
        result = loader._normalize_org(_make_subtier_org())

        assert result["fh_org_id"] == 100234567
        assert result["fh_org_type"] == "Sub-Tier"
        assert result["parent_org_id"] == 100123456
        assert result["level"] == 2

    def test_normalize_office_uses_last_path_segment(self):
        loader = self._loader()
        result = loader._normalize_org(_make_office_org())

        assert result["fh_org_id"] == 100345678
        assert result["fh_org_type"] == "Office"
        # Parent should be the last segment of the full path
        assert result["parent_org_id"] == 100234567
        assert result["level"] == 3

    def test_normalize_empty_cgaclist(self):
        loader = self._loader()
        raw = _make_raw_org(cgaclist=[])
        result = loader._normalize_org(raw)
        assert result["cgac"] is None

    def test_normalize_no_parent_history_uses_dept_id(self):
        """Sub-tier without parent history falls back to fhdeptindagencyorgid."""
        loader = self._loader()
        raw = _make_subtier_org(fhorgparenthistory=[])
        result = loader._normalize_org(raw)
        assert result["parent_org_id"] == 100123456

    def test_normalize_empty_raw(self):
        loader = self._loader()
        result = loader._normalize_org({})
        assert result["fh_org_id"] is None
        assert result["fh_org_name"] is None
        assert result["level"] is None

    def test_normalize_string_fhorgid_parsed(self):
        loader = self._loader()
        raw = _make_raw_org(fhorgid="100999999")
        result = loader._normalize_org(raw)
        assert result["fh_org_id"] == 100999999


# ===================================================================
# load_organizations tests
# ===================================================================

class TestLoadOrganizations:

    def test_load_single_org_inserted(self):
        mock_cd = MagicMock()
        mock_cd.get_existing_hashes.return_value = {}
        mock_cd.compute_hash.return_value = "newhash"
        mock_lm = MagicMock()

        with patch("etl.fedhier_loader.get_connection") as mock_gc, \
             patch("etl.fedhier_loader.fetch_existing_hashes", return_value={}), \
             patch("etl.staging_mixin.get_connection") as mock_stg_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1  # inserted
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn
            mock_stg_gc.return_value = mock_conn

            loader = FedHierLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            stats = loader.load_organizations([_make_raw_org()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_errored"] == 0


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestFedHierHashFields:

    def test_returns_copy(self):
        fields = FedHierLoader.get_hash_fields()
        assert fields == list(_ORG_HASH_FIELDS)
        fields.append("extra")
        assert "extra" not in _ORG_HASH_FIELDS


# ===================================================================
# Org type level mapping
# ===================================================================

class TestOrgTypeLevels:

    def test_levels_defined(self):
        assert _ORG_TYPE_LEVELS["Department/Ind. Agency"] == 1
        assert _ORG_TYPE_LEVELS["Sub-Tier"] == 2
        assert _ORG_TYPE_LEVELS["Office"] == 3
