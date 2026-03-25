"""CLI command to create OS-level scheduled tasks for all ETL jobs.

Commands: setup-schedule

Creates Windows Task Scheduler entries (schtasks) or Linux crontab entries
for all ETL jobs defined in this module.
"""

import sys
import subprocess

import click

from pathlib import Path


PYTHON_PATH = sys.executable
MAIN_PY = Path(__file__).parent.parent / "main.py"
WORKING_DIR = MAIN_PY.parent

# Task prefix for all scheduled tasks (used for identification and cleanup)
TASK_PREFIX = "FedContract_"

# Scheduled task definitions with OS-specific scheduling parameters.
# Not imported from etl/scheduler.py because JOBS dict lacks schtasks-specific
# fields (schedule type, days, start time, crontab expression).
SCHEDULED_TASKS = [
    {
        "task_name": "FedContract_Opportunities",
        "command_args": "load opportunities --key 2",
        "description": "Refresh contract opportunities from SAM.gov",
        "windows": {"sc": "HOURLY", "mo": "4"},
        "crontab": "0 */4 * * *",
    },
    {
        "task_name": "FedContract_EntityDaily",
        "command_args": "load entities --type api",
        "description": "Refresh entities updated today via API",
        "windows": {"sc": "WEEKLY", "d": "TUE,WED,THU,FRI,SAT", "st": "06:00"},
        "crontab": "0 6 * * 2-6",
    },
    {
        "task_name": "FedContract_Hierarchy",
        "command_args": "load hierarchy --full-refresh --key 2",
        "description": "Refresh federal org hierarchy",
        "windows": {"sc": "MONTHLY", "d": "1", "st": "02:00"},
        "crontab": "0 2 1 * *",
    },
    {
        "task_name": "FedContract_Awards",
        "command_args": "load awards --naics 541511 --key 2",
        "description": "Refresh contract awards data",
        "windows": {"sc": "WEEKLY", "d": "SAT", "st": "03:00"},
        "crontab": "0 3 * * 6",
    },
    {
        "task_name": "FedContract_CalcRates",
        "command_args": "load labor-rates",
        "description": "Refresh GSA CALC+ labor rates",
        "windows": {"sc": "MONTHLY", "d": "1", "st": "04:00"},
        "crontab": "0 4 1 * *",
    },
    {
        "task_name": "FedContract_Exclusions",
        "command_args": "load exclusions --key 2",
        "description": "Refresh SAM.gov exclusions data",
        "windows": {"sc": "WEEKLY", "d": "MON", "st": "06:00"},
        "crontab": "0 6 * * 1",
    },
    {
        "task_name": "FedContract_HealthCheck",
        "command_args": "health check",
        "description": "Run system health check",
        "windows": {"sc": "DAILY", "st": "09:00"},
        "crontab": "0 9 * * *",
    },
    {
        "task_name": "FedContract_SavedSearches",
        "command_args": "job run-searches",
        "description": "Run all active saved searches",
        "windows": {"sc": "DAILY", "st": "07:00"},
        "crontab": "0 7 * * *",
    },
    {
        "task_name": "FedContract_Maintenance",
        "command_args": "maintain db",
        "description": "Run database maintenance",
        "windows": {"sc": "MONTHLY", "d": "1", "st": "01:00"},
        "crontab": "0 1 1 * *",
    },
    {
        "task_name": "FedContract_AttachmentAI",
        "command_args": "extract attachment-ai --model haiku --batch-size 50",
        "description": "Run AI analysis on attachment text",
        "windows": {"sc": "DAILY", "st": "10:00"},
        "crontab": "0 10 * * *",
    },
    {
        "task_name": "FedContract_IntelBackfill",
        "command_args": "backfill opportunity-intel",
        "description": "Backfill opportunity intel from attachment analysis",
        "windows": {"sc": "DAILY", "st": "11:00"},
        "crontab": "0 11 * * *",
    },
    {
        "task_name": "FedContract_AttachmentCleanup",
        "command_args": "maintain attachment-files",
        "description": "Clean up processed attachment files",
        "windows": {"sc": "DAILY", "st": "12:00"},
        "crontab": "0 12 * * *",
    },
]


def _detect_platform():
    """Auto-detect platform: 'windows' or 'linux'."""
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _build_full_tr(command_args):
    """Build the full /tr value for schtasks using absolute paths."""
    python_path = str(PYTHON_PATH)
    main_py_path = str(MAIN_PY.resolve())
    return f'"{python_path}" "{main_py_path}" {command_args}'


def _build_schtasks_create(task):
    """Build a schtasks /create command list for a single task."""
    tr_value = _build_full_tr(task["command_args"])
    win = task["windows"]

    cmd = [
        "schtasks", "/create",
        "/tn", task["task_name"],
        "/tr", tr_value,
        "/sc", win["sc"],
    ]

    if "mo" in win:
        cmd.extend(["/mo", win["mo"]])
    if "d" in win:
        cmd.extend(["/d", win["d"]])
    if "st" in win:
        cmd.extend(["/st", win["st"]])

    # /f forces overwrite of existing task
    cmd.append("/f")

    return cmd


