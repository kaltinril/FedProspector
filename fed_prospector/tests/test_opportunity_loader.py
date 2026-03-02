"""Tests for etl.opportunity_loader -- normalisation, change detection, upsert logic."""

import pytest
from unittest.mock import MagicMock, patch

from etl.opportunity_loader import OpportunityLoader, _OPPORTUNITY_HASH_FIELDS, _str_or_none


# ---------------------------------------------------------------------------
# Sample API response data
# ---------------------------------------------------------------------------
def _make_raw_opportunity(**overrides):
    """Return a minimal raw API opportunity dict."""
    base = {
        "noticeId": "OPP-001",
        "title": "Test Opportunity",
        "solicitationNumber": "SOL-123",
        "fullParentPathName": "Dept of Testing.Sub Tier.Office Name",
        "fullParentPathCode": "DOT.ST.OFF",
        "postedDate": "2026-01-15",
        "responseDeadLine": "2026-02-15T14:30:00-05:00",
        "archiveDate": "2026-03-01",
        "type": "o",
        "baseType": "Presolicitation",
        "typeOfSetAside": "WOSB",
        "typeOfSetAsideDescription": "Women-Owned Small Business",
        "classificationCode": "D301",
        "naicsCode": "541511",
        "placeOfPerformance": {
            "state": {"code": "VA"},
            "country": {"code": "USA"},
            "zip": "22030",
            "city": {"name": "Fairfax"},
        },
        "active": "Yes",
        "award": {
            "number": "AWD-001",
            "date": "2026-02-01",
            "amount": "150000.00",
            "awardee": {"ueiSAM": "TESTUEISAM1", "name": "Awardee LLC"},
        },
        "description": "A test opportunity",
        "uiLink": "https://sam.gov/opp/OPP-001/view",
        "resourceLinks": ["https://example.com/attachment.pdf"],
    }
    base.update(overrides)
    return base


# ===================================================================
# _normalize_opportunity tests
# ===================================================================

