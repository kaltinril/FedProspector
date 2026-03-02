"""Tests for etl.usaspending_loader -- normalisation, enrichment, upsert logic."""

import pytest
from unittest.mock import MagicMock, patch

from etl.usaspending_loader import USASpendingLoader, _AWARD_HASH_FIELDS


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_award(**overrides):
    """Return a minimal raw USASpending search result dict."""
    base = {
        "generated_internal_id": "CONT_AWD_GS35F0001_4700",
        "generated_unique_award_id": None,  # None in search results
        "Award ID": "GS-35F-0001",
        "FAIN": None,
        "URI": None,
        "Contract Award Type": "D",
        "Description": "IT Support Services",
        "Recipient Name": "Test Corp",
        "Recipient UEI": "TESTAWARDEE1",
        "Award Amount": "500000.00",
        "Base and All Options Value": "750000.00",
        "Start Date": "2026-01-15",
        "End Date": "2027-01-14",
        "Last Date to Order": "2026-12-31",
        "Awarding Agency": "General Services Administration",
        "Awarding Sub Agency": "PBS",
        "Funding Agency": "GSA",
        "NAICS Code": "541511",
        "NAICS Description": "Custom Computer Programming Services",
        "PSC Code": "D301",
        "Type of Set Aside": "WOSB",
        "Place of Performance State Code": "VA",
        "Place of Performance Country Code": "USA",
        "Place of Performance Zip5": "22030",
        "Place of Performance City Code": "26000",
    }
    base.update(overrides)
    return base


# ===================================================================
# _normalize_award tests
# ===================================================================

