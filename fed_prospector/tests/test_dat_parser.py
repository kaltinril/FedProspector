"""Tests for etl.dat_parser -- DAT file parsing, field extraction, multi-value fields."""

import pytest
from unittest.mock import patch

from etl.dat_parser import (
    get_dat_record_count,
    parse_dat_file,
    _parse_dat_line,
    _field_or_none,
    _norm_date,
    _build_address,
    _parse_naics_string,
    _parse_naics_exception_string,
    _parse_psc_string,
    _parse_business_type_string,
    _parse_sba_string,
    _parse_disaster_string,
    _extract_poc,
    _merge_extra_cage_codes,
    EXPECTED_FIELD_COUNT,
    F_UEI_SAM,
    F_CAGE_CODE,
    F_LEGAL_BUSINESS_NAME,
    F_PRIMARY_NAICS,
    F_REG_STATUS,
)


# ---------------------------------------------------------------------------
# Helper: build a mock 142-field line
# ---------------------------------------------------------------------------
def _make_dat_fields(uei="TESTUEI001234", cage="A1B2C", legal_name="Test Corp",
                     primary_naics="541511", reg_status="A", **overrides):
    """Build a list of 142 pipe-delimited field values for a single DAT line."""
    fields = [""] * EXPECTED_FIELD_COUNT
    fields[F_UEI_SAM] = uei
    fields[F_CAGE_CODE] = cage
    fields[F_LEGAL_BUSINESS_NAME] = legal_name
    fields[F_PRIMARY_NAICS] = primary_naics
    fields[F_REG_STATUS] = reg_status
    fields[141] = "!end"

    for idx, val in overrides.items():
        fields[int(idx)] = val

    return fields


def _fields_to_line(fields):
    """Join field list back into a pipe-delimited line."""
    return "|".join(fields)


# ===================================================================
# _field_or_none tests
# ===================================================================

class TestFieldOrNone:

    def test_normal_value(self):
        assert _field_or_none("hello") == "hello"

    def test_strips_whitespace(self):
        assert _field_or_none("  hello  ") == "hello"

    def test_empty_string_returns_none(self):
        assert _field_or_none("") is None

    def test_whitespace_only_returns_none(self):
        assert _field_or_none("   ") is None

    def test_none_returns_none(self):
        assert _field_or_none(None) is None


# ===================================================================
# _norm_date tests
# ===================================================================

class TestNormDate:

    @pytest.mark.parametrize("input_val,expected", [
        ("20260201", "2026-02-01"),
        ("20251231", "2025-12-31"),
        ("", None),
        (None, None),
        ("   ", None),
        ("2026-02-01", None),   # Not 8-digit, returns None
        ("abcdefgh", None),     # Not digits
        ("202601", None),       # Only 6 digits
    ])
    def test_norm_date(self, input_val, expected):
        assert _norm_date(input_val) == expected


# ===================================================================
# _build_address tests
# ===================================================================

class TestBuildAddress:

    def test_full_physical_address(self):
        fields = _make_dat_fields()
        fields[15] = "123 Main St"
        fields[16] = "Suite 100"
        fields[17] = "Springfield"
        fields[18] = "VA"
        fields[19] = "22150"
        fields[20] = "1234"
        fields[21] = "USA"
        fields[22] = "11"

        addr = _build_address("TESTUEI", "PHYSICAL", fields,
                              15, 16, 17, 18, 19, 20, 21,
                              congressional_district_idx=22)

        assert addr is not None
        assert addr["address_type"] == "PHYSICAL"
        assert addr["address_line_1"] == "123 Main St"
        assert addr["city"] == "Springfield"
        assert addr["state_or_province"] == "VA"
        assert addr["congressional_district"] == "11"

    def test_empty_address_returns_none(self):
        fields = _make_dat_fields()
        addr = _build_address("TESTUEI", "MAILING", fields,
                              39, 40, 41, 45, 42, 43, 44)
        assert addr is None

    def test_partial_address_with_city_only(self):
        fields = _make_dat_fields()
        fields[17] = "Somewhere"
        addr = _build_address("TESTUEI", "PHYSICAL", fields,
                              15, 16, 17, 18, 19, 20, 21)
        assert addr is not None
        assert addr["city"] == "Somewhere"


# ===================================================================
# Multi-value field parser tests
# ===================================================================

