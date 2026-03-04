"""Tests for etl.load_manager -- load lifecycle, error logging."""

import pytest
from unittest.mock import MagicMock, patch, call

from etl.load_manager import LoadManager


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _make_mock_conn():
    """Create a mock connection with cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ===================================================================
# start_load tests
# ===================================================================

class TestStartLoad:

    def test_start_load_returns_load_id(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_cursor.lastrowid = 42
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            load_id = lm.start_load("SAM_ENTITY", "FULL")

        assert load_id == 42
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO etl_load_log" in sql
        assert "'RUNNING'" in sql
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_start_load_with_source_file(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_cursor.lastrowid = 10
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            load_id = lm.start_load(
                "SAM_ENTITY", "FULL",
                source_file="/data/entities.json"
            )

        assert load_id == 10
        params = mock_cursor.execute.call_args[0][1]
        assert params[3] == "/data/entities.json"

    def test_start_load_with_parameters(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_cursor.lastrowid = 5
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            load_id = lm.start_load(
                "GSA_CALC", "FULL",
                parameters={"method": "api_multi_sort"}
            )

        assert load_id == 5
        params = mock_cursor.execute.call_args[0][1]
        # parameters JSON should be the last arg
        assert '"method"' in params[4]


# ===================================================================
# complete_load tests
# ===================================================================

class TestCompleteLoad:

    def test_complete_load_updates_status(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            lm.complete_load(
                load_id=42,
                records_read=100,
                records_inserted=80,
                records_updated=10,
                records_unchanged=5,
                records_errored=5,
            )

        sql = mock_cursor.execute.call_args[0][0]
        assert "status = 'SUCCESS'" in sql
        params = mock_cursor.execute.call_args[0][1]
        # Check counts are passed (they come after datetime)
        assert 100 in params  # records_read
        assert 80 in params   # records_inserted
        assert 42 in params   # load_id
        mock_conn.commit.assert_called_once()


# ===================================================================
# fail_load tests
# ===================================================================

class TestFailLoad:

    def test_fail_load_updates_status(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            lm.fail_load(42, "Connection timeout")

        sql = mock_cursor.execute.call_args[0][0]
        assert "status = 'FAILED'" in sql
        mock_conn.commit.assert_called_once()

    def test_fail_load_truncates_long_message(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            long_msg = "X" * 10000
            lm.fail_load(42, long_msg)

        params = mock_cursor.execute.call_args[0][1]
        # error_message should be truncated to 5000
        error_msg = params[1]
        assert len(error_msg) == 5000


# ===================================================================
# log_record_error tests
# ===================================================================

class TestLogRecordError:

    def test_log_record_error_inserts(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            lm.log_record_error(
                load_id=42,
                record_identifier="OPP-001",
                error_type="ValueError",
                error_message="Missing field",
                raw_data='{"noticeId": "OPP-001"}',
            )

        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO etl_load_error" in sql
        mock_conn.commit.assert_called_once()

    def test_log_record_error_truncates_raw_data(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            long_raw = "X" * 20000
            lm.log_record_error(42, "REC-1", "Error", "msg", raw_data=long_raw)

        params = mock_cursor.execute.call_args[0][1]
        # raw_data should be truncated to 10000
        raw = params[4]
        assert len(raw) == 10000

    def test_log_record_error_none_raw_data(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn()
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            lm.log_record_error(42, "REC-1", "Error", "msg", raw_data=None)

        params = mock_cursor.execute.call_args[0][1]
        assert params[4] is None


# ===================================================================
# get_last_load tests
# ===================================================================

class TestGetLastLoad:

    def test_get_last_load_returns_dict(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                "load_id": 42,
                "source_system": "SAM_ENTITY",
                "status": "SUCCESS",
            }
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            result = lm.get_last_load("SAM_ENTITY")

        assert result["load_id"] == 42
        assert result["status"] == "SUCCESS"

    def test_get_last_load_returns_none_when_empty(self):
        with patch("etl.load_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            lm = LoadManager()
            result = lm.get_last_load("NONEXISTENT")

        assert result is None