class TestNormalizeAward:

    def _loader(self):
        with patch("etl.usaspending_loader.get_connection"):
            return USASpendingLoader()

    def test_normalize_basic_fields(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())

        assert result["piid"] == "GS-35F-0001"
        assert result["award_type"] == "D"
        assert result["recipient_name"] == "Test Corp"
        assert result["recipient_uei"] == "TESTAWARDEE1"

    def test_normalize_falls_back_to_internal_id(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["generated_unique_award_id"] == "CONT_AWD_GS35F0001_4700"

    def test_normalize_prefers_explicit_unique_id(self):
        loader = self._loader()
        raw = _make_raw_award(generated_unique_award_id="EXPLICIT_ID")
        result = loader._normalize_award(raw)
        assert result["generated_unique_award_id"] == "EXPLICIT_ID"

    def test_normalize_dollars(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["total_obligation"] == "500000.00"
        assert result["base_and_all_options_value"] == "750000.00"

    def test_normalize_dates(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["start_date"] == "2026-01-15"
        assert result["end_date"] == "2027-01-14"

    def test_normalize_pop_fields(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["pop_state"] == "VA"
        assert result["pop_country"] == "USA"
        assert result["pop_zip"] == "22030"

    def test_normalize_none_only_detail_fields(self):
        loader = self._loader()
        result = loader._normalize_award(_make_raw_award())
        assert result["recipient_parent_name"] is None
        assert result["recipient_parent_uei"] is None
        assert result["type_of_set_aside_description"] is None
        assert result["solicitation_identifier"] is None


# ===================================================================
# enrich_from_detail tests
# ===================================================================

class TestEnrichFromDetail:

    def _loader(self):
        with patch("etl.usaspending_loader.get_connection"):
            return USASpendingLoader()

    def test_enrich_recipient_parent(self):
        loader = self._loader()
        award = {"recipient_parent_name": None, "recipient_parent_uei": None}
        detail = {
            "recipient": {
                "parent_recipient_name": "Parent Corp",
                "parent_recipient_uei": "PARENTUEI123",
            },
        }
        result = loader.enrich_from_detail(award, detail)
        assert result["recipient_parent_name"] == "Parent Corp"
        assert result["recipient_parent_uei"] == "PARENTUEI123"

    def test_enrich_naics_from_hierarchy(self):
        loader = self._loader()
        award = {"naics_code": None, "naics_description": None}
        detail = {
            "naics_hierarchy": {
                "base_code": {"code": "541511", "description": "Custom Programming"},
            },
        }
        result = loader.enrich_from_detail(award, detail)
        assert result["naics_code"] == "541511"
        assert result["naics_description"] == "Custom Programming"

    def test_enrich_set_aside(self):
        loader = self._loader()
        award = {"type_of_set_aside": None, "type_of_set_aside_description": None}
        detail = {
            "latest_transaction_contract_data": {
                "type_of_set_aside": "WOSB",
                "type_of_set_aside_description": "Women-Owned Small Business",
                "solicitation_identifier": "SOL-123",
            },
        }
        result = loader.enrich_from_detail(award, detail)
        assert result["type_of_set_aside"] == "WOSB"
        assert result["type_of_set_aside_description"] == "Women-Owned Small Business"

    def test_enrich_pop(self):
        loader = self._loader()
        award = {"pop_state": None, "pop_country": None, "pop_zip": None, "pop_city": None}
        detail = {
            "place_of_performance": {
                "state_code": "MD",
                "location_country_code": "USA",
                "zip5": "20850",
                "city_name": "Rockville",
            },
        }
        result = loader.enrich_from_detail(award, detail)
        assert result["pop_state"] == "MD"
        assert result["pop_city"] == "Rockville"

    def test_enrich_none_detail_returns_unchanged(self):
        loader = self._loader()
        award = {"pop_state": "VA"}
        result = loader.enrich_from_detail(award, None)
        assert result["pop_state"] == "VA"

    def test_enrich_empty_detail_returns_unchanged(self):
        loader = self._loader()
        award = {"pop_state": "VA"}
        result = loader.enrich_from_detail(award, {})
        assert result["pop_state"] == "VA"


# ===================================================================
# Date and decimal parsing
# ===================================================================

class TestUSASpendingParseDate:

    def _loader(self):
        with patch("etl.usaspending_loader.get_connection"):
            return USASpendingLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("2026-01-15", "2026-01-15"),
        ("01/15/2026", "2026-01-15"),
        (None, None),
        ("", None),
    ])
    def test_parse_date(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_date(input_val) == expected


class TestUSASpendingParseDecimal:

    def _loader(self):
        with patch("etl.usaspending_loader.get_connection"):
            return USASpendingLoader()

    @pytest.mark.parametrize("input_val,expected", [
        ("500000.00", "500000.00"),
        (-25000, "-25000"),
        (0, "0"),
        (None, None),
        ("not_a_number", None),
    ])
    def test_parse_decimal(self, input_val, expected):
        loader = self._loader()
        assert loader._parse_decimal(input_val) == expected


# ===================================================================
# Upsert outcome tests
# ===================================================================

class TestUSASpendingUpsert:

    def _loader(self):
        with patch("etl.usaspending_loader.get_connection"):
            return USASpendingLoader()

    def test_upsert_inserted(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 1
        assert loader._upsert_award(cursor, {"generated_unique_award_id": "ID1"}, 1) == "inserted"

    def test_upsert_updated(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 2
        assert loader._upsert_award(cursor, {"generated_unique_award_id": "ID1"}, 1) == "updated"

    def test_upsert_unchanged(self):
        loader = self._loader()
        cursor = MagicMock()
        cursor.rowcount = 0
        assert loader._upsert_award(cursor, {"generated_unique_award_id": "ID1"}, 1) == "unchanged"


# ===================================================================
# load_awards integration test
# ===================================================================

class TestLoadAwards:

    def test_new_award_inserted(self, mock_change_detector, mock_load_manager):
        mock_change_detector.compute_hash.return_value = "newhash"

        with patch("etl.usaspending_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = USASpendingLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            stats = loader.load_awards([_make_raw_award()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1

    def test_missing_award_id_errors(self, mock_change_detector, mock_load_manager):
        with patch("etl.usaspending_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = USASpendingLoader(
                change_detector=mock_change_detector,
                load_manager=mock_load_manager,
            )
            bad_record = {}  # no IDs at all
            stats = loader.load_awards([bad_record], load_id=1)

        assert stats["records_errored"] == 1


# ===================================================================
# Hash fields accessor
# ===================================================================

class TestUSASpendingGetHashFields:

    def test_returns_copy(self):
        fields = USASpendingLoader.get_hash_fields()
        assert fields == list(_AWARD_HASH_FIELDS)
