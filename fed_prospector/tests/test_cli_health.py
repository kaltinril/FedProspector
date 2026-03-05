"""Tests for CLI health commands (cli/health.py, cli/schema.py).

Tests the Click CLI wiring for: check, load-history, check-schema, status,
maintain-db, run-job.  All external dependencies are mocked.
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

class TestHealthHelp:

    def test_health_check_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "Comprehensive system health check" in result.output

    def test_health_load_history_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "load-history", "--help"])
        assert result.exit_code == 0
        assert "Show ETL load history" in result.output

    def test_health_check_schema_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check-schema", "--help"])
        assert result.exit_code == 0
        assert "Compare live database schema" in result.output

    def test_health_maintain_db_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "maintain-db", "--help"])
        assert result.exit_code == 0
        assert "Run database maintenance tasks" in result.output

    def test_health_run_job_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-job", "--help"])
        assert result.exit_code == 0
        assert "Manually trigger a scheduled job" in result.output

    def test_health_catchup_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "catchup", "--help"])
        assert result.exit_code == 0
        assert "Check which data sources are stale" in result.output

    def test_health_run_all_searches_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-all-searches", "--help"])
        assert result.exit_code == 0
        assert "Run all saved searches" in result.output


# ===================================================================
# check-health tests
# ===================================================================

class TestCheckHealth:

    @patch("etl.health_check.HealthCheck")
    def test_check_health_displays_sections(self, mock_hc_cls):
        """health check should display all sections."""
        mock_hc = MagicMock()
        mock_hc.check_all.return_value = {
            "data_freshness": [
                {
                    "source": "SAM_OPPORTUNITY",
                    "label": "Opportunities",
                    "status": "OK",
                    "last_load": "2026-03-04 10:00:00",
                    "hours_ago": 2.5,
                }
            ],
            "table_stats": [
                {"table_name": "opportunity", "row_count": 5000},
            ],
            "api_usage": [
                {"source": "SAM_KEY_1", "used": 3, "limit": 10, "remaining": 7},
            ],
            "api_key_status": [
                {"key_name": "SAM Key 1", "configured": True, "daily_limit": 10},
            ],
            "alerts": [],
            "recent_errors": [],
        }
        mock_hc_cls.return_value = mock_hc

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check"])

        assert result.exit_code == 0
        assert "Data Freshness" in result.output
        assert "Table Statistics" in result.output
        assert "API Usage Today" in result.output
        assert "API Key Status" in result.output
        assert "Alerts" in result.output
        assert "No alerts" in result.output
        mock_hc.check_all.assert_called_once()

    @patch("etl.health_check.HealthCheck")
    def test_check_health_json_mode(self, mock_hc_cls):
        """health check --json should output parseable JSON."""
        mock_hc = MagicMock()
        mock_hc.check_all.return_value = {
            "data_freshness": [],
            "table_stats": [],
            "api_usage": [],
            "api_key_status": [],
            "alerts": [],
            "recent_errors": [],
        }
        mock_hc_cls.return_value = mock_hc

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check", "--json"])

        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "data_freshness" in data
        assert "alerts" in data

    @patch("etl.health_check.HealthCheck")
    def test_check_health_shows_alerts(self, mock_hc_cls):
        """health check should display alerts when present."""
        mock_hc = MagicMock()
        mock_hc.check_all.return_value = {
            "data_freshness": [],
            "table_stats": [],
            "api_usage": [],
            "api_key_status": [],
            "alerts": [
                {"level": "WARNING", "message": "Opportunity data is stale"},
            ],
            "recent_errors": [],
        }
        mock_hc_cls.return_value = mock_hc

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check"])

        assert result.exit_code == 0
        assert "WARNING" in result.output
        assert "Opportunity data is stale" in result.output

    @patch("etl.health_check.HealthCheck")
    def test_check_health_shows_recent_errors(self, mock_hc_cls):
        """health check should display recent error entries."""
        mock_hc = MagicMock()
        mock_hc.check_all.return_value = {
            "data_freshness": [],
            "table_stats": [],
            "api_usage": [],
            "api_key_status": [],
            "alerts": [],
            "recent_errors": [
                {
                    "started_at": "2026-03-04 09:00",
                    "source_system": "SAM_ENTITY",
                    "error_message": "Connection timeout",
                },
            ],
        }
        mock_hc_cls.return_value = mock_hc

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check"])

        assert result.exit_code == 0
        assert "Recent Errors" in result.output
        assert "Connection timeout" in result.output


# ===================================================================
# load-history tests
# ===================================================================

class TestLoadHistory:

    @patch("db.connection.get_cursor")
    def test_load_history_no_results(self, mock_get_cursor):
        """load-history with no records should say so."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_get_cursor.return_value = mock_cursor

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "load-history"])

        assert result.exit_code == 0
        assert "No load history found" in result.output

    @patch("db.connection.get_cursor")
    def test_load_history_with_source_filter(self, mock_get_cursor):
        """--source should filter results by source_system."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "started_at": "2026-03-04 10:00:00",
                "source_system": "SAM_OPPORTUNITY",
                "status": "SUCCESS",
                "duration_secs": 45,
                "records_read": 100,
                "records_inserted": 90,
                "records_updated": 10,
                "records_errored": 0,
                "error_message": None,
            }
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_get_cursor.return_value = mock_cursor

        runner = CliRunner()
        result = runner.invoke(cli, [
            "health", "load-history", "--source", "SAM_OPPORTUNITY"
        ])

        assert result.exit_code == 0
        assert "SAM_OPPORTUNITY" in result.output
        call_args = mock_cursor.execute.call_args
        assert "SAM_OPPORTUNITY" in call_args[0][1]


# ===================================================================
# check-schema tests
# ===================================================================

class TestCheckSchema:

    @patch("etl.schema_checker.run_schema_check")
    def test_check_schema_all_ok(self, mock_check):
        """check-schema with no drift should report 0 DRIFT, 0 MISSING."""
        mock_check.return_value = (
            {"opportunity": MagicMock(), "entity": MagicMock()},  # expected_tables
            {"v_prospect_summary": MagicMock()},  # expected_views
            {"opportunity", "entity"},  # live_tables
            {"v_prospect_summary"},  # live_views
            [],  # no drifts
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check-schema"])

        assert result.exit_code == 0
        assert "0 DRIFT" in result.output
        assert "0 MISSING" in result.output

    @patch("etl.schema_checker.run_schema_check")
    def test_check_schema_with_drift_exits_1(self, mock_check):
        """check-schema with drifts should exit 1."""
        drift = MagicMock()
        drift.table = "opportunity"
        drift.category = "type_mismatch"
        drift.detail = "Column 'title' expected VARCHAR(500) but got VARCHAR(255)"
        drift.fix_sql = "ALTER TABLE opportunity MODIFY title VARCHAR(500);"
        mock_check.return_value = (
            {"opportunity": MagicMock()},
            {},
            {"opportunity"},
            set(),
            [drift],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check-schema"])

        assert result.exit_code == 1
        assert "DRIFT" in result.output

    @patch("etl.schema_checker.run_schema_check")
    def test_check_schema_fix_prints_alter(self, mock_check):
        """check-schema --fix should print ALTER statements."""
        drift = MagicMock()
        drift.table = "opportunity"
        drift.category = "type_mismatch"
        drift.detail = "Column 'title' expected VARCHAR(500) but got VARCHAR(255)"
        drift.fix_sql = "ALTER TABLE opportunity MODIFY title VARCHAR(500);"
        mock_check.return_value = (
            {"opportunity": MagicMock()},
            {},
            {"opportunity"},
            set(),
            [drift],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check-schema", "--fix"])

        assert result.exit_code == 1
        assert "ALTER TABLE" in result.output

    @patch("etl.schema_checker.run_schema_check")
    def test_check_schema_error(self, mock_check):
        """check-schema should handle errors gracefully."""
        mock_check.side_effect = Exception("Cannot connect to DB")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "check-schema"])

        assert result.exit_code == 1
        assert "Cannot connect to DB" in result.output


# ===================================================================
# maintain-db tests
# ===================================================================

class TestMaintainDb:

    @patch("etl.db_maintenance.DatabaseMaintenance")
    def test_maintain_db_dry_run(self, mock_maint_cls):
        """maintain-db --dry-run should preview without deleting."""
        mock_maint = MagicMock()
        mock_maint.run_all.return_value = {
            "old_history_records": 500,
            "old_staging_records": 100,
        }
        mock_maint_cls.return_value = mock_maint

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "maintain-db", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        mock_maint.run_all.assert_called_once_with(dry_run=True)

    @patch("etl.db_maintenance.DatabaseMaintenance")
    def test_maintain_db_sizes(self, mock_maint_cls):
        """maintain-db --sizes should show table sizes."""
        mock_maint = MagicMock()
        mock_maint.get_table_sizes.return_value = [
            {"table_name": "opportunity", "data_mb": 10.5, "index_mb": 2.1, "rows": 5000},
        ]
        mock_maint_cls.return_value = mock_maint

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "maintain-db", "--sizes"])

        assert result.exit_code == 0
        assert "opportunity" in result.output
        assert "Table Sizes" in result.output

    @patch("etl.db_maintenance.DatabaseMaintenance")
    def test_maintain_db_analyze(self, mock_maint_cls):
        """maintain-db --analyze should call analyze_tables."""
        mock_maint = MagicMock()
        mock_maint_cls.return_value = mock_maint

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "maintain-db", "--analyze"])

        assert result.exit_code == 0
        mock_maint.analyze_tables.assert_called_once()
        assert "Done" in result.output


# ===================================================================
# run-job tests
# ===================================================================

class TestRunJob:

    @patch("etl.scheduler.JOBS", {"opportunities": {
        "schedule": "daily", "priority": "HIGH",
        "description": "Load new opportunities",
    }})
    @patch("etl.scheduler.JobRunner")
    def test_run_job_list(self, mock_runner_cls):
        """run-job --list should show available jobs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-job", "--list"])

        assert result.exit_code == 0
        assert "opportunities" in result.output
        assert "Load new opportunities" in result.output

    @patch("etl.scheduler.JOBS", {})
    def test_run_job_requires_name(self):
        """run-job without a name should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-job"])

        assert result.exit_code == 0  # exits normally with message
        assert "Job name is required" in result.output

    @patch("etl.scheduler.JOBS", {"opportunities": {
        "schedule": "daily", "priority": "HIGH",
        "description": "Load new opportunities",
    }})
    @patch("etl.scheduler.JobRunner")
    def test_run_job_executes_successfully(self, mock_runner_cls):
        """run-job <name> should execute the job and report success."""
        mock_runner = MagicMock()
        mock_runner.run_job.return_value = (True, "All done")
        mock_runner_cls.return_value = mock_runner

        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-job", "opportunities"])

        assert result.exit_code == 0
        assert "completed successfully" in result.output
        mock_runner.run_job.assert_called_once_with("opportunities")

    @patch("etl.scheduler.JOBS", {"opportunities": {
        "schedule": "daily", "priority": "HIGH",
        "description": "Load new opportunities",
    }})
    @patch("etl.scheduler.JobRunner")
    def test_run_job_unknown_name(self, mock_runner_cls):
        """run-job with unknown name should show available jobs."""
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "run-job", "bogus_job"])

        assert result.exit_code == 0
        assert "Unknown job" in result.output