class TestParseNaicsString:

    def test_normal_naics(self):
        result = _parse_naics_string("541511Y~541512N~236220E", "541511")
        assert len(result) == 3
        assert result[0]["naics_code"] == "541511"
        assert result[0]["is_primary"] == "Y"
        assert result[0]["sba_small_business"] == "Y"
        assert result[1]["naics_code"] == "541512"
        assert result[1]["is_primary"] == "N"

    def test_empty_string(self):
        assert _parse_naics_string("", "541511") == []

    def test_none_value(self):
        assert _parse_naics_string(None, "541511") == []

    def test_single_char_entry_skipped(self):
        result = _parse_naics_string("Y", "541511")
        assert result == []

    def test_tilde_separated_with_whitespace(self):
        result = _parse_naics_string(" 541511Y ~ 541512N ", "541511")
        assert len(result) == 2


class TestParseNaicsExceptionString:

    def test_normal_exception(self):
        result = _parse_naics_exception_string("541519YY  ~541511NN  ")
        assert result["541519"] == "YY"
        assert result["541511"] == "NN"

    def test_empty_returns_empty_dict(self):
        assert _parse_naics_exception_string("") == {}
        assert _parse_naics_exception_string(None) == {}

    def test_short_entry_skipped(self):
        result = _parse_naics_exception_string("ABC")
        assert result == {}


class TestParsePscString:

    def test_normal(self):
        assert _parse_psc_string("D301~R408~J099") == ["D301", "R408", "J099"]

    def test_empty(self):
        assert _parse_psc_string(None) == []
        assert _parse_psc_string("") == []


class TestParseBusinessTypeString:

    def test_normal(self):
        assert _parse_business_type_string("2X~8W~A2") == ["2X", "8W", "A2"]

    def test_empty(self):
        assert _parse_business_type_string(None) == []


class TestParseSbaString:

    def test_padded_entries_stripped(self):
        result = _parse_sba_string("XX        ~A4        ")
        assert result == ["XX", "A4"]

    def test_empty(self):
        assert _parse_sba_string(None) == []
        assert _parse_sba_string("") == []


class TestParseDisasterString:

    def test_normal(self):
        assert _parse_disaster_string("STANC~STANY") == ["STANC", "STANY"]

    def test_empty(self):
        assert _parse_disaster_string(None) == []


# ===================================================================
# _extract_poc tests
# ===================================================================

class TestExtractPoc:

    def test_poc_with_name(self):
        fields = _make_dat_fields()
        # POC block starts at index 46 (governmentBusinessPOC)
        fields[46] = "John"      # first_name
        fields[47] = "M"         # middle_initial
        fields[48] = "Smith"     # last_name
        fields[49] = "Director"  # title
        fields[50] = "123 St"   # address_line_1
        fields[51] = ""          # address_line_2
        fields[52] = "DC"        # city
        fields[53] = "20001"     # zip_code
        fields[54] = ""          # zip_code_plus4
        fields[55] = "USA"       # country_code
        fields[56] = "DC"        # state_or_province

        poc = _extract_poc(fields, 46)
        assert poc is not None
        assert poc["first_name"] == "John"
        assert poc["last_name"] == "Smith"
        assert poc["title"] == "Director"

    def test_poc_without_name_returns_none(self):
        fields = _make_dat_fields()
        # All empty at offset 46
        poc = _extract_poc(fields, 46)
        assert poc is None


# ===================================================================
# _parse_dat_line tests
# ===================================================================

class TestParseDatLine:

    def test_entity_basic_fields(self):
        fields = _make_dat_fields(
            uei="MYUEI123456789",
            cage="ABCDE",
            legal_name="My Corp",
            primary_naics="541511",
            reg_status="A",
        )
        result = _parse_dat_line(fields)

        assert result["entity"]["uei_sam"] == "MYUEI123456789"
        assert result["entity"]["cage_code"] == "ABCDE"
        assert result["entity"]["legal_business_name"] == "My Corp"
        assert result["entity"]["primary_naics"] == "541511"
        assert result["entity"]["registration_status"] == "A"

    def test_entity_has_all_child_keys(self):
        fields = _make_dat_fields()
        result = _parse_dat_line(fields)

        expected_keys = {
            "entity", "addresses", "naics", "pscs",
            "business_types", "sba_certifications", "pocs", "disaster_response",
        }
        assert set(result.keys()) == expected_keys


# ===================================================================
# get_dat_record_count tests
# ===================================================================

