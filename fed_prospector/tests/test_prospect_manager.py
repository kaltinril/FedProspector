"""Tests for ProspectManager -- user management, prospect CRUD, notes,
team members, saved searches, reassignment, and dashboard.

Scoring and status-flow tests live in test_prospect_scoring.py and
test_status_flow.py respectively.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import mysql.connector

from etl.prospect_manager import ProspectManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager():
    """Return a ProspectManager (no DB init needed)."""
    return ProspectManager()


def _mock_connection(cursor=None):
    """Create a (mock_conn, mock_cursor) pair wired together."""
    mock_conn = MagicMock()
    mock_cursor = cursor or MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ===================================================================
# User management
# ===================================================================

class TestAddUser:

    def test_add_user_returns_user_id(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None  # username not taken
            mock_cursor.lastrowid = 42
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_user("jdoe", "Jane Doe", email="jdoe@test.com")

        assert result == 42
        mock_conn.commit.assert_called_once()

    def test_add_user_duplicate_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = (1,)  # username exists
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="already exists"):
                pm.add_user("jdoe", "Jane Doe")

    def test_add_user_default_role(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.add_user("jdoe", "Jane Doe")

        # The INSERT should contain 'MEMBER' as the role
        insert_call = mock_cursor.execute.call_args_list[1]
        assert "MEMBER" in str(insert_call)

    def test_add_user_custom_role(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.add_user("admin", "Admin User", role="ADMIN")

        insert_call = mock_cursor.execute.call_args_list[1]
        assert "ADMIN" in str(insert_call)

    def test_add_user_rollback_on_error(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_cursor.execute.side_effect = [None, mysql.connector.Error("DB error")]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(mysql.connector.Error, match="DB error"):
                pm.add_user("jdoe", "Jane Doe")

        mock_conn.rollback.assert_called_once()


class TestListUsers:

    def test_list_users_active_only(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = [
                {"user_id": 1, "username": "alice"},
                {"user_id": 2, "username": "bob"},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_users(active_only=True)

        assert len(result) == 2
        sql = mock_cursor.execute.call_args[0][0]
        assert "is_active = 'Y'" in sql

    def test_list_users_all(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_users(active_only=False)

        assert result == []
        sql = mock_cursor.execute.call_args[0][0]
        # When active_only=False, no WHERE clause should filter by is_active
        assert "WHERE" not in sql


class TestDeactivateUser:

    def test_deactivate_existing_user(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.rowcount = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.deactivate_user("jdoe")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_deactivate_nonexistent_user_returns_false(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.rowcount = 0
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.deactivate_user("nobody")

        assert result is False


# ===================================================================
# Prospect CRUD
# ===================================================================

class TestCreateProspect:

    def test_create_prospect_happy_path(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # notice_id exists
                (10,),  # user_id lookup
            ]
            mock_cursor.lastrowid = 100
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.create_prospect("N123", "jdoe", priority="HIGH")

        assert result == 100
        mock_conn.commit.assert_called_once()

    def test_create_prospect_auto_creates_status_note(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # notice_id
                (10,),  # user_id
            ]
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.create_prospect("N1", "jdoe", notes="Initial review")

        # The last execute should be the note INSERT
        note_call = mock_cursor.execute.call_args_list[-1]
        sql = note_call[0][0]
        assert "prospect_note" in sql
        assert "STATUS_CHANGE" in str(note_call)

    def test_create_prospect_invalid_notice_id_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None  # notice_id not found
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.create_prospect("BAD_NOTICE", "jdoe")

    def test_create_prospect_invalid_user_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # notice_id exists
                None,   # user not found
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.create_prospect("N1", "baduser")

    def test_create_prospect_default_priority(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [(1,), (10,)]
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.create_prospect("N1", "jdoe")

        # Check that MEDIUM priority is used
        insert_call = mock_cursor.execute.call_args_list[2]  # 0=notice, 1=user, 2=INSERT
        assert "MEDIUM" in str(insert_call)


class TestListProspects:

    def test_list_all_no_filters(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = [
                {"prospect_id": 1, "status": "NEW"},
                {"prospect_id": 2, "status": "REVIEWING"},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_prospects()

        assert len(result) == 2

    def test_list_with_status_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.list_prospects(status="NEW")

        sql = mock_cursor.execute.call_args[0][0]
        assert "p.status = %s" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert "NEW" in params

    def test_list_open_only_excludes_terminal(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.list_prospects(open_only=True)

        sql = mock_cursor.execute.call_args[0][0]
        assert "NOT IN" in sql

    def test_list_with_assigned_to_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.list_prospects(assigned_to="alice")

        sql = mock_cursor.execute.call_args[0][0]
        assert "u.username = %s" in sql

    def test_list_with_priority_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.list_prospects(priority="HIGH")

        sql = mock_cursor.execute.call_args[0][0]
        assert "p.priority = %s" in sql


class TestGetProspectDetail:

    def test_prospect_found_returns_full_detail(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "prospect_id": 1, "notice_id": "N1", "title": "Test Opp"
            }
            mock_cursor.fetchall.side_effect = [
                [{"note_id": 1, "note_text": "note"}],          # notes
                [{"id": 1, "uei_sam": "UEI1", "role": "PRIME"}], # team_members
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_prospect_detail(1)

        assert result is not None
        assert result["prospect"]["prospect_id"] == 1
        assert len(result["notes"]) == 1
        assert len(result["team_members"]) == 1

    def test_prospect_not_found_returns_none(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_prospect_detail(999)

        assert result is None


# ===================================================================
# Reassignment
# ===================================================================

class TestReassignProspect:

    def test_reassign_success(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                {"prospect_id": 1, "assigned_to": 10, "old_username": "alice"},
                {"user_id": 20},  # new user
                {"user_id": 30},  # by user
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.reassign_prospect(1, "bob", "admin")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_reassign_prospect_not_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.reassign_prospect(999, "bob", "admin")

    def test_reassign_creates_assignment_note(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                {"prospect_id": 1, "assigned_to": 10, "old_username": "alice"},
                {"user_id": 20},
                {"user_id": 30},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.reassign_prospect(1, "bob", "admin", notes="Urgent reassign")

        # Last execute should be the note INSERT
        note_call = mock_cursor.execute.call_args_list[-1]
        assert "ASSIGNMENT" in str(note_call)
        assert "Reassigned from alice to bob" in str(note_call)

    def test_reassign_unassigned_prospect(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                {"prospect_id": 1, "assigned_to": None, "old_username": None},
                {"user_id": 20},
                {"user_id": 30},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.reassign_prospect(1, "bob", "admin")

        note_call = mock_cursor.execute.call_args_list[-1]
        assert "(unassigned)" in str(note_call)


# ===================================================================
# Notes
# ===================================================================

class TestAddNote:

    def test_add_note_happy_path(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # prospect exists
                (10,),  # user lookup
            ]
            mock_cursor.lastrowid = 55
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_note(1, "jdoe", "COMMENT", "This looks promising")

        assert result == 55
        mock_conn.commit.assert_called_once()

    def test_add_note_invalid_type_raises(self):
        pm = _make_manager()
        with pytest.raises(ValueError, match="Invalid note type"):
            pm.add_note(1, "jdoe", "BOGUS", "text")

    def test_add_note_prospect_not_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="Prospect .* not found"):
                pm.add_note(999, "jdoe", "COMMENT", "text")

    def test_add_note_user_not_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # prospect exists
                None,   # user not found
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.add_note(1, "nobody", "COMMENT", "text")

    @pytest.mark.parametrize("note_type", ProspectManager.NOTE_TYPES)
    def test_all_valid_note_types_accepted(self, note_type):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [(1,), (10,)]
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_note(1, "jdoe", note_type, "text")

        assert result == 1


class TestListNotes:

    def test_list_notes_returns_chronological(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = [
                {"note_id": 1, "note_type": "STATUS_CHANGE"},
                {"note_id": 2, "note_type": "COMMENT"},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_notes(1)

        assert len(result) == 2
        sql = mock_cursor.execute.call_args[0][0]
        assert "ORDER BY" in sql
        assert "ASC" in sql

    def test_list_notes_empty(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_notes(1)

        assert result == []


# ===================================================================
# Team members
# ===================================================================

class TestAddTeamMember:

    def test_add_team_member_happy_path(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # prospect exists
                (1,),   # entity UEI exists
            ]
            mock_cursor.lastrowid = 7
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_team_member(1, "UEI12345", "PRIME", notes="Prime contractor")

        assert result == 7
        mock_conn.commit.assert_called_once()

    def test_add_team_member_invalid_role_raises(self):
        pm = _make_manager()
        with pytest.raises(ValueError, match="Invalid team role"):
            pm.add_team_member(1, "UEI1", "INVALID_ROLE")

    def test_add_team_member_prospect_not_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="Prospect .* not found"):
                pm.add_team_member(999, "UEI1", "PRIME")

    def test_add_team_member_unknown_uei_still_succeeds(self):
        """UEI not in entity table should log warning but still insert."""
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [
                (1,),   # prospect exists
                None,   # UEI NOT found
            ]
            mock_cursor.lastrowid = 8
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_team_member(1, "UNKNOWN_UEI", "SUB")

        assert result == 8

    @pytest.mark.parametrize("role", ProspectManager.TEAM_ROLES)
    def test_all_valid_roles_accepted(self, role):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.side_effect = [(1,), (1,)]
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.add_team_member(1, "UEI1", role)

        assert result == 1


class TestListTeamMembers:

    def test_list_team_members(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = [
                {"id": 1, "uei_sam": "UEI1", "role": "PRIME", "legal_business_name": "Acme"},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_team_members(1)

        assert len(result) == 1
        assert result[0]["role"] == "PRIME"

    def test_list_team_members_empty(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_team_members(1)

        assert result == []


# ===================================================================
# Saved searches
# ===================================================================

class TestSaveSearch:

    def test_save_search_happy_path(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = (10,)  # user_id
            mock_cursor.lastrowid = 5
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            criteria = {"set_aside_codes": ["WOSB"], "naics_codes": ["541511"]}
            result = pm.save_search("WOSB IT", "jdoe", criteria, description="IT opportunities")

        assert result == 5
        mock_conn.commit.assert_called_once()

    def test_save_search_stores_json_criteria(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = (10,)
            mock_cursor.lastrowid = 1
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            criteria = {"states": ["VA", "MD"]}
            pm.save_search("VA/MD", "jdoe", criteria)

        # Verify criteria was serialized to JSON
        insert_call = mock_cursor.execute.call_args_list[-1]
        params = insert_call[0][1]
        # params[3] is the criteria_json
        parsed = json.loads(params[3])
        assert parsed == {"states": ["VA", "MD"]}

    def test_save_search_user_not_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.save_search("test", "nobody", {})


class TestRunSearch:

    def test_run_search_by_id(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": json.dumps({"set_aside_codes": ["WOSB"]}),
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = [
                {"notice_id": "N1", "title": "Opp 1", "first_loaded_at": datetime.now()},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.run_search(search_id=1)

        assert result["count"] == 1
        assert result["new_count"] == 1  # first run, all are new

    def test_run_search_by_name(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 2,
                "search_name": "WOSB IT",
                "filter_criteria": {"open_only": True},
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.run_search(search_name="WOSB IT")

        assert result["count"] == 0
        assert result["search"]["search_name"] == "WOSB IT"

    def test_run_search_no_args_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="Either search_id or search_name"):
                pm.run_search()

    def test_run_search_not_found_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            with pytest.raises(ValueError, match="not found"):
                pm.run_search(search_id=999)

    def test_run_search_new_count_since_last_run(self):
        """Results loaded after last_run should be counted as new."""
        last_run = datetime(2026, 1, 1)
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": "{}",
                "last_run_at": last_run,
            }
            mock_cursor.fetchall.return_value = [
                {"notice_id": "N1", "first_loaded_at": datetime(2025, 12, 1)},  # old
                {"notice_id": "N2", "first_loaded_at": datetime(2026, 2, 1)},   # new
                {"notice_id": "N3", "first_loaded_at": datetime(2026, 3, 1)},   # new
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.run_search(search_id=1)

        assert result["count"] == 3
        assert result["new_count"] == 2

    def test_run_search_builds_set_aside_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": json.dumps({"set_aside_codes": ["WOSB", "8A"]}),
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.run_search(search_id=1)

        # Check the opportunity query includes set_aside_code IN clause
        opp_query_call = mock_cursor.execute.call_args_list[1]  # [0]=search lookup, [1]=opp query
        sql = opp_query_call[0][0]
        assert "set_aside_code IN" in sql

    def test_run_search_builds_naics_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": json.dumps({"naics_codes": ["541511", "541512"]}),
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.run_search(search_id=1)

        opp_query_call = mock_cursor.execute.call_args_list[1]
        sql = opp_query_call[0][0]
        assert "naics_code IN" in sql

    def test_run_search_open_only_filter(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": json.dumps({"open_only": True}),
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.run_search(search_id=1)

        opp_query_call = mock_cursor.execute.call_args_list[1]
        sql = opp_query_call[0][0]
        assert "response_deadline > NOW()" in sql
        assert "active = 'Y'" in sql

    def test_run_search_updates_last_run(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchone.return_value = {
                "search_id": 1,
                "search_name": "Test",
                "filter_criteria": "{}",
                "last_run_at": None,
            }
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.run_search(search_id=1)

        # Check the UPDATE saved_search call
        update_call = mock_cursor.execute.call_args_list[-1]
        sql = update_call[0][0]
        assert "UPDATE saved_search" in sql
        assert "last_run_at" in sql


class TestListSavedSearches:

    def test_list_all_searches(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = [
                {"search_id": 1, "search_name": "WOSB IT"},
                {"search_id": 2, "search_name": "8A Construction"},
            ]
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.list_saved_searches()

        assert len(result) == 2

    def test_list_searches_by_username(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.return_value = []
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            pm.list_saved_searches(username="jdoe")

        sql = mock_cursor.execute.call_args[0][0]
        assert "u.username = %s" in sql


# ===================================================================
# Dashboard
# ===================================================================

class TestGetDashboardData:

    def test_dashboard_returns_all_keys(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            # fetchall is called 4 times (by_status, due_this_week, by_assignee, saved_searches)
            mock_cursor.fetchall.side_effect = [
                [{"status": "NEW", "cnt": 5}, {"status": "REVIEWING", "cnt": 3}],
                [{"prospect_id": 1, "title": "Urgent"}],
                [{"username": "jdoe", "display_name": "Jane", "cnt": 4}],
                [{"outcome": "WON", "cnt": 2}],
                [{"search_id": 1, "search_name": "S1"}],
            ]
            # fetchone is called once (total_open)
            mock_cursor.fetchone.return_value = {"cnt": 8}
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_dashboard_data()

        assert "by_status" in result
        assert "due_this_week" in result
        assert "by_assignee" in result
        assert "win_loss" in result
        assert "saved_searches" in result
        assert "total_open" in result

    def test_dashboard_by_status_dict(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.side_effect = [
                [{"status": "NEW", "cnt": 5}],
                [], [], [], [],
            ]
            mock_cursor.fetchone.return_value = {"cnt": 5}
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_dashboard_data()

        assert result["by_status"] == {"NEW": 5}

    def test_dashboard_total_open(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.side_effect = [[], [], [], [], []]
            mock_cursor.fetchone.return_value = {"cnt": 12}
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_dashboard_data()

        assert result["total_open"] == 12

    def test_dashboard_total_open_none_row(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn, mock_cursor = _mock_connection()
            mock_cursor.fetchall.side_effect = [[], [], [], [], []]
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = _make_manager()
            result = pm.get_dashboard_data()

        assert result["total_open"] == 0


# ===================================================================
# Internal helpers
# ===================================================================

class TestGetUserId:

    def test_get_user_id_tuple_cursor(self):
        with patch("etl.prospect_manager.get_connection"):
            pm = _make_manager()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (42,)

            result = pm._get_user_id(mock_cursor, "jdoe")

        assert result == 42

    def test_get_user_id_dict_cursor(self):
        with patch("etl.prospect_manager.get_connection"):
            pm = _make_manager()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"user_id": 42}

            result = pm._get_user_id(mock_cursor, "jdoe")

        assert result == 42

    def test_get_user_id_not_found_raises(self):
        with patch("etl.prospect_manager.get_connection"):
            pm = _make_manager()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None

            with pytest.raises(ValueError, match="not found"):
                pm._get_user_id(mock_cursor, "nobody")


class TestValidateNoticeId:

    def test_validate_existing_notice_id(self):
        with patch("etl.prospect_manager.get_connection"):
            pm = _make_manager()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ("N1",)

            # Should not raise
            pm._validate_notice_id(mock_cursor, "N1")

    def test_validate_missing_notice_id_raises(self):
        with patch("etl.prospect_manager.get_connection"):
            pm = _make_manager()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None

            with pytest.raises(ValueError, match="not found"):
                pm._validate_notice_id(mock_cursor, "BAD_ID")
