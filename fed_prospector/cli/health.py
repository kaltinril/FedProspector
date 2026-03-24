"""CLI commands for system health, monitoring, and maintenance (Phase 6).

Commands: check-health, load-history, catchup-datasets, run-job,
          maintain-app-data, maintain-db, run-all-searches, ai-usage
"""

import sys

import click
from config.logging_config import setup_logging


@click.command("check-health")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def check_health(as_json):
    """Comprehensive system health check with data freshness and alerts.

    Shows data freshness for all sources, API usage, key status,
    recent errors, and actionable alerts.

    Examples:
        python main.py health check
        python main.py health check --json
    """
    logger = setup_logging()
    from etl.health_check import HealthCheck

    hc = HealthCheck()
    results = hc.check_all()

    # Save snapshot for health trends (Phase 70)
    try:
        hc.save_snapshot(results)
    except Exception:
        logger.warning("Failed to save health snapshot", exc_info=True)

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
        expiry = ""
        if item.get("days_remaining") is not None:
            days = item["days_remaining"]
            if days < 14:
                expiry = f"  ** EXPIRES in {days} days! **"
            else:
                expiry = f"  (expires in {days} days)"
        elif item.get("created_date") is None and item["configured"]:
            expiry = "  (set SAM_API_KEY_CREATED in .env for expiry tracking)"
        click.echo(f"  {item['key_name']:20s} {status} (limit: {item['daily_limit']}/day){expiry}")

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


@click.command("load-history")
@click.option("--source", default=None,
              help="Filter by source_system (e.g., SAM_OPPORTUNITY, SAM_ENTITY)")
@click.option("--days", default=None, type=int,
              help="Number of days to look back")
@click.option("--status", default=None,
              help="Filter by status (e.g., SUCCESS, FAILED, RUNNING)")
@click.option("--limit", default=20, type=int,
              help="Max rows to return (default: 20)")
def load_history(source, days, status, limit):
    """Show ETL load history from etl_load_log.

    Displays recent ETL load runs with timing, record counts, and errors.

    Examples:
        python main.py health load-history
        python main.py health load-history --source SAM_OPPORTUNITY
        python main.py health load-history --days 7
        python main.py health load-history --status FAILED
        python main.py health load-history --limit 50
    """
    setup_logging()
    from datetime import datetime, timedelta
    from db.connection import get_cursor

    try:
        query = (
            "SELECT started_at, source_system, status, "
            "TIMESTAMPDIFF(SECOND, started_at, completed_at) as duration_secs, "
            "records_read, records_inserted, records_updated, records_errored, "
            "error_message "
            "FROM etl_load_log "
            "WHERE 1=1"
        )
        params = []

        if source:
            query += " AND source_system = %s"
            params.append(source)

        if days:
            cutoff = datetime.now() - timedelta(days=days)
            query += " AND started_at >= %s"
            params.append(cutoff)

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY started_at DESC LIMIT %s"
        params.append(limit)

        with get_cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows:
            click.echo("No load history found matching the given filters.")
            return

        # Format duration
        def fmt_duration(secs):
            if secs is None:
                return "-"
            if secs < 60:
                return f"{secs}s"
            minutes = secs // 60
            remainder = secs % 60
            return f"{minutes}m {remainder}s"

        # Format number with commas or dash if None
        def fmt_num(val):
            if val is None:
                return "-"
            return f"{val:,d}"

        click.echo("ETL Load History")
        click.echo("================")
        click.echo(
            f"  {'Started':<21s}{'Source':<20s}{'Status':<10s}"
            f"{'Duration':<11s}{'Read':>7s}  {'Insert':>7s}  "
            f"{'Update':>7s}  {'Errors':>6s}"
        )
        click.echo(
            f"  {'-------------------':<21s}{'------------------':<20s}"
            f"{'--------':<10s}{'----------':<11s}{'-' * 7:>7s}  "
            f"{'-' * 7:>7s}  {'-' * 7:>7s}  {'-' * 6:>6s}"
        )

        for row in rows:
            started = row["started_at"]
            if isinstance(started, datetime):
                started_str = started.strftime("%Y-%m-%d %H:%M:%S")
            else:
                started_str = str(started)

            duration_str = fmt_duration(row["duration_secs"])
            err_msg = row.get("error_message") or ""

            click.echo(
                f"  {started_str:<21s}{row['source_system']:<20s}"
                f"{row['status']:<10s}{duration_str:<11s}"
                f"{fmt_num(row['records_read']):>7s}  "
                f"{fmt_num(row['records_inserted']):>7s}  "
                f"{fmt_num(row['records_updated']):>7s}  "
                f"{fmt_num(row['records_errored']):>6s}"
            )

            if err_msg:
                truncated = err_msg[:50] + "..." if len(err_msg) > 50 else err_msg
                click.echo(
                    f"  {'':21s}Error: {truncated}"
                )

    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


