"""Job scheduler definitions and runner.

Defines all automated jobs with their schedules, commands, and dependencies.
Jobs are triggered via CLI (`health run-job`) or Windows Task Scheduler.
This is NOT a daemon - each invocation runs one job and exits.

Windows Task Scheduler setup commands:
  schtasks /create /tn "FedContract_Opportunities" /tr "python main.py load opportunities --key 2" /sc HOURLY /mo 4
  schtasks /create /tn "FedContract_EntityDaily" /tr "python main.py load entities --type api" /sc WEEKLY /d TUE,WED,THU,FRI,SAT /st 06:00
  schtasks /create /tn "FedContract_Hierarchy" /tr "python main.py load hierarchy --full-refresh --key 2" /sc WEEKLY /d SUN /st 02:00
  schtasks /create /tn "FedContract_Awards" /tr "python main.py load awards --key 2" /sc WEEKLY /d SAT /st 03:00
  schtasks /create /tn "FedContract_CalcRates" /tr "python main.py load labor-rates" /sc MONTHLY /d 1 /st 04:00
  schtasks /create /tn "FedContract_Exclusions" /tr "python main.py load exclusions --key 2" /sc WEEKLY /d MON /st 06:00
  schtasks /create /tn "FedContract_HealthCheck" /tr "python main.py health check" /sc DAILY /st 09:00
  schtasks /create /tn "FedContract_SavedSearches" /tr "python main.py health run-all-searches" /sc DAILY /st 07:00
  schtasks /create /tn "FedContract_Maintenance" /tr "python main.py health maintain-db" /sc MONTHLY /d 1 /st 01:00
"""

import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from db.connection import get_connection


logger = logging.getLogger("fed_prospector.scheduler")


# Job definitions: name, schedule description, CLI command, source_system for staleness
JOBS = {
    "opportunities": {
        "description": "Refresh contract opportunities from SAM.gov",
        "command": ["python", "main.py", "load", "opportunities", "--key", "2"],
        "source_system": "SAM_OPPORTUNITY",
        "schedule": "Every 4 hours",
        "staleness_hours": 6,
        "daily_freshness_hours": 4,
        "priority": "Critical",
        "catchup_safe": True,
        "estimated_api_calls": 5,   # 4 set-aside types, ~1 page each
    },
    "entity_daily": {
        "description": "Refresh entities updated today via API",
        "command": ["python", "main.py", "load", "entities", "--type", "api"],
        "source_system": "SAM_ENTITY",
        "schedule": "Tue-Sat 06:00",
        "staleness_hours": 48,  # 2 days (skip weekends)
        "daily_freshness_hours": 20,
        "priority": "High",
        "catchup_safe": True,
        "estimated_api_calls": 50,  # Paginated API, ~10 entities/page
    },
    "hierarchy": {
        "description": "Refresh federal org hierarchy",
        "command": ["python", "main.py", "load", "hierarchy", "--full-refresh", "--key", "2"],
        "source_system": "SAM_FEDHIER",
        "schedule": "Sunday 02:00",
        "staleness_hours": 336,  # 14 days
        "daily_freshness_hours": 144,
        "priority": "Medium",
        "catchup_safe": True,
        "estimated_api_calls": 50,  # ~5K orgs at 100/page
    },
    "awards": {
        "description": "Refresh contract awards data",
        "command": ["python", "main.py", "load", "awards", "--key", "2"],
        "source_system": "SAM_AWARDS",
        "schedule": "Saturday 03:00",
        "staleness_hours": 336,  # 14 days
        "daily_freshness_hours": 24,
        "priority": "Medium",
        "catchup_safe": True,
        # 24 NAICS x 3 set-asides; budget-limited per run, resume handles multi-day completion
        "estimated_api_calls": 72,
    },
    "calc_rates": {
        "description": "Refresh GSA CALC+ labor rates",
        "command": ["python", "main.py", "load", "labor-rates"],
        "source_system": "GSA_CALC",
        "schedule": "1st of month 04:00",
        "staleness_hours": 1080,  # 45 days
        "daily_freshness_hours": 504,
        "priority": "Low",
        "catchup_safe": True,
        "estimated_api_calls": 0,   # GSA API, no SAM key
    },
    "usaspending": {
        "description": "Refresh USASpending data",
        "command": ["python", "main.py", "load", "usaspending"],
        "source_system": "USASPENDING",
        "schedule": "1st of month 05:00",
        "staleness_hours": 1080,  # 45 days
        "daily_freshness_hours": 504,
        "priority": "Medium",
        "catchup_safe": False,
        "estimated_api_calls": 0,   # Separate API, no SAM key
    },
    "exclusions": {
        "description": "Refresh SAM.gov exclusions data",
        "command": ["python", "main.py", "load", "exclusions", "--key", "2"],
        "source_system": "SAM_EXCLUSIONS",
        "schedule": "Monday 06:00",
        "staleness_hours": 336,  # 14 days
        "daily_freshness_hours": 24,
        "priority": "High",
        "catchup_safe": True,
        "estimated_api_calls": 20,  # Default --max-calls
    },
    "saved_searches": {
        "description": "Run all active saved searches",
        "command": ["python", "main.py", "health", "run-all-searches"],
        "source_system": None,  # No staleness tracking
        "schedule": "Daily 07:00",
        "staleness_hours": None,
        "daily_freshness_hours": 1,
        "priority": "Medium",
        "catchup_safe": False,
        "estimated_api_calls": 0,   # Local DB queries only
    },
    "auto_prospect": {
        "description": "Auto-generate prospects from saved searches and recompete detection",
        "command": ["python", "main.py", "prospect", "auto-generate", "--all-orgs"],
        "source_system": None,  # No staleness tracking
        "schedule": "Daily 07:30",
        "staleness_hours": None,
        "daily_freshness_hours": 1,
        "priority": "Medium",
        "catchup_safe": False,
        "estimated_api_calls": 0,   # Calls local C# API only
    },
}


