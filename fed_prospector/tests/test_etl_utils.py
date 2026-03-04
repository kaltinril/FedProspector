"""Tests for etl.etl_utils -- shared date/decimal parsing, hashing, TSV escaping."""

import pytest
from unittest.mock import MagicMock, patch

from etl.etl_utils import parse_date, parse_decimal, fetch_existing_hashes, escape_tsv_value


# ===================================================================
# parse_date tests
# ===================================================================

class TestParseDate:

    @pytest.mark.parametrize("input_val,expected", [
        # ISO format
        ("2026-01-15", "2026-01-15"),
        # Compact YYYYMMDD
        ("20260115", "2026-01-15"),
        # US MM/DD/YYYY
        ("01/15/2026", "2026-01-15"),
        # Dash-US MM-DD-YYYY
        ("01-15-2026", "2026-01-15"),
        # ISO with time component (T stripped)
        ("2026-01-15T14:30:00", "2026-01-15"),
        # ISO with timezone
        ("2026-01-15T14:30:00-05:00", "2026-01-15"),
        # Empty string
        ("", None),
        # None
        (None, None),
        # Invalid string
        ("not-a-date", None),
        # Whitespace only
        ("   ", None),
        # Integer input (converted to str via str())
        (20260115, "2026-01-15"),
    ])
    def test_parse_date(self, input_val, expected):
        assert parse_date(input_val) == expected

    def test_parse_date_preserves_correct_day(self):
        """Verify no off-by-one or month/day swap."""
        assert parse_date("12/31/2025") == "2025-12-31"
        assert parse_date("2025-12-31") == "2025-12-31"


# ===================================================================
# parse_decimal tests
# ===================================================================

class TestParseDecimal:

    @pytest.mark.parametrize("input_val,expected", [
        # Normal decimal string
        ("150000.00", "150000.00"),
        # Comma-separated
        ("1,500,000.50", "1500000.50"),
        # Integer
        (42, "42"),
        # None
        (None, None),
        # Empty string
        ("", None),
        # Invalid
        ("not-a-number", None),
    ])
    def test_parse_decimal(self, input_val, expected):
        assert parse_decimal(input_val) == expected

    def test_parse_decimal_strips_whitespace(self):
        """Leading/trailing whitespace should not cause failure."""
        assert parse_decimal("  100.50  ") == "100.50"


# ===================================================================
# fetch_existing_hashes tests
# ===================================================================

class TestFetchExistingHashes:

    def test_returns_dict_of_hashes(self):
        """Happy path: rows returned are converted to {key: hash} dict."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("KEY-001", "hash_aaa"),
            ("KEY-002", "hash_bbb"),
        ]
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.etl_utils.get_connection", return_value=mock_conn):
            result = fetch_existing_hashes("opportunity", "notice_id")

        assert result == {"KEY-001": "hash_aaa", "KEY-002": "hash_bbb"}

    def test_empty_table_returns_empty_dict(self):
        """An empty table should return {}."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.etl_utils.get_connection", return_value=mock_conn):
            result = fetch_existing_hashes("opportunity", "notice_id")

        assert result == {}

    def test_connection_cleanup(self):
        """cursor and connection must be closed in the finally block."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.etl_utils.get_connection", return_value=mock_conn):
            fetch_existing_hashes("award", "award_id")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_connection_cleanup_on_error(self):
        """Even if the query fails, cursor and connection must be closed."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.etl_utils.get_connection", return_value=mock_conn):
            with pytest.raises(Exception, match="DB error"):
                fetch_existing_hashes("award", "award_id")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


# ===================================================================
# escape_tsv_value tests
# ===================================================================

class TestEscapeTsvValue:

    def test_tab_escaped(self):
        assert escape_tsv_value("hello\tworld") == "hello\\tworld"

    def test_newline_escaped(self):
        assert escape_tsv_value("line1\nline2") == "line1\\nline2"

    def test_backslash_escaped(self):
        assert escape_tsv_value("back\\slash") == "back\\\\slash"

    def test_none_returns_null_marker(self):
        assert escape_tsv_value(None) == "\\N"

    def test_integer_converted_to_string(self):
        assert escape_tsv_value(42) == "42"

    def test_carriage_return_escaped(self):
        assert escape_tsv_value("line1\rline2") == "line1\\rline2"

    def test_plain_string_unchanged(self):
        assert escape_tsv_value("hello world") == "hello world"

    def test_combined_special_chars(self):
        """All special chars in one string."""
        result = escape_tsv_value("a\\b\tc\nd\re")
        assert result == "a\\\\b\\tc\\nd\\re"
