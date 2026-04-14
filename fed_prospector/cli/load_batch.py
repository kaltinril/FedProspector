"""CLI commands for batch loading: daily, weekly, monthly sequences (Phase 61).

Commands: job daily, job weekly, job monthly
"""

import subprocess
import sys
import time
from pathlib import Path

import click

from config.logging_config import setup_logging


NAICS = "336611,488190,519210,541219,541330,541511,541512,541513,541519,541611,541612,541613,541690,541990,561110,561210,561510,561990,611430,611710,621111,621399,624190,812910"

# Job-key sequences for weekly/monthly (use JOBS-based approach)
DAILY_SEQUENCE = [
    "opportunities",
    "fetch_descriptions",
    "usaspending_bulk",
    "awards",
    "calc_rates",
    "download_attachments",
    "extract_text",
    "attachment_intel",
    "description_intel",
    "extract_identifiers",
    "cross_ref_identifiers",
    "intel_backfill",
    "attachment_cleanup",
    "sca_revisions",
]
WEEKLY_SEQUENCE = [
    "entity_daily", "opportunities", "awards", "exclusions",
    "subawards", "saved_searches",
]
MONTHLY_SEQUENCE = [
    "entity_daily", "opportunities", "awards",
    "subawards", "hierarchy", "usaspending", "saved_searches",
]

KEY_LIMITS = {"1": "10/day", "2": "1000/day"}


def _get_daily_steps():
    """Return the daily load step definitions.

    Each step has a name, description, and command list.
    This matches the daily_load.bat sequence exactly.
    """
    return [
        {
            "name": "opportunities",
            "description": "Load opportunities (31 days back, key 2)",
            "command": ["python", "main.py", "load", "opportunities",
                        "--max-calls", "300", "--key", "2", "--days-back", "31", "--force"],
        },
        {
            "name": "fetch_descriptions",
            "description": "Fetch missing descriptions (priority NAICS+set-aside)",
            "command": ["python", "main.py", "update", "fetch-descriptions",
                        "--key", "2", "--limit", "100",
                        "--naics", NAICS, "--set-aside", "WOSB,8A,SBA"],
        },
        {
            "name": "usaspending_bulk",
            "description": "Load USASpending bulk (5 days back)",
            "command": ["python", "main.py", "load", "usaspending-bulk", "--days-back", "5"],
        },
        {
            "name": "awards_8a",
            "description": "Load awards - 8(a) set-aside",
            "command": ["python", "main.py", "load", "awards",
                        "--naics", NAICS, "--days-back", "10", "--max-calls", "100",
                        "--key", "2", "--set-aside", "8a"],
        },
        {
            "name": "awards_wosb",
            "description": "Load awards - WOSB set-aside",
            "command": ["python", "main.py", "load", "awards",
                        "--naics", NAICS, "--days-back", "10", "--max-calls", "100",
                        "--key", "2", "--set-aside", "WOSB"],
        },
        {
            "name": "awards_sba",
            "description": "Load awards - SBA set-aside",
            "command": ["python", "main.py", "load", "awards",
                        "--naics", NAICS, "--days-back", "10", "--max-calls", "100",
                        "--key", "2", "--set-aside", "SBA"],
        },
        {
            "name": "calc_rates",
            "description": "Load CALC+ labor rates (skips if <30 days old)",
            "command": ["python", "main.py", "load", "labor-rates"],
        },
        {
            "name": "download_attachments",
            "description": "Download attachments (active opps, missing only)",
            "command": ["python", "main.py", "download", "attachments",
                        "--missing-only", "--active-only", "--batch-size", "5000"],
        },
        {
            "name": "extract_text",
            "description": "Extract text from downloaded attachments",
            "command": ["python", "main.py", "extract", "attachment-text",
                        "--batch-size", "5000", "--workers", "10"],
        },
        {
            "name": "attachment_intel",
            "description": "Extract keyword intelligence from attachment text",
            "command": ["python", "main.py", "extract", "attachment-intel", "--batch-size", "5000"],
        },
        {
            "name": "description_intel",
            "description": "Extract keyword intelligence from description text",
            "command": ["python", "main.py", "extract", "description-intel", "--batch-size", "5000"],
        },
        {
            "name": "extract_identifiers",
            "description": "Extract federal identifiers from document text",
            "command": ["python", "main.py", "extract", "identifiers", "--batch-size", "5000"],
        },
        {
            "name": "cross_ref_identifiers",
            "description": "Cross-reference extracted identifiers against database",
            "command": ["python", "main.py", "extract", "cross-ref-identifiers", "--batch-size", "5000"],
        },
        {
            "name": "intel_backfill",
            "description": "Backfill opportunity intel from analysis results",
            "command": ["python", "main.py", "backfill", "opportunity-intel"],
        },
        {
            "name": "attachment_cleanup",
            "description": "Clean up fully-analyzed attachment files",
            "command": ["python", "main.py", "maintain", "attachment-files"],
        },
        {
            "name": "sca_revisions",
            "description": "Check SCA wage determinations for new revisions",
            "command": ["python", "main.py", "load", "sca"],
        },
    ]


