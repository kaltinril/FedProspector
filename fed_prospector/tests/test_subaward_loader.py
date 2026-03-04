"""Tests for etl.subaward_loader -- normalisation, composite keys, upsert."""

import pytest
from unittest.mock import MagicMock, patch

from etl.subaward_loader import SubawardLoader, _make_subaward_key, _SUBAWARD_HASH_FIELDS


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_subaward(**overrides):
    """Return a minimal raw SAM.gov Subaward API response dict."""
    base = {
        "piid": "GS-35F-0001",
        "agencyId": "4700",
        "primeEntityUei": "PRIMEUEI12345",
        "primeEntityName": "Prime Contractor Corp",
        "subEntityUei": "SUBUEI123456",
        "subEntityLegalBusinessName": "Small Sub LLC",
        "subAwardAmount": "50000.00",
        "subAwardDate": "2026-01-15",
        "subAwardDescription": "IT Sub-contract",
        "primeNaics": "541512",
        "primeOrganizationInfo": {
            "contractingAgency": {
                "code": "4700",
                "name": "GSA",
            },
        },
        "entityPhysicalAddress": {
            "state": {"code": "VA"},
            "country": {"code": "USA"},
            "zip": "22201",
        },
        "subBusinessType": [
            {"code": "8W"},
            {"code": "27"},
        ],
        "recoveryModelQ1": "No",
        "recoveryModelQ2": "No",
    }
    base.update(overrides)
    return base


# ===================================================================
# _make_subaward_key tests
# ===================================================================

class TestMakeSubawardKey:

    def test_normal_key(self):
        record = {
            "prime_piid": "GS-35F-0001",
            "sub_uei": "SUBUEI123456",
            "sub_date": "2026-01-15",
        }
        assert _make_subaward_key(record) == "GS-35F-0001|SUBUEI123456|2026-01-15"

    def test_missing_fields(self):
        record = {}
        assert _make_subaward_key(record) == "||"

    def test_none_values(self):
        record = {"prime_piid": None, "sub_uei": None, "sub_date": None}
        assert _make_subaward_key(record) == "||"


# ===================================================================
# _normalize_subaward tests
# ===================================================================

class TestNormalizeSubaward:

    def _loader(self):
        with patch("etl.subaward_loader.get_connection"), \
             patch("etl.staging_mixin.get_connection"):
            return SubawardLoader()

    def test_normalize_basic_fields(self):
        loader = self._loader()
        result = loader._normalize_subaward(_make_raw_subaward())

        assert result["prime_piid"] == "GS-35F-0001"
        assert result["prime_agency_id"] == "4700"
        assert result["prime_agency_name"] == "GSA"
        assert result["prime_uei"] == "PRIMEUEI12345"
        assert result["prime_name"] == "Prime Contractor Corp"
        assert result["sub_uei"] == "SUBUEI123456"
        assert result["sub_name"] == "Small Sub LLC"
        assert result["sub_amount"] == "50000.00"
        assert result["sub_date"] == "2026-01-15"
        assert result["sub_description"] == "IT Sub-contract"
        assert result["naics_code"] == "541512"
        assert result["psc_code"] is None  # Not in API

    def test_normalize_pop_fields(self):
        loader = self._loader()
        result = loader._normalize_subaward(_make_raw_subaward())

        assert result["pop_state"] == "VA"
        assert result["pop_country"] == "USA"
        assert result["pop_zip"] == "22201"

    def test_normalize_business_types_comma_separated(self):
        loader = self._loader()
        result = loader._normalize_subaward(_make_raw_subaward())
        assert result["sub_business_type"] == "8W, 27"

    def test_normalize_empty_business_types(self):
        loader = self._loader()
        result = loader._normalize_subaward(_make_raw_subaward(subBusinessType=[]))
        assert result["sub_business_type"] is None

    def test_normalize_missing_org_info(self):
        loader = self._loader()
        raw = _make_raw_subaward()
        raw["primeOrganizationInfo"] = None
        result = loader._normalize_subaward(raw)
        assert result["prime_agency_name"] is None
        # Falls back to agencyId
        assert result["prime_agency_id"] == "4700"

    def test_normalize_empty_raw(self):
        loader = self._loader()
        result = loader._normalize_subaward({})
        assert result["prime_piid"] is None
        assert result["sub_uei"] is None
        assert result["sub_amount"] is None

    def test_normalize_recovery_model_fields(self):
        loader = self._loader()
        result = loader._normalize_subaward(_make_raw_subaward())
        assert result["recovery_model_q1"] == "No"
        assert result["recovery_model_q2"] == "No"


# ===================================================================
# load_subawards tests
# ===================================================================

class TestLoadSubawards:

    def test_load_single_subaward_inserted(self):
        mock_cd = MagicMock()
        mock_cd.compute_hash.return_value = "newhash"
        mock_lm = MagicMock()

        with patch("etl.subaward_loader.get_connection") as mock_gc, \
             patch("etl.staging_mixin.get_connection") as mock_stg_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            # Hash lookup returns no existing records
            mock_cursor.fetchall.return_value = []
            # Upsert: no existing found, insert
            mock_cursor.fetchone.return_value = None
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn
            mock_stg_gc.return_value = mock_conn

            loader = SubawardLoader(
                change_detector=mock_cd,
                load_manager=mock_lm,
            )
            stats = loader.load_subawards([_make_raw_subaward()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_errored"] == 0


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestSubawardHashFields:

    def test_returns_copy(self):
        fields = SubawardLoader.get_hash_fields()
        assert fields == list(_SUBAWARD_HASH_FIELDS)
        fields.append("extra")
        assert "extra" not in _SUBAWARD_HASH_FIELDS
