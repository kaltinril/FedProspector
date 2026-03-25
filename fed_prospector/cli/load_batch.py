"""CLI commands for batch loading: daily, weekly, monthly sequences (Phase 61).

Commands: job-daily, job-weekly, job-monthly
"""

import time

import click

from config.logging_config import setup_logging


# Job sequences for each batch mode
DAILY_SEQUENCE = ["opportunities", "awards", "saved_searches", "auto_prospect"]
FULL_SEQUENCE = [
    "entity_daily", "opportunities", "awards",
    "subawards", "hierarchy",
    "attachment_ai", "intel_backfill", "attachment_cleanup",
    "saved_searches",
]
WEEKLY_SEQUENCE = [
    "entity_daily", "hierarchy", "awards", "exclusions",
    "subawards", "saved_searches",
]
MONTHLY_SEQUENCE = [
    "entity_daily", "opportunities", "awards",
    "subawards", "hierarchy", "calc_rates", "usaspending", "saved_searches",
]

KEY_LIMITS = {"1": "10/day", "2": "1000/day"}


def _format_duration(seconds):
    """Format seconds as Xs or Xm Ys."""
    secs = int(seconds)
    if secs < 60:
        return f"{secs}s"
    minutes = secs // 60
    remainder = secs % 60
    return f"{minutes}m {remainder}s"


def _run_batch(mode_name, sequence, key, skip, dry_run, continue_on_failure, force):
    """Shared logic for daily/weekly/monthly batch commands."""
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
    click.echo(f"  Mode: {'Full' if len(jobs) > len(DAILY_SEQUENCE) else 'Standard'} ({len(jobs)} jobs)")
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
            # Show awards parameter preview
            if job_name == "awards":
                try:
                    from etl.load_manager import LoadManager
                    from config import settings
                    lm = LoadManager()
                    wm = lm.get_watermark("SAM_AWARDS", date_key="date_to")
                    _, resume_params = lm.get_resumable_load("SAM_AWARDS")
                    from etl.etl_utils import get_tracked_naics, get_tracked_set_asides
                    naics_count = len(get_tracked_naics())
                    sa_count = len(get_tracked_set_asides())
                    wm_display = f"{wm} to today" if wm else "none (1yr fallback)"
                    if resume_params:
                        done = len(resume_params.get("completed_combos", []))
                        cur_sa = resume_params.get("current_set_aside", "?")
                        cur_n = resume_params.get("current_naics", "?")
                        cur_p = resume_params.get("current_page", 0)
                        resume_display = f"{done} done, next: {cur_sa}/{cur_n} pg {cur_p}"
                    else:
                        resume_display = "none"
                    click.echo(f"         watermark: {wm_display} | {naics_count} NAICS x {sa_count} set-asides | resume: {resume_display}")
                except Exception:
                    pass  # Don't let preview errors block dry-run

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
@click.option("--full", is_flag=True, default=False,
              help="Include entity refresh + hierarchy + subawards")
@click.option("--skip", multiple=True,
              help="Skip specific jobs (repeatable: --skip awards --skip exclusions)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would run without executing")
@click.option("--continue-on-failure", is_flag=True, default=False,
              help="Continue to next job if one fails (default: stop)")
@click.option("--force", is_flag=True, default=False,
              help="Override freshness check - run everything")
def load_daily(key, full, skip, dry_run, continue_on_failure, force):
    """Run the daily load sequence.

    Standard: opportunities, awards, saved_searches
    Full (--full): entity_daily, opportunities, awards,
                   subawards, hierarchy, attachment_ai,
                   intel_backfill, attachment_cleanup, saved_searches

    Examples:
        python main.py job daily
        python main.py job daily --key 1
        python main.py job daily --full
        python main.py job daily --skip awards
        python main.py job daily --dry-run
    """
    sequence = FULL_SEQUENCE if full else DAILY_SEQUENCE
    _run_batch("Daily", sequence, key, skip, dry_run, continue_on_failure, force)


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

    Sequence: entity_daily, hierarchy, awards, exclusions,
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
              subawards, hierarchy, calc_rates, usaspending, saved_searches

    Examples:
        python main.py job monthly
        python main.py job monthly --dry-run
        python main.py job monthly --key 1
    """
    _run_batch("Monthly", MONTHLY_SEQUENCE, key, skip, dry_run, continue_on_failure, force)
