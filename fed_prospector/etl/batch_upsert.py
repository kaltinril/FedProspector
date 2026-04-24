"""Batch upsert helpers for ETL loaders.

Provides reusable functions to build INSERT ... ON DUPLICATE KEY UPDATE SQL
and execute it via cursor.executemany() for batch performance.

Used by awards, fedhier, usaspending, and opportunity loaders.
"""

import logging
import time

import mysql.connector

logger = logging.getLogger(__name__)

# Deadlock retry settings
_MAX_DEADLOCK_RETRIES = 3
_DEADLOCK_BACKOFF_FACTOR = 0.5  # seconds, multiplied by 2^attempt


def build_upsert_sql(table: str, columns: list[str], pk_fields: set[str],
                     timestamp_cols: dict[str, str] | None = None) -> str:
    """Build a static INSERT ... ON DUPLICATE KEY UPDATE SQL string.

    Called once at loader init or class definition time, not per record.

    Args:
        table: Target table name.
        columns: Ordered list of column names for the INSERT (including PK
            and last_load_id, but excluding auto-managed timestamp columns).
        pk_fields: Set of column names that form the primary/unique key.
            These are excluded from the UPDATE clause.
        timestamp_cols: Optional dict mapping column names to SQL expressions
            for auto-managed timestamp columns. Defaults to
            {"first_loaded_at": "NOW()", "last_loaded_at": "NOW()"}.

    Returns:
        SQL string with %s placeholders matching the columns list.
    """
    if timestamp_cols is None:
        timestamp_cols = {
            "first_loaded_at": "NOW()",
            "last_loaded_at": "NOW()",
        }

    placeholders = ", ".join(["%s"] * len(columns))
    col_list = ", ".join(columns)

    # Append timestamp columns to the INSERT column list
    ts_col_names = ", ".join(timestamp_cols.keys())
    ts_col_values = ", ".join(timestamp_cols.values())

    # ON DUPLICATE KEY UPDATE: all non-PK columns + last_loaded_at.
    # Row-alias `AS new` syntax (MySQL 8.0.20+); VALUES() is deprecated.
    update_parts = []
    for c in columns:
        if c not in pk_fields:
            update_parts.append(f"{c} = new.{c}")

    # Always update last_loaded_at on duplicate
    if "last_loaded_at" in timestamp_cols:
        update_parts.append(f"last_loaded_at = {timestamp_cols['last_loaded_at']}")

    update_clause = ", ".join(update_parts)

    sql = (
        f"INSERT INTO {table} ({col_list}, {ts_col_names}) "
        f"VALUES ({placeholders}, {ts_col_values}) AS new "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )
    return sql


def executemany_upsert(cursor, sql: str, rows: list[tuple]) -> int:
    """Execute a batch upsert using cursor.executemany().

    Args:
        cursor: Active DB cursor.
        sql: Pre-built INSERT ... ON DUPLICATE KEY UPDATE SQL from build_upsert_sql().
        rows: List of value tuples, each matching the columns order in the SQL.

    Returns:
        Total affected rowcount from MySQL. For ON DUPLICATE KEY UPDATE:
        1 = inserted, 2 = updated per row. The total is the sum across all rows.
    """
    if not rows:
        return 0

    for attempt in range(_MAX_DEADLOCK_RETRIES + 1):
        try:
            cursor.executemany(sql, rows)
            return cursor.rowcount
        except mysql.connector.errors.DatabaseError as e:
            if e.errno == 1213 and attempt < _MAX_DEADLOCK_RETRIES:
                wait = _DEADLOCK_BACKOFF_FACTOR * (2 ** attempt)
                logger.warning(
                    "Deadlock on batch upsert (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, _MAX_DEADLOCK_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
