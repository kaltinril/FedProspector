"""Tests for CLI prospecting commands (cli/prospecting.py).

Tests the Click CLI wiring for: create, update, list, show, assign,
add-note, add-partner, save-search, run-search, list-searches, dashboard,
add-user, list-users.  All external dependencies are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

FED_PROSPECTOR_DIR = Path(__file__).resolve().parent.parent
if str(FED_PROSPECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(FED_PROSPECTOR_DIR))

from main import cli


# ===================================================================
# --help smoke tests
# ===================================================================

class TestProspectHelp:

    def test_prospect_create_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "create", "--help"])
        assert result.exit_code == 0
        assert "Create a new prospect" in result.output

    def test_prospect_update_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "update", "--help"])
        assert result.exit_code == 0
        assert "Update the status" in result.output

    def test_prospect_list_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list", "--help"])
        assert result.exit_code == 0
        assert "List prospects" in result.output

    def test_prospect_show_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "show", "--help"])
        assert result.exit_code == 0
        assert "Show full prospect detail" in result.output

    def test_prospect_assign_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "assign", "--help"])
        assert result.exit_code == 0
        assert "Reassign a prospect" in result.output

    def test_prospect_add_note_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "add-note", "--help"])
        assert result.exit_code == 0
        assert "Add a note" in result.output

    def test_prospect_add_partner_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "add-partner", "--help"])
        assert result.exit_code == 0
        assert "Add a teaming partner" in result.output

    def test_prospect_save_search_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "save-search", "--help"])
        assert result.exit_code == 0
        assert "Save a reusable search filter" in result.output

    def test_prospect_run_search_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "run-search", "--help"])
        assert result.exit_code == 0
        assert "Execute a saved search" in result.output

    def test_prospect_list_searches_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list-searches", "--help"])
        assert result.exit_code == 0
        assert "List saved searches" in result.output

    def test_prospect_dashboard_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "dashboard", "--help"])
        assert result.exit_code == 0
        assert "prospect pipeline dashboard" in result.output

    def test_prospect_add_user_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "add-user", "--help"])
        assert result.exit_code == 0
        assert "Add a team member" in result.output

    def test_prospect_list_users_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list-users", "--help"])
        assert result.exit_code == 0
        assert "List team members" in result.output


# ===================================================================
# create-prospect tests
# ===================================================================

class TestCreateProspect:

    @patch("etl.prospect_manager.ProspectManager")
    def test_create_prospect_calls_manager(self, mock_mgr_cls):
        """create should call ProspectManager.create_prospect with correct args."""
        mock_mgr = MagicMock()
        mock_mgr.create_prospect.return_value = 42
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "create",
            "--notice-id", "ABC123",
            "--assign-to", "jdoe",
            "--org", "1",
            "--priority", "HIGH",
        ])

        assert result.exit_code == 0
        assert "Created prospect 42" in result.output
        assert "ABC123" in result.output
        mock_mgr.create_prospect.assert_called_once_with(
            "ABC123", "jdoe", organization_id=1, priority="HIGH", notes=None
        )

    @patch("etl.prospect_manager.ProspectManager")
    def test_create_prospect_with_notes(self, mock_mgr_cls):
        """create --notes should pass notes through."""
        mock_mgr = MagicMock()
        mock_mgr.create_prospect.return_value = 1
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "create",
            "--notice-id", "XYZ789",
            "--assign-to", "jsmith",
            "--org", "2",
            "--notes", "Looks promising",
        ])

        assert result.exit_code == 0
        mock_mgr.create_prospect.assert_called_once_with(
            "XYZ789", "jsmith", organization_id=2, priority="MEDIUM", notes="Looks promising"
        )

    @patch("etl.prospect_manager.ProspectManager")
    def test_create_prospect_handles_value_error(self, mock_mgr_cls):
        """create should exit 1 on ValueError."""
        mock_mgr = MagicMock()
        mock_mgr.create_prospect.side_effect = ValueError("Notice ID not found")
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "create",
            "--notice-id", "BOGUS",
            "--assign-to", "jdoe",
            "--org", "1",
        ])

        assert result.exit_code == 1
        assert "Notice ID not found" in result.output

    def test_create_prospect_requires_notice_id(self):
        """create without --notice-id should fail."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "create",
            "--assign-to", "jdoe",
            "--org", "1",
        ])
        assert result.exit_code != 0

    def test_create_prospect_validates_priority(self):
        """create --priority=BOGUS should fail Click validation."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "create",
            "--notice-id", "ABC123",
            "--assign-to", "jdoe",
            "--org", "1",
            "--priority", "BOGUS",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


# ===================================================================
# update-prospect tests
# ===================================================================

class TestUpdateProspect:

    @patch("etl.prospect_manager.ProspectManager")
    def test_update_prospect_calls_manager(self, mock_mgr_cls):
        """update should call update_status with correct args."""
        mock_mgr = MagicMock()
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "update",
            "--id", "1",
            "--status", "REVIEWING",
            "--user", "jdoe",
            "--notes", "Looks good",
        ])

        assert result.exit_code == 0
        assert "REVIEWING" in result.output
        mock_mgr.update_status.assert_called_once_with(
            1, "REVIEWING", "jdoe", notes="Looks good"
        )

    def test_update_prospect_validates_status(self):
        """update --status=BOGUS should fail Click validation."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "update",
            "--id", "1",
            "--status", "BOGUS",
            "--user", "jdoe",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_update_prospect_handles_error(self, mock_mgr_cls):
        """update should exit 1 on ValueError from manager."""
        mock_mgr = MagicMock()
        mock_mgr.update_status.side_effect = ValueError("Invalid status transition")
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "update",
            "--id", "1",
            "--status", "WON",
            "--user", "jdoe",
        ])

        assert result.exit_code == 1
        assert "Invalid status transition" in result.output


