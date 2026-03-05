"""Tests for etl.reference_loader -- CSV parsing, hierarchy, category mapping."""

import csv
import io
import pytest
from unittest.mock import MagicMock, patch, mock_open

from etl.reference_loader import ReferenceLoader


# ---------------------------------------------------------------------------
# Helper to build a ReferenceLoader with DB mocked
# ---------------------------------------------------------------------------
def _make_loader():
    return ReferenceLoader()


# ===================================================================
# _naics_hierarchy tests
# ===================================================================

class TestNaicsHierarchy:

    def test_two_digit_sector(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("11")
        assert level == 1
        assert name == "Sector"
        assert parent is None

    def test_three_digit_subsector(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("111")
        assert level == 2
        assert name == "Subsector"
        assert parent == "11"

    def test_four_digit_industry_group(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("1111")
        assert level == 3
        assert name == "Industry Group"
        assert parent == "111"

    def test_five_digit_naics_industry(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("11111")
        assert level == 4
        assert name == "NAICS Industry"
        assert parent == "1111"

    def test_six_digit_national_industry(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("541512")
        assert level == 5
        assert name == "National Industry"
        assert parent == "54151"

    def test_exception_code_alpha_suffix_stripped(self):
        """NAICS codes like '115310e' should strip the trailing alpha suffix."""
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("115310e")
        assert level == 5
        assert name == "National Industry"
        assert parent == "11531"

    def test_exception_code_mixed_suffix_not_stripped(self):
        """NAICS codes like '115310e1' end with digit so rstrip leaves them as-is (8 chars, unknown)."""
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("115310e1")
        assert level is None
        assert name is None

    def test_single_digit_unknown(self):
        loader = _make_loader()
        level, name, parent = loader._naics_hierarchy("1")
        assert level is None
        assert name is None
        assert parent is None


# ===================================================================
# _get_business_type_category tests
# ===================================================================

class TestBusinessTypeCategory:

    def test_known_codes(self):
        loader = _make_loader()
        assert loader._get_business_type_category("A2") == "Woman-Owned"
        assert loader._get_business_type_category("A5") == "Veteran"
        assert loader._get_business_type_category("27") == "Small Business"
        assert loader._get_business_type_category("2R") == "Government"
        assert loader._get_business_type_category("M8") == "Education"
        assert loader._get_business_type_category("80") == "Healthcare"

    def test_unknown_code(self):
        loader = _make_loader()
        assert loader._get_business_type_category("ZZ_UNKNOWN") is None


# ===================================================================
# load_naics_codes tests
# ===================================================================

class TestLoadNaicsCodes:

    def test_load_naics_basic(self):
        """Verify NAICS codes are read from CSV and inserted."""
        loader = _make_loader()

        # Build minimal CSV content
        csv_2022 = "2022 NAICS US   Code,2022 NAICS US Title\n541512,Computer Systems Design\n"
        csv_2017 = "2017 NAICS Code,2017 NAICS Title\n541511,Custom Programming\n"

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value = mock_cursor

        file_contents = {
            "2022": csv_2022,
            "2017": csv_2017,
        }

        call_count = [0]
        original_open = open

        def fake_open(path, *args, **kwargs):
            path_str = str(path)
            call_count[0] += 1
            if "2-6 digit_2022" in path_str:
                return io.StringIO(csv_2022)
            elif "6-digit_2017" in path_str:
                return io.StringIO(csv_2017)
            raise FileNotFoundError(f"Unexpected file: {path_str}")

        with patch("etl.reference_loader.get_connection", return_value=mock_conn), \
             patch("builtins.open", side_effect=fake_open):
            count = loader.load_naics_codes()

        # 1 code from 2022 + 1 from 2017
        assert count >= 1
        mock_cursor.executemany.assert_called()
        mock_conn.commit.assert_called_once()


# ===================================================================
# load_psc_codes tests
# ===================================================================

class TestLoadPscCodes:

    def test_load_psc_basic(self):
        """Verify PSC codes are parsed and inserted."""
        loader = _make_loader()

        csv_content = (
            "PSC CODE,PRODUCT AND SERVICE CODE NAME,START DATE,END DATE,"
            "PRODUCT AND SERVICE CODE FULL NAME (DESCRIPTION),"
            "PRODUCT AND SERVICE CODE INCLUDES,PRODUCT AND SERVICE CODE EXCLUDES,"
            "PRODUCT AND SERVICE CODE NOTES,Parent PSC Code,"
            "PSC Category: Service (S)/Product (P),"
            "Level 1 Category Code,Level 1 Category,Level 2 Category Code,Level 2 Category\n"
            "D301,IT Services,2020-01-01,,Full description,,,,D3,S,D,IT,,\n"
        )

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        def fake_open(path, *args, **kwargs):
            return io.StringIO(csv_content)

        with patch("etl.reference_loader.get_connection", return_value=mock_conn), \
             patch("builtins.open", side_effect=fake_open):
            count = loader.load_psc_codes()

        assert count == 1
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()


# ===================================================================
# load_size_standards tests
# ===================================================================

class TestLoadSizeStandards:

    def test_load_size_standards_decimal_parsing(self):
        """Verify size_standard is parsed from CSV without error."""
        loader = _make_loader()

        csv_content = (
            "NAICS Codes,NAICS Industry Description,Size_standard,TYPE,Footnote\n"
            "541512,Computer Systems Design,$27.5 million,R,\n"
        )

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Return valid NAICS code for FK check
        mock_cursor.fetchall.return_value = [("541512",)]
        mock_conn.cursor.return_value = mock_cursor

        def fake_open(path, *args, **kwargs):
            return io.StringIO(csv_content)

        with patch("etl.reference_loader.get_connection", return_value=mock_conn), \
             patch("builtins.open", side_effect=fake_open):
            count = loader.load_size_standards()

        assert count == 1
        mock_cursor.executemany.assert_called_once()

    def test_load_size_standards_skips_missing_naics(self):
        """Rows with unknown NAICS codes should be skipped."""
        loader = _make_loader()

        csv_content = (
            "NAICS Codes,NAICS Industry Description,Size_standard,TYPE,Footnote\n"
            "999999,Unknown Industry,$10 million,R,\n"
        )

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # No valid NAICS codes in DB
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        def fake_open(path, *args, **kwargs):
            return io.StringIO(csv_content)

        with patch("etl.reference_loader.get_connection", return_value=mock_conn), \
             patch("builtins.open", side_effect=fake_open):
            count = loader.load_size_standards()

        assert count == 0


# ===================================================================
# Error handling tests
# ===================================================================

class TestReferenceLoaderErrors:

    def test_file_not_found_raises(self):
        """Missing CSV file should propagate FileNotFoundError."""
        from pathlib import Path

        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.reference_loader.get_connection", return_value=mock_conn), \
             patch("etl.reference_loader.settings") as mock_settings:
            mock_settings.REF_DATA_DIR = Path("/nonexistent/path/that/does/not/exist")
            with pytest.raises(FileNotFoundError):
                loader.load_footnotes()

    def test_load_all_catches_individual_errors(self):
        """load_all should continue past individual loader failures."""
        loader = _make_loader()

        # Make every individual loader fail
        with patch.object(loader, "load_footnotes", side_effect=ValueError("fail")), \
             patch.object(loader, "load_naics_codes", side_effect=ValueError("fail")), \
             patch.object(loader, "load_size_standards", side_effect=ValueError("fail")), \
             patch.object(loader, "load_psc_codes", side_effect=ValueError("fail")), \
             patch.object(loader, "load_country_codes", side_effect=ValueError("fail")), \
             patch.object(loader, "load_state_codes", side_effect=ValueError("fail")), \
             patch.object(loader, "load_fips_counties", side_effect=ValueError("fail")), \
             patch.object(loader, "load_business_types", side_effect=ValueError("fail")), \
             patch.object(loader, "load_entity_structures", side_effect=ValueError("fail")), \
             patch.object(loader, "load_set_aside_types", side_effect=ValueError("fail")), \
             patch.object(loader, "load_sba_types", side_effect=ValueError("fail")):
            results = loader.load_all()

        # All entries should be -1 (failure)
        for table_name, count in results.items():
            assert count == -1, f"Expected -1 for {table_name}"


# ===================================================================
# Socioeconomic / Small Business flag tests
# ===================================================================

class TestReferenceLoaderFlags:

    def test_socioeconomic_codes_populated(self):
        assert "A2" in ReferenceLoader.SOCIOECONOMIC_CODES
        assert "8W" in ReferenceLoader.SOCIOECONOMIC_CODES

    def test_small_business_codes_populated(self):
        assert "27" in ReferenceLoader.SMALL_BUSINESS_CODES
        assert "8W" in ReferenceLoader.SMALL_BUSINESS_CODES
