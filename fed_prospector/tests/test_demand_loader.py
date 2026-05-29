"""Tests for etl.demand_loader DESCRIPTION_FETCH handling (Phase 123 Unit C).

Covers:
  * Successful DESCRIPTION_FETCH writes description_text to opportunity
    and marks the row COMPLETED.
  * Rate-limited DESCRIPTION_FETCH transitions the row to PENDING_RETRY
    with retry_after set from the exception's reset_at (does NOT mark FAILED).
  * Row-selection SQL includes PENDING_RETRY rows whose retry_after has
    elapsed.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from etl.demand_loader import DemandLoader
from api_clients.sam_opportunities_client import DescriptionFetchRateLimited


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_mock_conn():
    """Mock connection whose cursor() returns a fresh mock cursor each call."""
    mock_conn = MagicMock()
    # Each cursor() call returns a fresh MagicMock so we can assert separately
    # on dict/positional cursors. rowcount on update cursor is patched per test.
    mock_conn.cursor.side_effect = lambda *args, **kwargs: MagicMock()
    return mock_conn


def _make_loader():
    """Build a DemandLoader without actually constructing API clients.

    BaseAPIClient.__init__ touches settings + the DB rate-limit table; the
    conftest auto-fixtures already neuter those, but we still avoid full
    construction by replacing the inner clients on the instance.
    """
    loader = DemandLoader()
    loader.sam_opportunities_client = MagicMock()
    return loader


# ===================================================================
# DESCRIPTION_FETCH: success path
# ===================================================================

class TestDescriptionFetchSuccess:

    def test_success_writes_description_and_marks_completed(self):
        loader = _make_loader()
        loader.sam_opportunities_client.fetch_description_text.return_value = (
            "Plain text description here."
        )

        # We need _set_status to update via a fresh cursor too. Patch the
        # module-level get_connection used inside _process_description_fetch
        # and _set_status.
        with patch("etl.demand_loader.get_connection") as mock_gc:
            update_conn = MagicMock()
            update_cursor = MagicMock()
            update_cursor.rowcount = 1
            update_conn.cursor.return_value = update_cursor

            status_conn = MagicMock()
            status_cursor = MagicMock()
            status_conn.cursor.return_value = status_cursor

            # _set_status is called twice (PROCESSING + COMPLETED) and the
            # opportunity UPDATE is called once. side_effect provides a fresh
            # connection per get_connection() call.
            mock_gc.side_effect = [status_conn, update_conn, status_conn]

            req = {
                "request_id": 501,
                "lookup_key": "notice-xyz-123",
                "lookup_key_type": "NOTICE_ID",
                "request_type": "DESCRIPTION_FETCH",
                "requested_by": 7,
            }
            loader._process_description_fetch(req)

        # noticedesc was fetched
        loader.sam_opportunities_client.fetch_description_text.assert_called_once_with(
            "notice-xyz-123"
        )

        # opportunity row was updated with the description
        update_calls = update_cursor.execute.call_args_list
        assert any(
            "UPDATE opportunity" in c[0][0]
            and "description_text" in c[0][0]
            for c in update_calls
        ), f"opportunity UPDATE not found in {update_calls!r}"

        # Final status set to COMPLETED — check the status update SQL/params
        status_calls = status_cursor.execute.call_args_list
        assert any(
            "UPDATE data_load_request" in c[0][0]
            and "COMPLETED" in c[0][1]
            for c in status_calls
        ), f"COMPLETED status update not found in {status_calls!r}"


# ===================================================================
# DESCRIPTION_FETCH: rate-limit path
# ===================================================================

class TestDescriptionFetchRateLimited:

    def test_rate_limited_transitions_to_pending_retry_with_retry_after(self):
        loader = _make_loader()
        reset_at = datetime(2026, 5, 29, 0, 0, 0, tzinfo=timezone.utc)
        loader.sam_opportunities_client.fetch_description_text.side_effect = (
            DescriptionFetchRateLimited("daily quota exhausted", reset_at=reset_at)
        )

        with patch("etl.demand_loader.get_connection") as mock_gc:
            status_conn = MagicMock()
            status_cursor = MagicMock()
            status_conn.cursor.return_value = status_cursor
            mock_gc.return_value = status_conn

            req = {
                "request_id": 502,
                "lookup_key": "notice-rl-456",
                "lookup_key_type": "NOTICE_ID",
                "request_type": "DESCRIPTION_FETCH",
                "requested_by": 7,
            }
            with pytest.raises(DescriptionFetchRateLimited):
                loader._process_description_fetch(req)

        # Inspect the status updates: should include PROCESSING then PENDING_RETRY
        executed_sqls = [c[0] for c in status_cursor.execute.call_args_list]
        statuses_set = []
        retry_after_values = []
        for sql, params in executed_sqls:
            if "UPDATE data_load_request" in sql and "status = %s" in sql:
                statuses_set.append(params[0])
                if "retry_after = %s" in sql:
                    # find the param index for retry_after
                    # sets are appended in order: status, started_at?, completed_at?,
                    # load_id?, error_message?, result_summary?, retry_after
                    retry_after_values.append(params[-2])  # last is request_id

        assert "PROCESSING" in statuses_set, f"expected PROCESSING in {statuses_set!r}"
        assert "PENDING_RETRY" in statuses_set, f"expected PENDING_RETRY in {statuses_set!r}"
        # retry_after should be the naive UTC value derived from reset_at
        expected_naive = reset_at.astimezone(timezone.utc).replace(tzinfo=None)
        assert expected_naive in retry_after_values, (
            f"expected retry_after={expected_naive!r} in {retry_after_values!r}"
        )

        # Should NOT have marked FAILED
        assert "FAILED" not in statuses_set


# ===================================================================
# Row selection — PENDING + eligible PENDING_RETRY
# ===================================================================

class TestRowSelection:

    def test_select_sql_covers_pending_and_eligible_pending_retry(self):
        loader = _make_loader()

        with patch("etl.demand_loader.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            loader.process_pending_requests()

        select_calls = [
            c[0][0] for c in mock_cursor.execute.call_args_list
            if "SELECT" in c[0][0] and "data_load_request" in c[0][0]
        ]
        assert select_calls, "expected a SELECT against data_load_request"
        sql = select_calls[0]
        assert "status = 'PENDING'" in sql
        assert "PENDING_RETRY" in sql
        assert "UTC_TIMESTAMP()" in sql, (
            "row selection must use MySQL UTC clock, not NOW(); got SQL:\n" + sql
        )