def _should_load_monthly_entities():
    """Check if monthly entity bulk load should run.

    Returns True if:
    1. Today is on or after the first Sunday of the current month
    2. No successful FULL entity load exists this month in etl_load_log
    """
    from datetime import date

    from db.connection import get_connection

    today = date.today()
    # Find first Sunday of current month
    first_sunday = None
    for day in range(1, 8):
        d = date(today.year, today.month, day)
        if d.weekday() == 6:  # Sunday
            first_sunday = d
            break

    if today < first_sunday:
        return False

    # Check if already loaded this month
    conn = get_connection()
    cursor = conn.cursor()
    try:
        first_of_month = date(today.year, today.month, 1)
        cursor.execute(
            "SELECT 1 FROM etl_load_log "
            "WHERE source_system = 'SAM_ENTITY' AND load_type = 'FULL' "
            "AND status = 'SUCCESS' AND started_at >= %s LIMIT 1",
            (first_of_month,),
        )
        return cursor.fetchone() is None
    finally:
        cursor.close()
        conn.close()


def _format_duration(seconds):
    """Format seconds as Xs or Xm Ys."""
    secs = int(seconds)
    if secs < 60:
        return f"{secs}s"
    minutes = secs // 60
    remainder = secs % 60
    return f"{minutes}m {remainder}s"


def _apply_key_override(command, key):
    """Replace --key value in a command list with the specified key."""
    cmd = list(command)
    try:
        key_idx = cmd.index("--key")
        if key_idx + 1 < len(cmd):
            cmd[key_idx + 1] = str(key)
    except ValueError:
        pass  # No --key in this command
    return cmd


def _resolve_command(command):
    """Resolve python and main.py paths in a command list."""
    main_py = Path(__file__).parent.parent / "main.py"
    cmd = list(command)
    if "main.py" in cmd:
        idx = cmd.index("main.py")
        cmd[idx] = str(main_py)
    if cmd[0] == "python":
        cmd[0] = sys.executable
    return cmd, main_py.parent


def _run_step(step, key, dry_run):
    """Run a single daily step. Returns (success, elapsed_seconds)."""
    command = _apply_key_override(step["command"], key)
    command, working_dir = _resolve_command(command)

    if dry_run:
        cmd_str = " ".join(command)
        click.echo(f"       cmd: {cmd_str}")
        return True, 0

    start = time.time()
    try:
        result = subprocess.run(
            command,
            cwd=str(working_dir),
            timeout=3600,
        )
        elapsed = time.time() - start
        return result.returncode == 0, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        click.echo("       TIMED OUT (3600s)")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        click.echo(f"       ERROR: {e}")
        return False, elapsed