# ===================================================================
# list-prospects tests
# ===================================================================

class TestListProspects:

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_prospects_no_results(self, mock_mgr_cls):
        """list with no prospects should report it."""
        mock_mgr = MagicMock()
        mock_mgr.list_prospects.return_value = []
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list"])

        assert result.exit_code == 0
        assert "No prospects found" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_prospects_with_filters(self, mock_mgr_cls):
        """list --status=REVIEWING --assigned-to=jdoe should pass filters."""
        mock_mgr = MagicMock()
        mock_mgr.list_prospects.return_value = [
            {
                "prospect_id": 1,
                "status": "REVIEWING",
                "priority": "HIGH",
                "title": "Test Opportunity",
                "set_aside_code": "WOSB",
                "response_deadline": "2026-04-01 00:00:00",
                "assigned_to": "jdoe",
            }
        ]
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "list",
            "--status", "REVIEWING",
            "--assigned-to", "jdoe",
        ])

        assert result.exit_code == 0
        mock_mgr.list_prospects.assert_called_once_with(
            status="REVIEWING",
            assigned_to="jdoe",
            priority=None,
            open_only=False,
        )

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_prospects_open_only(self, mock_mgr_cls):
        """list --open-only should pass open_only=True."""
        mock_mgr = MagicMock()
        mock_mgr.list_prospects.return_value = []
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list", "--open-only"])

        assert result.exit_code == 0
        mock_mgr.list_prospects.assert_called_once_with(
            status=None,
            assigned_to=None,
            priority=None,
            open_only=True,
        )


# ===================================================================
# show-prospect tests
# ===================================================================

class TestShowProspect:

    @patch("etl.prospect_manager.ProspectManager")
    def test_show_prospect_not_found(self, mock_mgr_cls):
        """show --id=999 when not found should exit 1."""
        mock_mgr = MagicMock()
        mock_mgr.get_prospect_detail.return_value = None
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "show", "--id", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_show_prospect_displays_detail(self, mock_mgr_cls):
        """show --id should display prospect detail."""
        mock_mgr = MagicMock()
        mock_mgr.get_prospect_detail.return_value = {
            "prospect": {
                "prospect_id": 1,
                "status": "REVIEWING",
                "priority": "HIGH",
                "notice_id": "ABC123",
                "title": "Test Opportunity",
                "assigned_to_username": "jdoe",
                "assigned_name": "Jane Doe",
                "created_at": "2026-03-01",
                "updated_at": "2026-03-04",
                "department_name": "DoD",
                "set_aside_code": "WOSB",
                "set_aside_description": "Women-Owned Small Business",
                "naics_code": "541512",
            },
            "team_members": [],
            "notes": [],
        }
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "show", "--id", "1"])

        assert result.exit_code == 0
        assert "PROSPECT #1" in result.output
        assert "REVIEWING" in result.output
        assert "Jane Doe" in result.output


# ===================================================================
# reassign-prospect tests
# ===================================================================

class TestReassignProspect:

    @patch("etl.prospect_manager.ProspectManager")
    def test_reassign_prospect(self, mock_mgr_cls):
        """assign should call reassign_prospect with correct args."""
        mock_mgr = MagicMock()
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "assign",
            "--id", "1",
            "--to", "jsmith",
            "--by", "jdoe",
        ])

        assert result.exit_code == 0
        assert "reassigned to 'jsmith'" in result.output
        mock_mgr.reassign_prospect.assert_called_once_with(
            1, "jsmith", "jdoe", notes=None
        )


