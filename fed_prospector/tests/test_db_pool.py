"""Tests for db.connection -- connection pool creation and parameter construction."""

import pytest
from unittest.mock import MagicMock, patch, call

import db.connection as db_mod

# Keep a reference to the real get_connection before conftest patches it.
_real_get_connection = db_mod.get_connection


class TestGetPool:

    def test_pool_created_with_correct_params(self):
        """Verify pool is created with expected MySQL parameters."""
        db_mod._pool = None  # Reset global pool
        with patch("db.connection.pooling.MySQLConnectionPool") as mock_pool_cls:
            mock_pool_cls.return_value = MagicMock()
            pool = db_mod.get_pool()

            mock_pool_cls.assert_called_once()
            kwargs = mock_pool_cls.call_args[1]
            assert kwargs["pool_name"] == "fed_pool"
            assert kwargs["pool_size"] == 10
            assert kwargs["charset"] == "utf8mb4"
            assert kwargs["collation"] == "utf8mb4_unicode_ci"
            assert kwargs["autocommit"] is False

        # Reset for other tests
        db_mod._pool = None

    def test_pool_singleton(self):
        """Second call to get_pool should return the same object."""
        db_mod._pool = None
        with patch("db.connection.pooling.MySQLConnectionPool") as mock_pool_cls:
            mock_instance = MagicMock()
            mock_pool_cls.return_value = mock_instance

            pool1 = db_mod.get_pool()
            pool2 = db_mod.get_pool()

            assert pool1 is pool2
            # Should only be called once (singleton)
            mock_pool_cls.assert_called_once()

        db_mod._pool = None

    def test_pool_uses_settings(self):
        """Verify host/port/db/user/password come from settings."""
        db_mod._pool = None
        with patch("db.connection.pooling.MySQLConnectionPool") as mock_pool_cls:
            import config.settings as settings
            mock_pool_cls.return_value = MagicMock()
            pool = db_mod.get_pool()

            kwargs = mock_pool_cls.call_args[1]
            assert kwargs["host"] == settings.DB_HOST
            assert kwargs["port"] == settings.DB_PORT
            assert kwargs["database"] == settings.DB_NAME
            assert kwargs["user"] == settings.DB_USER
            assert kwargs["password"] == settings.DB_PASSWORD

        db_mod._pool = None


class TestGetConnection:

    def test_get_connection_returns_from_pool(self):
        db_mod._pool = None
        with patch("db.connection.pooling.MySQLConnectionPool") as mock_pool_cls:
            mock_pool = MagicMock()
            mock_conn = MagicMock()
            mock_pool.get_connection.return_value = mock_conn
            mock_pool_cls.return_value = mock_pool

            # Use the real function (conftest replaces db_mod.get_connection
            # with an autouse mock; _real_get_connection bypasses that).
            conn = _real_get_connection()
            assert conn is mock_conn
            mock_pool.get_connection.assert_called_once()

        db_mod._pool = None


class TestExecuteSqlFile:

    def test_executes_statements(self, tmp_path):
        sql_file = tmp_path / "test.sql"
        sql_file.write_text(
            "CREATE TABLE test (id INT);\n"
            "INSERT INTO test VALUES (1);\n"
        )

        with patch("db.connection.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            db_mod.execute_sql_file(str(sql_file))

            assert mock_cursor.execute.call_count == 2
            mock_conn.commit.assert_called_once()
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_skips_comments(self, tmp_path):
        sql_file = tmp_path / "test.sql"
        # The source splits on ";" first, then checks startswith("--").
        # A comment must be in its own ";"-delimited segment to be skipped.
        sql_file.write_text(
            "-- This is a comment;\n"
            "CREATE TABLE test (id INT);\n"
        )

        with patch("db.connection.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            db_mod.execute_sql_file(str(sql_file))

            assert mock_cursor.execute.call_count == 1

    def test_rollback_on_error(self, tmp_path):
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("INVALID SQL STATEMENT;\n")

        with patch("db.connection.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("SQL error")
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            with pytest.raises(Exception, match="SQL error"):
                db_mod.execute_sql_file(str(sql_file))

            mock_conn.rollback.assert_called_once()


# ===================================================================
# get_cursor context manager tests
# ===================================================================

class TestGetCursor:

    def test_get_cursor_yields_cursor(self):
        """get_cursor should yield a cursor object from the connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.connection.get_connection", return_value=mock_conn):
            with db_mod.get_cursor() as cursor:
                assert cursor is mock_cursor
            mock_conn.cursor.assert_called_once_with(dictionary=False)

    def test_get_cursor_closes_on_exit(self):
        """Both cursor and connection must be closed after normal exit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.connection.get_connection", return_value=mock_conn):
            with db_mod.get_cursor() as cursor:
                pass  # normal exit

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_get_cursor_closes_on_exception(self):
        """Both cursor and connection must be closed even if body raises."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.connection.get_connection", return_value=mock_conn):
            with pytest.raises(ValueError, match="boom"):
                with db_mod.get_cursor() as cursor:
                    raise ValueError("boom")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_get_cursor_dictionary_param(self):
        """dictionary=True should be forwarded to conn.cursor()."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.connection.get_connection", return_value=mock_conn):
            with db_mod.get_cursor(dictionary=True) as cursor:
                assert cursor is mock_cursor
            mock_conn.cursor.assert_called_once_with(dictionary=True)
