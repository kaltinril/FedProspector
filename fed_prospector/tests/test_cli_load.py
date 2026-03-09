"""Tests for CLI load commands (cli/entities.py, cli/opportunities.py, cli/awards.py).

Tests the Click CLI wiring for: load entities, load opportunities, load awards.
All external dependencies (API clients, loaders, DB) are mocked.
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

class TestLoadHelp:

    def test_load_entities_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--help"])
        assert result.exit_code == 0
        assert "Load SAM.gov entity data" in result.output

    def test_load_opportunities_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "opportunities", "--help"])
        assert result.exit_code == 0
        assert "Load contract opportunities" in result.output

    def test_load_awards_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "awards", "--help"])
        assert result.exit_code == 0
        assert "Load historical contract awards" in result.output

    def test_search_opportunities_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "opportunities", "--help"])
        assert result.exit_code == 0
        assert "Search loaded opportunities" in result.output

    def test_search_entities_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "entities", "--help"])
        assert result.exit_code == 0
        assert "Search loaded entities" in result.output

    def test_search_awards_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "awards", "--help"])
        assert result.exit_code == 0
        assert "Search loaded contract awards" in result.output


# ===================================================================
# load entities tests
# ===================================================================

class TestLoadEntities:

    def test_load_entities_help(self):
        """load entities --help should show all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "daily" not in result.output
        assert "monthly" in result.output
        assert "api" in result.output
        assert "--file" in result.output

    def test_load_entities_file_not_found(self):
        """load entities with nonexistent --file should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--file", "/nonexistent/file.dat"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("etl.bulk_loader.BulkLoader")
    @patch("etl.dat_parser.parse_dat_file")
    @patch("etl.dat_parser.get_dat_record_count")
    def test_load_entities_dat_file_uses_bulk_loader(
        self, mock_count, mock_parse, mock_bulk_cls, tmp_path
    ):
        """load entities --file=X.dat should use BulkLoader."""
        dat_file = tmp_path / "test.dat"
        dat_file.write_text("dummy data")

        mock_count.return_value = 100
        mock_parse.return_value = iter([])
        mock_loader = MagicMock()
        mock_loader.bulk_load_entities.return_value = {
            "records_inserted": 100,
            "child_counts": {},
        }
        mock_bulk_cls.return_value = mock_loader

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--file", str(dat_file)])
        assert result.exit_code == 0
        assert "Bulk load complete" in result.output
        mock_bulk_cls.assert_called_once()
        mock_loader.bulk_load_entities.assert_called_once()

    @patch("etl.load_manager.LoadManager")
    @patch("etl.data_cleaner.DataCleaner")
    @patch("etl.change_detector.ChangeDetector")
    @patch("etl.entity_loader.EntityLoader")
    def test_load_entities_json_file_uses_entity_loader(
        self, mock_el_cls, mock_cd_cls, mock_dc_cls, mock_lm_cls, tmp_path
    ):
        """load entities --file=X.json should use EntityLoader."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"entities": []}')

        mock_loader = MagicMock()
        mock_loader.load_from_json_extract.return_value = {
            "records_read": 0, "records_inserted": 0,
            "records_updated": 0, "records_unchanged": 0,
            "records_errored": 0,
        }
        mock_el_cls.return_value = mock_loader

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--file", str(json_file)])
        assert result.exit_code == 0
        assert "Load complete" in result.output

    def test_load_entities_type_option_validates(self):
        """--type must be 'monthly' or 'api'."""
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "entities", "--type", "bogus"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output

        # 'daily' is no longer a valid type
        result = runner.invoke(cli, ["load", "entities", "--type", "daily"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


# ===================================================================
# load opportunities tests
# ===================================================================

class TestLoadOpportunities:

    @patch("db.connection.get_connection")
    @patch("etl.load_manager.LoadManager")
    @patch("etl.opportunity_loader.OpportunityLoader")
    @patch("api_clients.sam_opportunity_client.SAMOpportunityClient")
    def test_load_opportunities_default_key(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls, mock_get_conn
    ):
        """load opportunities with defaults should use key 1 and budget 5."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 10
        mock_client.max_daily_requests = 10
        mock_client.estimate_calls_needed.return_value = 4
        mock_client.iter_opportunity_pages.return_value = iter([])
        mock_client_cls.return_value = mock_client

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "opportunities"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(call_budget=5, api_key_number=1)
        assert "API key:     #1" in result.output

    @patch("db.connection.get_connection")
    @patch("etl.load_manager.LoadManager")
    @patch("etl.opportunity_loader.OpportunityLoader")
    @patch("api_clients.sam_opportunity_client.SAMOpportunityClient")
    def test_load_opportunities_key_2(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls, mock_get_conn
    ):
        """--key=2 should pass api_key_number=2 to the client."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 1000
        mock_client.max_daily_requests = 1000
        mock_client.estimate_calls_needed.return_value = 4
        mock_client.iter_opportunity_pages.return_value = iter([])
        mock_client_cls.return_value = mock_client

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "opportunities", "--key", "2"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(call_budget=5, api_key_number=2)
        assert "API key:     #2" in result.output

    @patch("db.connection.get_connection")
    @patch("etl.load_manager.LoadManager")
    @patch("etl.opportunity_loader.OpportunityLoader")
    @patch("api_clients.sam_opportunity_client.SAMOpportunityClient")
    def test_load_opportunities_days_back(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls, mock_get_conn
    ):
        """--days-back should produce an INCREMENTAL load type."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 10
        mock_client.max_daily_requests = 10
        mock_client.estimate_calls_needed.return_value = 1
        mock_client.iter_opportunity_pages.return_value = iter([])
        mock_client_cls.return_value = mock_client

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "opportunities", "--days-back", "30"])

        assert result.exit_code == 0
        assert "INCREMENTAL" in result.output

    @patch("db.connection.get_connection")
    @patch("etl.load_manager.LoadManager")
    @patch("etl.opportunity_loader.OpportunityLoader")
    @patch("api_clients.sam_opportunity_client.SAMOpportunityClient")
    def test_load_opportunities_set_aside_filter(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls, mock_get_conn
    ):
        """--set-aside=WOSB should query only WOSB."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 10
        mock_client.max_daily_requests = 10
        mock_client.estimate_calls_needed.return_value = 1
        mock_client.iter_opportunity_pages.return_value = iter([])
        mock_client_cls.return_value = mock_client

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "opportunities", "--set-aside", "WOSB"])

        assert result.exit_code == 0
        assert "WOSB" in result.output