def _run_daily_batch(steps, key, skip, dry_run):
    """Run the daily batch of steps."""
    skip_set = set(skip) if skip else set()
    total = len(steps)

    click.echo(f"\n=== FedProspect Daily Load ===")
    click.echo(f"  Key: {key} ({KEY_LIMITS.get(key, '?')} limit)")
    click.echo(f"  Steps: {total}")
    click.echo()

    ran = 0
    skipped = 0
    failed = 0
    batch_start = time.time()

    for i, step in enumerate(steps, 1):
        name = step["name"]
        desc = step["description"]
        pad = "." * max(1, 30 - len(name))

        if name in skip_set:
            click.echo(f"  [{i:2d}/{total}] {name} {pad} SKIP (--skip)")
            skipped += 1
            continue

        click.echo(f"  [{i:2d}/{total}] {name} {pad} {desc}")

        if dry_run:
            _run_step(step, key, dry_run=True)
            ran += 1
            continue

        success, elapsed = _run_step(step, key, dry_run=False)
        duration_str = _format_duration(elapsed)

        if success:
            click.echo(f"  [{i:2d}/{total}] {name} {pad} OK  ({duration_str})")
            ran += 1
        else:
            click.echo(f"  [{i:2d}/{total}] {name} {pad} FAILED  ({duration_str})")
            failed += 1
            # Always continue on failure for daily batch

    total_elapsed = time.time() - batch_start

    click.echo(f"\n=== Summary ===")
    if dry_run:
        click.echo(f"  [DRY RUN] {ran} would run, {skipped} would skip")
    else:
        click.echo(f"  Ran: {ran}    Skipped: {skipped}    Failed: {failed}")
        click.echo(f"  Total time: {_format_duration(total_elapsed)}")


