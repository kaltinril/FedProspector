"""MySQL connection pool using mysql-connector-python.

GOTCHA — PooledMySQLConnection autocommit:
    mysql-connector-python's PooledMySQLConnection wrapper does NOT proxy the
    ``autocommit`` property to the underlying MySQLConnection._cnx.  Setting
    ``conn.autocommit = True`` on a pooled connection is silently ignored.

    This module patches PooledMySQLConnection with a proper autocommit
    property so callers can use ``conn.autocommit = True`` normally.
"""

import logging
from contextlib import contextmanager
from mysql.connector import pooling
from config import settings

logger = logging.getLogger("fed_prospector.db")

# ---------------------------------------------------------------------------
# Patch PooledMySQLConnection so .autocommit proxies to the inner connection.
# Without this, setting conn.autocommit = True is silently ignored and
# statements remain uncommitted until an explicit conn.commit().
# ---------------------------------------------------------------------------
if not hasattr(pooling.PooledMySQLConnection, "_autocommit_patched"):

    def _get_autocommit(self):
        return self._cnx.autocommit

    def _set_autocommit(self, value):
        self._cnx.autocommit = value

    pooling.PooledMySQLConnection.autocommit = property(_get_autocommit, _set_autocommit)
    pooling.PooledMySQLConnection._autocommit_patched = True

_pool = None


def get_pool():
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="fed_pool",
            pool_size=5,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=False,
        )
        logger.info("MySQL connection pool created (size=5)")
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return get_pool().get_connection()


@contextmanager
def get_cursor(dictionary=False):
    """
    Context manager that yields an open cursor and closes both cursor and
    connection on exit. For read-only or single-statement operations only.
    Do NOT use where batch commits or explicit transaction control is needed.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def execute_sql_file(file_path):
    """Execute a SQL file against the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            sql = f.read()
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                cursor.execute(stmt)
        conn.commit()
        logger.info(f"Executed SQL file: {file_path}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error executing {file_path}: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