class TestNormalizeOpportunity:

    def _loader(self):
        with patch("etl.opportunity_loader.get_connection"):
            return OpportunityLoader()

    def test_normalize_basic_fields(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        result = loader._normalize_opportunity(raw)

        assert result["notice_id"] == "OPP-001"
        assert result["title"] == "Test Opportunity"
        assert result["solicitation_number"] == "SOL-123"
        assert result["type"] == "o"
        assert result["base_type"] == "Presolicitation"
        assert result["set_aside_code"] == "WOSB"
        assert result["classification_code"] == "D301"
        assert result["naics_code"] == "541511"

    def test_normalize_department_hierarchy(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        result = loader._normalize_opportunity(raw)

        assert result["department_name"] == "Dept of Testing"
        assert result["sub_tier"] == "Sub Tier"
        assert result["office"] == "Office Name"
        assert result["contracting_office_id"] == "OFF"

    def test_normalize_two_segment_path(self):
        loader = self._loader()
        raw = _make_raw_opportunity(
            fullParentPathName="Department.Office",
            fullParentPathCode="DEPT.OFFC",
        )
        result = loader._normalize_opportunity(raw)

        assert result["department_name"] == "Department"
        assert result["sub_tier"] == "Office"
        assert result["office"] == "Office"
        assert result["contracting_office_id"] == "OFFC"

    def test_normalize_single_segment_path(self):
        loader = self._loader()
        raw = _make_raw_opportunity(
            fullParentPathName="OnlyDept",
            fullParentPathCode="OD",
        )
        result = loader._normalize_opportunity(raw)

        assert result["department_name"] == "OnlyDept"
        assert result["sub_tier"] is None
        assert result["office"] is None
        assert result["contracting_office_id"] == "OD"

    def test_normalize_empty_path(self):
        loader = self._loader()
        raw = _make_raw_opportunity(fullParentPathName="", fullParentPathCode="")
        result = loader._normalize_opportunity(raw)

        assert result["department_name"] is None
        assert result["sub_tier"] is None
        assert result["office"] is None
        assert result["contracting_office_id"] is None

    def test_normalize_place_of_performance(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        result = loader._normalize_opportunity(raw)

        assert result["pop_state"] == "VA"
        assert result["pop_country"] == "USA"
        assert result["pop_zip"] == "22030"
        assert result["pop_city"] == "Fairfax"

    def test_normalize_pop_missing(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        raw.pop("placeOfPerformance")
        result = loader._normalize_opportunity(raw)

        assert result["pop_state"] is None
        assert result["pop_country"] is None

    def test_normalize_active_yes_to_y(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity(active="Yes"))
        assert result["active"] == "Y"

    def test_normalize_active_no_to_n(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity(active="No"))
        assert result["active"] == "N"

    def test_normalize_active_other_value(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity(active="true"))
        assert result["active"] == "T"

    def test_normalize_active_none(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity(active=None))
        assert result["active"] is None

    def test_normalize_award_fields(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity())

        assert result["award_number"] == "AWD-001"
        assert result["award_date"] == "2026-02-01"
        assert result["award_amount"] == "150000.00"
        assert result["awardee_uei"] == "TESTUEISAM1"
        assert result["awardee_name"] == "Awardee LLC"

    def test_normalize_award_missing(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        raw.pop("award")
        result = loader._normalize_opportunity(raw)

        assert result["award_number"] is None
        assert result["awardee_uei"] is None

    def test_normalize_resource_links_json(self):
        loader = self._loader()
        result = loader._normalize_opportunity(_make_raw_opportunity())
        import json
        assert json.loads(result["resource_links"]) == ["https://example.com/attachment.pdf"]

    def test_normalize_resource_links_none(self):
        loader = self._loader()
        raw = _make_raw_opportunity()
        raw.pop("resourceLinks")
        result = loader._normalize_opportunity(raw)
        assert result["resource_links"] is None


# ===================================================================
# Date parsing tests
# ===================================================================

class TestParseDateFormats:

    def _loader(self):
        with patch("etl.opportunity_loader.get_connection"):
            return OpportunityLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("2026-01-15", "2026-01-15"),
        ("20260115", "2026-01-15"),
        ("01/15/2026", "2026-01-15"),
        ("2026-01-15T14:30:00-05:00", "2026-01-15"),
        (None, None),
        ("", None),
        ("  ", None),
    ])
    def test_parse_date(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_date(input_val) == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("2026-01-15T14:30:00-05:00", "2026-01-15 14:30:00"),
        ("2026-01-15T14:30:00", "2026-01-15 14:30:00"),
        ("2026-01-15 14:30:00", "2026-01-15 14:30:00"),
        ("01/15/2026 02:30 PM", "2026-01-15 14:30:00"),
        (None, None),
        ("", None),
    ])
    def test_parse_datetime(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_datetime(input_val) == expected

    def test_parse_datetime_date_only_gets_midnight(self):
        loader = self._loader()
        assert loader._parse_datetime("2026-01-15") == "2026-01-15 00:00:00"


# ===================================================================
# Decimal parsing tests
# ===================================================================

class TestParseDecimal:

    def _loader(self):
        with patch("etl.opportunity_loader.get_connection"):
            return OpportunityLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("150000.00", "150000.00"),
        (150000, "150000"),
        (150000.50, "150000.5"),
        (None, None),
        ("not-a-number", None),
    ])
    def test_parse_decimal(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_decimal(input_val) == expected


# ===================================================================
# _safe_get tests
# ===================================================================

class TestSafeGet:

    def _loader(self):
        with patch("etl.opportunity_loader.get_connection"):
            return OpportunityLoader()

    def test_safe_get_single_key(self):
        loader = self._loader()
        assert loader._safe_get({"a": 1}, "a") == 1

    def test_safe_get_nested(self):
        loader = self._loader()
        data = {"a": {"b": {"c": "deep"}}}
        assert loader._safe_get(data, "a", "b", "c") == "deep"

    def test_safe_get_missing_key_returns_default(self):
        loader = self._loader()
        assert loader._safe_get({"a": 1}, "b") is None
        assert loader._safe_get({"a": 1}, "b", default="X") == "X"

    def test_safe_get_none_intermediate(self):
        loader = self._loader()
        assert loader._safe_get({"a": None}, "a", "b") is None


# ===================================================================
# Upsert outcome tests (mock cursor.rowcount)
# ===================================================================

class TestUpsertOpportunity:

    def _loader(self):
        with patch("etl.opportunity_loader.get_connection"):
            return OpportunityLoader()

    def test_upsert_inserted(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 1
        opp_data = {"notice_id": "OPP-001", "record_hash": "h"}
        assert loader._upsert_opportunity(cursor, opp_data, load_id=10) == "inserted"

    def test_upsert_updated(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 2
        opp_data = {"notice_id": "OPP-001", "record_hash": "h"}
        assert loader._upsert_opportunity(cursor, opp_data, load_id=10) == "updated"

    def test_upsert_unchanged(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 0
        opp_data = {"notice_id": "OPP-001", "record_hash": "h"}
        assert loader._upsert_opportunity(cursor, opp_data, load_id=10) == "unchanged"


# ===================================================================
# load_opportunities integration test (all DB mocked)
# ===================================================================

class TestLoadOpportunities:

    def test_new_record_is_inserted(self, mock_change_detector, mock_load_manager):
        mock_change_detector.compute_hash.return_value = "newhash"

        with patch("etl.opportunity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1  # inserted
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = OpportunityLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            raw_records = [_make_raw_opportunity()]
            stats = loader.load_opportunities(raw_records, load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_updated"] == 0
        assert stats["records_errored"] == 0

    def test_unchanged_record_is_skipped(self, mock_change_detector, mock_load_manager):
        mock_change_detector.get_existing_hashes.return_value = {"OPP-001": "samehash"}
        mock_change_detector.compute_hash.return_value = "samehash"

        with patch("etl.opportunity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = OpportunityLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            stats = loader.load_opportunities([_make_raw_opportunity()], load_id=1)

        assert stats["records_unchanged"] == 1
        assert stats["records_inserted"] == 0

    def test_error_record_increments_errored(self, mock_change_detector, mock_load_manager):
        """A record missing noticeId should be counted as errored."""
        mock_change_detector.compute_hash.return_value = "h"

        with patch("etl.opportunity_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = OpportunityLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            bad_record = {"title": "No notice_id here"}
            stats = loader.load_opportunities([bad_record], load_id=1)

        assert stats["records_errored"] == 1
        mock_load_manager.log_record_error.assert_called_once()


# ===================================================================
# Module-level helper
# ===================================================================

class TestStrOrNone:

    def test_none_returns_none(self):
        assert _str_or_none(None) is None

    def test_string_returns_string(self):
        assert _str_or_none("hello") == "hello"

    def test_int_returns_string(self):
        assert _str_or_none(42) == "42"


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestGetHashFields:

    def test_returns_list_copy(self):
        fields = OpportunityLoader.get_hash_fields()
        assert isinstance(fields, list)
        assert fields == list(_OPPORTUNITY_HASH_FIELDS)
        # Mutating the returned list should not affect the original
        fields.append("extra")
        assert "extra" not in _OPPORTUNITY_HASH_FIELDS
