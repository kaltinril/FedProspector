"""MySQL connection pool using mysql-connector-python."""

import logging
from mysql.connector import pooling
from config import settings

logger = logging.getLogger("fed_prospector.db")

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
