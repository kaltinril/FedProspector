"""Tests for cli.bulk_spending --check-available flag (Phase 97).

Uses Click's CliRunner to invoke the usaspending_bulk command with mocked
external dependencies (USASpendingClient, DB connection, USASpendingBulkLoader).
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli.bulk_spending import usaspending_bulk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_archive_response(files):
    """Build a mock API response dict for list_archive_files."""
    return {"monthly_files": files}


def _full_file(fy=2026, period=6, date="2026-03-15"):
    return {
        "file_name": f"FY{fy}P{period:02d}_All_Contracts_Full_{date.replace('-', '')}.zip",
        "updated_date": date,
        "url": f"https://files.usaspending.gov/FY{fy}P{period:02d}_All_Contracts_Full_{date.replace('-', '')}.zip",
    }


def _delta_file(fy=2026, period=6, date="2026-03-15"):
    return {
        "file_name": f"FY{fy}P{period:02d}_All_Contracts_Delta_{date.replace('-', '')}.zip",
        "updated_date": date,
        "url": f"https://files.usaspending.gov/FY{fy}P{period:02d}_All_Contracts_Delta_{date.replace('-', '')}.zip",
    }


def _make_mock_cursor(load_rows=None):
    """Create a mock cursor for the etl_load_log query.

    load_rows: list of dicts or None.  When None, fetchall returns [].
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = load_rows or []
    cursor.fetchone.return_value = None
    cursor.description = []
    return cursor


def _make_mock_conn(cursor=None):
    """Create a mock DB connection returning the given cursor."""
    conn = MagicMock()
    conn.cursor.return_value = cursor or _make_mock_cursor()
    return conn


def _make_load_row(load_type, completed_at_str, load_id, records_inserted, fiscal_year=None):
    """Build a mock etl_load_log row dict with a real datetime for completed_at."""
    return {
        "load_id": load_id,
        "load_type": load_type,
        "completed_at": datetime.strptime(completed_at_str, "%Y-%m-%d") if completed_at_str else None,
        "records_inserted": records_inserted,
        "parameters": json.dumps({"fiscal_year": fiscal_year}) if fiscal_year else None,
    }


# _check_available does `from db.connection import get_connection` as a local
# import, so we must patch at the source module.
_PATCH_CLIENT = "api_clients.usaspending_client.USASpendingClient"
_PATCH_CONN = "db.connection.get_connection"


def _invoke(args, archive_response=None, load_rows=None):
    """Helper: invoke the CLI command with standard mocks, return CliRunner result.

    archive_response: dict returned by list_archive_files (per FY call).
                      If None, returns empty monthly_files.
    load_rows:        list of dicts returned by cursor.fetchall for etl_load_log query.
    """
    mock_client_instance = MagicMock()
    mock_client_instance.list_archive_files.return_value = (
        archive_response or _mock_archive_response([])
    )

    mock_cursor = _make_mock_cursor(load_rows)
    mock_conn = _make_mock_conn(mock_cursor)

    runner = CliRunner()
    with patch(_PATCH_CLIENT, return_value=mock_client_instance), \
         patch(_PATCH_CONN, return_value=mock_conn):
        result = runner.invoke(usaspending_bulk, args)

    return result, mock_client_instance


# ===================================================================
# Test: --check-available calls list_archive_files, never creates loader
# ===================================================================

