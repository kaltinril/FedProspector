"""Tests for etl.bulk_loader -- TSV writing, LOAD DATA INFILE generation, escape logic."""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from etl.bulk_loader import (
    BulkLoader,
    _escape_tsv_value,
    _ENTITY_COLUMNS,
    _CHILD_COLUMNS,
    _CHILD_TABLE_NAMES,
    _ENTITY_HASH_FIELDS,
)


# ===================================================================
# _escape_tsv_value tests
# ===================================================================

class TestEscapeTsvValue:

    def test_none_becomes_backslash_n(self):
        assert _escape_tsv_value(None) == "\\N"

    def test_normal_string(self):
        assert _escape_tsv_value("hello") == "hello"

    def test_tab_escaped(self):
        assert _escape_tsv_value("a\tb") == "a\\tb"

    def test_newline_escaped(self):
        assert _escape_tsv_value("line1\nline2") == "line1\\nline2"

    def test_carriage_return_escaped(self):
        assert _escape_tsv_value("line1\rline2") == "line1\\rline2"

    def test_backslash_doubled(self):
        assert _escape_tsv_value("path\\to\\file") == "path\\\\to\\\\file"

    def test_backslash_before_tab(self):
        """Backslash doubling happens first, so \t in input becomes \\\\t not \\t."""
        assert _escape_tsv_value("\\\t") == "\\\\\\t"

    def test_integer_converted_to_string(self):
        assert _escape_tsv_value(42) == "42"

    def test_empty_string_stays_empty(self):
        assert _escape_tsv_value("") == ""


# ===================================================================
# _write_tsv_row tests
# ===================================================================

class TestWriteTsvRow:

    def test_writes_tab_separated_values(self, tmp_path):
        from io import StringIO
        buf = StringIO()
        data = {"col_a": "val1", "col_b": "val2", "col_c": None}
        BulkLoader._write_tsv_row(buf, data, ["col_a", "col_b", "col_c"])
        assert buf.getvalue() == "val1\tval2\t\\N\n"

    def test_missing_key_becomes_null(self, tmp_path):
        from io import StringIO
        buf = StringIO()
        data = {"col_a": "val1"}
        BulkLoader._write_tsv_row(buf, data, ["col_a", "col_b"])
        assert buf.getvalue() == "val1\t\\N\n"


# ===================================================================
# _write_tsv_files tests (temp file creation)
# ===================================================================

