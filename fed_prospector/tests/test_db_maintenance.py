"""Tests for etl.db_maintenance -- purge staging, purge errors, batch delete."""

import pytest
from unittest.mock import MagicMock, patch

from etl.db_maintenance import DatabaseMaintenance, DELETE_BATCH_SIZE


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _make_mock_conn(count_result=0, batch_rowcount=0):
    """Create a mock connection with cursor pre-configured for batch_delete.

    Args:
        count_result: What COUNT(*) should return.
        batch_rowcount: What DELETE ... LIMIT should report as rowcount.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # fetchone returns (count_result,) for the COUNT query
    mock_cursor.fetchone.return_value = (count_result,)
    mock_cursor.rowcount = batch_rowcount

    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ===================================================================
# purge_staging tests
# ===================================================================

class TestPurgeStaging:

    def test_purge_staging_dry_run_returns_counts(self):
        """dry_run=True should count but not delete."""
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=100)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint.purge_staging(days=30, dry_run=True)

        # Result should be a dict with 7 staging table counts
        assert isinstance(result, dict)
        assert len(result) == 7
        for table_name, count in result.items():
            assert count == 100
            assert table_name.startswith("stg_")

    def test_purge_staging_dry_run_no_delete(self):
        """dry_run=True should NOT execute DELETE statements."""
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=5)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            maint.purge_staging(days=30, dry_run=True)

        # Check that no DELETE was executed
        for call_item in mock_cursor.execute.call_args_list:
            sql = call_item[0][0]
            assert "DELETE" not in sql


# ===================================================================
# purge_load_errors tests
# ===================================================================

class TestPurgeLoadErrors:

    def test_purge_load_errors_dry_run(self):
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=250)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint.purge_load_errors(days=90, dry_run=True)

        assert result == 250

    def test_purge_load_errors_no_records(self):
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=0)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint.purge_load_errors(days=90, dry_run=False)

        assert result == 0


# ===================================================================
# _batch_delete tests
# ===================================================================

class TestBatchDelete:

    def test_batch_delete_dry_run_returns_count(self):
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=500)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint._batch_delete(
                table="test_table",
                where_clause="created_at < %s",
                params=("2025-01-01",),
                dry_run=True,
                description="test cleanup",
            )

        assert result == 500

    def test_batch_delete_executes_in_batches(self):
        """Verify it loops until all records are deleted."""
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()

            # COUNT returns 15000
            mock_cursor.fetchone.return_value = (15000,)

            # First batch deletes 10000, second deletes 5000, then 0 to stop
            mock_cursor.rowcount = 0  # default

            delete_call_count = [0]

            def side_effect(sql, *args):
                if "DELETE" in sql:
                    delete_call_count[0] += 1
                    if delete_call_count[0] == 1:
                        mock_cursor.rowcount = DELETE_BATCH_SIZE
                    elif delete_call_count[0] == 2:
                        mock_cursor.rowcount = 5000
                    else:
                        mock_cursor.rowcount = 0

            mock_cursor.execute.side_effect = side_effect
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint._batch_delete(
                table="test_table",
                where_clause="created_at < %s",
                params=("2025-01-01",),
                dry_run=False,
                description="test cleanup",
            )

        assert result == 15000

    def test_batch_delete_zero_records(self):
        """No records to delete should return 0 immediately."""
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn, mock_cursor = _make_mock_conn(count_result=0)
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            result = maint._batch_delete(
                table="test_table",
                where_clause="created_at < %s",
                params=("2025-01-01",),
                dry_run=False,
                description="test cleanup",
            )

        assert result == 0
        # Should have executed only the COUNT query, no DELETE
        assert mock_cursor.execute.call_count == 1

    def test_batch_delete_error_rolls_back(self):
        """DB error during delete should rollback and re-raise."""
        with patch("etl.db_maintenance.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (100,)

            call_count = [0]

            def side_effect(sql, *args):
                call_count[0] += 1
                if "DELETE" in sql:
                    raise Exception("DB Error")

            mock_cursor.execute.side_effect = side_effect
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            maint = DatabaseMaintenance()
            with pytest.raises(Exception, match="DB Error"):
                maint._batch_delete(
                    table="test_table",
                    where_clause="created_at < %s",
                    params=("2025-01-01",),
                    dry_run=False,
                    description="test cleanup",
                )

        mock_conn.rollback.assert_called_once()


# ===================================================================
# run_all tests
# ===================================================================

class TestRunAll:

    def test_run_all_calls_all_tasks(self):
        maint = DatabaseMaintenance()

        with patch.object(maint, "archive_entity_history", return_value=10) as m1, \
             patch.object(maint, "archive_opportunity_history", return_value=5) as m2, \
             patch.object(maint, "purge_staging", return_value={"stg_a": 3}) as m3, \
             patch.object(maint, "purge_load_errors", return_value=2) as m4:
            summary = maint.run_all(dry_run=True)

        assert summary["entity_history"] == 10
        assert summary["opportunity_history"] == 5
        assert summary["staging_data"] == {"stg_a": 3}
        assert summary["load_errors"] == 2
        m1.assert_called_once_with(dry_run=True)
        m2.assert_called_once_with(dry_run=True)
        m3.assert_called_once_with(dry_run=True)
        m4.assert_called_once_with(dry_run=True)