class JobRunner:
    """Execute scheduled jobs with logging and error handling."""

    def __init__(self):
        self.logger = logging.getLogger("fed_prospector.scheduler.runner")
        self.main_py = Path(__file__).parent.parent / "main.py"

    def run_job(self, job_name):
        """Run a single named job. Returns (success: bool, output: str)."""
        if job_name not in JOBS:
            return False, f"Unknown job: {job_name}"

        job = JOBS[job_name]
        self.logger.info("Starting job: %s (%s)", job_name, job["description"])

        # Build the command with the correct path to main.py
        command = list(job["command"])
        # Replace "main.py" with full path if present
        if "main.py" in command:
            idx = command.index("main.py")
            command[idx] = str(self.main_py)

        # Replace "python" with the current interpreter
        if command[0] == "python":
            command[0] = sys.executable

        working_dir = self.main_py.parent

        try:
            result = subprocess.run(
                command,
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max per job
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr

            success = result.returncode == 0

            if success:
                self.logger.info("Job '%s' completed successfully", job_name)
            else:
                self.logger.error(
                    "Job '%s' failed (exit code %d): %s",
                    job_name, result.returncode, output[:500],
                )

            return success, output.strip()

        except subprocess.TimeoutExpired:
            msg = f"Job '{job_name}' timed out after 3600 seconds"
            self.logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Job '{job_name}' failed to execute: {e}"
            self.logger.error(msg)
            return False, msg

    def run_job_streaming(self, job_name):
        """Run a single named job with output streamed to console in real-time."""
        if job_name not in JOBS:
            return False, f"Unknown job: {job_name}"

        job = JOBS[job_name]
        self.logger.info("Starting job: %s (%s)", job_name, job["description"])

        command = list(job["command"])
        if "main.py" in command:
            idx = command.index("main.py")
            command[idx] = str(self.main_py)
        if command[0] == "python":
            command[0] = sys.executable

        working_dir = self.main_py.parent

        try:
            result = subprocess.run(
                command,
                cwd=str(working_dir),
                timeout=3600,
            )
            success = result.returncode == 0
            if success:
                self.logger.info("Job '%s' completed successfully", job_name)
            else:
                self.logger.error("Job '%s' failed (exit code %d)", job_name, result.returncode)
            return success, ""
        except subprocess.TimeoutExpired:
            msg = f"Job '{job_name}' timed out after 3600 seconds"
            self.logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Job '{job_name}' failed to execute: {e}"
            self.logger.error(msg)
            return False, msg

    def list_jobs(self):
        """Return list of all job definitions with status."""
        results = []
        for name, job in JOBS.items():
            entry = {
                "name": name,
                "description": job["description"],
                "schedule": job["schedule"],
                "priority": job["priority"],
                "source_system": job["source_system"],
                "staleness_hours": job["staleness_hours"],
            }

            # Merge with last-run info from etl_load_log
            if job["source_system"]:
                status_info = self.get_job_status(name)
                if status_info:
                    entry.update(status_info)

            results.append(entry)

        return results

    def get_job_status(self, job_name):
        """Get last run status for a job from etl_load_log."""
        if job_name not in JOBS:
            return None

        job = JOBS[job_name]
        source_system = job.get("source_system")
        if not source_system:
            return None

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT status, started_at, completed_at, "
                "records_read, records_inserted, records_updated, "
                "records_errored, error_message "
                "FROM etl_load_log "
                "WHERE source_system = %s "
                "ORDER BY started_at DESC LIMIT 1",
                (source_system,),
            )
            row = cursor.fetchone()
            if row:
                hours_ago = None
                if row["started_at"]:
                    delta = datetime.now() - row["started_at"]
                    hours_ago = delta.total_seconds() / 3600

                return {
                    "last_status": row["status"],
                    "last_run_at": row["started_at"],
                    "last_completed_at": row["completed_at"],
                    "last_records_read": row["records_read"],
                    "last_records_inserted": row["records_inserted"],
                    "last_records_updated": row["records_updated"],
                    "last_records_errored": row["records_errored"],
                    "last_error": row["error_message"],
                    "hours_since_last_run": hours_ago,
                }
            return None
        finally:
            cursor.close()
            conn.close()