def _build_schtasks_delete(task):
    """Build a schtasks /delete command list for a single task."""
    return ["schtasks", "/delete", "/tn", task["task_name"], "/f"]


def _build_crontab_line(task):
    """Build a crontab entry for a single task."""
    python_path = str(PYTHON_PATH)
    working_dir = str(WORKING_DIR.resolve())
    main_py_path = str(MAIN_PY.resolve())
    return (
        f'{task["crontab"]} '
        f'cd "{working_dir}" && "{python_path}" "{main_py_path}" {task["command_args"]}'
    )


def _run_command(cmd, dry_run):
    """Execute a command or print it in dry-run mode. Returns True on success."""
    cmd_str = " ".join(cmd)

    if dry_run:
        click.echo(f"[DRY RUN] {cmd_str}")
        return True

    click.echo(f"Running: {cmd_str}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            click.echo(f"  OK")
            return True
        else:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            detail = stderr or stdout
            click.echo(f"  FAILED (exit code {result.returncode}): {detail}")
            return False
    except subprocess.TimeoutExpired:
        click.echo(f"  FAILED: Command timed out")
        return False
    except Exception as e:
        click.echo(f"  FAILED: {e}")
        return False


@click.command("setup-schedule")
@click.option("--platform", "platform_name",
              type=click.Choice(["windows", "linux"], case_sensitive=False),
              default=None,
              help="Target platform (default: auto-detect)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show commands without executing them")
@click.option("--remove", is_flag=True, default=False,
              help="Remove all previously created scheduled tasks")
def setup_schedule(platform_name, dry_run, remove):
    """Create OS-level scheduled tasks for all ETL jobs.

    Auto-detects the current platform and creates Windows Task Scheduler
    entries (schtasks) or Linux crontab entries for each ETL job.

    Use --dry-run to preview commands without executing.
    Use --remove to delete all previously created tasks.

    Examples:
        python main.py setup schedule-jobs
        python main.py setup schedule-jobs --platform windows
        python main.py setup schedule-jobs --platform linux
        python main.py setup schedule-jobs --dry-run
        python main.py setup schedule-jobs --remove
    """
    platform = platform_name or _detect_platform()
    task_count = len(SCHEDULED_TASKS)

    if platform == "windows":
        _setup_windows(dry_run, remove, task_count)
    else:
        _setup_linux(dry_run, remove, task_count)


def _setup_windows(dry_run, remove, task_count):
    """Create or remove Windows Task Scheduler entries."""
    if remove:
        click.echo(f"Removing {task_count} Windows scheduled tasks...")
        success_count = 0
        fail_count = 0

        for task in SCHEDULED_TASKS:
            cmd = _build_schtasks_delete(task)
            if _run_command(cmd, dry_run):
                success_count += 1
            else:
                fail_count += 1

        prefix = "[DRY RUN] " if dry_run else ""
        click.echo(
            f"\n{prefix}Removed {success_count}/{task_count} tasks"
            f"{f' ({fail_count} failed)' if fail_count else ''}"
        )
        if fail_count and not dry_run:
            sys.exit(1)
        return

    # Create tasks
    click.echo(f"Creating {task_count} Windows scheduled tasks...")
    click.echo(f"Python: {PYTHON_PATH}")
    click.echo(f"main.py: {MAIN_PY.resolve()}")
    click.echo()

    success_count = 0
    fail_count = 0

    for task in SCHEDULED_TASKS:
        click.echo(f"  {task['task_name']} - {task['description']}")
        cmd = _build_schtasks_create(task)
        if _run_command(cmd, dry_run):
            success_count += 1
        else:
            fail_count += 1

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"\n{prefix}Created {success_count}/{task_count} tasks"
        f"{f' ({fail_count} failed)' if fail_count else ''}"
    )
    if fail_count and not dry_run:
        sys.exit(1)


def _setup_linux(dry_run, remove, task_count):
    """Create or remove Linux crontab entries."""
    marker = "# FedContract ETL"

    if remove:
        click.echo("To remove FedContract cron entries, edit your crontab:")
        click.echo("  crontab -e")
        click.echo()
        click.echo(f"Remove all lines between '{marker} BEGIN' and '{marker} END'.")
        return

    # Generate crontab entries
    click.echo(f"Generated {task_count} crontab entries.")
    click.echo(f"Python: {PYTHON_PATH}")
    click.echo(f"main.py: {MAIN_PY.resolve()}")
    click.echo()

    lines = []
    lines.append(f"{marker} BEGIN")
    for task in SCHEDULED_TASKS:
        lines.append(f"# {task['description']}")
        lines.append(_build_crontab_line(task))
    lines.append(f"{marker} END")

    crontab_block = "\n".join(lines)

    if dry_run:
        click.echo("[DRY RUN] The following would be added to crontab:")
        click.echo()
        click.echo(crontab_block)
    else:
        click.echo("Add the following block to your crontab (run 'crontab -e'):")
        click.echo()
        click.echo(crontab_block)

    click.echo()
    click.echo("To install, run:")
    click.echo("  crontab -e")
    click.echo("Then paste the block above and save.")
