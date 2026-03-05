"""Tests for CLI database commands (cli/database.py).

Tests the Click CLI wiring for: build-database, seed-lookups, status,
test-api, seed-rules.  All external dependencies are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# Ensure fed_prospector is importable
FED_PROSPECTOR_DIR = Path(__file__).resolve().parent.parent
if str(FED_PROSPECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(FED_PROSPECTOR_DIR))

from main import cli


# ===================================================================
# --help smoke tests
# ===================================================================

class TestDatabaseHelp:

    def test_setup_build_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "build", "--help"])
        assert result.exit_code == 0
        assert "Create all database tables" in result.output

    def test_setup_seed_lookups_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-lookups", "--help"])
        assert result.exit_code == 0
        assert "Load reference/lookup data" in result.output

    def test_health_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "status", "--help"])
        assert result.exit_code == 0
        assert "database connection status" in result.output

    def test_setup_test_api_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "test-api", "--help"])
        assert result.exit_code == 0
        assert "Test the SAM.gov API key" in result.output

    def test_setup_seed_rules_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-rules", "--help"])
        assert result.exit_code == 0
        assert "Seed the etl_data_quality_rule table" in result.output


# ===================================================================
# build-database tests
# ===================================================================

class TestBuildDatabase:

    @patch("db.connection.get_connection")
    def test_build_database_runs_sql(self, mock_get_conn):
        """build-database should open a connection and process SQL files."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "build"])
        # It will execute SQL files from the real schema dir.
        # The main check is that it ran without an unhandled crash
        # and attempted to use the DB connection.
        assert mock_get_conn.called

    @patch("db.connection.get_connection")
    def test_build_database_drop_first_prompts(self, mock_get_conn):
        """--drop-first should prompt for confirmation and abort on 'n'."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "build", "--drop-first"], input="n\n")
        assert "Aborted" in result.output


# ===================================================================
# seed-quality-rules tests
# ===================================================================

class TestSeedQualityRules:

    @patch("db.connection.get_connection")
    def test_seed_quality_rules_calls_impl_and_commits(self, mock_get_conn):
        """seed-rules should insert rules and commit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-rules"])
        assert result.exit_code == 0
        assert "Seeded" in result.output
        assert "data quality rules" in result.output
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("db.connection.get_connection")
    def test_seed_quality_rules_handles_error(self, mock_get_conn):
        """seed-rules should rollback and exit 1 on error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-rules"])
        assert result.exit_code == 1
        assert "ERROR" in result.output
        mock_conn.rollback.assert_called_once()


# ===================================================================
# load-lookups tests
# ===================================================================

class TestLoadLookups:

    @patch("etl.reference_loader.ReferenceLoader")
    def test_load_lookups_all(self, mock_loader_cls):
        """seed-lookups with no --table loads all reference tables."""
        mock_loader = MagicMock()
        mock_loader.load_all.return_value = {
            "ref_naics_code": 1200,
            "ref_psc_code": 500,
        }
        mock_loader_cls.return_value = mock_loader

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-lookups"])
        assert result.exit_code == 0
        mock_loader.load_all.assert_called_once()
        assert "ref_naics_code" in result.output

    @patch("etl.reference_loader.ReferenceLoader")
    def test_load_lookups_specific_table(self, mock_loader_cls):
        """seed-lookups --table=naics calls the naics loader method."""
        mock_loader = MagicMock()
        mock_loader.load_naics_codes.return_value = 1200
        mock_loader_cls.return_value = mock_loader

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-lookups", "--table", "naics"])
        assert result.exit_code == 0
        mock_loader.load_naics_codes.assert_called_once()
        assert "Loaded 1200 rows" in result.output

    @patch("etl.reference_loader.ReferenceLoader")
    def test_load_lookups_unknown_table_exits(self, mock_loader_cls):
        """seed-lookups --table=bogus should error."""
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "seed-lookups", "--table", "bogus"])
        assert result.exit_code == 1
        assert "Unknown table" in result.output


# ===================================================================
# status tests
# ===================================================================

class TestStatus:

    @patch("db.connection.get_connection")
    def test_status_shows_mysql_version(self, mock_get_conn):
        """health status should display MySQL version info."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("8.4.8",),   # SELECT VERSION()
            (10,),        # table count
            (4,),         # view count
            (1,),         # opportunity table exists
            (100,),       # opportunity count
            (50,),        # open opportunities
            (None,),      # max last_loaded_at
            (None,),      # CALC+ load
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # information_schema tables
            [],  # rate limits
            [],  # set-aside breakdown
            [],  # recent loads
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "status"])
        assert result.exit_code == 0
        assert "MySQL" in result.output
        assert "8.4.8" in result.output