# ===================================================================
# add-note tests
# ===================================================================

class TestAddNote:

    @patch("etl.prospect_manager.ProspectManager")
    def test_add_note(self, mock_mgr_cls):
        """add-note should call add_note with correct args."""
        mock_mgr = MagicMock()
        mock_mgr.add_note.return_value = 5
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-note",
            "--prospect-id", "1",
            "--user", "jdoe",
            "--type", "COMMENT",
            "--text", "Spoke with CO",
        ])

        assert result.exit_code == 0
        assert "COMMENT" in result.output
        assert "note_id=5" in result.output
        mock_mgr.add_note.assert_called_once_with(1, "jdoe", "COMMENT", "Spoke with CO")

    def test_add_note_validates_type(self):
        """add-note --type=BOGUS should fail Click validation."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-note",
            "--prospect-id", "1",
            "--user", "jdoe",
            "--type", "BOGUS",
            "--text", "test",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


# ===================================================================
# add-team-member tests
# ===================================================================

class TestAddTeamMember:

    @patch("etl.prospect_manager.ProspectManager")
    def test_add_team_member(self, mock_mgr_cls):
        """add-partner should call add_team_member with correct args."""
        mock_mgr = MagicMock()
        mock_mgr.add_team_member.return_value = 3
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-partner",
            "--prospect-id", "1",
            "--uei", "ABC123DEF456",
            "--role", "SUB",
        ])

        assert result.exit_code == 0
        assert "UEI=ABC123DEF456" in result.output
        assert "role=SUB" in result.output
        mock_mgr.add_team_member.assert_called_once_with(
            1, "ABC123DEF456", "SUB", notes=None
        )

    def test_add_team_member_validates_role(self):
        """add-partner --role=BOGUS should fail Click validation."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-partner",
            "--prospect-id", "1",
            "--uei", "ABC123DEF456",
            "--role", "BOGUS",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


# ===================================================================
# save-search tests
# ===================================================================

class TestSaveSearch:

    @patch("etl.prospect_manager.ProspectManager")
    def test_save_search_with_filters(self, mock_mgr_cls):
        """save-search should build criteria dict from options."""
        mock_mgr = MagicMock()
        mock_mgr.save_search.return_value = 10
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "save-search",
            "--name", "WOSB IT",
            "--user", "jdoe",
            "--set-asides", "WOSB,EDWOSB",
            "--naics", "541511,541512",
            "--open-only",
        ])

        assert result.exit_code == 0
        assert "search_id=10" in result.output
        call_args = mock_mgr.save_search.call_args
        criteria = call_args[0][2]
        assert criteria["set_aside_codes"] == ["WOSB", "EDWOSB"]
        assert criteria["naics_codes"] == ["541511", "541512"]
        assert criteria["open_only"] is True

    @patch("etl.prospect_manager.ProspectManager")
    def test_save_search_requires_at_least_one_filter(self, mock_mgr_cls):
        """save-search with no filter options should error."""
        mock_mgr = MagicMock()
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "save-search",
            "--name", "Empty",
            "--user", "jdoe",
        ])

        assert result.exit_code == 1
        assert "At least one filter option is required" in result.output


# ===================================================================
# run-search tests
# ===================================================================

