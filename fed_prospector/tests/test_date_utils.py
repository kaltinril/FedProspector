"""Unit tests for utils/date_utils.py.

Tests cover:
- parse_yyyymmdd with YYYYMMDD, YYYY-MM-DD, MM/dd/yyyy formats
- Edge cases: None, empty, invalid dates
- format_sam_date formatting
"""

from datetime import date

import pytest

from utils.date_utils import parse_yyyymmdd, format_sam_date


# =========================================================================
# parse_yyyymmdd
# =========================================================================

class TestParseYyyymmdd:
    """Tests for parse_yyyymmdd."""

    # --- YYYYMMDD format (most common in SAM extracts) ---

    def test_yyyymmdd_valid(self):
        assert parse_yyyymmdd("20260115") == date(2026, 1, 15)

    def test_yyyymmdd_end_of_year(self):
        assert parse_yyyymmdd("20261231") == date(2026, 12, 31)

    def test_yyyymmdd_start_of_year(self):
        assert parse_yyyymmdd("20260101") == date(2026, 1, 1)

    def test_yyyymmdd_invalid_month_returns_none(self):
        assert parse_yyyymmdd("20261301") is None

    def test_yyyymmdd_invalid_day_returns_none(self):
        assert parse_yyyymmdd("20260132") is None

    def test_yyyymmdd_feb_29_leap_year(self):
        assert parse_yyyymmdd("20240229") == date(2024, 2, 29)

    def test_yyyymmdd_feb_29_non_leap_year_returns_none(self):
        assert parse_yyyymmdd("20250229") is None

    # --- YYYY-MM-DD format ---

    def test_iso_date_valid(self):
        assert parse_yyyymmdd("2026-01-15") == date(2026, 1, 15)

    def test_iso_date_with_extra_text_truncated(self):
        # parse_yyyymmdd takes first 10 chars
        assert parse_yyyymmdd("2026-01-15T12:00:00") == date(2026, 1, 15)

    # --- MM/dd/yyyy format ---

    def test_mmddyyyy_valid(self):
        assert parse_yyyymmdd("01/15/2026") == date(2026, 1, 15)

    def test_mmddyyyy_single_digit_month_not_matched(self):
        # The regex requires position [2] == '/', so single-digit months
        # like "1/15/2026" won't match this branch
        assert parse_yyyymmdd("1/15/2026") is None

    # --- Edge cases ---

    def test_none_returns_none(self):
        assert parse_yyyymmdd(None) is None

    def test_empty_string_returns_none(self):
        assert parse_yyyymmdd("") is None

    def test_whitespace_only_returns_none(self):
        assert parse_yyyymmdd("   ") is None

    def test_non_string_returns_none(self):
        assert parse_yyyymmdd(12345) is None

    def test_unrecognized_format_returns_none(self):
        assert parse_yyyymmdd("Jan 15, 2026") is None

    def test_too_short_returns_none(self):
        assert parse_yyyymmdd("2026") is None


# =========================================================================
# format_sam_date
# =========================================================================

class TestFormatSamDate:
    def test_formats_date_object(self):
        assert format_sam_date(date(2026, 1, 15)) == "01/15/2026"

    def test_string_passthrough(self):
        assert format_sam_date("01/15/2026") == "01/15/2026"

    def test_non_date_passthrough(self):
        assert format_sam_date(42) == 42