# ===================================================================
# load awards tests
# ===================================================================

class TestLoadAwards:

    def test_load_awards_requires_filter(self):
        """load awards with no filter should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["load", "awards"])
        assert result.exit_code == 1
        assert "At least one filter is required" in result.output

    @patch("etl.load_manager.LoadManager")
    @patch("etl.awards_loader.AwardsLoader")
    @patch("api_clients.sam_awards_client.SAMAwardsClient")
    def test_load_awards_with_naics(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls
    ):
        """load awards --naics 541512 should create client and load records."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 100
        mock_client.max_daily_requests = 1000
        mock_client.search_awards.return_value = {
            "awardSummary": [{"piid": "TEST001"}],
            "totalRecords": 1,
        }
        mock_client_cls.return_value = mock_client

        mock_loader = MagicMock()
        mock_loader.load_awards.return_value = {
            "records_read": 1, "records_inserted": 1,
            "records_updated": 0, "records_unchanged": 0,
            "records_errored": 0,
        }
        mock_loader_cls.return_value = mock_loader

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "awards", "--naics", "541512"])

        assert result.exit_code == 0
        assert "Load complete" in result.output
        mock_loader.load_awards.assert_called_once()

    @patch("etl.load_manager.LoadManager")
    @patch("etl.awards_loader.AwardsLoader")
    @patch("api_clients.sam_awards_client.SAMAwardsClient")
    def test_load_awards_key_1_vs_key_2(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls
    ):
        """--key=1 vs --key=2 should pass correct api_key_number."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 100
        mock_client.max_daily_requests = 1000
        mock_client.search_awards.return_value = {
            "awardSummary": [],
            "totalRecords": 0,
        }
        mock_client_cls.return_value = mock_client

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        runner = CliRunner()

        result = runner.invoke(cli, ["load", "awards", "--naics", "541512", "--key", "1"])
        assert result.exit_code == 0
        mock_client_cls.assert_called_with(api_key_number=1)

        mock_client_cls.reset_mock()

        result = runner.invoke(cli, ["load", "awards", "--naics", "541512", "--key", "2"])
        assert result.exit_code == 0
        mock_client_cls.assert_called_with(api_key_number=2)

    @patch("etl.load_manager.LoadManager")
    @patch("etl.awards_loader.AwardsLoader")
    @patch("api_clients.sam_awards_client.SAMAwardsClient")
    def test_load_awards_multiple_naics(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls
    ):
        """Comma-separated NAICS codes should each be queried."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 100
        mock_client.max_daily_requests = 1000
        mock_client.search_awards.return_value = {
            "awardSummary": [{"piid": "TEST001"}],
            "totalRecords": 1,
        }
        mock_client_cls.return_value = mock_client

        mock_loader = MagicMock()
        mock_loader.load_awards.return_value = {
            "records_read": 2, "records_inserted": 2,
            "records_updated": 0, "records_unchanged": 0,
            "records_errored": 0,
        }
        mock_loader_cls.return_value = mock_loader

        mock_lm = MagicMock()
        mock_lm.start_load.return_value = 1
        mock_lm_cls.return_value = mock_lm

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "awards", "--naics", "541512,541511"])

        assert result.exit_code == 0
        assert "541512" in result.output
        assert "541511" in result.output
        # Should query each NAICS code
        assert mock_client.search_awards.call_count >= 2

    @patch("etl.load_manager.LoadManager")
    @patch("etl.awards_loader.AwardsLoader")
    @patch("api_clients.sam_awards_client.SAMAwardsClient")
    def test_load_awards_no_remaining_calls(
        self, mock_client_cls, mock_loader_cls, mock_lm_cls
    ):
        """Should error when no API calls remaining."""
        mock_client = MagicMock()
        mock_client._get_remaining_requests.return_value = 0
        mock_client.max_daily_requests = 1000
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["load", "awards", "--naics", "541512"])

        assert result.exit_code == 1
        assert "No API calls remaining" in result.output


# ===================================================================
# search commands tests (local DB queries)
# ===================================================================

class TestSearchOpportunities:

    @patch("db.connection.get_connection")
    def test_search_opportunities_no_results(self, mock_get_conn):
        """search opportunities with no matches should say so."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["search", "opportunities"])

        assert result.exit_code == 0
        assert "No opportunities found" in result.output

    @patch("db.connection.get_connection")
    def test_search_opportunities_with_set_aside(self, mock_get_conn):
        """--set-aside should be included in the SQL query params."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["search", "opportunities", "--set-aside", "WOSB"])

        assert result.exit_code == 0
        call_args = mock_cursor.execute.call_args
        assert "WOSB" in call_args[0][1]


class TestSearchAwards:

    @patch("db.connection.get_connection")
    def test_search_awards_no_results(self, mock_get_conn):
        """search awards with no matches should say so."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["search", "awards"])

        assert result.exit_code == 0
        assert "No awards found" in result.output
