"""Tests for etl.staging_mixin -- raw JSON staging write/update methods."""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from etl.staging_mixin import StagingMixin


# ---------------------------------------------------------------------------
# Concrete test subclass of StagingMixin
# ---------------------------------------------------------------------------
class _TestLoader(StagingMixin):
    """Minimal StagingMixin subclass for testing."""
    _STG_TABLE = "stg_test"
    _STG_KEY_COLS = ["test_id"]

    def _extract_staging_key(self, raw: dict) -> dict:
        return {"test_id": raw.get("id", "")}


class _TestLoaderMultiKey(StagingMixin):
    """StagingMixin subclass with multiple key columns."""
    _STG_TABLE = "stg_multi"
    _STG_KEY_COLS = ["key_a", "key_b"]

    def _extract_staging_key(self, raw: dict) -> dict:
        return {"key_a": raw.get("a", ""), "key_b": raw.get("b", "")}


# ===================================================================
# _open_stg_conn tests
# ===================================================================

class TestOpenStgConn:

    def test_autocommit_set_to_true(self):
        """_open_stg_conn must set autocommit on the inner connection.

        PooledMySQLConnection wraps the real connection in _cnx and does not
        proxy autocommit, so _open_stg_conn targets _cnx directly.
        """
        mock_inner = MagicMock()
        mock_conn = MagicMock()
        mock_conn._cnx = mock_inner
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("etl.staging_mixin.get_connection", return_value=mock_conn):
            loader = _TestLoader()
            conn, cursor = loader._open_stg_conn()

        assert mock_inner.autocommit is True
        assert conn is mock_conn
        assert cursor is mock_cursor


# ===================================================================
# _insert_staging tests
# ===================================================================

class TestInsertStaging:

    def test_sql_structure_and_columns(self):
        """Verify the INSERT SQL has correct table, columns, and placeholders."""
        loader = _TestLoader()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42

        raw = {"id": "T-001", "data": "some value"}
        result = loader._insert_staging(mock_cursor, load_id=10, key_vals={"test_id": "T-001"}, raw=raw)

        assert result == 42
        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]

        # SQL structure checks
        assert "INSERT INTO stg_test" in sql
        assert "load_id" in sql
        assert "test_id" in sql
        assert "raw_json" in sql
        assert "raw_record_hash" in sql

        # Params: [load_id, test_id, raw_json, raw_record_hash]
        assert params[0] == 10       # load_id
        assert params[1] == "T-001"  # test_id
        raw_json_str = json.dumps(raw, sort_keys=True, default=str)
        assert params[2] == raw_json_str  # raw_json

    def test_multi_key_columns(self):
        """Loader with two key columns should produce correct SQL."""
        loader = _TestLoaderMultiKey()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 99

        raw = {"a": "A1", "b": "B1", "extra": "x"}
        key_vals = {"key_a": "A1", "key_b": "B1"}
        result = loader._insert_staging(mock_cursor, load_id=5, key_vals=key_vals, raw=raw)

        assert result == 99
        sql, params = mock_cursor.execute.call_args[0]

        assert "key_a" in sql
        assert "key_b" in sql
        # 5 placeholders: load_id, key_a, key_b, raw_json, raw_record_hash
        assert sql.count("%s") == 5
        assert params[0] == 5     # load_id
        assert params[1] == "A1"  # key_a
        assert params[2] == "B1"  # key_b

    def test_returns_lastrowid(self):
        """_insert_staging should return the cursor lastrowid."""
        loader = _TestLoader()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 777

        result = loader._insert_staging(mock_cursor, load_id=1, key_vals={"test_id": "X"}, raw={})
        assert result == 777


# ===================================================================
# _mark_staging tests
# ===================================================================

class TestMarkStaging:

    def test_mark_processed_success(self):
        """processed='Y' should call UPDATE with correct params."""
        loader = _TestLoader()
        mock_cursor = MagicMock()

        loader._mark_staging(mock_cursor, staging_id=42, processed="Y")

        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]

        assert "UPDATE stg_test" in sql
        assert "SET processed=%s" in sql
        assert "error_message=%s" in sql
        assert "WHERE id=%s" in sql
        assert params == ("Y", None, 42)

    def test_mark_processed_error(self):
        """processed='E' with short error_msg should pass through."""
        loader = _TestLoader()
        mock_cursor = MagicMock()

        loader._mark_staging(mock_cursor, staging_id=10, processed="E", error_msg="Something broke")

        _, params = mock_cursor.execute.call_args[0]
        assert params == ("E", "Something broke", 10)

    def test_error_msg_truncated_to_500(self):
        """A 600-character error_msg should be truncated to 500."""
        loader = _TestLoader()
        mock_cursor = MagicMock()

        long_msg = "x" * 600
        loader._mark_staging(mock_cursor, staging_id=5, processed="E", error_msg=long_msg)

        _, params = mock_cursor.execute.call_args[0]
        assert len(params[1]) == 500
        assert params[1] == "x" * 500

    def test_error_msg_none_when_not_provided(self):
        """When error_msg is not given, it defaults to None."""
        loader = _TestLoader()
        mock_cursor = MagicMock()

        loader._mark_staging(mock_cursor, staging_id=1, processed="Y")

        _, params = mock_cursor.execute.call_args[0]
        assert params[1] is None
