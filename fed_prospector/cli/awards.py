"""CLI commands for contract award data (Phase 5A)."""

import sys
import time

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-awards")
@click.option("--naics", default=None, help="NAICS code to search (e.g., 541512)")
@click.option("--set-aside", "set_aside", default=None, help="Set-aside type (WOSB, 8A, etc.)")
@click.option("--agency", default=None, help="Contracting department CGAC code")
@click.option("--awardee-uei", default=None, help="Awardee UEI to search")
@click.option("--piid", default=None, help="Contract PIID to search")
@click.option("--years-back", default=3, type=int, help="Years of history to load (default: 3)")
@click.option("--fiscal-year", default=None, type=int, help="Specific fiscal year (overrides --years-back)")
@click.option("--max-calls", default=10, type=int, help="Max API calls for this invocation (default: 10)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def load_awards(naics, set_aside, agency, awardee_uei, piid, years_back,
                fiscal_year, max_calls, api_key_number):
    """Load historical contract awards from SAM.gov Contract Awards API.

    Fetches contract award records into fpds_contract table. This data
    includes number of bidders, competition type, and award details
    needed for capture management.

    Uses offset-based pagination (100 records per API call). Each page
    counts as one API call against the daily SAM.gov limit.

    At least one filter is required: --naics, --set-aside, --agency,
    --awardee-uei, --piid, or --fiscal-year.

    Examples:
        python main.py load-awards --naics 541512 --years-back 5
        python main.py load-awards --set-aside WOSB --years-back 3
        python main.py load-awards --awardee-uei ABC123DEF456
        python main.py load-awards --piid W911NF25C0001
        python main.py load-awards --naics 541512 --set-aside WOSB --key 2
    """
    logger = setup_logging()

    if not any([naics, set_aside, agency, awardee_uei, piid, fiscal_year]):
        click.echo("ERROR: At least one filter is required (--naics, --set-aside, --agency, --awardee-uei, --piid, or --fiscal-year)")
        sys.exit(1)

    from datetime import date, timedelta
    from api_clients.sam_awards_client import SAMAwardsClient
    from etl.awards_loader import AwardsLoader
    from etl.load_manager import LoadManager

    client = SAMAwardsClient(api_key_number=api_key_number)
    loader = AwardsLoader()
    load_manager = LoadManager()

    # Date range
    today = date.today()
    if fiscal_year:
        date_from = date(fiscal_year - 1, 10, 1)
        date_to = date(fiscal_year, 9, 30)
    else:
        date_from = today - timedelta(days=365 * years_back)
        date_to = today

    remaining = client._get_remaining_requests()

    click.echo("SAM.gov Contract Awards Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Date range:  {date_from} to {date_to}")
    if naics:
        click.echo(f"  NAICS:       {naics}")
    if set_aside:
        click.echo(f"  Set-aside:   {set_aside}")
    if agency:
        click.echo(f"  Agency:      {agency}")
    if awardee_uei:
        click.echo(f"  Awardee UEI: {awardee_uei}")
    if piid:
        click.echo(f"  PIID:        {piid}")
    click.echo(f"  Max calls:   {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # Start load
    params_dict = {
        "naics": naics, "set_aside": set_aside, "agency": agency,
        "awardee_uei": awardee_uei, "piid": piid,
        "date_from": str(date_from), "date_to": str(date_to),
    }
    load_id = load_manager.start_load("SAM_AWARDS", "HISTORICAL", parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    try:
        # Collect awards with pagination (respecting max_calls)
        # NOTE: The SAM Awards API 'offset' is a PAGE INDEX, not record offset.
        # offset=0 is page 0, offset=1 is page 1, etc.
        all_awards = []
        calls_made = 0
        page = 0
        page_size = 100
        total = 0

        while calls_made < max_calls:
            # Don't send dateSigned range when fiscalYear is set — they're
            # redundant and combining them causes pagination issues.
            data = client.search_awards(
                naics_code=naics, set_aside=set_aside, agency_code=agency,
                awardee_uei=awardee_uei, piid=piid,
                date_signed_from=date_from if not fiscal_year else None,
                date_signed_to=date_to if not fiscal_year else None,
                fiscal_year=fiscal_year,
                limit=page_size, offset=page,
            )
            calls_made += 1

            records = data.get("awardSummary", [])
            total = int(data.get("totalRecords", 0))
            all_awards.extend(records)

            click.echo(f"  Page {calls_made}: {len(records)} records (total available: {total:,d}, fetched so far: {len(all_awards):,d})")

            if not records or (page + 1) * page_size >= total:
                break
            page += 1

        # Check if budget was exhausted before all data was fetched
        if calls_made >= max_calls and total > 0 and len(all_awards) < total:
            remaining_records = total - len(all_awards)
            remaining_calls = (remaining_records + page_size - 1) // page_size
            click.echo(f"\n  ** BUDGET EXHAUSTED: Retrieved {len(all_awards):,d} of {total:,d} available records.")
            click.echo(f"     {remaining_records:,d} records remain ({remaining_calls} more API calls needed).")
            click.echo(f"     To get all data, re-run with: --max-calls {calls_made + remaining_calls}")

        click.echo(f"\nFetched {len(all_awards):,d} award records in {calls_made} API calls")

        if not all_awards:
            click.echo("No awards found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # Load into database
        click.echo("Loading into fpds_contract table...")
        stats = loader.load_awards(all_awards, load_id)

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
        logger.exception("Awards load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)
