"""Opportunity loading and search CLI commands.

Commands: load-opportunities, search
"""

import sys

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-opportunities")
@click.option("--days-back", default=7, type=int,
              help="Load opportunities posted in the last N days (default: 7)")
@click.option("--set-aside", "set_aside", default=None,
              help="Filter by set-aside code (e.g., WOSB, 8A, SBA). "
                   "If not specified, loads priority set-asides within call budget.")
@click.option("--naics", default=None,
              help="Filter by NAICS code")
@click.option("--posted-from", "posted_from", default=None,
              help="Start date (MM/dd/yyyy) - overrides --days-back")
@click.option("--posted-to", "posted_to", default=None,
              help="End date (MM/dd/yyyy) - defaults to today")
@click.option("--historical", is_flag=True, default=False,
              help="Load 2 years of historical data (breaks into 1-year chunks)")
@click.option("--max-calls", default=5, type=int,
              help="Max API calls for this invocation (default: 5, reserves 5 of 10/day for other work)")
@click.option("--key", "api_key_number", default=1, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 1)")
def load_opportunities(days_back, set_aside, naics, posted_from, posted_to, historical, max_calls, api_key_number):
    """Load contract opportunities from the SAM.gov Opportunities API.

    Fetches opportunities matching the given filters and loads them into
    the local database with change detection and history tracking.

    By default, reserves only 5 API calls for opportunity loading (out of
    10/day free-tier limit), saving the other 5 for entity/other work.
    Use --max-calls to adjust.

    When no --set-aside is specified, loads the top 4 priority set-asides
    (WOSB, EDWOSB, 8A, 8AN) which fit within the 5-call budget for date
    ranges up to 1 year.

    WARNING: Each API call uses 1 of your daily API calls. Multiple
    set-aside types and date chunks each require separate API calls.

    Examples:
        python main.py load-opportunities
        python main.py load-opportunities --days-back=30
        python main.py load-opportunities --set-aside=WOSB --naics=541511
        python main.py load-opportunities --posted-from=01/01/2026 --posted-to=02/01/2026
        python main.py load-opportunities --historical
        python main.py load-opportunities --max-calls=8
    """
    logger = setup_logging()
    from datetime import date as date_cls, timedelta
    from api_clients.sam_opportunity_client import (
        SAMOpportunityClient, ALL_SB_SET_ASIDES, PRIORITY_SET_ASIDES,
    )
    from etl.opportunity_loader import OpportunityLoader
    from etl.load_manager import LoadManager

    chosen_key = settings.SAM_API_KEY_2 if api_key_number == 2 else settings.SAM_API_KEY
    if not chosen_key or chosen_key == "your_api_key_here":
        click.echo(f"ERROR: SAM_API_KEY{'_2' if api_key_number == 2 else ''} not configured in .env file")
        sys.exit(1)

    client = SAMOpportunityClient(call_budget=max_calls, api_key_number=api_key_number)
    loader = OpportunityLoader()
    load_manager = LoadManager()

    # --- Determine date range ---
    today = date_cls.today()

    if historical:
        dt_from = today - timedelta(days=730)  # ~2 years
        # Avoid Feb 29 (leap day) as start date -- SAM.gov API rejects it
        if dt_from.month == 2 and dt_from.day == 29:
            dt_from = dt_from.replace(month=3, day=1)
        dt_to = today
        load_type = "HISTORICAL"
    elif posted_from:
        # posted_from is already in MM/dd/yyyy format for the API
        dt_from = posted_from
        dt_to = posted_to or today.strftime("%m/%d/%Y")
        load_type = "INCREMENTAL"
    else:
        dt_from = today - timedelta(days=days_back)
        dt_to = today
        load_type = "INCREMENTAL"

    # --- Determine which set-aside codes to query ---
    if set_aside:
        # User specified a single set-aside type
        query_codes = [set_aside]
        set_aside_label = set_aside
    else:
        # Default: use priority set-asides (WOSB, EDWOSB, 8A, 8AN) which
        # fit within the 5-call budget for date ranges up to 1 year.
        # With a larger budget, use all 12 set-aside types.
        query_codes = PRIORITY_SET_ASIDES if max_calls <= 5 else ALL_SB_SET_ASIDES
        set_aside_label = f"top {len(query_codes)} priority" if query_codes is PRIORITY_SET_ASIDES else f"all {len(query_codes)} SB"

    # --- Estimate API calls and warn user ---
    remaining = client._get_remaining_requests()
    est_calls = client.estimate_calls_needed(query_codes, dt_from, dt_to)

    click.echo("SAM.gov Opportunities Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Date range:  {client._format_date(dt_from)} to {client._format_date(dt_to)}")
    click.echo(f"  Set-asides:  {set_aside_label} ({', '.join(query_codes)})")
    if naics:
        click.echo(f"  NAICS:       {naics}")
    click.echo(f"  Load type:   {load_type}")
    click.echo(f"  Call budget: {max_calls}")
    click.echo(f"  Est. API calls: ~{est_calls} (at minimum, more with pagination)")
    click.echo(f"  API calls remaining today: {remaining}")

    if est_calls > max_calls:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) exceed call budget "
            f"({max_calls}). Some set-aside types will be skipped."
        )

    if est_calls > remaining:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) may exceed remaining "
            f"daily quota ({remaining}). Some set-aside types may not be queried."
        )

    if historical:
        click.echo(
            "\nHistorical load will fetch 2 years of data across "
            f"{len(query_codes)} set-aside types."
        )
        if est_calls > max_calls:
            click.echo(
                f"NOTE: Budget is tight ({max_calls} calls for {est_calls} "
                f"estimated). Consider using --set-aside to focus on one type, "
                f"or --max-calls to increase the budget."
            )
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    # --- Create load log entry ---
    params_dict = {
        "days_back": days_back,
        "set_aside": set_aside,
        "set_aside_codes": query_codes,
        "naics": naics,
        "posted_from": client._format_date(dt_from),
        "posted_to": client._format_date(dt_to),
        "historical": historical,
        "max_calls": max_calls,
    }
    load_id = load_manager.start_load(
        source_system="SAM_OPPORTUNITY",
        load_type=load_type,
        parameters=params_dict,
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    # --- Fetch opportunities ---
    try:
        if set_aside:
            # Single set-aside search (not subject to budget)
            click.echo(f"Searching for set-aside: {set_aside}...")
            results = list(client.search_opportunities(
                posted_from=dt_from,
                posted_to=dt_to,
                set_aside=set_aside,
                naics=naics,
            ))
        else:
            # Multiple set-aside types (respects call budget)
            click.echo(f"Searching {len(query_codes)} set-aside types within {max_calls}-call budget...")
            results = client.load_all_set_asides(
                posted_from=dt_from,
                posted_to=dt_to,
                naics=naics,
                set_aside_codes=query_codes,
            )

        click.echo(f"Retrieved {len(results):,d} unique opportunities from API")

        if not results:
            click.echo("No opportunities found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # --- Load into database ---
        click.echo("Loading into database...")
        stats = loader.load_opportunities(results, load_id)

        # --- Complete load log ---
        load_manager.complete_load(
            load_id,
            records_read=stats["records_read"],
            records_inserted=stats["records_inserted"],
            records_updated=stats["records_updated"],
            records_unchanged=stats["records_unchanged"],
            records_errored=stats["records_errored"],
        )

        click.echo(f"\nLoad complete!")
        click.echo(f"  Records read:      {stats['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {stats['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {stats['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {stats['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {stats['records_errored']:>10,d}")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Opportunity load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("search")
@click.option("--set-aside", "set_aside", default=None,
              help="Filter by set-aside code (WOSB, 8A, etc.)")
@click.option("--naics", default=None,
              help="Filter by NAICS code")
@click.option("--open-only", is_flag=True, default=False,
              help="Only show opportunities with future response deadlines")
@click.option("--days", default=30, type=int,
              help="Show opportunities posted in last N days (default: 30)")
@click.option("--limit", default=25, type=int,
              help="Max results to show (default: 25)")
def search(set_aside, naics, open_only, days, limit):
    """Search loaded opportunities in the local database.

    Queries the opportunity table (no API calls). Results are ordered by
    response deadline (most urgent first).

    Examples:
        python main.py search
        python main.py search --set-aside=WOSB --open-only
        python main.py search --naics=541511 --days=60
        python main.py search --set-aside=8A --limit=50
    """
    logger = setup_logging()
    from datetime import datetime as dt_cls, timedelta
    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Build query dynamically
        where_clauses = []
        params = []

        # Date filter: posted in last N days
        cutoff = (dt_cls.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        where_clauses.append("o.posted_date >= %s")
        params.append(cutoff)

        if set_aside:
            where_clauses.append("o.set_aside_code = %s")
            params.append(set_aside)

        if naics:
            where_clauses.append("o.naics_code = %s")
            params.append(naics)

        if open_only:
            where_clauses.append("o.response_deadline > NOW()")
            where_clauses.append("o.active = 'Y'")

        where_sql = " AND ".join(where_clauses)

        sql = (
            "SELECT o.title, o.set_aside_code, o.naics_code, "
            "  o.response_deadline, o.posted_date, o.department_name, "
            "  n.description "
            "FROM opportunity o "
            "LEFT JOIN ref_naics_code n ON o.naics_code = n.naics_code "
            f"WHERE {where_sql} "
            "ORDER BY o.response_deadline ASC "
            "LIMIT %s"
        )
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            click.echo("No opportunities found matching the criteria.")
            click.echo(f"  Filters: set-aside={set_aside or 'any'}, "
                       f"naics={naics or 'any'}, "
                       f"posted in last {days} days"
                       + (", open only" if open_only else ""))
            return

        # Print header
        click.echo(f"\nFound {len(rows)} opportunities"
                   + (f" (showing top {limit})" if len(rows) == limit else ""))
        click.echo("")

        # Column headers
        header = (
            f"{'Title':<60s}  {'Set-Aside':>9s}  {'NAICS':>6s}  "
            f"{'Deadline':>12s}  {'Days Left':>9s}  {'Posted':>10s}  "
            f"{'Department':<30s}"
        )
        click.echo(header)
        click.echo("-" * len(header))

        now = dt_cls.now()
        for title, sa_code, naics_code, deadline, posted, dept, naics_desc in rows:
            # Truncate title
            title_str = (title[:57] + "...") if title and len(title) > 60 else (title or "")
            title_str = f"{title_str:<60s}"

            sa_str = f"{(sa_code or ''):>9s}"
            naics_str = f"{(naics_code or ''):>6s}"

            # Response deadline
            if deadline:
                deadline_str = deadline.strftime("%Y-%m-%d")
                delta = deadline - now
                days_left = delta.days
                if days_left < 0:
                    days_str = "CLOSED"
                else:
                    days_str = str(days_left)
            else:
                deadline_str = "N/A"
                days_str = "N/A"

            deadline_str = f"{deadline_str:>12s}"
            days_str = f"{days_str:>9s}"

            # Posted date
            if posted:
                posted_str = posted.strftime("%Y-%m-%d")
            else:
                posted_str = "N/A"
            posted_str = f"{posted_str:>10s}"

            # Department (truncated)
            dept_str = (dept[:27] + "...") if dept and len(dept) > 30 else (dept or "")
            dept_str = f"{dept_str:<30s}"

            click.echo(
                f"{title_str}  {sa_str}  {naics_str}  "
                f"{deadline_str}  {days_str}  {posted_str}  "
                f"{dept_str}"
            )

        # Summary footer
        click.echo("")
        click.echo(f"Filters: set-aside={set_aside or 'any'}, "
                   f"naics={naics or 'any'}, "
                   f"posted in last {days} days"
                   + (", open only" if open_only else ""))

    except Exception as e:
        logger.exception("Search failed")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