# Manual instructions for sources that can't be auto-caught-up
MANUAL_INSTRUCTIONS = {
    "usaspending": [
        "python main.py load usaspending  (requires --award-id)",
    ],
}

# Hints for sources that have no scheduled job at all
NO_JOB_HINTS = {
    "SAM_SUBAWARD": "python main.py load subawards --key 2",
}


@click.command("catchup-datasets")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be done without actually running")
@click.option("--include-all", is_flag=True, default=False,
              help="Include unsafe jobs that normally require manual steps")
def catchup_datasets(dry_run, include_all):
    """Check which data sources are stale or never-loaded and refresh the safe ones.

    Automatically runs catchup-safe jobs (opportunities, hierarchy, awards,
    calc_rates, exclusions). Skips jobs that require manual multi-step processes
    (entity_daily, usaspending) unless --include-all is used.

    Examples:
        python main.py health catchup
        python main.py health catchup --dry-run
        python main.py health catchup --include-all
    """
    logger = setup_logging()
    from etl.health_check import HealthCheck
    from etl.scheduler import JobRunner, JOBS

    click.echo("Checking data freshness...\n")

    hc = HealthCheck()
    freshness = hc.check_data_freshness()

    # Build a reverse map: source_system -> job_name
    source_to_job = {}
    for job_name, job_def in JOBS.items():
        if job_def.get("source_system"):
            source_to_job[job_def["source_system"]] = job_name

    runner = JobRunner()

    count_refreshed = 0
    count_would_refresh = 0
    count_skipped = 0
    count_healthy = 0
    count_no_job = 0
    total_estimated = 0

    for item in freshness:
        source = item["source"]
        label = item["label"]
        status = item["status"]

        # Format the status line
        if status == "OK":
            click.echo(f"  {label:25s} healthy")
            count_healthy += 1
            continue

        # Build status detail
        if item["hours_ago"] is not None:
            detail = f"{item['hours_ago']:.1f}h ago, threshold {item['threshold_hours']}h"
        else:
            detail = "never loaded"
        click.echo(f"  {label:25s} {status} ({detail})")

        # Find the matching job
        job_name = source_to_job.get(source)

        if not job_name:
            # No job defined for this source
            hint = NO_JOB_HINTS.get(source)
            if hint:
                click.echo(f"    -> No auto-catchup job defined. Run manually:")
                click.echo(f"       {hint}")
            else:
                click.echo(f"    -> No auto-catchup job defined for {source}")
            count_no_job += 1
            continue

        job_def = JOBS[job_name]
        is_safe = job_def.get("catchup_safe", False)

        if not is_safe and not include_all:
            # Unsafe job -- show skip message with manual instructions
            instructions = MANUAL_INSTRUCTIONS.get(job_name)
            if instructions:
                click.echo(f"    -> SKIPPED: Requires manual steps. Run manually:")
                for cmd in instructions:
                    click.echo(f"       {cmd}")
            else:
                click.echo(f"    -> SKIPPED: Not safe for auto-catchup")
            count_skipped += 1
            continue

        # Safe to run (or --include-all was given)
        est = job_def.get("estimated_api_calls", "?")
        if isinstance(est, int):
            total_estimated += est

        if dry_run:
            click.echo(f"    -> DRY RUN: Would run job '{job_name}' (~{est} API calls)")
            count_would_refresh += 1
        else:
            click.echo(f"    -> Running job '{job_name}'...")
            success, output = runner.run_job_streaming(job_name)
            if success:
                click.echo(f"    -> Job '{job_name}' completed OK")
            else:
                click.echo(f"    -> Job '{job_name}' FAILED")
                if output:
                    first_line = output.strip().split("\n")[0][:120]
                    click.echo(f"       Error: {first_line}")
            count_refreshed += 1

    # Summary
    if dry_run:
        click.echo(
            f"\n[DRY RUN] Summary: {count_would_refresh} would be refreshed, "
            f"{count_skipped} skipped, {count_healthy} healthy, {count_no_job} no job defined"
        )
    else:
        click.echo(
            f"\nSummary: {count_refreshed} refreshed, {count_skipped} skipped, "
            f"{count_healthy} healthy, {count_no_job} no job defined"
        )
    if dry_run and total_estimated > 0:
        click.echo(f"\nEstimated total SAM.gov API calls: ~{total_estimated}")


