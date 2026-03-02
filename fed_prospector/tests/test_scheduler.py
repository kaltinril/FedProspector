"""Tests for etl.scheduler -- job definitions, runner, and status."""

import pytest
from unittest.mock import MagicMock, patch

from etl.scheduler import JOBS, JobRunner


# ===================================================================
# Job definitions tests
# ===================================================================

class TestJobDefinitions:

    def test_all_jobs_have_required_keys(self):
        required_keys = {"description", "command", "source_system", "schedule",
                         "staleness_hours", "priority"}
        for name, job in JOBS.items():
            assert required_keys.issubset(job.keys()), (
                f"Job '{name}' missing keys: {required_keys - set(job.keys())}"
            )

    def test_all_commands_are_lists(self):
        for name, job in JOBS.items():
            assert isinstance(job["command"], list), f"Job '{name}' command is not a list"
            assert len(job["command"]) >= 2, f"Job '{name}' command too short"

    def test_all_commands_start_with_python(self):
        for name, job in JOBS.items():
            assert job["command"][0] == "python", (
                f"Job '{name}' command should start with 'python'"
            )

    def test_priority_values_valid(self):
        valid = {"Critical", "High", "Medium", "Low"}
        for name, job in JOBS.items():
            assert job["priority"] in valid, (
                f"Job '{name}' has invalid priority '{job['priority']}'"
            )

    def test_staleness_hours_positive_or_none(self):
        for name, job in JOBS.items():
            sh = job["staleness_hours"]
            assert sh is None or (isinstance(sh, int) and sh > 0), (
                f"Job '{name}' has invalid staleness_hours: {sh}"
            )

    def test_known_jobs_exist(self):
        expected = {"opportunities", "entity_daily", "hierarchy", "awards",
                    "calc_rates", "usaspending", "exclusions", "saved_searches"}
        assert expected.issubset(set(JOBS.keys()))

    def test_opportunities_is_critical(self):
        assert JOBS["opportunities"]["priority"] == "Critical"

    def test_opportunities_staleness_6_hours(self):
        assert JOBS["opportunities"]["staleness_hours"] == 6


# ===================================================================
# JobRunner tests
# ===================================================================

class TestJobRunner:

    def test_run_unknown_job_returns_failure(self):
        runner = JobRunner()
        success, output = runner.run_job("nonexistent_job")
        assert success is False
        assert "Unknown job" in output

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Load complete",
            stderr="",
        )
        runner = JobRunner()
        success, output = runner.run_job("opportunities")

        assert success is True
        assert "Load complete" in output
        mock_run.assert_called_once()

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Connection refused",
        )
        runner = JobRunner()
        success, output = runner.run_job("opportunities")

        assert success is False

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=3600)

        runner = JobRunner()
        success, output = runner.run_job("opportunities")

        assert success is False
        assert "timed out" in output

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_exception(self, mock_run):
        mock_run.side_effect = OSError("Command not found")

        runner = JobRunner()
        success, output = runner.run_job("opportunities")

        assert success is False
        assert "failed to execute" in output

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_replaces_python_with_sys_executable(self, mock_run):
        import sys
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        runner = JobRunner()
        runner.run_job("opportunities")

        actual_command = mock_run.call_args[0][0]
        assert actual_command[0] == sys.executable

    @patch("etl.scheduler.subprocess.run")
    def test_run_job_replaces_main_py_with_full_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        runner = JobRunner()
        runner.run_job("opportunities")

        actual_command = mock_run.call_args[0][0]
        # main.py should be replaced with an absolute path
        main_py_arg = [a for a in actual_command if "main.py" in str(a)]
        assert len(main_py_arg) == 1
        assert str(runner.main_py) in str(main_py_arg[0])


# ===================================================================
# list_jobs tests
# ===================================================================

class TestListJobs:

    @patch("etl.scheduler.get_connection")
    def test_list_jobs_returns_all(self, mock_gc):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_gc.return_value = mock_conn

        runner = JobRunner()
        jobs = runner.list_jobs()

        assert len(jobs) == len(JOBS)
        names = {j["name"] for j in jobs}
        assert names == set(JOBS.keys())

    @patch("etl.scheduler.get_connection")
    def test_list_jobs_includes_description(self, mock_gc):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_gc.return_value = mock_conn

        runner = JobRunner()
        jobs = runner.list_jobs()

        for job in jobs:
            assert "description" in job
            assert "schedule" in job
            assert "priority" in job


# ===================================================================
# get_job_status tests
# ===================================================================

class TestGetJobStatus:

    def test_unknown_job_returns_none(self):
        runner = JobRunner()
        assert runner.get_job_status("nonexistent") is None

    def test_job_without_source_system_returns_none(self):
        runner = JobRunner()
        # saved_searches has source_system=None
        assert runner.get_job_status("saved_searches") is None
