"""Database maintenance operations.

Handles periodic cleanup of old data to keep table sizes manageable:
- Archive old history records (> 1 year)
- Purge old staging data (> 30 days)
- Purge old load errors (> 90 days)
- Update table statistics
"""

import logging
from datetime import datetime, timedelta

from db.connection import get_connection
from config import settings


logger = logging.getLogger("fed_prospector.maintenance")

# Batch size for DELETE operations to avoid long locks
DELETE_BATCH_SIZE = 10000


class DatabaseMaintenance:
    """Perform database cleanup and maintenance tasks."""

    def run_all(self, dry_run=False):
        """Run all maintenance tasks. Returns summary dict."""
        summary = {}
        summary["entity_history"] = self.archive_entity_history(dry_run=dry_run)
        summary["opportunity_history"] = self.archive_opportunity_history(dry_run=dry_run)
        summary["staging_data"] = self.purge_staging(dry_run=dry_run)
        summary["load_errors"] = self.purge_load_errors(dry_run=dry_run)
        return summary

    def archive_entity_history(self, days=365, dry_run=False):
        """Delete entity_history records older than N days.

        Args:
            days: Records older than this many days will be deleted.
            dry_run: If True, count only without deleting.

        Returns:
            int: Number of records deleted (or would-be-deleted if dry_run).
        """
        cutoff = datetime.now() - timedelta(days=days)
        return self._batch_delete(
            table="entity_history",
            where_clause="changed_at < %s",
            params=(cutoff,),
            dry_run=dry_run,
            description=f"entity_history older than {days} days",
        )

    def archive_opportunity_history(self, days=365, dry_run=False):
        """Delete opportunity_history records older than N days.

        Args:
            days: Records older than this many days will be deleted.
            dry_run: If True, count only without deleting.

        Returns:
            int: Number of records deleted (or would-be-deleted if dry_run).
        """
        cutoff = datetime.now() - timedelta(days=days)
        return self._batch_delete(
            table="opportunity_history",
            where_clause="changed_at < %s",
            params=(cutoff,),
            dry_run=dry_run,
            description=f"opportunity_history older than {days} days",
        )

    def purge_staging(self, days=30, dry_run=False):
        """Delete old stg_entity_raw records.

        Args:
            days: Records older than this many days will be deleted.
            dry_run: If True, count only without deleting.

        Returns:
            int: Number of records deleted (or would-be-deleted if dry_run).
        """
        cutoff = datetime.now() - timedelta(days=days)
        return self._batch_delete(
            table="stg_entity_raw",
            where_clause="created_at < %s",
            params=(cutoff,),
            dry_run=dry_run,
            description=f"stg_entity_raw older than {days} days",
        )

    def purge_load_errors(self, days=90, dry_run=False):
        """Delete old etl_load_error records.

        Args:
            days: Records older than this many days will be deleted.
            dry_run: If True, count only without deleting.

        Returns:
            int: Number of records deleted (or would-be-deleted if dry_run).
        """
        cutoff = datetime.now() - timedelta(days=days)
        return self._batch_delete(
            table="etl_load_error",
            where_clause="created_at < %s",
            params=(cutoff,),
            dry_run=dry_run,
            description=f"etl_load_error older than {days} days",
        )

    def _batch_delete(self, table, where_clause, params, dry_run, description):
        """Delete records in batches to avoid long table locks.

        Args:
            table: Table name.
            where_clause: SQL WHERE clause (without WHERE keyword).
            params: Tuple of parameters for the WHERE clause.
            dry_run: If True, count only.
            description: Human-readable description for logging.

        Returns:
            int: Total records deleted (or counted if dry_run).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Count records to be deleted
            cursor.execute(
                f"SELECT COUNT(*) FROM `{table}` WHERE {where_clause}",
                params,
            )
            total_count = cursor.fetchone()[0]

            if dry_run:
                logger.info(
                    "[DRY RUN] Would delete %d records from %s",
                    total_count, description,
                )
                return total_count

            if total_count == 0:
                logger.info("No records to delete from %s", description)
                return 0

            # Delete in batches
            total_deleted = 0
            while total_deleted < total_count:
                cursor.execute(
                    f"DELETE FROM `{table}` WHERE {where_clause} LIMIT {DELETE_BATCH_SIZE}",
                    params,
                )
                batch_deleted = cursor.rowcount
                conn.commit()
                total_deleted += batch_deleted
                logger.info(
                    "Deleted %d/%d records from %s",
                    total_deleted, total_count, description,
                )

                if batch_deleted == 0:
                    break

            logger.info(
                "Finished: deleted %d records from %s",
                total_deleted, description,
            )
            return total_deleted
        except Exception as e:
            conn.rollback()
            logger.error("Error deleting from %s: %s", description, e)
            raise
        finally:
            cursor.close()
            conn.close()

    def analyze_tables(self):
        """Run ANALYZE TABLE on all tables for optimizer stats."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (settings.DB_NAME,),
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"ANALYZE TABLE `{table}`")
                logger.info("Analyzed table: %s", table)

            logger.info("Analyzed %d tables", len(tables))
        finally:
            cursor.close()
            conn.close()

    def get_table_sizes(self):
        """Get table sizes in MB from information_schema."""
        results = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT TABLE_NAME, "
                "  ROUND(DATA_LENGTH / 1024 / 1024, 2) AS data_mb, "
                "  ROUND(INDEX_LENGTH / 1024 / 1024, 2) AS index_mb, "
                "  TABLE_ROWS AS rows "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY (DATA_LENGTH + INDEX_LENGTH) DESC",
                (settings.DB_NAME,),
            )
            for row in cursor.fetchall():
                results.append({
                    "table_name": row["TABLE_NAME"],
                    "data_mb": float(row["data_mb"] or 0),
                    "index_mb": float(row["index_mb"] or 0),
                    "rows": row["rows"] or 0,
                })
            return results
        finally:
            cursor.close()
            conn.close()
