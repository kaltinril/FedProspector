"""CLI commands for system health, monitoring, and maintenance (Phase 6)."""

import click
from config.logging_config import setup_logging


@click.command("check-health")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def check_health(as_json):
    """Comprehensive system health check with data freshness and alerts.

    Shows data freshness for all sources, API usage, key status,
    recent errors, and actionable alerts.

    Examples:
        python main.py check-health
        python main.py check-health --json
    """
    logger = setup_logging()
    from etl.health_check import HealthCheck

    hc = HealthCheck()
    results = hc.check_all()

    if as_json:
        import json
        # Convert datetime objects to strings for JSON serialization
        click.echo(json.dumps(results, default=str, indent=2))
        return

    # Pretty-print the health check results
    # Section: Data Freshness
    click.echo("=== Data Freshness ===")
    for item in results["data_freshness"]:
        status_icon = {
            "OK": "OK",
            "WARNING": "WARN",
            "STALE": "STALE!",
            "NEVER": "NEVER",
        }
        icon = status_icon.get(item["status"], "???")
        if item["last_load"]:
            click.echo(
                f"  {item['label']:25s} Last: {item['last_load']}  "
                f"({item['hours_ago']:.0f}h ago)  [{icon}]"
            )
        else:
            click.echo(f"  {item['label']:25s} Never loaded  [{icon}]")

    # Section: Table Statistics
    click.echo("\n=== Table Statistics ===")
    for item in results["table_stats"]:
        click.echo(f"  {item['table_name']:35s} {item['row_count']:>10,d}")

    # Section: API Usage Today
    click.echo("\n=== API Usage Today ===")
    for item in results["api_usage"]:
        click.echo(
            f"  {item['source']:20s} {item['used']:>4d} / {item['limit']:>5d} "
            f"({item['remaining']} remaining)"
        )

    # Section: API Keys
    click.echo("\n=== API Key Status ===")
    for item in results["api_key_status"]:
        status = "configured" if item["configured"] else "NOT CONFIGURED"
        click.echo(f"  {item['key_name']:20s} {status} (limit: {item['daily_limit']}/day)")

    # Section: Alerts
    click.echo("\n=== Alerts ===")
    alerts = results["alerts"]
    if alerts:
        for alert in alerts:
            click.echo(f"  [{alert['level']}] {alert['message']}")
    else:
        click.echo("  [OK] No alerts")

    # Section: Recent Errors
    if results["recent_errors"]:
        click.echo(f"\n=== Recent Errors (last 7 days) ===")
        for err in results["recent_errors"]:
            msg = err.get("error_message", "")
            if msg and len(msg) > 80:
                msg = msg[:80] + "..."
            click.echo(
                f"  {err['started_at']} | {err['source_system']:20s} | {msg}"
            )


@click.command("run-job")
@click.argument("job_name", default="_")
@click.option("--list", "list_jobs", is_flag=True, help="List all available jobs")
def run_job(job_name, list_jobs):
    """Manually trigger a scheduled job by name.

    Available jobs: opportunities, entity_daily, hierarchy, awards,
    calc_rates, usaspending, exclusions, saved_searches

    Examples:
        python main.py run-job opportunities
        python main.py run-job --list
        python main.py run-job exclusions
    """
    logger = setup_logging()
    from etl.scheduler import JobRunner, JOBS

    if list_jobs:
        click.echo("Available jobs:")
        click.echo(
            f"  {'Name':20s}  {'Schedule':25s}  {'Priority':10s}  Description"
        )
        click.echo(f"  {'-'*20}  {'-'*25}  {'-'*10}  {'-'*40}")
        for name, job in JOBS.items():
            click.echo(
                f"  {name:20s}  {job['schedule']:25s}  "
                f"{job['priority']:10s}  {job['description']}"
            )
        return

    if job_name == "_":
        click.echo("ERROR: Job name is required. Use --list to see available jobs.")
        return

    if job_name not in JOBS:
        click.echo(f"Unknown job: {job_name}")
        click.echo(f"Available: {', '.join(JOBS.keys())}")
        return

    runner = JobRunner()
    click.echo(f"Running job: {job_name} ({JOBS[job_name]['description']})")
    success, output = runner.run_job(job_name)

    if success:
        click.echo(f"\nJob completed successfully.")
    else:
        click.echo(f"\nJob FAILED.")

    if output:
        click.echo(f"\nOutput:\n{output}")


@click.command("maintain-db")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--analyze", is_flag=True, help="Run ANALYZE TABLE on all tables")
@click.option("--sizes", is_flag=True, help="Show table sizes in MB")
def maintain_db(dry_run, analyze, sizes):
    """Run database maintenance tasks (cleanup old data, update stats).

    Cleans up:
    - Entity/opportunity history records older than 1 year
    - Staging data older than 30 days
    - Load error records older than 90 days

    Use --dry-run to preview what would be cleaned up.
    Use --analyze to update table statistics for the query optimizer.
    Use --sizes to show table sizes.

    Examples:
        python main.py maintain-db --dry-run
        python main.py maintain-db
        python main.py maintain-db --analyze
        python main.py maintain-db --sizes
    """
    logger = setup_logging()
    from etl.db_maintenance import DatabaseMaintenance

    maint = DatabaseMaintenance()

    if sizes:
        click.echo("=== Table Sizes ===")
        table_sizes = maint.get_table_sizes()
        for ts in table_sizes:
            click.echo(
                f"  {ts['table_name']:35s} {ts['data_mb']:>8.1f} MB data  "
                f"{ts['index_mb']:>8.1f} MB index  {ts['rows']:>10,d} rows"
            )
        total_data = sum(t["data_mb"] for t in table_sizes)
        total_idx = sum(t["index_mb"] for t in table_sizes)
        click.echo(
            f"  {'TOTAL':35s} {total_data:>8.1f} MB data  "
            f"{total_idx:>8.1f} MB index"
        )
        return

    if analyze:
        click.echo("Running ANALYZE TABLE on all tables...")
        maint.analyze_tables()
        click.echo("Done.")
        return

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Running database maintenance...")

    summary = maint.run_all(dry_run=dry_run)

    click.echo(f"\n{prefix}Maintenance summary:")
    for task, count in summary.items():
        verb = "would be " if dry_run else ""
        click.echo(f"  {task:40s} {count:>8,d} records {verb}deleted")


@click.command("run-all-searches")
def run_all_searches():
    """Run all saved searches with notifications enabled.

    Executes each saved search and reports new results since the last run.
    This is used by the scheduled job system.

    Examples:
        python main.py run-all-searches
    """
    logger = setup_logging()
    from db.connection import get_connection
    from etl.prospect_manager import ProspectManager

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT search_id, search_name, filter_criteria "
            "FROM saved_search "
            "WHERE is_active = 'Y'"
        )
        searches = cursor.fetchall()

        if not searches:
            click.echo("No active saved searches found.")
            return

        click.echo(f"Running {len(searches)} saved search(es)...")

        pm = ProspectManager()
        for search in searches:
            try:
                result = pm.run_search(search_id=search["search_id"])
                count = result.get("count", 0) if result else 0
                new_count = result.get("new_count", 0) if result else 0
                click.echo(
                    f"  {search['search_name']:30s}  "
                    f"{count:>5d} results ({new_count} new)"
                )
            except Exception as e:
                click.echo(
                    f"  {search['search_name']:30s}  ERROR: {e}"
                )
                logger.warning(
                    "Saved search %s failed: %s", search["search_name"], e
                )
    finally:
        cursor.close()
        conn.close()