@click.command("run-job")
@click.argument("job_name", default="_")
@click.option("--list", "list_jobs", is_flag=True, help="List all available jobs")
def run_job(job_name, list_jobs):
    """Manually trigger a scheduled job by name.

    Available jobs: opportunities, entity_daily, hierarchy, awards,
    calc_rates, usaspending, exclusions, saved_searches

    Examples:
        python main.py health run-job opportunities
        python main.py health run-job --list
        python main.py health run-job exclusions
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


@click.command("maintain-app-data")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def maintain_app_data(dry_run):
    """Clean up old application data (history, staging, errors).

    Cleans up:
    - Entity/opportunity history records older than 1 year
    - Staging data older than 30 days
    - Load error records older than 90 days

    Use --dry-run to preview what would be cleaned up.

    Examples:
        python main.py health maintain-app-data --dry-run
        python main.py health maintain-app-data
    """
    logger = setup_logging()
    from etl.db_maintenance import DatabaseMaintenance

    maint = DatabaseMaintenance()

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Running application data maintenance...")

    summary = maint.run_all(dry_run=dry_run)

    click.echo(f"\n{prefix}Maintenance summary:")
    for task, count in summary.items():
        verb = "would be " if dry_run else ""
        click.echo(f"  {task:40s} {count:>8,d} records {verb}deleted")


@click.command("maintain-db")
@click.option("--optimize", is_flag=True, default=False,
              help="Include OPTIMIZE TABLE (off by default; rebuilds indexes, can be slow)")
@click.option("--skip-analyze", is_flag=True, default=False,
              help="Skip ANALYZE TABLE (on by default)")
@click.option("--purge-binlog-days", type=int, default=None,
              help="Purge binary logs older than N days")
@click.option("--tables", default=None,
              help="Comma-separated list of tables to operate on (default: all)")
@click.option("--sizes", is_flag=True, default=False,
              help="Show table sizes in MB")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be done without making changes")
def maintain_db(optimize, skip_analyze, purge_binlog_days, tables, sizes, dry_run):
    """Run engine-level MySQL maintenance (analyze, optimize, purge logs).

    By default runs ANALYZE TABLE on all tables to update optimizer statistics.
    Use --optimize to also defragment tables and rebuild indexes (slow on large tables).
    Use --purge-binlog-days N to purge old binary logs.

    Examples:
        python main.py health maintain-db                    # analyze all tables
        python main.py health maintain-db --optimize         # analyze + optimize
        python main.py health maintain-db --dry-run          # preview
        python main.py health maintain-db --purge-binlog-days 7
        python main.py health maintain-db --tables stg_entity_raw,stg_opportunity_raw --optimize
        python main.py health maintain-db --sizes
    """
    logger = setup_logging()
    from db.connection import get_connection
    from config import settings
    from etl.db_maintenance import DatabaseMaintenance

    prefix = "[DRY RUN] " if dry_run else ""
    maint = DatabaseMaintenance()

    # --- Show table sizes ---
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
        if not (optimize or not skip_analyze or purge_binlog_days):
            return

    # --- Resolve table list ---
    if tables:
        table_list = [t.strip() for t in tables.split(",")]
    else:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (settings.DB_NAME,),
            )
            table_list = [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    # --- ANALYZE TABLE ---
    if not skip_analyze:
        click.echo(f"\n{prefix}=== ANALYZE TABLE ({len(table_list)} tables) ===")
        if not dry_run:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                for tbl in table_list:
                    cursor.execute(f"ANALYZE TABLE `{tbl}`")
                    logger.info("Analyzed table: %s", tbl)
                    click.echo(f"  Analyzed: {tbl}")
            finally:
                cursor.close()
                conn.close()
        else:
            for tbl in table_list:
                click.echo(f"  Would analyze: {tbl}")

    # --- OPTIMIZE TABLE ---
    if optimize:
        click.echo(f"\n{prefix}=== OPTIMIZE TABLE ({len(table_list)} tables) ===")
        click.echo("  (This also rebuilds indexes; may take a while on large tables)")
        if not dry_run:
            # Get before sizes for comparison
            before_sizes = {ts["table_name"]: ts for ts in maint.get_table_sizes()}

            conn = get_connection()
            cursor = conn.cursor()
            try:
                for tbl in table_list:
                    before = before_sizes.get(tbl)
                    before_mb = before["data_mb"] + before["index_mb"] if before else 0
                    click.echo(f"  Optimizing: {tbl}...", nl=False)
                    cursor.execute(f"OPTIMIZE TABLE `{tbl}`")
                    logger.info("Optimized table: %s", tbl)
                    click.echo(" done")
            finally:
                cursor.close()
                conn.close()

            # Show before/after sizes
            after_sizes = {ts["table_name"]: ts for ts in maint.get_table_sizes()}
            click.echo(f"\n{prefix}=== Size Changes ===")
            for tbl in table_list:
                before = before_sizes.get(tbl)
                after = after_sizes.get(tbl)
                if before and after:
                    b_total = before["data_mb"] + before["index_mb"]
                    a_total = after["data_mb"] + after["index_mb"]
                    diff = a_total - b_total
                    sign = "+" if diff >= 0 else ""
                    click.echo(
                        f"  {tbl:35s} {b_total:>8.1f} MB -> {a_total:>8.1f} MB "
                        f"({sign}{diff:.1f} MB)"
                    )
        else:
            for tbl in table_list:
                click.echo(f"  Would optimize: {tbl}")

    # --- Binary log purge ---
    if purge_binlog_days is not None:
        click.echo(f"\n{prefix}=== Binary Log Purge ===")
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW VARIABLES LIKE 'log_bin'")
            row = cursor.fetchone()
            log_bin_enabled = row and row[1].upper() == "ON"

            if not log_bin_enabled:
                click.echo("  Binary logging is NOT enabled. Skipping purge.")
            else:
                if dry_run:
                    click.echo(
                        f"  Would purge binary logs older than {purge_binlog_days} days"
                    )
                else:
                    cursor.execute(
                        f"PURGE BINARY LOGS BEFORE NOW() - INTERVAL {purge_binlog_days} DAY"
                    )
                    click.echo(
                        f"  Purged binary logs older than {purge_binlog_days} days"
                    )
                    logger.info("Purged binary logs older than %d days", purge_binlog_days)
        finally:
            cursor.close()
            conn.close()

    # --- InnoDB undo log truncation status ---
    click.echo(f"\n{prefix}=== InnoDB Status ===")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Undo log truncation
        cursor.execute("SHOW VARIABLES LIKE 'innodb_undo_log_truncate'")
        row = cursor.fetchone()
        undo_status = row[1] if row else "unknown"
        click.echo(f"  innodb_undo_log_truncate: {undo_status}")

        # Buffer pool size
        cursor.execute("SHOW VARIABLES LIKE 'innodb_buffer_pool_size'")
        row = cursor.fetchone()
        if row:
            pool_bytes = int(row[1])
            pool_mb = pool_bytes / (1024 * 1024)
            click.echo(f"  innodb_buffer_pool_size:  {pool_mb:.0f} MB")

        # Redo log
        cursor.execute("SHOW VARIABLES LIKE 'innodb_redo_log_capacity'")
        row = cursor.fetchone()
        if row:
            redo_bytes = int(row[1])
            redo_mb = redo_bytes / (1024 * 1024)
            click.echo(f"  innodb_redo_log_capacity: {redo_mb:.0f} MB")

        # Undo tablespaces
        cursor.execute(
            "SELECT TABLESPACE_NAME, FILE_NAME, "
            "ROUND(TOTAL_EXTENTS * EXTENT_SIZE / 1024 / 1024, 1) AS size_mb "
            "FROM information_schema.FILES "
            "WHERE FILE_TYPE = 'UNDO LOG' "
            "ORDER BY TABLESPACE_NAME"
        )
        undo_rows = cursor.fetchall()
        if undo_rows:
            click.echo("  Undo tablespaces:")
            for urow in undo_rows:
                click.echo(f"    {urow[0]}: {urow[2]} MB ({urow[1]})")
    finally:
        cursor.close()
        conn.close()

    click.echo(f"\n{prefix}Engine maintenance complete.")


@click.command("ai-usage")
@click.option("--days", default=30, type=int, help="Number of days to look back (default: 30)")
def ai_usage(days):
    """Show AI analysis cost and token usage summary.

    Queries the ai_usage_log table for spending visibility on Claude API usage
    for attachment analysis.

    Examples:
        python main.py health ai-usage
        python main.py health ai-usage --days 7
        python main.py health ai-usage --days 90
    """
    setup_logging()
    from db.connection import get_cursor

    try:
        # Summary
        with get_cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT "
                "  COUNT(*) as total_requests, "
                "  COUNT(DISTINCT attachment_id) as total_documents, "
                "  COALESCE(SUM(input_tokens), 0) as total_input_tokens, "
                "  COALESCE(SUM(output_tokens), 0) as total_output_tokens, "
                "  COALESCE(SUM(cost_usd), 0) as total_cost_usd "
                "FROM ai_usage_log "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,),
            )
            summary = cursor.fetchone()

        # By model
        with get_cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT model, COUNT(*) as requests, "
                "  COALESCE(SUM(cost_usd), 0) as cost_usd "
                "FROM ai_usage_log "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY model ORDER BY cost_usd DESC",
                (days,),
            )
            by_model = cursor.fetchall()

        # By day (last 7 days within the period)
        with get_cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT DATE(created_at) as day, COUNT(*) as requests, "
                "  COALESCE(SUM(cost_usd), 0) as cost_usd "
                "FROM ai_usage_log "
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                "GROUP BY DATE(created_at) ORDER BY day DESC "
                "LIMIT 7",
                (days,),
            )
            by_day = cursor.fetchall()

        # Format output
        click.echo(f"\nAI Analysis Usage - Last {days} Days")
        click.echo("=" * 40)
        click.echo(f"  Total cost:       ${summary['total_cost_usd']:.2f}")
        click.echo(f"  Total requests:   {summary['total_requests']:,d}")
        click.echo(f"  Total documents:  {summary['total_documents']:,d}")
        click.echo(f"  Input tokens:     {int(summary['total_input_tokens']):,d}")
        click.echo(f"  Output tokens:    {int(summary['total_output_tokens']):,d}")

        if by_model:
            click.echo(f"\nBy Model:")
            for row in by_model:
                model_name = row["model"] or "unknown"
                click.echo(
                    f"  {model_name:20s} ${row['cost_usd']:.2f}  "
                    f"({row['requests']:,d} requests)"
                )

        if by_day:
            click.echo(f"\nBy Day (last 7):")
            for row in by_day:
                day_str = str(row["day"])
                click.echo(
                    f"  {day_str}  ${row['cost_usd']:.2f}  "
                    f"({row['requests']:,d} requests)"
                )

        if summary["total_requests"] == 0:
            click.echo("\n  No AI usage recorded in this period.")

    except Exception as e:
        err_msg = str(e)
        if "ai_usage_log" in err_msg.lower() or "doesn't exist" in err_msg.lower():
            click.echo(
                "ERROR: ai_usage_log table does not exist.\n"
                "Run 'python main.py setup build' to create it, or run the "
                "Phase 110C schema migration."
            )
        else:
            click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("run-all-searches")
def run_all_searches():
    """Run all saved searches with notifications enabled.

    Executes each saved search and reports new results since the last run.
    This is used by the scheduled job system.

    Examples:
        python main.py health run-all-searches
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