class TestGetDatRecordCount:

    def test_valid_bof_header(self, tmp_path):
        dat_file = tmp_path / "test.dat"
        dat_file.write_text("BOF PUBLIC V2 00000000 20260201 0872819 0008169\n")
        assert get_dat_record_count(str(dat_file)) == 872819

    def test_invalid_header_raises(self, tmp_path):
        dat_file = tmp_path / "test.dat"
        dat_file.write_text("NOT_A_BOF_HEADER\n")
        with pytest.raises(ValueError, match="Expected BOF header"):
            get_dat_record_count(str(dat_file))

    def test_short_header_raises(self, tmp_path):
        dat_file = tmp_path / "test.dat"
        dat_file.write_text("BOF PUBLIC V2\n")
        with pytest.raises(ValueError, match="has only"):
            get_dat_record_count(str(dat_file))

    def test_non_numeric_count_raises(self, tmp_path):
        dat_file = tmp_path / "test.dat"
        dat_file.write_text("BOF PUBLIC V2 00000000 20260201 NOTANUMBER 0008169\n")
        with pytest.raises(ValueError, match="Cannot parse record count"):
            get_dat_record_count(str(dat_file))


# ===================================================================
# parse_dat_file integration test
# ===================================================================

class TestParseDatFile:

    def test_single_entity(self, tmp_path):
        fields = _make_dat_fields(uei="UEI00000000001")
        line = _fields_to_line(fields)

        dat_file = tmp_path / "test.dat"
        dat_file.write_text(
            "BOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
            f"{line}\n"
            "EOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
        )

        results = list(parse_dat_file(str(dat_file)))
        assert len(results) == 1
        assert results[0]["entity"]["uei_sam"] == "UEI00000000001"

    def test_multi_row_entity_grouped(self, tmp_path):
        """Two lines with the same UEI should yield one entity."""
        fields1 = _make_dat_fields(uei="UEI00000000001", cage="CAGE1")
        fields2 = _make_dat_fields(uei="UEI00000000001", cage="CAGE2")

        dat_file = tmp_path / "test.dat"
        dat_file.write_text(
            "BOF PUBLIC V2 00000000 20260201 0000002 0000001\n"
            f"{_fields_to_line(fields1)}\n"
            f"{_fields_to_line(fields2)}\n"
            "EOF PUBLIC V2 00000000 20260201 0000002 0000001\n"
        )

        results = list(parse_dat_file(str(dat_file)))
        assert len(results) == 1
        assert results[0]["entity"]["cage_code"] == "CAGE1"

    def test_two_different_entities(self, tmp_path):
        fields1 = _make_dat_fields(uei="UEI00000000001")
        fields2 = _make_dat_fields(uei="UEI00000000002")

        dat_file = tmp_path / "test.dat"
        dat_file.write_text(
            "BOF PUBLIC V2 00000000 20260201 0000002 0000002\n"
            f"{_fields_to_line(fields1)}\n"
            f"{_fields_to_line(fields2)}\n"
            "EOF PUBLIC V2 00000000 20260201 0000002 0000002\n"
        )

        results = list(parse_dat_file(str(dat_file)))
        assert len(results) == 2

    def test_short_line_skipped(self, tmp_path):
        """A line with too few fields should be skipped."""
        dat_file = tmp_path / "test.dat"
        dat_file.write_text(
            "BOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
            "only|three|fields\n"
            "EOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
        )

        results = list(parse_dat_file(str(dat_file)))
        assert len(results) == 0

    def test_missing_uei_skipped(self, tmp_path):
        fields = _make_dat_fields(uei="")
        dat_file = tmp_path / "test.dat"
        dat_file.write_text(
            "BOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
            f"{_fields_to_line(fields)}\n"
            "EOF PUBLIC V2 00000000 20260201 0000001 0000001\n"
        )

        results = list(parse_dat_file(str(dat_file)))
        assert len(results) == 0


# ===================================================================
# _merge_extra_cage_codes tests
# ===================================================================

class TestMergeExtraCageCodes:

    def test_no_extra_codes(self):
        parsed = {"entity": {"uei_sam": "UEI1"}}
        _merge_extra_cage_codes(parsed, [], [])
        # Should not crash, entity unchanged
        assert parsed["entity"]["uei_sam"] == "UEI1"

    def test_with_extra_codes_logs_debug(self):
        parsed = {"entity": {"uei_sam": "UEI1"}}
        _merge_extra_cage_codes(parsed, ["CAGE2", "CAGE3"], ["1", "2"])
        # Just verify no crash; actual logging is debug level
        assert parsed["entity"]["uei_sam"] == "UEI1"
