"""CLI commands for federal hierarchy data (Phase 5D)."""

import sys
import time

import click

from config.logging_config import setup_logging


@click.command("load-hierarchy")
@click.option("--status", default="Active", help="Organization status filter (Active/Inactive, default: Active)")
@click.option("--max-calls", default=50, type=int, help="Max API calls for this invocation (default: 50)")
@click.option("--full-refresh", "full_refresh", is_flag=True, default=False,
              help="TRUNCATE table and reload all data (default: incremental upsert)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def load_hierarchy(status, max_calls, full_refresh, api_key_number):
    """Load federal organization hierarchy from SAM.gov Federal Hierarchy API.

    Fetches the federal agency organizational structure (departments,
    sub-tier agencies, and offices) into the federal_organization table.
    This data enables agency targeting and cross-referencing with
    opportunity and award data.

    Uses offset-based pagination (100 records per API call). Each page
    counts as one API call against the daily SAM.gov limit.

    Use --full-refresh for periodic complete reloads (TRUNCATE + reload).
    Default behavior is incremental upsert with SHA-256 change detection.

    Examples:
        python main.py load-hierarchy
        python main.py load-hierarchy --full-refresh --key 2
        python main.py load-hierarchy --status Inactive --max-calls 20
    """
    logger = setup_logging()

    from api_clients.sam_fedhier_client import SAMFedHierClient
    from etl.fedhier_loader import FedHierLoader
    from etl.load_manager import LoadManager

    client = SAMFedHierClient(api_key_number=api_key_number)
    loader = FedHierLoader()
    load_manager = LoadManager()

    remaining = client._get_remaining_requests()

    click.echo("SAM.gov Federal Hierarchy Load")
    click.echo(f"  API key:      #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Status:       {status}")
    click.echo(f"  Mode:         {'Full Refresh (TRUNCATE)' if full_refresh else 'Incremental Upsert'}")
    click.echo(f"  Max calls:    {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # Start load
    load_type = "FULL" if full_refresh else "INCREMENTAL"
    params_dict = {"status": status, "full_refresh": full_refresh}
    load_id = load_manager.start_load("SAM_FEDHIER", load_type, parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    try:
        # Collect organizations with pagination (respecting max_calls)
        all_orgs = []
        calls_made = 0
        offset = 0

        while calls_made < max_calls:
            data = client.search_organizations(
                status=status, limit=100, offset=offset,
            )
            calls_made += 1

            records = data.get("orglist", [])
            total = data.get("totalrecords", 0)
            all_orgs.extend(records)

            click.echo(f"  Page {calls_made}: {len(records)} records (total available: {total:,d}, fetched so far: {len(all_orgs):,d})")

            if not records or offset + 100 >= total:
                break
            offset += 100

        click.echo(f"\nFetched {len(all_orgs):,d} organization records in {calls_made} API calls")

        if not all_orgs:
            click.echo("No organizations found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # Load into database
        click.echo("Loading into federal_organization table...")
        if full_refresh:
            stats = loader.full_refresh(all_orgs, load_id)
        else:
            stats = loader.load_organizations(all_orgs, load_id)

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
        logger.exception("Federal Hierarchy load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


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
        python main.py search-agencies --name "Defense"
        python main.py search-agencies --code 9700
        python main.py search-agencies --type Department
        python main.py search-agencies --name "Army" --type Sub-Tier
    """
    setup_logging()

    if not any([name, code, org_type]):
        click.echo("ERROR: At least one filter is required (--name, --code, or --type)")
        sys.exit(1)

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conditions = ["1=1"]
        params = []

        if name:
            conditions.append("fh_org_name LIKE %s")
            params.append(f"%{name}%")
        if code:
            conditions.append("(agency_code = %s OR cgac = %s)")
            params.append(code)
            params.append(code)
        if org_type:
            type_map = {
                "department": "Department/Ind. Agency",
                "sub-tier": "Sub-Tier",
                "office": "Office",
            }
            conditions.append("fh_org_type = %s")
            params.append(type_map.get(org_type.lower(), org_type))

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT fh_org_id, fh_org_name, fh_org_type, status, "
            f"agency_code, cgac, parent_org_id, level "
            f"FROM federal_organization "
            f"WHERE {where_clause} "
            f"ORDER BY level, fh_org_name "
            f"LIMIT %s"
        )
        params.append(limit)

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

    finally:
        cursor.close()
        conn.close()
