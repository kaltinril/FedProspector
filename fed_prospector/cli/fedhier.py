"""CLI commands for federal hierarchy data (Phase 5D)."""

import sys
import time
from datetime import date, timedelta

import click

from config.logging_config import setup_logging
from cli.cli_utils import QueryBuilder


@click.command("load-hierarchy")
@click.option("--status", default="Active", help="Organization status filter (Active/Inactive, default: Active)")
@click.option("--max-calls", default=50, type=int, help="Max API calls for this invocation (default: 50)")
@click.option("--full-refresh", "full_refresh", is_flag=True, default=False,
              help="TRUNCATE table and reload all data (default: incremental upsert)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
@click.option("--force", is_flag=True, default=False,
              help="Ignore previous progress and start fresh")
@click.option("--days-back", type=int, default=None,
              help="Only load orgs updated in the last N days (incremental). Omit for full refresh.")
def load_hierarchy(status, max_calls, full_refresh, api_key_number, force, days_back):
    """Load federal organization hierarchy from SAM.gov Federal Hierarchy API.

    Fetches the federal agency organizational structure (departments,
    sub-tier agencies, and offices) into the federal_organization table.
    This data enables agency targeting and cross-referencing with
    opportunity and award data.

    Uses offset-based pagination (100 records per API call). Each page
    counts as one API call against the daily SAM.gov limit.

    Incremental loads are resumable: progress is saved after each page.
    If interrupted, re-run the same command to continue from where it
    left off. Use --force to ignore previous progress and start fresh.

    Use --full-refresh for periodic complete reloads (TRUNCATE + reload).
    Default behavior is incremental upsert with SHA-256 change detection.

    Examples:
        python main.py load hierarchy
        python main.py load hierarchy --full-refresh --key 2
        python main.py load hierarchy --status Inactive --max-calls 20
        python main.py load hierarchy --force
        python main.py load hierarchy --days-back 30
    """
    logger = setup_logging()

    if days_back is not None and full_refresh:
        click.echo("ERROR: --days-back and --full-refresh are mutually exclusive.")
        sys.exit(1)

    # Calculate updateddatefrom when --days-back is provided
    updated_date_from = None
    if days_back is not None:
        updated_date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    from api_clients.sam_fedhier_client import SAMFedHierClient
    from api_clients.base_client import RateLimitExceeded
    from etl.fedhier_loader import FedHierLoader
    from etl.load_manager import LoadManager

    client = SAMFedHierClient(api_key_number=api_key_number)
    loader = FedHierLoader()
    load_manager = LoadManager()

    remaining = client._get_remaining_requests()

    if updated_date_from:
        mode_str = f"Incremental (updated since {updated_date_from})"
    elif full_refresh:
        mode_str = "Full Refresh (TRUNCATE)"
    else:
        mode_str = "Incremental Upsert"

    click.echo("SAM.gov Federal Hierarchy Load")
    click.echo(f"  API key:      #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Status:       {status}")
    click.echo(f"  Mode:         {mode_str}")
    click.echo(f"  Max calls:    {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    if full_refresh:
        _load_hierarchy_full(logger, client, loader, load_manager,
                             status, max_calls)
    else:
        _load_hierarchy_incremental(logger, client, loader, load_manager,
                                     status, max_calls, api_key_number, force,
                                     updated_date_from=updated_date_from)


def _load_hierarchy_full(logger, client, loader, load_manager, status, max_calls):
    """Full-refresh path: fetch all orgs then TRUNCATE + reload (non-resumable)."""
    load_id = load_manager.start_load(
        "SAM_FEDHIER", "FULL",
        parameters={"status": status, "full_refresh": True},
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    try:
        # Collect all organizations first
        all_orgs = []
        calls_made = 0
        offset = 0
        total = 0

        while calls_made < max_calls:
            data = client.search_organizations(
                status=status, limit=100, offset=offset,
            )
            calls_made += 1

            records = data.get("orglist", [])
            total = data.get("totalrecords", 0)
            all_orgs.extend(records)

            click.echo(f"  Page {calls_made}: {len(records)} records "
                       f"(total available: {total:,d}, fetched so far: {len(all_orgs):,d})")

            if not records or offset + 100 >= total:
                break
            offset += 100

        if calls_made >= max_calls and total > 0 and len(all_orgs) < total:
            remaining_records = total - len(all_orgs)
            remaining_calls = (remaining_records + 100 - 1) // 100
            click.echo(f"\n  ** BUDGET EXHAUSTED: Retrieved {len(all_orgs):,d} of {total:,d} available records.")
            click.echo(f"     {remaining_records:,d} records remain ({remaining_calls} more API calls needed).")
            click.echo(f"     To get all data, re-run with: --max-calls {calls_made + remaining_calls}")

        click.echo(f"\nFetched {len(all_orgs):,d} organization records in {calls_made} API calls")

        if not all_orgs:
            click.echo("No organizations found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        click.echo("Loading into federal_organization table...")
        stats = loader.full_refresh(all_orgs, load_id)

        elapsed = time.time() - t_start
        load_manager.complete_load(load_id, **stats)

        click.echo(f"\nLoad complete! ({elapsed:.1f}s)")
        click.echo(f"  Records read:      {stats['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {stats['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {stats['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {stats['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {stats['records_errored']:>10,d}")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Federal Hierarchy full refresh failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


def _load_hierarchy_incremental(logger, client, loader, load_manager,
                                 status, max_calls, api_key_number, force,
                                 updated_date_from=None):
    """Incremental path: page-by-page loading with resume support."""
    import json as _json
    from api_clients.base_client import RateLimitExceeded
    from db.connection import get_connection

    # ---- Check previous loads for this status (resume support) ----
    resume_offset = 0
    if not force:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT load_id, status, parameters "
                "FROM etl_load_log "
                "WHERE source_system = 'SAM_FEDHIER' "
                "AND parameters LIKE %s "
                "ORDER BY CAST(JSON_EXTRACT(parameters, '$.pages_fetched') AS UNSIGNED) DESC "
                "LIMIT 1",
                (f'%"status_filter": "{status}"%',),
            )
            prev_load = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if prev_load:
            prev_params = _json.loads(prev_load["parameters"]) if prev_load["parameters"] else {}
            prev_pages = prev_params.get("pages_fetched", 0)
            prev_total = prev_params.get("total_records")
            is_complete = prev_params.get("complete", False)

            if is_complete:
                click.echo(f"Already loaded all {status} organizations "
                           f"(load_id={prev_load['load_id']}). Skipping.")
                click.echo("  Use --force to reload from scratch.")
                return

            if prev_pages > 0:
                resume_offset = prev_pages * 100
                click.echo(f"Resuming from offset {resume_offset} "
                           f"(previous run loaded {prev_pages} pages, "
                           f"~{resume_offset} of {prev_total or '?'} records).")

    # ---- Create load entry and process page by page ----
    load_id = load_manager.start_load(
        "SAM_FEDHIER", "INCREMENTAL",
        parameters={
            "status_filter": status,
            "pages_fetched": resume_offset // 100,
            "total_records": None,
            "complete": False,
        },
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()
    pages_fetched_total = resume_offset // 100
    total_records = None
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    rate_limited = False

    try:
        iter_kwargs = dict(status=status, start_offset=resume_offset, max_pages=max_calls)
        if updated_date_from:
            iter_kwargs["updateddatefrom"] = updated_date_from
        for org_list, offset, total_records in client.iter_organization_pages(
            **iter_kwargs,
        ):
            if org_list:
                page_stats = loader.load_organization_batch(org_list, load_id)
                for k in cumulative:
                    cumulative[k] += page_stats.get(k, 0)

            pages_fetched_total = (offset // 100) + 1
            is_complete = total_records is not None and offset + 100 >= total_records

            # Save progress after each page (survives ctrl+c / kill)
            load_manager.save_load_progress(
                load_id,
                parameters={
                    "status_filter": status,
                    "pages_fetched": pages_fetched_total,
                    "total_records": total_records,
                    "complete": is_complete,
                },
                **cumulative,
            )

            total_pages = (total_records + 99) // 100 if total_records else "?"
            click.echo(
                f"  Page {pages_fetched_total}: {len(org_list)} records "
                f"(offset {offset}, {pages_fetched_total}/{total_pages} pages)"
            )

    except KeyboardInterrupt:
        new_pages = pages_fetched_total - (resume_offset // 100)
        click.echo(f"\n  Interrupted. {new_pages} new page(s) saved.")
        click.echo("  Run the same command again to continue.")
        return
    except RateLimitExceeded:
        rate_limited = True
        new_pages = pages_fetched_total - (resume_offset // 100)
        click.echo(f"  Rate limit reached after {new_pages} new pages.")
    except Exception as e:
        # Ctrl+C during MySQL ops raises InternalError("Unread result found")
        # with KeyboardInterrupt as __context__. Don't mark as FAILED.
        if isinstance(getattr(e, '__context__', None), KeyboardInterrupt):
            new_pages = pages_fetched_total - (resume_offset // 100)
            click.echo(f"\n  Interrupted. {new_pages} new page(s) saved.")
            click.echo("  Run the same command again to continue.")
            return
        if "429" in str(e):
            rate_limited = True
            new_pages = pages_fetched_total - (resume_offset // 100)
            click.echo(f"  Server rate limit (429) after {new_pages} new pages.")
            if api_key_number == 1:
                click.echo("  Tip: Use --key=2 for the 1000/day tier.")
        else:
            load_manager.fail_load(load_id, str(e))
            logger.exception("Federal Hierarchy load failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)

    # ---- Handle edge case: no new pages fetched ----
    initial_pages = resume_offset // 100
    if pages_fetched_total == initial_pages:
        load_manager.save_load_progress(
            load_id,
            parameters={
                "status_filter": status,
                "pages_fetched": pages_fetched_total,
                "total_records": total_records,
                "complete": False,
            },
            **cumulative,
        )
        if rate_limited:
            click.echo("Rate limited before any new pages could be fetched.")
            click.echo(f"  Will resume from offset {resume_offset} next time.")
        else:
            click.echo(f"No organizations found matching status={status}.")
        return

    # ---- Summary ----
    elapsed = time.time() - t_start
    is_complete = (
        total_records is not None
        and pages_fetched_total * 100 >= total_records
    )
    total_pages = (total_records + 99) // 100 if total_records else "?"
    status_str = "COMPLETE" if is_complete else f"PARTIAL ({pages_fetched_total} of {total_pages} pages)"
    remaining_after = client._get_remaining_requests()

    click.echo(f"\nIncremental load {status_str}! ({elapsed:.1f}s)")
    click.echo(f"  Records read:      {cumulative['records_read']:>10,d}")
    click.echo(f"  Records inserted:  {cumulative['records_inserted']:>10,d}")
    click.echo(f"  Records updated:   {cumulative['records_updated']:>10,d}")
    click.echo(f"  Records unchanged: {cumulative['records_unchanged']:>10,d}")
    click.echo(f"  Records errored:   {cumulative['records_errored']:>10,d}")
    click.echo(f"  API calls remaining: {remaining_after}")
    if not is_complete:
        click.echo("  Run the same command again to continue.")


@click.command("load-offices")
@click.option("--max-calls", default=200, type=int, help="Max API calls for this invocation (default: 200)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
@click.option("--force", is_flag=True, default=False,
              help="Ignore previous progress and start fresh")
@click.option("--verify", is_flag=True, default=False,
              help="Compare API totalrecords vs DB count for completed orgs (read-only)")
@click.option("--backfill", is_flag=True, default=False,
              help="Verify and fetch missing office pages for mismatched orgs")
@click.option("--days-back", type=int, default=None,
              help="Only load offices updated in the last N days (incremental). Omit for full refresh.")
def load_offices(max_calls, api_key_number, force, verify, backfill, days_back):
    """Load Level 3 office organizations from SAM.gov Federal Hierarchy API.

    Fetches Level 3 (Office) organizations by querying the hierarchy
    endpoint for each Level 2 sub-tier already in the database. This
    requires one API call per sub-tier (~738 calls), so the command
    supports resume across multiple runs via --max-calls budget control.

    Level 2 sub-tiers must be loaded first via 'load hierarchy'.

    Progress is saved after each sub-tier is fully loaded. If interrupted
    or budget is exhausted, re-run the same command to continue from the
    last completed sub-tier. Use --force to restart from scratch.

    Use --days-back N to scan all sub-tiers for recently updated offices.
    NOTE: --days-back still requires one API call per sub-tier (~738 calls)
    because the hierarchy endpoint must be queried per Level 2 org. It only
    reduces the number of records returned per call, not the call count.
    This means it offers minimal savings when rate-limited on calls/day.

    Examples:
        python main.py load offices
        python main.py load offices --max-calls 100
        python main.py load offices --force
        python main.py load offices --key 1
        python main.py load offices --days-back 30
    """
    logger = setup_logging()

    if verify and backfill:
        click.echo("ERROR: --verify and --backfill are mutually exclusive.")
        sys.exit(1)

    if days_back is not None and force:
        click.echo("ERROR: --days-back and --force are mutually exclusive.")
        sys.exit(1)

    # Calculate updateddatefrom when --days-back is provided
    updated_date_from = None
    if days_back is not None:
        updated_date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    import json as _json
    from api_clients.sam_fedhier_client import SAMFedHierClient
    from api_clients.base_client import RateLimitExceeded
    from etl.fedhier_loader import FedHierLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection, get_cursor

    client = SAMFedHierClient(api_key_number=api_key_number)
    loader = FedHierLoader()
    load_manager = LoadManager()

    SOURCE_SYSTEM = "SAM_FEDHIER_OFFICES"

    remaining = client._get_remaining_requests()

    if updated_date_from:
        mode_str = f"Incremental (updated since {updated_date_from})"
    else:
        mode_str = "Incremental Upsert"

    click.echo("SAM.gov Federal Hierarchy — Level 3 Office Load")
    click.echo(f"  API key:      #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Mode:         {mode_str}")
    click.echo(f"  Max calls:    {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # ---- Query Level 2 sub-tiers from the database ----
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT fh_org_id, fh_org_name FROM federal_organization "
            "WHERE level = 2 AND status = 'Active' "
            "ORDER BY fh_org_id"
        )
        subtiers = cursor.fetchall()

    if not subtiers:
        click.echo("\nERROR: No Level 2 sub-tiers found. Run 'load hierarchy' first.")
        sys.exit(1)

    click.echo(f"  Sub-tiers:    {len(subtiers)} Level 2 orgs in database")

    # ---- Resume support ----
    completed_orgs = []
    resume_load = None
    resume_params = None
    resume_current_org = ""
    resume_current_page = 0

    if not force:
        # Clean up stale RUNNING loads
        load_manager.cleanup_stale_running(SOURCE_SYSTEM)

        resume_load, resume_params = load_manager.get_resumable_load(
            SOURCE_SYSTEM, date_from=updated_date_from)

        if resume_params:
            completed_orgs = resume_params.get("completed_orgs", [])
            prev_calls = resume_params.get("calls_made", 0)
            prev_fetched = resume_params.get("total_fetched", 0)
            is_complete = resume_params.get("complete", False)

            if is_complete:
                click.echo(f"\nAll sub-tiers already processed "
                           f"(load_id={resume_load['load_id']}, "
                           f"{prev_fetched} offices fetched). Skipping.")
                click.echo("  Use --force to reload from scratch.")
                return

            resume_current_org = str(resume_params.get("current_org") or "")
            resume_current_page = int(resume_params.get("current_page") or 0)

            if completed_orgs:
                click.echo(f"  Resuming: {len(completed_orgs)} of {len(subtiers)} "
                           f"sub-tiers already done ({prev_calls} calls, "
                           f"{prev_fetched} offices fetched)")
                if resume_current_org and resume_current_page > 0:
                    click.echo(f"  Mid-org resume: org {resume_current_org} "
                               f"from offset {resume_current_page}")

    if verify or backfill:
        _verify_offices(client, completed_orgs, subtiers, max_calls, backfill,
                        loader, load_manager)
        return

    # ---- Create load entry ----
    load_params = {
        "completed_orgs": completed_orgs,
        "total_subtiers": len(subtiers),
        "current_org": None,
        "current_page": 0,
        "complete": False,
        "calls_made": resume_params.get("calls_made", 0) if resume_params else 0,
        "total_fetched": resume_params.get("total_fetched", 0) if resume_params else 0,
    }
    if updated_date_from:
        load_params["date_from"] = updated_date_from
    load_id = load_manager.start_load(
        SOURCE_SYSTEM, "INCREMENTAL",
        parameters=load_params,
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()
    calls_made = resume_params.get("calls_made", 0) if resume_params else 0
    total_fetched = resume_params.get("total_fetched", 0) if resume_params else 0
    calls_this_run = 0
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    rate_limited = False
    completed_orgs_set = set(str(x) for x in completed_orgs)
    partial_org_id = None      # org ID if we stopped mid-org
    partial_org_offset = 0     # next offset to resume from

    # ---- Process each sub-tier ----
    subtiers_remaining = [
        s for s in subtiers if str(s["fh_org_id"]) not in completed_orgs_set
    ]
    click.echo(f"  Processing {len(subtiers_remaining)} remaining sub-tiers...\n")

    try:
        for idx, subtier in enumerate(subtiers_remaining, 1):
            fhorgid = subtier["fh_org_id"]
            org_name = subtier["fh_org_name"] or f"ID:{fhorgid}"

            if calls_this_run >= max_calls:
                click.echo(f"\n  Budget exhausted ({calls_this_run} calls this run). "
                           f"Saving progress.")
                break

            # Compute resume offset before saving progress
            start_offset = 0
            if str(fhorgid) == resume_current_org and resume_current_page > 0:
                start_offset = resume_current_page
                click.echo(f"    Resuming {org_name} from offset {start_offset}")
                # Clear so we don't re-apply on retry
                resume_current_org = ""
                resume_current_page = 0

            # Update current_org in progress (preserve resume offset)
            _save_offices_progress(
                load_manager, load_id, completed_orgs, len(subtiers),
                str(fhorgid), start_offset, False, calls_made, total_fetched, cumulative,
                date_from=updated_date_from,
            )

            # Fetch all pages of children for this sub-tier
            subtier_offices = 0
            subtier_complete = True
            partial_org_id = str(fhorgid)
            partial_org_offset = start_offset
            last_offset = start_offset
            try:
                for child_orgs, offset, total_records in client.iter_org_children_pages(
                    fhorgid, start_offset=start_offset, max_pages=max_calls - calls_this_run,
                    updateddatefrom=updated_date_from,
                ):
                    calls_made += 1
                    calls_this_run += 1
                    last_offset = offset
                    partial_org_offset = offset + 100

                    page_num = (offset // 100) + 1
                    total_pages = (total_records + 99) // 100 if total_records else 1
                    if total_pages > 1:
                        extra = f"  [{total_records} total offices]" if page_num == 1 else ""
                        msg = (f"    {org_name}: page {page_num}/{total_pages} "
                               f"({len(child_orgs) if child_orgs else 0} records){extra}")
                        click.echo(f"\r{msg:<80}", nl=False)

                    if child_orgs:
                        # Ensure parent_org_id is set for child records that
                        # may not have fhorgparenthistory
                        for org in child_orgs:
                            if not org.get("fhorgparenthistory"):
                                # Inject parent info so _normalize_org can
                                # extract the correct parent_org_id
                                org.setdefault("_injected_parent_org_id", fhorgid)

                        page_stats = loader.load_organization_batch(child_orgs, load_id)
                        for k in cumulative:
                            cumulative[k] += page_stats.get(k, 0)
                        subtier_offices += len(child_orgs)
                        total_fetched += len(child_orgs)

                    if calls_this_run >= max_calls and page_num < total_pages:
                        # Budget exhausted mid-org — don't mark complete
                        subtier_complete = False
                        click.echo(
                            f"\n    {org_name}: budget exhausted at page "
                            f"{page_num}/{total_pages} — will resume next run"
                        )
                        break

            except RateLimitExceeded:
                rate_limited = True
                subtier_complete = False
                click.echo(f"  Rate limit reached during sub-tier {org_name}")
                break
            except Exception as e:
                if isinstance(getattr(e, '__context__', None), KeyboardInterrupt):
                    raise KeyboardInterrupt from None
                if "429" in str(e):
                    rate_limited = True
                    subtier_complete = False
                    click.echo(f"  Server rate limit (429) during sub-tier {org_name}")
                    break
                logger.warning("Error fetching children for %s: %s", fhorgid, e)
                # Mark as completed to avoid infinite retries on permanently
                # failing sub-tiers
                click.echo(f"  WARN: Error on sub-tier {org_name}: {e} — skipping")

            # Only mark complete if all pages were fetched
            if subtier_complete:
                completed_orgs.append(str(fhorgid))
                completed_orgs_set.add(str(fhorgid))

            done_total = len(completed_orgs)
            status = "" if subtier_complete else " [PARTIAL]"
            click.echo(
                f"\r  [{done_total}/{len(subtiers)}] {org_name}: "
                f"{subtier_offices} offices "
                f"(calls: {calls_this_run}/{max_calls}){status:<20}"
            )

            # Save progress after each sub-tier
            if subtier_complete:
                partial_org_id = None
                partial_org_offset = 0
                _save_offices_progress(
                    load_manager, load_id, completed_orgs, len(subtiers),
                    None, 0, False, calls_made, total_fetched, cumulative,
                    date_from=updated_date_from,
                )
            else:
                # Save mid-org resume point: next offset to fetch
                partial_org_id = str(fhorgid)
                partial_org_offset = last_offset + 100
                _save_offices_progress(
                    load_manager, load_id, completed_orgs, len(subtiers),
                    partial_org_id, partial_org_offset, False,
                    calls_made, total_fetched, cumulative,
                    date_from=updated_date_from,
                )

    except KeyboardInterrupt:
        click.echo(f"\n  Interrupted. Progress saved ({len(completed_orgs)} sub-tiers done).")
        _save_offices_progress(
            load_manager, load_id, completed_orgs, len(subtiers),
            partial_org_id, partial_org_offset, False,
            calls_made, total_fetched, cumulative,
            date_from=updated_date_from,
        )
        click.echo("  Run the same command again to continue.")
        return

    # ---- Check if all sub-tiers are done ----
    is_complete = len(completed_orgs) >= len(subtiers)

    _save_offices_progress(
        load_manager, load_id, completed_orgs, len(subtiers),
        None if is_complete else partial_org_id,
        0 if is_complete else partial_org_offset,
        is_complete, calls_made, total_fetched, cumulative,
        date_from=updated_date_from,
    )

    if is_complete:
        load_manager.complete_load(load_id, **cumulative)

    # ---- Summary ----
    elapsed = time.time() - t_start
    remaining_after = client._get_remaining_requests()
    status_str = "COMPLETE" if is_complete else f"PARTIAL ({len(completed_orgs)}/{len(subtiers)} sub-tiers)"

    click.echo(f"\nOffice load {status_str}! ({elapsed:.1f}s)")
    click.echo(f"  Sub-tiers processed:  {len(completed_orgs):>6,d} / {len(subtiers):,d}")
    click.echo(f"  Offices fetched:      {total_fetched:>10,d}")
    click.echo(f"  Records read:         {cumulative['records_read']:>10,d}")
    click.echo(f"  Records inserted:     {cumulative['records_inserted']:>10,d}")
    click.echo(f"  Records updated:      {cumulative['records_updated']:>10,d}")
    click.echo(f"  Records unchanged:    {cumulative['records_unchanged']:>10,d}")
    click.echo(f"  Records errored:      {cumulative['records_errored']:>10,d}")
    click.echo(f"  API calls this run:   {calls_this_run:>10,d}")
    click.echo(f"  API calls total:      {calls_made:>10,d}")
    click.echo(f"  API calls remaining:  {remaining_after}")
    if not is_complete:
        click.echo("  Run the same command again to continue.")
        if rate_limited and api_key_number == 1:
            click.echo("  Tip: Use --key=2 for the 1000/day tier.")


def _save_offices_progress(load_manager, load_id, completed_orgs, total_subtiers,
                           current_org, current_page, complete, calls_made,
                           total_fetched, cumulative, date_from=None):
    """Save office load progress to etl_load_log."""
    params = {
        "completed_orgs": completed_orgs,
        "total_subtiers": total_subtiers,
        "current_org": current_org,
        "current_page": current_page,
        "complete": complete,
        "calls_made": calls_made,
        "total_fetched": total_fetched,
    }
    if date_from:
        params["date_from"] = date_from
    load_manager.save_load_progress(
        load_id,
        parameters=params,
        **cumulative,
    )


def _verify_offices(client, completed_orgs, subtiers, max_calls, do_backfill,
                    loader, load_manager):
    """Find completed orgs with suspicious office counts (divisible by 100).

    A count divisible by 100 suggests pagination was cut short at a page
    boundary. This check is DB-only — no API calls needed.
    """
    from db.connection import get_cursor

    subtier_names = {str(s["fh_org_id"]): s["fh_org_name"] or f"ID:{s['fh_org_id']}"
                     for s in subtiers}

    click.echo(f"\nVerifying {len(completed_orgs)} completed orgs (DB-only check)...\n")

    suspects = []

    with get_cursor() as cursor:
        for i, oid in enumerate(completed_orgs, 1):
            org_name = subtier_names.get(str(oid), f"ID:{oid}")

            cursor.execute(
                "SELECT COUNT(*) FROM federal_organization "
                "WHERE parent_org_id = %s AND level = 3",
                (int(oid),)
            )
            (db_count,) = cursor.fetchone()

            if db_count % 100 == 0:
                suspects.append({
                    "fh_org_id": oid,
                    "org_name": org_name,
                    "db_count": db_count,
                })
                click.echo(f"\n  SUSPECT: {org_name} — {db_count} offices "
                           f"(exactly {db_count // 100} pages)")
            else:
                msg = f"  Checking [{i}/{len(completed_orgs)}] {org_name}: {db_count} OK"
                click.echo(f"\r{msg:<80}", nl=False)

    # Summary
    click.echo(f"\n\nVerification complete (no API calls used)")
    click.echo(f"  Checked:  {len(completed_orgs)}")
    click.echo(f"  OK:       {len(completed_orgs) - len(suspects)}")
    click.echo(f"  Suspect:  {len(suspects)}")

    if not suspects:
        click.echo("  No suspicious counts found.")
        return

    if not do_backfill:
        click.echo("\nSuspect orgs have counts divisible by 100 (possible truncation).")
        click.echo("Re-run with --backfill to confirm via API and fetch missing records.")
        return

    # Backfill confirms via API then fetches missing pages
    _backfill_offices(client, loader, load_manager, suspects, max_calls)


def _backfill_offices(client, loader, load_manager, suspects, remaining_budget):
    """Confirm suspect orgs via API, then fetch missing pages.

    For each suspect (DB count divisible by 100), makes one API call to get
    the true totalrecords. If the counts match, the org is fine. If not,
    fetches the missing pages.
    """
    from api_clients.base_client import RateLimitExceeded

    SOURCE_SYSTEM = "SAM_FEDHIER_OFFICES"

    # First pass: confirm which suspects are actually incomplete
    click.echo(f"\nConfirming {len(suspects)} suspect orgs via API...")
    confirmed = []
    calls_used = 0

    for s in suspects:
        if calls_used >= remaining_budget:
            click.echo(f"  Budget exhausted during confirmation.")
            break

        fhorgid = int(s["fh_org_id"])
        org_name = s["org_name"]
        db_count = s["db_count"]

        try:
            data = client.get_org_children(fhorgid, limit=1, offset=0)
            calls_used += 1
        except Exception as e:
            click.echo(f"  WARN: API error for {org_name}: {e}")
            continue

        api_total = data.get("totalrecords", data.get("totalRecords", 0))

        if db_count < api_total:
            confirmed.append({
                "fh_org_id": s["fh_org_id"],
                "org_name": org_name,
                "db_count": db_count,
                "api_total": api_total,
            })
            click.echo(f"  CONFIRMED: {org_name} — have {db_count}, need {api_total}")
        else:
            msg = f"  OK: {org_name} — {db_count} is correct"
            click.echo(f"\r{msg:<80}", nl=False)

    click.echo(f"\n  Confirmed {len(confirmed)} incomplete orgs "
               f"({len(suspects) - len(confirmed)} were fine)")

    if not confirmed:
        click.echo("  Nothing to backfill.")
        return

    # Second pass: fetch missing pages
    load_id = load_manager.start_load(
        SOURCE_SYSTEM, "BACKFILL",
        parameters={"mode": "backfill", "confirmed": len(confirmed)},
    )

    click.echo(f"\nBackfilling {len(confirmed)} orgs "
               f"(budget: {remaining_budget - calls_used} calls, load_id={load_id})")

    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }

    for m in confirmed:
        if calls_used >= remaining_budget:
            click.echo(f"  Budget exhausted during backfill.")
            break

        fhorgid = int(m["fh_org_id"])
        org_name = m["org_name"]
        db_count = m["db_count"]
        api_total = m["api_total"]

        # Align to page boundary
        start_offset = (db_count // 100) * 100

        click.echo(f"  {org_name}: fetching from offset {start_offset} "
                    f"(have {db_count}, need {api_total})")

        try:
            for child_orgs, offset, total_records in client.iter_org_children_pages(
                fhorgid, start_offset=start_offset,
                max_pages=remaining_budget - calls_used,
            ):
                calls_used += 1

                if child_orgs:
                    for org in child_orgs:
                        if not org.get("fhorgparenthistory"):
                            org.setdefault("_injected_parent_org_id", fhorgid)

                    page_stats = loader.load_organization_batch(child_orgs, load_id)
                    for k in cumulative:
                        cumulative[k] += page_stats.get(k, 0)

                page_num = (offset // 100) + 1
                total_pages = (total_records + 99) // 100 if total_records else 1
                msg = f"    page {page_num}/{total_pages}: {len(child_orgs) if child_orgs else 0} records"
                click.echo(f"\r{msg:<80}", nl=False)

                if calls_used >= remaining_budget:
                    break

        except RateLimitExceeded:
            click.echo(f"\n  Rate limit reached during backfill of {org_name}")
            break
        except Exception as e:
            if "429" in str(e):
                click.echo(f"\n  Server rate limit (429) during {org_name}")
                break
            click.echo(f"\n  WARN: Error backfilling {org_name}: {e}")
            continue

        click.echo("")  # newline after last page's \r

    load_manager.complete_load(load_id, **cumulative)

    click.echo(f"\nBackfill complete:")
    click.echo(f"  API calls:         {calls_used}")
    click.echo(f"  Records inserted:  {cumulative['records_inserted']}")
    click.echo(f"  Records updated:   {cumulative['records_updated']}")
    click.echo(f"  Records unchanged: {cumulative['records_unchanged']}")


@click.command("search-agencies")
@click.option("--name", default=None, help="Organization name to search (partial match)")
@click.option("--code", default=None, help="Agency code to search")
@click.option("--type", "org_type", default=None,
              type=click.Choice(["Department", "Sub-Tier", "Office"], case_sensitive=False),
              help="Filter by organization type")
@click.option("--limit", default=25, type=int, help="Max results to display (default: 25)")
def search_agencies(name, code, org_type, limit):
    """Search federal organizations in the local database.

    Searches the federal_organization table for agencies matching the
    given criteria. Requires load-hierarchy to have been run first.

    Examples:
        python main.py search agencies --name "Defense"
        python main.py search agencies --code 9700
        python main.py search agencies --type Department
        python main.py search agencies --name "Army" --type Sub-Tier
    """
    logger = setup_logging()

    if not any([name, code, org_type]):
        click.echo("ERROR: At least one filter is required (--name, --code, or --type)")
        sys.exit(1)

    from db.connection import get_cursor

    try:
        qb = QueryBuilder()
        if name:
            qb.filter("fh_org_name LIKE %s", f"%{name}%")
        if code:
            qb.filter("(agency_code = %s OR cgac = %s)", code, code)
        if org_type:
            type_map = {
                "department": "Department/Ind. Agency",
                "sub-tier": "Sub-Tier",
                "office": "Office",
            }
            qb.filter("fh_org_type = %s", type_map.get(org_type.lower(), org_type))

        where_sql, params = qb.build_where()
        if not where_sql:
            where_sql = "WHERE 1=1"

        sql = (
            f"SELECT fh_org_id, fh_org_name, fh_org_type, status, "
            f"agency_code, cgac, parent_org_id, level "
            f"FROM federal_organization "
            f"{where_sql} "
            f"ORDER BY level, fh_org_name "
            f"LIMIT %s"
        )
        params.append(limit)

        with get_cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        if not rows:
            click.echo("No organizations found matching the criteria.")
            return

        click.echo(f"\nFound {len(rows)} organization(s):\n")
        click.echo(f"  {'ID':<12s}  {'Name':<50s}  {'Type':<25s}  {'Code':<8s}  {'Status':<10s}")
        click.echo(f"  {'-'*12}  {'-'*50}  {'-'*25}  {'-'*8}  {'-'*10}")

        for row in rows:
            org_name = (row["fh_org_name"] or "")[:50]
            org_type_val = (row["fh_org_type"] or "")[:25]
            agency_code = row["agency_code"] or ""
            status_val = row["status"] or ""
            click.echo(
                f"  {row['fh_org_id']:<12}  {org_name:<50s}  {org_type_val:<25s}  "
                f"{agency_code:<8s}  {status_val:<10s}"
            )

    except Exception as e:
        logger.exception("Agency search failed")
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)