def _run_batch(mode_name, sequence, key, skip, dry_run, continue_on_failure, force):
    """Shared logic for weekly/monthly batch commands (JOBS-based)."""
    setup_logging()
    from etl.scheduler import JobRunner, JOBS

    # Filter out skipped jobs
    skip_set = set(skip) if skip else set()
    jobs = [j for j in sequence if j not in skip_set]

    # Calculate estimated API calls
    total_est = sum(JOBS[j].get("estimated_api_calls", 0) for j in jobs if j in JOBS)

    # Header
    click.echo(f"\n=== FedProspect {mode_name} Load ===")
    click.echo(f"  Key: {key} ({KEY_LIMITS.get(key, '?')} limit)")
    click.echo(f"  Jobs: {len(jobs)}")
    click.echo(f"  Est. API calls: ~{total_est}")
    click.echo()

    if dry_run:
        runner = JobRunner()
        would_run = 0
        would_skip = 0
        for i, job_name in enumerate(jobs, 1):
            pad = "." * max(1, 25 - len(job_name))
            job_def = JOBS.get(job_name)
            if not job_def:
                click.echo(f"  [{i}/{len(jobs)}] {job_name} {pad} SKIP (unknown job)")
                would_skip += 1
                continue

            source = job_def.get("source_system")
            staleness_h = job_def.get("staleness_hours")

            if not force and source and staleness_h:
                status_info = runner.get_job_status(job_name)
                threshold = job_def.get("daily_freshness_hours", staleness_h / 2)
                if status_info and status_info.get("hours_since_last_run") is not None:
                    hours_ago = status_info["hours_since_last_run"]
                    last_status = status_info.get("last_status")
                    if last_status == "SUCCESS" and hours_ago < threshold:
                        click.echo(
                            f"  [{i}/{len(jobs)}] {job_name} {pad} "
                            f"SKIP  (fresh - {hours_ago:.0f}h ago, threshold {threshold:.0f}h)"
                        )
                        would_skip += 1
                        continue
                    elif last_status == "SUCCESS":
                        click.echo(
                            f"  [{i}/{len(jobs)}] {job_name} {pad} "
                            f"RUN   (stale - {hours_ago:.0f}h ago, threshold {threshold:.0f}h)"
                        )
                    elif last_status:
                        click.echo(
                            f"  [{i}/{len(jobs)}] {job_name} {pad} "
                            f"RUN   (last {last_status.lower()} {hours_ago:.0f}h ago)"
                        )
                    else:
                        click.echo(
                            f"  [{i}/{len(jobs)}] {job_name} {pad} "
                            f"RUN   (never loaded)"
                        )
                else:
                    click.echo(
                        f"  [{i}/{len(jobs)}] {job_name} {pad} "
                        f"RUN   (never loaded)"
                    )
            else:
                if force:
                    click.echo(f"  [{i}/{len(jobs)}] {job_name} {pad} RUN   (--force)")
                else:
                    click.echo(f"  [{i}/{len(jobs)}] {job_name} {pad} RUN   (no freshness tracking)")

            would_run += 1
        click.echo(f"\n=== Summary ===")
        click.echo(f"  [DRY RUN] {would_run} would run, {would_skip} would skip (fresh)")
        return

    runner = JobRunner()
    ran = 0
    skipped = 0
    failed = 0
    succeeded_jobs = []
    batch_start = time.time()

    for i, job_name in enumerate(jobs, 1):
        if job_name not in JOBS:
            pad = "." * max(1, 25 - len(job_name))
            click.echo(f"  [{i}/{len(jobs)}] {job_name} {pad} SKIP (unknown job)")
            skipped += 1
            continue

        job_def = JOBS[job_name]

        # Freshness check: skip if recently loaded successfully (unless --force)
        if not force and job_def.get("source_system") and job_def.get("staleness_hours"):
            status_info = runner.get_job_status(job_name)
            if status_info and status_info.get("hours_since_last_run") is not None:
                threshold = job_def.get("daily_freshness_hours", job_def["staleness_hours"] / 2)
                hours_ago = status_info["hours_since_last_run"]
                last_status = status_info.get("last_status")
                if last_status == "SUCCESS" and hours_ago < threshold:
                    pad = "." * max(1, 25 - len(job_name))
                    click.echo(
                        f"  [{i}/{len(jobs)}] {job_name} {pad} "
                        f"SKIP (fresh - {hours_ago:.0f}h ago)"
                    )
                    skipped += 1
                    continue
                if last_status and last_status != "SUCCESS":
                    pad = "." * max(1, 25 - len(job_name))
                    click.echo(
                        f"  [{i}/{len(jobs)}] {job_name} {pad} "
                        f"(last run {last_status.lower()} {hours_ago:.0f}h ago - re-running)"
                    )

        # Apply key override for SAM jobs that have --key in their command
        original_command = None
        if "--key" in job_def["command"]:
            original_command = list(job_def["command"])
            cmd = list(job_def["command"])
            key_idx = cmd.index("--key")
            if key_idx + 1 < len(cmd):
                cmd[key_idx + 1] = str(key)
            job_def["command"] = cmd

        # Run the job
        job_start = time.time()
        try:
            success, output = runner.run_job_streaming(job_name)
        finally:
            # Restore original command
            if original_command is not None:
                job_def["command"] = original_command

        elapsed = time.time() - job_start
        duration_str = _format_duration(elapsed)
        pad = "." * max(1, 25 - len(job_name))

        if success:
            # Get post-run stats
            if job_def.get("source_system"):
                post_status = runner.get_job_status(job_name)
                ins = post_status.get("last_records_inserted", 0) if post_status else 0
                upd = post_status.get("last_records_updated", 0) if post_status else 0
                click.echo(
                    f"  [{i}/{len(jobs)}] {job_name} {pad} "
                    f"OK  ({duration_str}, {ins} new, {upd} updated)"
                )
            else:
                click.echo(
                    f"  [{i}/{len(jobs)}] {job_name} {pad} OK  ({duration_str})"
                )
            ran += 1
            succeeded_jobs.append(job_name)
        else:
            click.echo(
                f"  [{i}/{len(jobs)}] {job_name} {pad} FAILED  ({duration_str})"
            )
            failed += 1
            if not continue_on_failure:
                click.echo("\n  Stopping due to failure. Use --continue-on-failure to keep going.")
                break

    total_elapsed = time.time() - batch_start

    click.echo(f"\n=== Summary ===")
    click.echo(f"  Ran: {ran}    Skipped: {skipped}    Failed: {failed}")
    click.echo(f"  Total time: {_format_duration(total_elapsed)}")
    actual_est = sum(JOBS[j].get("estimated_api_calls", 0) for j in succeeded_jobs if j in JOBS)
    click.echo(f"  Est. API calls used: ~{actual_est}")