class TestRunSearch:

    def test_run_search_requires_name_or_id(self):
        """run-search without --name or --id should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "run-search"])

        assert result.exit_code == 1
        assert "Either --name or --id is required" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_run_search_by_name(self, mock_mgr_cls):
        """run-search --name should pass search_name."""
        mock_mgr = MagicMock()
        mock_mgr.run_search.return_value = {
            "search": {"search_name": "WOSB IT", "last_run_at": None},
            "results": [],
            "count": 0,
            "new_count": 0,
        }
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "run-search", "--name", "WOSB IT"
        ])

        assert result.exit_code == 0
        assert "WOSB IT" in result.output
        mock_mgr.run_search.assert_called_once_with(
            search_id=None, search_name="WOSB IT"
        )

    @patch("etl.prospect_manager.ProspectManager")
    def test_run_search_by_id(self, mock_mgr_cls):
        """run-search --id should pass search_id."""
        mock_mgr = MagicMock()
        mock_mgr.run_search.return_value = {
            "search": {"search_name": "WOSB IT", "last_run_at": None},
            "results": [],
            "count": 0,
            "new_count": 0,
        }
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "run-search", "--id", "5"
        ])

        assert result.exit_code == 0
        mock_mgr.run_search.assert_called_once_with(
            search_id=5, search_name=None
        )


# ===================================================================
# list-searches tests
# ===================================================================

class TestListSearches:

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_searches_no_results(self, mock_mgr_cls):
        """list-searches with no saved searches should report it."""
        mock_mgr = MagicMock()
        mock_mgr.list_saved_searches.return_value = []
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list-searches"])

        assert result.exit_code == 0
        assert "No saved searches found" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_searches_with_user_filter(self, mock_mgr_cls):
        """list-searches --user should pass username filter."""
        mock_mgr = MagicMock()
        mock_mgr.list_saved_searches.return_value = [
            {
                "search_id": 1,
                "search_name": "WOSB IT",
                "username": "jdoe",
                "last_run_at": None,
                "last_new_results": 0,
                "is_active": "Y",
            }
        ]
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "list-searches", "--user", "jdoe"
        ])

        assert result.exit_code == 0
        assert "WOSB IT" in result.output
        mock_mgr.list_saved_searches.assert_called_once_with(username="jdoe")


# ===================================================================
# dashboard tests
# ===================================================================

class TestDashboard:

    @patch("etl.prospect_manager.ProspectManager")
    def test_dashboard_displays_sections(self, mock_mgr_cls):
        """dashboard should display all sections."""
        mock_mgr = MagicMock()
        mock_mgr.get_dashboard_data.return_value = {
            "by_status": {"REVIEWING": 3, "PURSUING": 2},
            "total_open": 5,
            "due_this_week": [],
            "by_assignee": [
                {"username": "jdoe", "display_name": "Jane Doe", "cnt": 3},
            ],
            "win_loss": {"WON": 2, "LOST": 1},
            "saved_searches": [],
        }
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "dashboard"])

        assert result.exit_code == 0
        assert "PROSPECT PIPELINE DASHBOARD" in result.output
        assert "Pipeline" in result.output
        assert "Workload by Assignee" in result.output
        assert "jdoe" in result.output
        assert "Win rate" in result.output

    @patch("etl.prospect_manager.ProspectManager")
    def test_dashboard_handles_error(self, mock_mgr_cls):
        """dashboard should exit 1 on error."""
        mock_mgr = MagicMock()
        mock_mgr.get_dashboard_data.side_effect = Exception("DB connection failed")
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "dashboard"])

        assert result.exit_code == 1
        assert "DB connection failed" in result.output


# ===================================================================
# add-user tests
# ===================================================================

class TestAddUser:

    @patch("etl.prospect_manager.ProspectManager")
    def test_add_user(self, mock_mgr_cls):
        """add-user should call add_user with correct args."""
        mock_mgr = MagicMock()
        mock_mgr.add_user.return_value = 7
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-user",
            "--username", "jdoe",
            "--name", "Jane Doe",
            "--email", "jane@example.com",
        ])

        assert result.exit_code == 0
        assert "Created user 'jdoe'" in result.output
        assert "user_id=7" in result.output
        mock_mgr.add_user.assert_called_once_with(
            "jdoe", "Jane Doe", email="jane@example.com", role="MEMBER"
        )

    @patch("etl.prospect_manager.ProspectManager")
    def test_add_user_with_role(self, mock_mgr_cls):
        """add-user --role ADMIN should pass role through."""
        mock_mgr = MagicMock()
        mock_mgr.add_user.return_value = 8
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, [
            "prospect", "add-user",
            "--username", "admin1",
            "--name", "Admin User",
            "--role", "ADMIN",
        ])

        assert result.exit_code == 0
        mock_mgr.add_user.assert_called_once_with(
            "admin1", "Admin User", email=None, role="ADMIN"
        )


# ===================================================================
# list-users tests
# ===================================================================

class TestListUsers:

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_users_no_results(self, mock_mgr_cls):
        """list-users with no users should report it."""
        mock_mgr = MagicMock()
        mock_mgr.list_users.return_value = []
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list-users"])

        assert result.exit_code == 0
        assert "No users found" in result.output
        mock_mgr.list_users.assert_called_once_with(active_only=True)

    @patch("etl.prospect_manager.ProspectManager")
    def test_list_users_all_flag(self, mock_mgr_cls):
        """list-users --all should pass active_only=False."""
        mock_mgr = MagicMock()
        mock_mgr.list_users.return_value = []
        mock_mgr_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(cli, ["prospect", "list-users", "--all"])

        assert result.exit_code == 0
        mock_mgr.list_users.assert_called_once_with(active_only=False)
