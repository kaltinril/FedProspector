"""Tests for etl.exclusions_loader -- normalisation, composite keys, upsert."""

import pytest
from unittest.mock import MagicMock, patch

from etl.exclusions_loader import ExclusionsLoader, _make_exclusion_key, _EXCLUSION_HASH_FIELDS


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_exclusion(**overrides):
    """Return a minimal raw SAM.gov Exclusions API response dict."""
    base = {
        "exclusionDetails": {
            "exclusionType": "Ineligible",
            "exclusionProgram": "Reciprocal",
            "excludingAgencyCode": "4700",
            "excludingAgencyName": "General Services Administration",
        },
        "exclusionIdentification": {
            "ueiSAM": "EXCL123UEI45",
            "cageCode": "9XYZ1",
            "entityName": "Excluded Corp",
            "firstName": None,
            "middleName": None,
            "lastName": None,
            "suffix": None,
            "prefix": None,
        },
        "exclusionActions": {
            "listOfActions": [
                {
                    "activateDate": "2025-06-15",
                    "terminationDate": "2027-06-15",
                }
            ],
        },
        "exclusionOtherInformation": {
            "additionalComments": "Test exclusion comment",
        },
    }
    base.update(overrides)
    return base


# ===================================================================
# _make_exclusion_key tests
# ===================================================================

class TestMakeExclusionKey:

    def test_with_uei(self):
        record = {
            "uei": "EXCL123UEI45",
            "activation_date": "2025-06-15",
            "exclusion_type": "Ineligible",
        }
        assert _make_exclusion_key(record) == "EXCL123UEI45|2025-06-15|Ineligible"

    def test_with_entity_name_fallback(self):
        record = {
            "uei": None,
            "entity_name": "Bad Actor Inc",
            "activation_date": "2025-01-01",
            "exclusion_type": "Debarred",
        }
        assert _make_exclusion_key(record) == "Bad Actor Inc|2025-01-01|Debarred"

    def test_all_empty(self):
        record = {}
        assert _make_exclusion_key(record) == "||"


# ===================================================================
# _normalize_exclusion tests
# ===================================================================

class TestNormalizeExclusion:

    def _loader(self):
        with patch("etl.exclusions_loader.get_connection"), \
             patch("etl.staging_mixin.get_connection"):
            return ExclusionsLoader()

    def test_normalize_basic_fields(self):
        loader = self._loader()
        result = loader._normalize_exclusion(_make_raw_exclusion())

        assert result["uei"] == "EXCL123UEI45"
        assert result["cage_code"] == "9XYZ1"
        assert result["entity_name"] == "Excluded Corp"
        assert result["exclusion_type"] == "Ineligible"
        assert result["exclusion_program"] == "Reciprocal"
        assert result["excluding_agency_code"] == "4700"
        assert result["excluding_agency_name"] == "General Services Administration"
        assert result["activation_date"] == "2025-06-15"
        assert result["termination_date"] == "2027-06-15"
        assert result["additional_comments"] == "Test exclusion comment"

    def test_normalize_individual_exclusion(self):
        """Entity exclusion for an individual (has name parts)."""
        loader = self._loader()
        raw = _make_raw_exclusion()
        raw["exclusionIdentification"]["ueiSAM"] = None
        raw["exclusionIdentification"]["entityName"] = None
        raw["exclusionIdentification"]["firstName"] = "John"
        raw["exclusionIdentification"]["lastName"] = "Doe"
        raw["exclusionIdentification"]["prefix"] = "Mr"
        result = loader._normalize_exclusion(raw)

        assert result["uei"] is None
        assert result["entity_name"] is None
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["prefix"] == "Mr"

    def test_normalize_empty_entity_name_becomes_none(self):
        loader = self._loader()
        raw = _make_raw_exclusion()
        raw["exclusionIdentification"]["entityName"] = "  "
        result = loader._normalize_exclusion(raw)
        assert result["entity_name"] is None

    def test_normalize_empty_actions_list(self):
        """No action entries should yield None dates."""
        loader = self._loader()
        raw = _make_raw_exclusion()
        raw["exclusionActions"]["listOfActions"] = []
        result = loader._normalize_exclusion(raw)
        assert result["activation_date"] is None
        assert result["termination_date"] is None

    def test_normalize_missing_blocks(self):
        """Empty dict should not crash."""
        loader = self._loader()
        result = loader._normalize_exclusion({})
        assert result["uei"] is None
        assert result["exclusion_type"] is None
        assert result["activation_date"] is None


# ===================================================================
# load_exclusions tests
# ===================================================================

class TestLoadExclusions:

    def test_load_single_exclusion_inserted(self):
        mock_cd = MagicMock()
        mock_cd.compute_hash.return_value = "newhash"
        mock_lm = MagicMock()

        with patch("etl.exclusions_loader.get_connection") as mock_gc, \
             patch("etl.staging_mixin.get_connection") as mock_stg_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            # For hash lookup query
            mock_cursor.fetchall.return_value = []
            # For upsert: no existing record found, then insert
            mock_cursor.fetchone.return_value = None
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn
            mock_stg_gc.return_value = mock_conn

            loader = ExclusionsLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            stats = loader.load_exclusions([_make_raw_exclusion()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_errored"] == 0


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestExclusionsHashFields:

    def test_returns_copy(self):
        fields = ExclusionsLoader.get_hash_fields()
        assert fields == list(_EXCLUSION_HASH_FIELDS)
        fields.append("extra")
        assert "extra" not in _EXCLUSION_HASH_FIELDS
