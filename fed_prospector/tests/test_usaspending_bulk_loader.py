"""Tests for etl.usaspending_bulk_loader -- row normalization, hashing, checkpoints."""

import hashlib
import os
import tempfile

import pytest
from unittest.mock import MagicMock, patch, call

from etl.usaspending_bulk_loader import (
    USASpendingBulkLoader,
    CSV_COLUMN_MAP,
    LOAD_COLUMNS,
    _DATE_COLUMNS,
    _MONEY_COLUMNS,
    BATCH_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv_row(**overrides):
    """Return a minimal CSV row dict keyed by CSV column names."""
    base = {
        "contract_award_unique_key": "CONT_AWD_GS35F0001_4700",
        "award_id_piid": "GS-35F-0001",
        "award_id_fain": "",
        "uri": "",
        "award_type": "D",
        "award_description": "IT Support Services",
        "recipient_name": "Test Corp",
        "recipient_uei": "TESTAWARDEE1",
        "recipient_parent_name": "Parent Corp",
        "recipient_parent_uei": "PARENTUEI123",
        "current_total_value_of_award": "750000.00",
        "total_dollars_obligated": "500000.00",
        "period_of_performance_start_date": "2026-01-15",
        "period_of_performance_current_end_date": "2027-01-14",
        "last_modified_date": "2026-03-01",
        "awarding_agency_name": "General Services Administration",
        "awarding_sub_agency_name": "PBS",
        "funding_agency_name": "GSA",
        "naics_code": "541511",
        "naics_description": "Custom Computer Programming Services",
        "product_or_service_code": "D301",
        "type_of_set_aside": "WOSB",
        "type_of_set_aside_description": "Women-Owned Small Business",
        "primary_place_of_performance_state_code": "VA",
        "primary_place_of_performance_country_code": "USA",
        "primary_place_of_performance_zip_4": "22030",
        "primary_place_of_performance_city_name": "Fairfax",
        "solicitation_identifier": "SOL-123",
    }
    base.update(overrides)
    return base


def _make_loader():
    """Create a USASpendingBulkLoader with mocked dependencies."""
    with patch("etl.usaspending_bulk_loader.LoadManager"):
        return USASpendingBulkLoader()


# ===================================================================
# _normalize_csv_row tests
# ===================================================================

class TestNormalizeCsvRow:

    def test_all_columns_mapped_correctly(self):
        loader = _make_loader()
        row = _make_csv_row()
        result = loader._normalize_csv_row(row, 2026)

        assert result["generated_unique_award_id"] == "CONT_AWD_GS35F0001_4700"
        assert result["piid"] == "GS-35F-0001"
        assert result["award_type"] == "D"
        assert result["award_description"] == "IT Support Services"
        assert result["recipient_name"] == "Test Corp"
        assert result["recipient_uei"] == "TESTAWARDEE1"
        assert result["recipient_parent_name"] == "Parent Corp"
        assert result["recipient_parent_uei"] == "PARENTUEI123"
        assert result["awarding_agency_name"] == "General Services Administration"
        assert result["awarding_sub_agency_name"] == "PBS"
        assert result["funding_agency_name"] == "GSA"
        assert result["naics_code"] == "541511"
        assert result["naics_description"] == "Custom Computer Programming Services"
        assert result["psc_code"] == "D301"
        assert result["type_of_set_aside"] == "WOSB"
        assert result["type_of_set_aside_description"] == "Women-Owned Small Business"
        assert result["pop_state"] == "VA"
        assert result["pop_country"] == "USA"
        assert result["pop_zip"] == "22030"
        assert result["pop_city"] == "Fairfax"
        assert result["solicitation_identifier"] == "SOL-123"

    def test_missing_pk_returns_none(self):
        loader = _make_loader()
        row = _make_csv_row(contract_award_unique_key="")
        result = loader._normalize_csv_row(row, 2026)
        assert result is None

    def test_absent_pk_returns_none(self):
        loader = _make_loader()
        row = _make_csv_row()
        del row["contract_award_unique_key"]
        result = loader._normalize_csv_row(row, 2026)
        assert result is None

    def test_date_columns_parsed(self):
        loader = _make_loader()
        row = _make_csv_row(
            period_of_performance_start_date="01/15/2026",
            period_of_performance_current_end_date="01/14/2027",
            last_modified_date="2026-03-01T10:30:00",
        )
        result = loader._normalize_csv_row(row, 2026)

        # parse_date normalizes to YYYY-MM-DD
        assert result["start_date"] == "2026-01-15"
        assert result["end_date"] == "2027-01-14"
        assert result["last_modified_date"] == "2026-03-01"

    def test_money_columns_parsed(self):
        loader = _make_loader()
        row = _make_csv_row(
            total_dollars_obligated="1,500,000.50",
            current_total_value_of_award="2,000,000.00",
        )
        result = loader._normalize_csv_row(row, 2026)

        # parse_decimal strips commas, returns decimal string
        assert result["total_obligation"] == "1500000.50"
        assert result["base_and_all_options_value"] == "2000000.00"

    def test_empty_strings_become_none(self):
        loader = _make_loader()
        row = _make_csv_row(
            award_id_fain="",
            uri="",
            recipient_parent_name="",
        )
        result = loader._normalize_csv_row(row, 2026)

        assert result["fain"] is None
        assert result["uri"] is None
        assert result["recipient_parent_name"] is None

    def test_fiscal_year_set(self):
        loader = _make_loader()
        row = _make_csv_row()
        result = loader._normalize_csv_row(row, 2025)
        assert result["fiscal_year"] == 2025

    def test_bulk_fields_initialized(self):
        loader = _make_loader()
        row = _make_csv_row()
        result = loader._normalize_csv_row(row, 2026)
        assert result["fpds_enriched_at"] is None
        assert result["record_hash"] is None

    def test_unmapped_csv_columns_ignored(self):
        """Extra columns in the CSV should not appear in the result."""
        loader = _make_loader()
        row = _make_csv_row()
        row["some_extra_column"] = "extra_value"
        result = loader._normalize_csv_row(row, 2026)
        assert "some_extra_column" not in result

    def test_none_date_not_parsed(self):
        """Empty date columns should become None, not get passed to parse_date."""
        loader = _make_loader()
        row = _make_csv_row(
            period_of_performance_start_date="",
            period_of_performance_current_end_date="",
            last_modified_date="",
        )
        result = loader._normalize_csv_row(row, 2026)
        assert result["start_date"] is None
        assert result["end_date"] is None
        assert result["last_modified_date"] is None

    def test_none_money_not_parsed(self):
        """Empty money columns should become None."""
        loader = _make_loader()
        row = _make_csv_row(
            total_dollars_obligated="",
            current_total_value_of_award="",
        )
        result = loader._normalize_csv_row(row, 2026)
        assert result["total_obligation"] is None
        assert result["base_and_all_options_value"] is None


# ===================================================================
# _compute_archive_hash tests
# ===================================================================

class TestComputeArchiveHash:

    def test_consistent_hash_for_same_file(self):
        loader = _make_loader()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"test archive content for hashing")
            tmp_path = f.name
        try:
            hash1 = loader._compute_archive_hash(tmp_path)
            hash2 = loader._compute_archive_hash(tmp_path)
            assert hash1 == hash2
        finally:
            os.unlink(tmp_path)

    def test_hash_includes_file_size(self):
        loader = _make_loader()
        content = b"deterministic content"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = loader._compute_archive_hash(tmp_path)
            expected_size = len(content)
            assert result.endswith(f":{expected_size}")
        finally:
            os.unlink(tmp_path)

    def test_hash_format_sha256_colon_size(self):
        loader = _make_loader()
        content = b"some test data"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = loader._compute_archive_hash(tmp_path)
            parts = result.split(":")
            assert len(parts) == 2, f"Expected 'sha256:size' but got '{result}'"
            sha_hex, size_str = parts
            assert len(sha_hex) == 64, "SHA-256 hex digest should be 64 chars"
            assert size_str == str(len(content))

            # Verify hash matches manual calculation
            expected_hash = hashlib.sha256(content).hexdigest()
            assert sha_hex == expected_hash
        finally:
            os.unlink(tmp_path)

    def test_different_files_produce_different_hashes(self):
        loader = _make_loader()
        paths = []
        try:
            for data in [b"file content A", b"file content B"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
                    f.write(data)
                    paths.append(f.name)
            hash_a = loader._compute_archive_hash(paths[0])
            hash_b = loader._compute_archive_hash(paths[1])
            assert hash_a != hash_b
        finally:
            for p in paths:
                os.unlink(p)


# ===================================================================
# _format_duration tests
# ===================================================================

class TestFormatDuration:

    def test_seconds_under_60(self):
        assert USASpendingBulkLoader._format_duration(45) == "45s"

    def test_zero_seconds(self):
        assert USASpendingBulkLoader._format_duration(0) == "0s"

    def test_exact_60_seconds(self):
        assert USASpendingBulkLoader._format_duration(60) == "1m 00s"

    def test_minutes_and_seconds(self):
        assert USASpendingBulkLoader._format_duration(125) == "2m 05s"

    def test_large_duration(self):
        assert USASpendingBulkLoader._format_duration(3661) == "61m 01s"

    def test_float_truncated(self):
        assert USASpendingBulkLoader._format_duration(59.9) == "59s"

    def test_just_under_60(self):
        assert USASpendingBulkLoader._format_duration(59) == "59s"

    def test_61_seconds(self):
        assert USASpendingBulkLoader._format_duration(61) == "1m 01s"


# ===================================================================
# Index management tests
# ===================================================================

class TestIndexManagement:

    def test_secondary_indexes_count(self):
        """SECONDARY_INDEXES should have exactly 10 entries."""
        assert len(USASpendingBulkLoader.SECONDARY_INDEXES) == 10

    def test_secondary_indexes_have_name_and_sql(self):
        """Each entry should be a (name, CREATE INDEX ...) tuple."""
        for name, sql in USASpendingBulkLoader.SECONDARY_INDEXES:
            assert name.startswith("idx_usa_")
            assert sql.startswith("CREATE INDEX")
            assert "usaspending_award" in sql

    def test_drop_secondary_indexes_handles_missing(self):
        """Dropping a non-existent index should not raise."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Every DROP INDEX raises an exception (index doesn't exist)
        mock_cursor.execute.side_effect = Exception("index doesn't exist")
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            # Should not raise
            loader._drop_secondary_indexes()

        # Should have tried all 10 indexes
        assert mock_cursor.execute.call_count == 10
        # Rollback called for each failed DROP
        assert mock_conn.rollback.call_count == 10

    def test_drop_secondary_indexes_succeeds(self):
        """Successful drops should commit after each."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            loader._drop_secondary_indexes()

        assert mock_cursor.execute.call_count == 10
        assert mock_conn.commit.call_count == 10

    def test_recreate_secondary_indexes_calls_create(self):
        """Recreate should execute each CREATE INDEX SQL."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            loader._recreate_secondary_indexes()

        assert mock_cursor.execute.call_count == 10
        assert mock_conn.commit.call_count == 10

        # Verify the actual SQL passed to execute matches the SECONDARY_INDEXES
        executed_sqls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        expected_sqls = [sql for _, sql in USASpendingBulkLoader.SECONDARY_INDEXES]
        assert executed_sqls == expected_sqls


# ===================================================================
# Checkpoint method tests
# ===================================================================

class TestCheckpointMethods:

    def test_get_or_create_checkpoint_creates_new(self):
        """When no checkpoint exists, a new one should be created."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No existing checkpoint (both queries)
        mock_cursor.lastrowid = 42
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            result = loader._get_or_create_checkpoint(
                load_id=1, fiscal_year=2026,
                csv_file_name="Contracts_2026.csv",
                archive_hash="abc123:1024",
            )

        assert result["checkpoint_id"] == 42
        assert result["status"] == "IN_PROGRESS"
        assert result["completed_batches"] == 0
        assert result["total_rows_loaded"] == 0
        mock_conn.commit.assert_called_once()

        # Verify: 1st call = cross-load COMPLETE check, 2nd = current load_id check, 3rd = INSERT
        insert_call = mock_cursor.execute.call_args_list[2]
        assert "INSERT INTO usaspending_load_checkpoint" in insert_call[0][0]
        assert insert_call[0][1] == (1, 2026, "Contracts_2026.csv", "abc123:1024")

    def test_get_or_create_checkpoint_returns_existing(self):
        """When a checkpoint exists, it should be returned as-is."""
        loader = _make_loader()

        existing = {
            "checkpoint_id": 99,
            "status": "COMPLETE",
            "completed_batches": 5,
            "total_rows_loaded": 250000,
        }

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = existing
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            result = loader._get_or_create_checkpoint(
                load_id=1, fiscal_year=2026,
                csv_file_name="Contracts_2026.csv",
                archive_hash="abc123:1024",
            )

        assert result == existing
        # Should NOT have called INSERT — found on first query (cross-load check)
        assert mock_cursor.execute.call_count == 1

    def test_update_checkpoint_batch(self):
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            loader._update_checkpoint_batch(
                checkpoint_id=42, completed_batches=3, rows_loaded=150000,
            )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "UPDATE usaspending_load_checkpoint" in sql
        assert "completed_batches" in sql
        assert "total_rows_loaded" in sql
        assert params == (3, 150000, 42)
        mock_conn.commit.assert_called_once()

    def test_complete_checkpoint(self):
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            loader._complete_checkpoint(checkpoint_id=42)

        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "status = 'COMPLETE'" in sql
        assert "completed_at = NOW()" in sql
        assert params == (42,)
        mock_conn.commit.assert_called_once()

    def test_fail_checkpoint(self):
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            loader._fail_checkpoint(checkpoint_id=42)

        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "status = 'FAILED'" in sql
        assert params == (42,)
        mock_conn.commit.assert_called_once()

    def test_is_fy_already_loaded_true(self):
        """Returns True when a matching load_id is found with all COMPLETE."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # load_id found
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            result = loader._is_fy_already_loaded(2026, "abc123:1024")

        assert result is True

        # Verify query params
        params = mock_cursor.execute.call_args[0][1]
        assert params == (2026, "abc123:1024")

    def test_is_fy_already_loaded_false(self):
        """Returns False when no matching load found."""
        loader = _make_loader()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.usaspending_bulk_loader.get_connection", return_value=mock_conn):
            result = loader._is_fy_already_loaded(2026, "abc123:1024")

        assert result is False


# ===================================================================
# Column constant consistency tests
# ===================================================================

class TestColumnConstants:

    def test_load_columns_includes_all_mapped_db_columns(self):
        """Every DB column from CSV_COLUMN_MAP should be in LOAD_COLUMNS."""
        for csv_col, db_col in CSV_COLUMN_MAP.items():
            assert db_col in LOAD_COLUMNS, (
                f"DB column '{db_col}' (mapped from '{csv_col}') "
                f"missing from LOAD_COLUMNS"
            )

    def test_load_columns_has_metadata_fields(self):
        """LOAD_COLUMNS should end with metadata fields."""
        assert "fiscal_year" in LOAD_COLUMNS
        assert "fpds_enriched_at" in LOAD_COLUMNS
        assert "record_hash" in LOAD_COLUMNS
        assert "last_load_id" in LOAD_COLUMNS

    def test_date_columns_are_valid_db_columns(self):
        """All _DATE_COLUMNS should be valid DB column names from the mapping."""
        db_columns = set(CSV_COLUMN_MAP.values())
        for col in _DATE_COLUMNS:
            assert col in db_columns, f"Date column '{col}' not in CSV_COLUMN_MAP values"

    def test_money_columns_are_valid_db_columns(self):
        """All _MONEY_COLUMNS should be valid DB column names from the mapping."""
        db_columns = set(CSV_COLUMN_MAP.values())
        for col in _MONEY_COLUMNS:
            assert col in db_columns, f"Money column '{col}' not in CSV_COLUMN_MAP values"

    def test_batch_size_is_positive(self):
        assert BATCH_SIZE > 0
        assert BATCH_SIZE == 50_000