class TestWriteTsvFiles:

    def _make_entity_record(self, uei="UEI001"):
        """Minimal parsed entity record from DAT parser."""
        return {
            "entity": {
                "uei_sam": uei,
                "cage_code": "CAGE1",
                "dodaac": None,
                "registration_status": "A",
                "purpose_of_registration": "Z1",
                "initial_registration_date": "2020-01-01",
                "registration_expiration_date": "2027-01-01",
                "last_update_date": "2026-01-01",
                "activation_date": "2020-01-02",
                "legal_business_name": "Test Corp",
                "dba_name": None,
                "entity_division": None,
                "entity_division_number": None,
                "dnb_open_data_flag": None,
                "entity_start_date": "2010-01-01",
                "fiscal_year_end_close": "12",
                "entity_url": None,
                "entity_structure_code": "2L",
                "state_of_incorporation": "VA",
                "country_of_incorporation": "USA",
                "primary_naics": "541511",
                "credit_card_usage": "N",
                "correspondence_flag": "M",
                "debt_subject_to_offset": "N",
                "exclusion_status_flag": "N",
                "no_public_display_flag": "N",
                "evs_source": "SAM",
            },
            "addresses": [],
            "naics": [],
            "pscs": [],
            "business_types": [],
            "sba_certifications": [],
            "pocs": [],
            "disaster_response": [],
        }

    @patch("etl.bulk_loader.get_connection")
    @patch("etl.bulk_loader.compute_record_hash", return_value="fakehash")
    def test_tsv_files_created(self, mock_hash, mock_gc, tmp_path):
        loader = BulkLoader()
        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
            "child_counts": {t: 0 for t in _CHILD_TABLE_NAMES},
        }

        records = [self._make_entity_record("UEI001")]
        tsv_paths = loader._write_tsv_files(iter(records), str(tmp_path), 1, stats)

        assert stats["records_read"] == 1
        assert "entity" in tsv_paths
        assert os.path.exists(tsv_paths["entity"])

        # Verify entity TSV has one line
        with open(tsv_paths["entity"], "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        # First field should be UEI
        assert lines[0].startswith("UEI001\t")


# ===================================================================
# _execute_load_data tests (SQL generation)
# ===================================================================

class TestExecuteLoadData:

    @patch("etl.bulk_loader.get_connection")
    def test_entity_load_data_sql(self, mock_gc):
        loader = BulkLoader()
        cursor = MagicMock()

        loader._execute_load_data(
            cursor,
            "C:\\tmp\\entity.tsv",
            "entity",
            _ENTITY_COLUMNS,
        )

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]

        # Must use forward slashes for MySQL path
        assert "C:/tmp/entity.tsv" in sql
        assert "LOAD DATA INFILE" in sql
        assert "INTO TABLE entity" in sql
        assert "SET first_loaded_at = NOW()" in sql
        # Entity table should NOT have IGNORE
        assert "IGNORE " not in sql.split("INTO TABLE")[0]

    @patch("etl.bulk_loader.get_connection")
    def test_child_table_has_ignore(self, mock_gc):
        loader = BulkLoader()
        cursor = MagicMock()

        loader._execute_load_data(
            cursor,
            "/tmp/entity_naics.tsv",
            "entity_naics",
            _CHILD_COLUMNS["entity_naics"],
        )

        sql = cursor.execute.call_args[0][0]
        assert "IGNORE " in sql
        # Child table should NOT have SET clause
        assert "SET first_loaded_at" not in sql


# ===================================================================
# _load_into_mysql tests
# ===================================================================

class TestLoadIntoMysql:

    @patch("etl.bulk_loader.get_connection")
    def test_full_load_truncates_tables(self, mock_gc):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_gc.return_value = mock_conn

        loader = BulkLoader()
        tsv_paths = {
            "entity": "/tmp/entity.tsv",
        }
        for t in _CHILD_TABLE_NAMES:
            tsv_paths[t] = f"/tmp/{t}.tsv"

        loader._load_into_mysql(tsv_paths, "FULL")

        # Should have SET FOREIGN_KEY_CHECKS = 0 at start
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        fk_off_found = any("FOREIGN_KEY_CHECKS = 0" in c for c in calls)
        fk_on_found = any("FOREIGN_KEY_CHECKS = 1" in c for c in calls)
        truncate_found = any("TRUNCATE TABLE entity" in c for c in calls)

        assert fk_off_found
        assert fk_on_found
        assert truncate_found
        mock_conn.commit.assert_called_once()

    @patch("etl.bulk_loader.get_connection")
    def test_incremental_does_not_truncate(self, mock_gc):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_gc.return_value = mock_conn

        loader = BulkLoader()
        tsv_paths = {"entity": "/tmp/entity.tsv"}
        for t in _CHILD_TABLE_NAMES:
            tsv_paths[t] = f"/tmp/{t}.tsv"

        loader._load_into_mysql(tsv_paths, "INCREMENTAL")

        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        truncate_found = any("TRUNCATE" in c for c in calls)
        assert not truncate_found


# ===================================================================
# Column list consistency tests
# ===================================================================

class TestColumnConstants:

    def test_entity_columns_end_with_hash_and_load_id(self):
        assert _ENTITY_COLUMNS[-2] == "record_hash"
        assert _ENTITY_COLUMNS[-1] == "last_load_id"

    def test_child_table_names_match_columns_dict(self):
        for table in _CHILD_TABLE_NAMES:
            assert table in _CHILD_COLUMNS, f"{table} missing from _CHILD_COLUMNS"

    def test_all_child_columns_start_with_uei_sam(self):
        for table, cols in _CHILD_COLUMNS.items():
            assert cols[0] == "uei_sam", f"{table} columns should start with uei_sam"
