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
              help="Set-aside filter. Comma-separated codes (WOSB,8A), "
                   "'all' for all 12 SB types. "
                   "Default: none (fetches all types, filter in the app).")
@click.option("--naics", default=None,
              help="NAICS code(s) to search -- comma-separated for multiple: 541512,541511")
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
@click.option("--force", is_flag=True, default=False,
              help="Ignore previous progress and start a fresh load")
def load_opportunities(days_back, set_aside, naics, posted_from, posted_to,
                       historical, max_calls, api_key_number, force):
    """Load contract opportunities from the SAM.gov Opportunities API.

    Fetches opportunities matching the given filters and loads them into
    the local database with change detection and history tracking.
    Automatically resumes from the last page fetched if a previous partial
    load exists for the same date range. Use --force to ignore previous
    progress and start fresh.

    By default, reserves only 5 API calls for opportunity loading (out of
    10/day free-tier limit), saving the other 5 for entity/other work.
    Use --max-calls to adjust.

    Set-aside behaviour:
      (omitted)       Use org's certification-based set-asides from DB
      --set-aside none     Omit typeOfSetAside param (returns ALL types)
      --set-aside all      All 12 SB set-aside codes, one call each
      --set-aside WOSB,8A  Specific codes, one call per code
      --set-aside WOSB     Single code

    NAICS behaviour:
      (omitted)            No NAICS filter (fetch all)
      --naics 541511       Single NAICS code
      --naics 541511,541512  Comma-separated, one API sweep per code

    WARNING: Each API call uses 1 of your daily API calls. Multiple
    NAICS codes and set-aside types each require separate API calls.

    Examples:
        python main.py load opportunities
        python main.py load opportunities --days-back=30
        python main.py load opportunities --set-aside=WOSB --naics=541511
        python main.py load opportunities --set-aside=none --naics=541511,541512
        python main.py load opportunities --set-aside=all --max-calls=20
        python main.py load opportunities --posted-from=01/01/2026 --posted-to=02/01/2026
        python main.py load opportunities --historical
        python main.py load opportunities --max-calls=8
        python main.py load opportunities --force
    """
    logger = setup_logging()
    from datetime import date as date_cls, timedelta
    import json as _json
    from api_clients.sam_opportunity_client import (
        SAMOpportunityClient, ALL_SB_SET_ASIDES, PRIORITY_SET_ASIDES,
    )
    from api_clients.base_client import RateLimitExceeded
    from etl.opportunity_loader import OpportunityLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection

    chosen_key = settings.SAM_API_KEY_2 if api_key_number == 2 else settings.SAM_API_KEY
    if not chosen_key or chosen_key == "your_api_key_here":
        click.echo(f"ERROR: SAM_API_KEY{'_2' if api_key_number == 2 else ''} not configured in .env file")
        sys.exit(1)

    client = SAMOpportunityClient(call_budget=max_calls, api_key_number=api_key_number)
    loader = OpportunityLoader()
    load_mgr = LoadManager()

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
        # Parse MM/dd/yyyy strings to date objects for consistent handling
        from datetime import datetime as _dt
        dt_from = _dt.strptime(posted_from, "%m/%d/%Y").date()
        dt_to = _dt.strptime(posted_to, "%m/%d/%Y").date() if posted_to else today
        load_type = "INCREMENTAL"
    else:
        dt_from = today - timedelta(days=days_back)
        dt_to = today
        load_type = "INCREMENTAL"

    # Normalise date strings for consistent resume key matching (always YYYY-MM-DD)
    posted_from_str = dt_from.isoformat()
    posted_to_str = dt_to.isoformat()

    # --- Parse NAICS codes ---
    naics_codes = [c.strip() for c in naics.split(',') if c.strip()] if naics else []
    # For iteration: [None] means "no NAICS filter"
    naics_codes_to_load = naics_codes if naics_codes else [None]

    # --- Determine which set-aside codes to query ---
    sa_strategy = "default"  # for display
    if set_aside is not None:
        sa_lower = set_aside.strip().lower()
        if sa_lower == "none":
            # Omit typeOfSetAside entirely -- returns all types
            query_codes = [None]
            set_aside_label = "none (all types)"
            sa_strategy = "none"
        elif sa_lower == "all":
            query_codes = list(ALL_SB_SET_ASIDES)
            set_aside_label = f"all {len(query_codes)} SB"
            sa_strategy = "all"
        else:
            # Comma-separated list of specific codes
            query_codes = [c.strip() for c in set_aside.split(',') if c.strip()]
            set_aside_label = ', '.join(query_codes)
            sa_strategy = "explicit"
    else:
        # Default: no set-aside filter — fetch everything, filter downstream
        query_codes = [None]
        set_aside_label = "none (all types)"
        sa_strategy = "none"

    # Total combos for progress tracking
    total_combos = len(naics_codes_to_load) * len(query_codes)

    # --- Check previous loads for this date range (resume support) ---
    completed_combos = []
    resume_naics = None
    resume_set_aside = None
    resume_page = 0
    pages_fetched_total = 0
    prev_load = None

    if not force:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT load_id, status, records_inserted, records_updated, parameters "
                "FROM etl_load_log "
                "WHERE source_system = 'SAM_OPPORTUNITY' "
                "AND parameters LIKE %s "
                "AND parameters LIKE %s "
                "ORDER BY CAST(JSON_EXTRACT(parameters, '$.pages_fetched') AS UNSIGNED) DESC "
                "LIMIT 1",
                (f'%"posted_from": "{posted_from_str}"%',
                 f'%"posted_to": "{posted_to_str}"%'),
            )
            prev_load = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if prev_load:
            prev_params = _json.loads(prev_load["parameters"]) if prev_load["parameters"] else {}
            prev_pages = prev_params.get("pages_fetched", 0)
            is_complete = prev_params.get("complete", False)

            if is_complete:
                click.echo(
                    f"Already loaded all opportunities for {posted_from_str} to "
                    f"{posted_to_str} (load_id={prev_load['load_id']}: "
                    f"{prev_load['records_inserted']} inserted, "
                    f"{prev_load['records_updated']} updated). Skipping."
                )
                click.echo("  Use --force to reload from scratch.")
                return

            if prev_pages > 0:
                completed_combos = list(prev_params.get("completed_combos", []))
                resume_naics = prev_params.get("current_naics")
                resume_set_aside = prev_params.get("current_set_aside")
                resume_page = prev_params.get("current_page", 0)
                pages_fetched_total = prev_pages
                click.echo(
                    f"Resuming from previous partial load (load_id={prev_load['load_id']})"
                )
                click.echo(
                    f"  Completed combos: {len(completed_combos)}/{total_combos}, "
                    f"total pages so far: {prev_pages}"
                )
                if resume_naics or resume_set_aside:
                    click.echo(
                        f"  Continuing from: naics={resume_naics or 'ALL'} "
                        f"sa={resume_set_aside or 'ALL'} page {resume_page}"
                    )

    # --- Estimate API calls and warn user ---
    remaining = client._get_remaining_requests()
    # Estimate: one call per (naics, set-aside) combo per date chunk, at minimum
    num_chunks = len(client._split_date_range(dt_from, dt_to))
    est_calls = total_combos * num_chunks

    click.echo("SAM.gov Opportunities Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Date range:  {posted_from_str} to {posted_to_str}")
    click.echo(f"  Set-asides:  {set_aside_label}")
    if naics_codes:
        click.echo(f"  NAICS:       {', '.join(naics_codes)} ({len(naics_codes)} codes)")
    else:
        click.echo(f"  NAICS:       all (no filter)")
    click.echo(f"  Combos:      {total_combos - len(completed_combos)} remaining of {total_combos}")
    click.echo(f"  Load type:   {load_type}")
    click.echo(f"  Call budget: {max_calls}")
    click.echo(f"  Est. API calls: ~{est_calls} (at minimum, more with pagination)")
    click.echo(f"  API calls remaining today: {remaining}")

    if est_calls > max_calls:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) exceed call budget "
            f"({max_calls}). Some combos will be skipped."
        )

    if est_calls > remaining:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) may exceed remaining "
            f"daily quota ({remaining}). Some combos may not be queried."
        )

    if historical:
        click.echo(
            "\nHistorical load will fetch 2 years of data across "
            f"{total_combos} combos."
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
        "posted_from": posted_from_str,
        "posted_to": posted_to_str,
        "set_aside": set_aside,
        "set_aside_codes": [c for c in query_codes if c is not None] or ["none"],
        "naics": naics,
        "naics_codes": naics_codes or [],
        "historical": historical,
        "max_calls": max_calls,
        "pages_fetched": pages_fetched_total,
        "total_records": None,
        "complete": False,
        "completed_combos": completed_combos,
        "current_naics": resume_naics,
        "current_set_aside": resume_set_aside,
        "current_page": resume_page,
    }

    load_id = load_mgr.start_load(
        source_system="SAM_OPPORTUNITY",
        load_type=load_type,
        parameters=params_dict,
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    # --- Nested-loop fetch and load ---
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    remaining_budget = max_calls
    rate_limited = False

    try:
        budget_exhausted = False

        for naics_code in naics_codes_to_load:
            if budget_exhausted:
                break

            for sa_code in query_codes:
                if budget_exhausted:
                    break

                # Build combo key for tracking (matches awards pattern)
                combo = [naics_code or "", sa_code or ""]

                # Skip completed combos
                if combo in completed_combos:
                    continue

                naics_label = naics_code or "ALL"
                sa_label = sa_code or "ALL"
                label = f"{sa_label}/{naics_label}"

                # Determine start page (resume within a combo)
                start_pg = 0
                if sa_code == resume_set_aside and naics_code == resume_naics:
                    start_pg = resume_page
                    resume_set_aside = None  # Clear resume state after using it
                    resume_naics = None
                    resume_page = 0
                    if start_pg > 0:
                        click.echo(f"    Resuming from page {start_pg}")

                if remaining_budget <= 0:
                    budget_exhausted = True
                    click.echo(f"\n  Budget exhausted ({max_calls} calls). Progress saved.")
                    click.echo(f"     Run again to resume from {label}.")
                    break

                click.echo(
                    f"\n  [{len(completed_combos)+1}/{total_combos}] "
                    f"sa={sa_label} naics={naics_label} (page {start_pg})..."
                )

                combo_exhausted = True  # assume we'll finish unless budget runs out
                for opps, page_num, total in client.iter_opportunity_pages(
                    posted_from=dt_from, posted_to=dt_to,
                    set_aside=sa_code, naics=naics_code,
                    start_page=start_pg, max_pages=remaining_budget,
                ):
                    if opps:
                        page_stats = loader.load_opportunity_batch(opps, load_id)
                        for k in cumulative:
                            cumulative[k] += page_stats.get(k, 0)

                    pages_fetched_total += 1
                    remaining_budget -= 1
                    pages_in_combo = page_num + 1

                    params_dict.update({
                        "current_naics": naics_code,
                        "current_set_aside": sa_code,
                        "current_page": pages_in_combo,
                        "completed_combos": completed_combos,
                        "pages_fetched": pages_fetched_total,
                        "total_records": total,
                        "complete": False,
                    })
                    load_mgr.save_load_progress(load_id, parameters=params_dict, **cumulative)

                    click.echo(f"    pg {page_num}: {len(opps)} rows")

                    if remaining_budget <= 0:
                        combo_exhausted = False
                        break
                else:
                    # for-loop completed without break => combo fully loaded
                    combo_exhausted = True

                if combo_exhausted:
                    completed_combos.append(combo)
                    params_dict["completed_combos"] = completed_combos
                    load_mgr.save_load_progress(load_id, parameters=params_dict, **cumulative)
                    click.echo(f"  Done: {label}")
                else:
                    budget_exhausted = True
                    click.echo(f"\n  Budget exhausted ({max_calls} calls). Progress saved.")
                    click.echo(f"     Run again to resume from {label} page {pages_in_combo}.")

        # Check if all combos complete
        if len(completed_combos) >= total_combos:
            params_dict["complete"] = True
            load_mgr.save_load_progress(load_id, parameters=params_dict, **cumulative)

    except KeyboardInterrupt:
        click.echo(f"\n  Interrupted. Progress saved.")
        click.echo("  Run the same command again to continue.")
        return
    except RateLimitExceeded:
        rate_limited = True
        click.echo(f"  Rate limit reached. Progress saved.")
    except Exception as e:
        if isinstance(getattr(e, '__context__', None), KeyboardInterrupt):
            click.echo(f"\n  Interrupted. Progress saved.")
            click.echo("  Run the same command again to continue.")
            return
        if "429" in str(e):
            rate_limited = True
            click.echo(f"  Server rate limit (429). Progress saved.")
            if api_key_number == 1:
                click.echo("  Tip: Use --key=2 for the 1000/day tier.")
        else:
            load_mgr.fail_load(load_id, str(e))
            logger.exception("Opportunity load failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)

    # --- Summary ---
    is_complete = params_dict.get("complete", False)
    remaining_after = client._get_remaining_requests()
    status = "COMPLETE" if is_complete else "PARTIAL"
    click.echo(f"\nOpportunity load {status}!")
    click.echo(f"  Combos completed:  {len(completed_combos)}/{total_combos}")
    click.echo(f"  Records read:      {cumulative['records_read']:>10,d}")
    click.echo(f"  Records inserted:  {cumulative['records_inserted']:>10,d}")
    click.echo(f"  Records updated:   {cumulative['records_updated']:>10,d}")
    click.echo(f"  Records unchanged: {cumulative['records_unchanged']:>10,d}")
    click.echo(f"  Records errored:   {cumulative['records_errored']:>10,d}")
    click.echo(f"  API calls remaining: {remaining_after}")
    if not is_complete:
        click.echo("  Run the same command again to continue.")


@click.command("search")
@click.option("--set-aside", "set_aside", default=None,
              help="Filter by set-aside code (WOSB, 8A, etc.)")
@click.option("--naics", default=None,
              help="Filter by NAICS code")
@click.option("--open-only", is_flag=True, default=False,
              help="Only show opportunities with future response deadlines")
@click.option("--days", default=30, type=int,
              help="Show opportunities posted in last N days (default: 30)")
@click.option("--keyword", default=None,
              help="Filter by keyword in opportunity title (partial match)")
@click.option("--department", default=None,
              help="Filter by department name (partial match)")
@click.option("--limit", default=25, type=int,
              help="Max results to show (default: 25)")
def search(set_aside, naics, open_only, days, keyword, department, limit):
    """Search loaded opportunities in the local database.

    Queries the opportunity table (no API calls). Results are ordered by
    response deadline (most urgent first).

    Examples:
        python main.py search opportunities
        python main.py search opportunities --set-aside=WOSB --open-only
        python main.py search opportunities --naics=541511 --days=60
        python main.py search opportunities --set-aside=8A --limit=50
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

        if keyword:
            where_clauses.append("o.title LIKE %s")
            params.append(f"%{keyword}%")

        if department:
            where_clauses.append("o.department_name LIKE %s")
            params.append(f"%{department}%")

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
                       f"keyword={keyword or 'any'}, "
                       f"department={department or 'any'}, "
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
                   f"keyword={keyword or 'any'}, "
                   f"department={department or 'any'}, "
                   f"posted in last {days} days"
                   + (", open only" if open_only else ""))

    except Exception as e:
        logger.exception("Search failed")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
