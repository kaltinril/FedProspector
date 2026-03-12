"""Tests for ProspectManager status flow validation."""

import pytest
from unittest.mock import MagicMock, patch

from etl.prospect_manager import ProspectManager


# ===================================================================
# Status flow constants
# ===================================================================

class TestStatusFlowConstants:

    def test_new_can_go_to_reviewing(self):
        assert "REVIEWING" in ProspectManager.STATUS_FLOW["NEW"]

    def test_new_can_go_to_declined(self):
        assert "DECLINED" in ProspectManager.STATUS_FLOW["NEW"]

    def test_reviewing_can_go_to_pursuing(self):
        assert "PURSUING" in ProspectManager.STATUS_FLOW["REVIEWING"]

    def test_reviewing_can_go_to_no_bid(self):
        assert "NO_BID" in ProspectManager.STATUS_FLOW["REVIEWING"]

    def test_pursuing_can_go_to_bid_submitted(self):
        assert "BID_SUBMITTED" in ProspectManager.STATUS_FLOW["PURSUING"]

    def test_bid_submitted_can_go_to_won(self):
        assert "WON" in ProspectManager.STATUS_FLOW["BID_SUBMITTED"]

    def test_bid_submitted_can_go_to_lost(self):
        assert "LOST" in ProspectManager.STATUS_FLOW["BID_SUBMITTED"]

    def test_terminal_statuses(self):
        expected = {"WON", "LOST", "DECLINED", "NO_BID"}
        assert ProspectManager.TERMINAL_STATUSES == expected


# ===================================================================
# update_status validation tests
# ===================================================================

class TestUpdateStatus:

    def _setup_mock(self, current_status):
        """Set up mocked connection that returns a prospect with the given status."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            {"prospect_id": 1, "status": current_status},  # prospect lookup
            {"user_id": 10},  # user lookup (dict cursor)
        ]

        return mock_conn, mock_cursor

    def test_valid_transition_new_to_reviewing(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = self._setup_mock("NEW")
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.update_status(1, "REVIEWING", "testuser")

        assert result is True

    def test_valid_transition_reviewing_to_pursuing(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = self._setup_mock("REVIEWING")
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.update_status(1, "PURSUING", "testuser")

        assert result is True

    def test_invalid_transition_new_to_won(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = self._setup_mock("NEW")
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="Invalid status transition"):
                pm.update_status(1, "WON", "testuser")

    def test_invalid_transition_new_to_pursuing(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = self._setup_mock("NEW")
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="Invalid status transition"):
                pm.update_status(1, "PURSUING", "testuser")

    def test_terminal_status_cannot_be_updated(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"prospect_id": 1, "status": "WON"}
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="terminal status"):
                pm.update_status(1, "REVIEWING", "testuser")

    def test_declined_is_terminal(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"prospect_id": 1, "status": "DECLINED"}
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="terminal status"):
                pm.update_status(1, "REVIEWING", "testuser")

    def test_prospect_not_found_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="not found"):
                pm.update_status(999, "REVIEWING", "testuser")

    def test_bid_submitted_sets_date(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = self._setup_mock("PURSUING")
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            pm.update_status(1, "BID_SUBMITTED", "testuser")

        # Verify the UPDATE call includes bid_submitted_date
        update_call = mock_cursor.execute.call_args_list[-2]  # last UPDATE before INSERT note
        sql_or_args = str(update_call)
        assert "bid_submitted_date" in sql_or_args

    def test_won_sets_outcome_fields(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.side_effect = [
                {"prospect_id": 1, "status": "BID_SUBMITTED"},
                {"user_id": 10},
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            pm.update_status(1, "WON", "testuser", notes="Great win!")

        update_call = mock_cursor.execute.call_args_list[-2]
        sql_or_args = str(update_call)
        assert "outcome" in sql_or_args


# ===================================================================
# Priority validation
# ===================================================================

class TestCreateProspectValidation:

    def test_invalid_priority_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="Invalid priority"):
                pm.create_prospect("N1", "user", organization_id=1, priority="URGENT")

    def test_valid_priority_levels(self):
        assert ProspectManager.PRIORITY_LEVELS == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


# ===================================================================
# Note type validation
# ===================================================================

class TestNoteTypeValidation:

    def test_invalid_note_type_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="Invalid note type"):
                pm.add_note(1, "user", "INVALID_TYPE", "text")

    def test_valid_note_types(self):
        expected = ["COMMENT", "STATUS_CHANGE", "ASSIGNMENT", "DECISION", "REVIEW", "MEETING"]
        assert ProspectManager.NOTE_TYPES == expected


# ===================================================================
# Team role validation
# ===================================================================

class TestTeamRoleValidation:

    def test_invalid_role_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="Invalid team role"):
                pm.add_team_member(1, "UEI1", "INVALID_ROLE")

    def test_valid_roles(self):
        assert ProspectManager.TEAM_ROLES == ["PRIME", "SUB", "MENTOR", "JV_PARTNER"]
