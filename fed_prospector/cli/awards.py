"""CLI commands for contract award data (Phase 5A)."""

import sys
import time

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-awards")
@click.option("--naics", default=None, help="NAICS code(s) to search — comma-separated for multiple: 541512,541511,561110")
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
        python main.py load awards --naics 541512 --years-back 5
        python main.py load awards --naics 541512,541511,561110 --years-back 5
        python main.py load awards --set-aside WOSB --years-back 3
        python main.py load awards --awardee-uei ABC123DEF456
        python main.py load awards --piid W911NF25C0001
        python main.py load awards --naics 541512 --set-aside WOSB --key 2
    """
    logger = setup_logging()

    # Parse comma-separated NAICS into a list
    naics_codes = [c.strip() for c in naics.split(',') if c.strip()] if naics else []

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
    if naics_codes:
        click.echo(f"  NAICS:       {', '.join(naics_codes)} ({len(naics_codes)} code{'s' if len(naics_codes) != 1 else ''})")
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
        # Collect awards with pagination (respecting max_calls budget across all NAICS codes).
        # NOTE: The SAM Awards API 'offset' is a PAGE INDEX, not record offset.
        # offset=0 is page 0, offset=1 is page 1, etc.
        all_awards = []
        calls_made = 0
        page_size = 100

        # Loop over each NAICS code; fall back to [None] for non-NAICS searches
        # (set-aside-only, agency-only, PIID, etc.)
        codes_to_load = naics_codes if naics_codes else [None]
        budget_exhausted = False

        for naics_code in codes_to_load:
            if budget_exhausted:
                break
            if naics_code and len(naics_codes) > 1:
                click.echo(f"\n  NAICS {naics_code}:")

            page = 0
            code_total = 0
            while calls_made < max_calls:
                # Don't send dateSigned range when fiscalYear is set — they're
                # redundant and combining them causes pagination issues.
                data = client.search_awards(
                    naics_code=naics_code, set_aside=set_aside, agency_code=agency,
                    awardee_uei=awardee_uei, piid=piid,
                    date_signed_from=date_from if not fiscal_year else None,
                    date_signed_to=date_to if not fiscal_year else None,
                    fiscal_year=fiscal_year,
                    limit=page_size, offset=page,
                )
                calls_made += 1

                records = data.get("awardSummary", [])
                code_total = int(data.get("totalRecords", 0))
                all_awards.extend(records)

                click.echo(f"  Page {page + 1}: {len(records)} records (total available: {code_total:,d}, fetched so far: {len(all_awards):,d})")

                if not records or (page + 1) * page_size >= code_total:
                    break
                page += 1

            # Check if budget was exhausted mid-NAICS
            if calls_made >= max_calls and code_total > 0 and (page + 1) * page_size < code_total:
                fetched_this_code = (page + 1) * page_size
                remaining_records = code_total - fetched_this_code
                remaining_calls = (remaining_records + page_size - 1) // page_size
                remaining_codes = len(naics_codes) - naics_codes.index(naics_code) - 1 if naics_code else 0
                click.echo(f"\n  ** BUDGET EXHAUSTED mid-load.")
                click.echo(f"     {remaining_records:,d} records remain for NAICS {naics_code} ({remaining_calls} more calls).")
                if remaining_codes:
                    click.echo(f"     {remaining_codes} NAICS code(s) not yet loaded.")
                click.echo(f"     To get all data, re-run with: --max-calls {calls_made + remaining_calls + remaining_codes}")
                budget_exhausted = True

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


@click.command("search-awards")
@click.option("--naics", default=None, help="Filter by NAICS code")
@click.option("--set-aside", "set_aside", default=None, help="Filter by set-aside type (WOSB, 8A, etc.)")
@click.option("--agency", default=None, help="Filter by agency ID or name (partial match)")
@click.option("--vendor", default=None, help="Filter by vendor UEI or name (partial match)")
@click.option("--piid", default=None, help="Filter by contract PIID (exact match)")
@click.option("--from-date", default=None, help="Award date from (YYYY-MM-DD)")
@click.option("--to-date", default=None, help="Award date to (YYYY-MM-DD)")
@click.option("--limit", default=25, type=int, help="Max results to show (default: 25)")
def search_awards(naics, set_aside, agency, vendor, piid, from_date, to_date, limit):
    """Search loaded contract awards in the local database.

    Queries the fpds_contract table (no API calls). Results are ordered by
    award date descending. By default shows only base awards (mod 0).

    Examples:
        python main.py search awards --naics 541512
        python main.py search awards --vendor "Acme" --set-aside WOSB
        python main.py search awards --agency "Army" --from-date 2025-01-01
        python main.py search awards --piid W911NF25C0001
    """
    logger = setup_logging()
    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        where_clauses = []
        params = []

        # Default: base awards only (mod 0), unless searching by PIID
        if not piid:
            where_clauses.append("modification_number = '0'")

        if naics:
            where_clauses.append("naics_code = %s")
            params.append(naics)

        if set_aside:
            where_clauses.append("set_aside_type = %s")
            params.append(set_aside)

        if agency:
            where_clauses.append("(agency_id = %s OR agency_name LIKE %s)")
            params.append(agency)
            params.append(f"%{agency}%")

        if vendor:
            where_clauses.append("(vendor_uei = %s OR vendor_name LIKE %s)")
            params.append(vendor)
            params.append(f"%{vendor}%")

        if piid:
            where_clauses.append("contract_id = %s")
            params.append(piid)

        if from_date:
            where_clauses.append("date_signed >= %s")
            params.append(from_date)

        if to_date:
            where_clauses.append("date_signed <= %s")
            params.append(to_date)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = (
            "SELECT contract_id, vendor_name, vendor_uei, dollars_obligated, "
            "  naics_code, set_aside_type, agency_name, date_signed, number_of_offers "
            "FROM fpds_contract "
            f"{where_sql} "
            "ORDER BY date_signed DESC "
            "LIMIT %s"
        )
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            click.echo("No awards found matching the criteria.")
            filter_parts = []
            if naics:
                filter_parts.append(f"naics={naics}")
            if set_aside:
                filter_parts.append(f"set-aside={set_aside}")
            if agency:
                filter_parts.append(f"agency={agency}")
            if vendor:
                filter_parts.append(f"vendor={vendor}")
            if piid:
                filter_parts.append(f"piid={piid}")
            if from_date:
                filter_parts.append(f"from={from_date}")
            if to_date:
                filter_parts.append(f"to={to_date}")
            click.echo(f"  Filters: {', '.join(filter_parts) if filter_parts else 'none'}")
            return

        click.echo(f"\nFound {len(rows)} award(s)"
                   + (f" (showing top {limit})" if len(rows) == limit else ""))
        click.echo("")

        header = (
            f"{'PIID':<17s}  {'Vendor':<35s}  {'$Amount':>15s}  "
            f"{'NAICS':<6s}  {'Set-Aside':<10s}  {'Agency':<25s}  "
            f"{'Date Signed':<12s}  {'Offers':<6s}"
        )
        click.echo(header)
        click.echo("-" * len(header))

        for row in rows:
            contract_id, vendor_name, vendor_uei, dollars_obligated, \
                naics_code, set_aside_type, agency_name, date_signed, num_offers = row

            piid_str = f"{(contract_id or ''):<17s}"
            vendor_trunc = (vendor_name[:32] + "...") if vendor_name and len(vendor_name) > 35 else (vendor_name or "")
            vendor_str = f"{vendor_trunc:<35s}"

            if dollars_obligated is not None:
                amount_str = f"${dollars_obligated:>13,.0f}"
            else:
                amount_str = f"{'N/A':>15s}"
            amount_str = f"{amount_str:>15s}"

            naics_str = f"{(naics_code or ''):<6s}"
            sa_str = f"{(set_aside_type or ''):<10s}"
            agency_trunc = (agency_name[:22] + "...") if agency_name and len(agency_name) > 25 else (agency_name or "")
            agency_str = f"{agency_trunc:<25s}"

            if date_signed:
                date_str = str(date_signed)[:10]
            else:
                date_str = "N/A"
            date_str = f"{date_str:<12s}"

            offers_str = f"{(str(num_offers) if num_offers is not None else 'N/A'):<6s}"

            click.echo(
                f"{piid_str}  {vendor_str}  {amount_str}  "
                f"{naics_str}  {sa_str}  {agency_str}  "
                f"{date_str}  {offers_str}"
            )

        click.echo("")
        click.echo("Note: Run 'python main.py load awards' to refresh local data.")

    except Exception as e:
        logger.exception("Award search failed")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