@click.command("load-daily")
@click.option("--key", type=click.Choice(["1", "2"]), default="2",
              help="SAM.gov API key (default: 2)")
@click.option("--skip", multiple=True,
              help="Skip specific steps by name (repeatable: --skip awards_8a --skip awards_wosb)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would run without executing")
def load_daily(key, skip, dry_run):
    """Run the daily load sequence (16 steps).

    Replaces daily_load.bat with a Python-native command.
    Checks monthly entity load eligibility before daily steps.
    Always continues on failure — no step blocks the next.

    Steps:
      1. opportunities        Load opportunities (31 days back)
      2. fetch_descriptions   Fetch missing descriptions
      3. usaspending_bulk     Load USASpending bulk (5 days back)
      4. awards_8a            Load awards - 8(a) set-aside
      5. awards_wosb          Load awards - WOSB set-aside
      6. awards_sba           Load awards - SBA set-aside
      7. calc_rates           Load CALC+ labor rates
      8. download_attachments Download attachments
      9. extract_text         Extract text from attachments
     10. attachment_intel     Keyword intel from attachment text
     11. description_intel    Keyword intel from description text
     12. extract_identifiers  Extract federal identifiers
     13. cross_ref_identifiers Cross-reference identifiers
     14. intel_backfill       Backfill opportunity intel
     15. attachment_cleanup   Clean up attachment files
     16. sca_revisions        Check SCA WD revisions

    Examples:
        python main.py job daily
        python main.py job daily --key 1
        python main.py job daily --skip awards_8a --skip awards_wosb
        python main.py job daily --dry-run
    """
    setup_logging()

    steps = _get_daily_steps()

    # Check if monthly entity load is needed
    try:
        if _should_load_monthly_entities():
            entity_step = {
                "name": "entity_monthly",
                "description": "Monthly bulk entity load (first Sunday+ of month, not yet loaded)",
                "command": ["python", "main.py", "load", "entities", "--type=monthly"],
            }
            steps = [entity_step] + steps
            click.echo("  Monthly entity load eligible — prepending to daily sequence.")
        else:
            click.echo("  Monthly entity load: not needed (already loaded or before first Sunday).")
    except Exception as e:
        click.echo(f"  Monthly entity check failed ({e}) — skipping.")

    _run_daily_batch(steps, key, skip, dry_run)


@click.command("load-weekly")
@click.option("--key", type=click.Choice(["1", "2"]), default="2",
              help="SAM.gov API key (default: 2)")
@click.option("--skip", multiple=True,
              help="Skip specific jobs (repeatable)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would run without executing")
@click.option("--continue-on-failure", is_flag=True, default=False,
              help="Continue to next job if one fails (default: stop)")
@click.option("--force", is_flag=True, default=False,
              help="Override freshness check - run everything")
def load_weekly(key, skip, dry_run, continue_on_failure, force):
    """Run the weekly load sequence.

    Sequence: entity_daily, opportunities, awards, exclusions,
              subawards, saved_searches

    Examples:
        python main.py job weekly
        python main.py job weekly --dry-run
        python main.py job weekly --skip hierarchy
    """
    _run_batch("Weekly", WEEKLY_SEQUENCE, key, skip, dry_run, continue_on_failure, force)


@click.command("load-monthly")
@click.option("--key", type=click.Choice(["1", "2"]), default="2",
              help="SAM.gov API key (default: 2)")
@click.option("--skip", multiple=True,
              help="Skip specific jobs (repeatable)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would run without executing")
@click.option("--continue-on-failure", is_flag=True, default=False,
              help="Continue to next job if one fails (default: stop)")
@click.option("--force", is_flag=True, default=False,
              help="Override freshness check - run everything")
def load_monthly(key, skip, dry_run, continue_on_failure, force):
    """Run the monthly load sequence.

    Sequence: entity_daily, opportunities, awards,
              subawards, hierarchy, usaspending, saved_searches

    Examples:
        python main.py job monthly
        python main.py job monthly --dry-run
        python main.py job monthly --key 1
    """
    _run_batch("Monthly", MONTHLY_SEQUENCE, key, skip, dry_run, continue_on_failure, force)
