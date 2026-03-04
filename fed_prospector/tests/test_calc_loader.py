"""Tests for etl.calc_loader -- normalisation, batch insert, full refresh."""

import pytest
from unittest.mock import MagicMock, patch

from etl.calc_loader import CalcLoader, _RATE_COLUMNS, _API_FIELD_MAP


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------
def _make_raw_rate(**overrides):
    """Return a minimal raw CALC+ API rate dict."""
    base = {
        "labor_category": "Senior Developer",
        "education_level": "Bachelors",
        "min_years_experience": 5,
        "current_price": "130.00",
        "next_year_price": "135.00",
        "second_year_price": "140.00",
        "schedule": "IT Schedule 70",
        "vendor_name": "Test Contractor Inc",
        "sin": "54151S",
        "business_size": "S",
        "security_clearance": "None",
        "worksite": "Customer",
        "contract_start": "2025-01-01",
        "contract_end": "2027-12-31",
    }
    base.update(overrides)
    return base


def _make_loader(load_manager=None):
    """Create a CalcLoader with DB mocked."""
    with patch("etl.calc_loader.get_connection"):
        return CalcLoader(load_manager=load_manager)


# ===================================================================
# _normalize_rate tests
# ===================================================================

class TestNormalizeRate:

    def test_normalize_basic_fields(self):
        loader = _make_loader()
        result = loader._normalize_rate(_make_raw_rate())

        assert result["labor_category"] == "Senior Developer"
        assert result["education_level"] == "Bachelors"
        assert result["min_years_experience"] == 5
        assert result["contractor_name"] == "Test Contractor Inc"
        assert result["business_size"] == "S"
        assert result["worksite"] == "Customer"

    def test_normalize_decimal_parsing(self):
        loader = _make_loader()
        result = loader._normalize_rate(_make_raw_rate())

        assert result["current_price"] == "130.00"
        assert result["next_year_price"] == "135.00"
        assert result["second_year_price"] == "140.00"

    def test_normalize_date_parsing(self):
        loader = _make_loader()
        result = loader._normalize_rate(_make_raw_rate())

        assert result["contract_start"] == "2025-01-01"
        assert result["contract_end"] == "2027-12-31"

    def test_normalize_vendor_name_maps_to_contractor(self):
        """API uses 'vendor_name' but DB column is 'contractor_name'."""
        loader = _make_loader()
        result = loader._normalize_rate(_make_raw_rate(vendor_name="ACME Corp"))
        assert result["contractor_name"] == "ACME Corp"

    def test_normalize_none_values(self):
        loader = _make_loader()
        raw = {k: None for k in _API_FIELD_MAP}
        result = loader._normalize_rate(raw)

        assert result["labor_category"] is None
        assert result["min_years_experience"] is None
        assert result["contract_start"] is None

    def test_normalize_boolean_security_clearance_coerced(self):
        """API can return booleans for string fields."""
        loader = _make_loader()
        result = loader._normalize_rate(_make_raw_rate(security_clearance=False))
        assert result["security_clearance"] == "False"

    def test_normalize_truncates_long_values(self):
        loader = _make_loader()
        result = loader._normalize_rate(
            _make_raw_rate(labor_category="X" * 300)
        )
        assert len(result["labor_category"]) == 200

    def test_normalize_sin_newlines_collapsed(self):
        loader = _make_loader()
        result = loader._normalize_rate(
            _make_raw_rate(sin="541611,541930,\n611430")
        )
        assert "\n" not in result["sin"]
        assert result["sin"] == "541611,541930,611430"


# ===================================================================
# _parse_int tests
# ===================================================================

class TestParseInt:

    @pytest.mark.parametrize("value,expected", [
        (5, 5),
        ("5", 5),
        ("5.7", 5),
        (None, None),
        ("", None),
        ("N/A", None),
        ("none", None),
    ])
    def test_parse_int(self, value, expected):
        assert CalcLoader._parse_int(value) == expected


# ===================================================================
# load_from_api tests
# ===================================================================

class TestLoadFromApi:

    def test_load_single_record(self):
        """Verify a single record is normalised and inserted."""
        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1

        with patch("etl.calc_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = CalcLoader(load_manager=mock_lm)
            stats = loader.load_from_api([_make_raw_rate()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_inserted"] == 1
        assert stats["records_errored"] == 0
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called()

    def test_load_normalisation_error_counted(self):
        """A record that fails normalization should be counted as errored."""
        mock_lm = MagicMock()

        with patch("etl.calc_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = CalcLoader(load_manager=mock_lm)
            # Patch _normalize_rate to raise
            with patch.object(loader, "_normalize_rate", side_effect=ValueError("bad")):
                stats = loader.load_from_api([_make_raw_rate()], load_id=1)

        assert stats["records_read"] == 1
        assert stats["records_errored"] == 1
        assert stats["records_inserted"] == 0


# ===================================================================
# full_refresh tests
# ===================================================================

class TestFullRefresh:

    def test_full_refresh_truncates_then_loads(self):
        """Verify full_refresh calls truncate then load_from_api."""
        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 10
        mock_client = MagicMock()
        mock_client.get_all_rates.return_value = iter([_make_raw_rate()])

        with patch("etl.calc_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader = CalcLoader(load_manager=mock_lm)
            stats = loader.full_refresh(mock_client)

        # Verify truncate was called
        truncate_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "TRUNCATE" in str(c)
        ]
        assert len(truncate_calls) >= 1

        mock_lm.complete_load.assert_called_once()
        assert stats["records_read"] == 1