class TestCheckAvailableBasic:

    def test_check_available_calls_list_archive_files_not_loader(self):
        """--check-available should query the archive API and never instantiate
        USASpendingBulkLoader."""
        mock_client_instance = MagicMock()
        mock_client_instance.list_archive_files.return_value = _mock_archive_response([
            _full_file(),
        ])

        mock_loader_cls = MagicMock()
        mock_conn = _make_mock_conn()

        runner = CliRunner()
        with patch(_PATCH_CLIENT, return_value=mock_client_instance), \
             patch("etl.usaspending_bulk_loader.USASpendingBulkLoader", mock_loader_cls), \
             patch(_PATCH_CONN, return_value=mock_conn):
            result = runner.invoke(usaspending_bulk, ["--check-available", "--fiscal-year", "2026"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_client_instance.list_archive_files.assert_called()
        mock_loader_cls.assert_not_called()

    def test_check_available_without_fiscal_year_checks_multiple_fys(self):
        """Without --fiscal-year, should check multiple fiscal years (default years-back)."""
        result, mock_client = _invoke(["--check-available"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Default years_back=5 means 5 FYs queried
        assert mock_client.list_archive_files.call_count >= 2


# ===================================================================
# Test: Output formatting
# ===================================================================

class TestCheckAvailableOutput:

    def test_output_contains_file_names_and_types(self):
        """Output should contain file names and type indicators (Full/Delta)."""
        files = [_full_file(), _delta_file()]
        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response(files),
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = result.output

        # File names should appear
        assert "FY2026P06_All_Contracts_Full_20260315.zip" in output
        assert "FY2026P06_All_Contracts_Delta_20260315.zip" in output

        # Type classification should appear
        assert "Full" in output
        assert "Delta" in output

        # Date should appear
        assert "2026-03-15" in output

    def test_output_contains_header(self):
        """Output should have a header mentioning archive availability."""
        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([_full_file()]),
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output_lower = result.output.lower()
        assert "availab" in output_lower or "archive" in output_lower

    def test_delta_file_labeled_with_delta_marker(self):
        """Delta files should be visually distinguished in output (e.g. [DELTA])."""
        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([_delta_file()]),
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "[DELTA]" in result.output


# ===================================================================
# Test: --check-available with --fiscal-year
# ===================================================================

class TestCheckAvailableFiscalYear:

    def test_fiscal_year_limits_query_to_single_fy(self):
        """--fiscal-year 2026 should call list_archive_files for only FY2026."""
        result, mock_client = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([_full_file()]),
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_client.list_archive_files.assert_called_once_with(2026)

    def test_years_back_controls_fy_count(self):
        """--years-back 2 should query exactly 2 fiscal years."""
        result, mock_client = _invoke(
            ["--check-available", "--years-back", "2"],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert mock_client.list_archive_files.call_count == 2


# ===================================================================
# Test: Mutual exclusivity with --fast
# ===================================================================

class TestCheckAvailableIncompatibleFast:

    def test_check_available_with_fast_errors(self):
        """--check-available and --fast are mutually exclusive and should error."""
        result, _ = _invoke(["--check-available", "--fast"])

        assert result.exit_code != 0, \
            f"Expected non-zero exit for --check-available + --fast, got: {result.output}"
        assert "mutually exclusive" in result.output.lower()


# ===================================================================
# Test: Mutual exclusivity with --skip-download
# ===================================================================

class TestCheckAvailableIncompatibleSkipDownload:

    def test_check_available_with_skip_download_errors(self):
        """--check-available and --skip-download are mutually exclusive and should error."""
        result, _ = _invoke(["--check-available", "--skip-download"])

        assert result.exit_code != 0, \
            f"Expected non-zero exit for --check-available + --skip-download, got: {result.output}"
        assert "mutually exclusive" in result.output.lower()


# ===================================================================
# Test: Mutual exclusivity with --delta
# ===================================================================

class TestCheckAvailableIncompatibleDelta:

    def test_check_available_with_delta_errors(self):
        """--check-available and --delta should be mutually exclusive."""
        result, _ = _invoke(["--check-available", "--delta"])

        assert result.exit_code != 0, \
            f"Expected non-zero exit for --check-available + --delta, got: {result.output}"
        assert "mutually exclusive" in result.output.lower()


# ===================================================================
# Test: Empty archive listing
# ===================================================================

class TestCheckAvailableEmpty:

    def test_no_files_shows_message(self):
        """When no archive files are returned, output should indicate no files found."""
        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([]),
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output_lower = result.output.lower()
        assert "no file" in output_lower or "no files" in output_lower or \
               "none" in output_lower, \
            f"Expected 'no files' message, got: {result.output}"


# ===================================================================
# Test: DB query for last load history
# ===================================================================

class TestCheckAvailableLoadHistory:

    def test_last_load_info_appears_in_output(self):
        """When etl_load_log has prior loads, the output should show last-loaded info."""
        load_rows = [
            _make_load_row("FULL", "2026-02-15", 1234, 1245678, fiscal_year=2026),
        ]

        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([_full_file(fy=2026, date="2026-03-15")]),
            load_rows=load_rows,
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = result.output

        # Should mention "Last loaded" and show the load details
        assert "Last loaded" in output or "last loaded" in output.lower()
        assert "1234" in output  # load_id
        assert "1,245,678" in output  # records formatted with commas

    def test_no_loads_shows_none_message(self):
        """When no completed loads exist, output should say so."""
        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([_full_file()]),
            load_rows=[],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output_lower = result.output.lower()
        assert "no completed load" in output_lower or "(none)" in output_lower

    def test_newer_full_archive_hint(self):
        """When a newer full archive exists than last loaded, output should hint at it."""
        load_rows = [
            _make_load_row("FULL", "2026-02-15", 1234, 1245678, fiscal_year=2026),
        ]

        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([
                _full_file(fy=2026, date="2026-03-15"),
            ]),
            load_rows=load_rows,
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = result.output
        # Should contain a hint about newer data
        assert "New" in output or "new" in output
        assert "2026-03-15" in output
        assert "2026-02-15" in output

    def test_newer_delta_hint(self):
        """When a newer delta file exists than last loaded delta, output should hint."""
        load_rows = [
            _make_load_row("DELTA", "2026-03-01", 1250, 12345),
        ]

        result, _ = _invoke(
            ["--check-available", "--fiscal-year", "2026"],
            archive_response=_mock_archive_response([
                _delta_file(fy=2026, date="2026-03-15"),
            ]),
            load_rows=load_rows,
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = result.output
        assert "delta" in output.lower()
        assert "2026-03-15" in output
        assert "2026-03-01" in output
