"""CLI commands for subaward data (Phase 5G)."""

import sys
import time

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-subawards")
@click.option("--naics", default=None, help="NAICS code filter (searches primeNaics)")
@click.option("--agency", default=None, help="Four-digit contracting agency code filter")
@click.option("--prime-uei", default=None, help="Prime contractor UEI filter")
@click.option("--max-calls", default=20, type=int,
              help="Max API calls for this invocation (default: 20)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def load_subawards(naics, agency, prime_uei, max_calls, api_key_number):
    """Load subaward/subcontract data from SAM.gov API.

    Fetches subaward records from the SAM.gov Acquisition Subaward Reporting
    API and loads them into the sam_subaward table. Uses SHA-256 change
    detection to skip unchanged records.

    Uses page-based pagination (up to 1,000 records per API call). Each page
    counts as one API call against the daily SAM.gov limit.

    Examples:
        python main.py load subawards
        python main.py load subawards --naics 541511
        python main.py load subawards --agency 9700 --key 2
        python main.py load subawards --prime-uei ABC123DEF456 --max-calls 50
    """
    logger = setup_logging()

    from api_clients.sam_subaward_client import SAMSubawardClient
    from etl.subaward_loader import SubawardLoader
    from etl.load_manager import LoadManager

    client = SAMSubawardClient(api_key_number=api_key_number)
    loader = SubawardLoader()
    load_manager = LoadManager()

    remaining = client._get_remaining_requests()

    click.echo("SAM.gov Subaward Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    if naics:
        click.echo(f"  NAICS:       {naics}")
    if agency:
        click.echo(f"  Agency:      {agency}")
    if prime_uei:
        click.echo(f"  Prime UEI:   {prime_uei}")
    click.echo(f"  Max calls:   {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # Start load
    params_dict = {
        "naics": naics,
        "agency": agency,
        "prime_uei": prime_uei,
    }
    load_id = load_manager.start_load("SAM_SUBAWARD", "FULL", parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    try:
        # Collect subawards with pagination (respecting max_calls)
        all_subawards = []
        calls_made = 0
        page_number = 0
        total = 0

        while calls_made < max_calls:
            data = client.search_subcontracts(
                naics_code=naics,
                agency_id=agency,
                prime_uei=prime_uei,
                page_number=page_number,
                page_size=1000,
            )
            calls_made += 1

            records = data.get("data", [])
            total = data.get("totalRecords", 0)
            total_pages = data.get("totalPages", 0)
            all_subawards.extend(records)

            click.echo(f"  Page {page_number + 1}/{total_pages or '?'}: {len(records)} records "
                       f"(total available: {total:,d}, fetched so far: {len(all_subawards):,d})")

            if not records or page_number + 1 >= total_pages:
                break
            page_number += 1

        # Check if budget was exhausted before all data was fetched
        if calls_made >= max_calls and total > 0 and len(all_subawards) < total:
            remaining_records = total - len(all_subawards)
            page_size = 1000
            remaining_calls = (remaining_records + page_size - 1) // page_size
            click.echo(f"\n  ** BUDGET EXHAUSTED: Retrieved {len(all_subawards):,d} of {total:,d} available records.")
            click.echo(f"     {remaining_records:,d} records remain ({remaining_calls} more API calls needed).")
            click.echo(f"     To get all data, re-run with: --max-calls {calls_made + remaining_calls}")

        click.echo(f"\nFetched {len(all_subawards):,d} subaward records in {calls_made} API calls")

        if not all_subawards:
            click.echo("No subawards found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # Load into database
        click.echo("Loading into sam_subaward table...")
        stats = loader.load_subawards(all_subawards, load_id)

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
        logger.exception("Subaward load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("search-subawards")
@click.option("--prime-uei", default=None, help="Prime contractor UEI to search")
@click.option("--sub-uei", default=None, help="Subcontractor UEI to search")
@click.option("--naics", default=None, help="NAICS code filter")
@click.option("--piid", default=None, help="Prime contract PIID to search")
@click.option("--limit", default=25, type=int, help="Max results to display (default: 25)")
def search_subawards(prime_uei, sub_uei, naics, piid, limit):
    """Search local subaward data for teaming analysis.

    Queries the local sam_subaward table (no API calls). Load data first
    with 'python main.py load subawards'.

    Examples:
        python main.py search subawards --prime-uei ABC123DEF456
        python main.py search subawards --sub-uei XYZ789GHI012
        python main.py search subawards --naics 541511 --limit 50
        python main.py search subawards --piid W91QVN-20-C-0001
    """
    logger = setup_logging()

    from db.connection import get_connection

    if not any([prime_uei, sub_uei, naics, piid]):
        click.echo("ERROR: At least one filter is required: --prime-uei, --sub-uei, --naics, or --piid")
        sys.exit(1)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conditions = []
        params = []

        if prime_uei:
            conditions.append("prime_uei = %s")
            params.append(prime_uei)
        if sub_uei:
            conditions.append("sub_uei = %s")
            params.append(sub_uei)
        if naics:
            conditions.append("naics_code = %s")
            params.append(naics)
        if piid:
            conditions.append("prime_piid = %s")
            params.append(piid)

        where = " AND ".join(conditions)
        params.append(limit)

        cursor.execute(
            f"SELECT prime_piid, prime_name, prime_uei, "
            f"       sub_name, sub_uei, sub_amount, sub_date, "
            f"       naics_code, sub_business_type, pop_state "
            f"FROM sam_subaward "
            f"WHERE {where} "
            f"ORDER BY sub_date DESC "
            f"LIMIT %s",
            params,
        )
        results = cursor.fetchall()

        if not results:
            click.echo("\nNo subaward records found matching the criteria.")
            click.echo("Tip: Load data first with 'python main.py load subawards'")
            return

        click.echo(f"\n  Found {len(results)} subaward record(s):")
        click.echo(f"  {'='*90}")

        for i, row in enumerate(results, 1):
            click.echo(f"\n  --- Record #{i} ---")
            click.echo(f"  Prime PIID:        {row.get('prime_piid', 'N/A')}")
            click.echo(f"  Prime Contractor:  {row.get('prime_name', 'N/A')}")
            click.echo(f"  Prime UEI:         {row.get('prime_uei', 'N/A')}")
            click.echo(f"  Subcontractor:     {row.get('sub_name', 'N/A')}")
            click.echo(f"  Sub UEI:           {row.get('sub_uei', 'N/A')}")
            amount = row.get('sub_amount')
            click.echo(f"  Sub Amount:        ${amount:,.2f}" if amount else "  Sub Amount:        N/A")
            click.echo(f"  Sub Date:          {row.get('sub_date', 'N/A')}")
            click.echo(f"  NAICS:             {row.get('naics_code', 'N/A')}")
            click.echo(f"  Business Type:     {row.get('sub_business_type', 'N/A')}")
            click.echo(f"  State:             {row.get('pop_state', 'N/A')}")

        click.echo(f"\n  Showing {len(results)} of matching records (limit: {limit})")

    except Exception as e:
        logger.exception("Subaward search failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("teaming-partners")
@click.option("--naics", default=None, help="NAICS code filter")
@click.option("--min-subs", default=2, type=int,
              help="Minimum number of subcontracts to qualify (default: 2)")
@click.option("--limit", default=25, type=int, help="Max results to display (default: 25)")
def teaming_partners(naics, min_subs, limit):
    """Find potential teaming partners from subaward data.

    Identifies prime contractors who frequently subcontract to small
    businesses in your NAICS codes. Queries the local sam_subaward table
    (no API calls). Load data first with 'python main.py load subawards'.

    Examples:
        python main.py analyze teaming
        python main.py analyze teaming --naics 541511
        python main.py analyze teaming --naics 541511 --min-subs 5 --limit 50
    """
    logger = setup_logging()

    from etl.subaward_loader import SubawardLoader

    loader = SubawardLoader()

    click.echo("Teaming Partner Analysis")
    if naics:
        click.echo(f"  NAICS filter: {naics}")
    click.echo(f"  Min subcontracts: {min_subs}")
    click.echo(f"  Max results: {limit}")

    try:
        results = loader.find_teaming_partners(
            naics_code=naics,
            min_subawards=min_subs,
            limit=limit,
        )

        if not results:
            click.echo("\nNo teaming partners found matching the criteria.")
            click.echo("Tip: Load data first with 'python main.py load subawards'")
            return

        click.echo(f"\n  Found {len(results)} potential teaming partner(s):")
        click.echo(f"  {'='*100}")
        click.echo(
            f"  {'Prime UEI':<14s}  {'Prime Name':<40s}  {'Subs':>5s}  "
            f"{'Unique':>6s}  {'Total Amount':>14s}  {'NAICS Codes'}"
        )
        click.echo(
            f"  {'-'*14}  {'-'*40}  {'-'*5}  "
            f"{'-'*6}  {'-'*14}  {'-'*20}"
        )

        for row in results:
            uei = row.get("prime_uei") or "N/A"
            name = row.get("prime_name") or "N/A"
            if len(name) > 40:
                name = name[:37] + "..."
            sub_count = row.get("sub_count", 0)
            unique_subs = row.get("unique_subs", 0)
            total = row.get("total_sub_amount")
            total_str = f"${total:,.2f}" if total else "N/A"
            naics_list = row.get("naics_codes") or "N/A"

            click.echo(
                f"  {uei:<14s}  {name:<40s}  {sub_count:>5d}  "
                f"{unique_subs:>6d}  {total_str:>14s}  {naics_list}"
            )

        click.echo(f"\n  Use 'python main.py search subawards --prime-uei <UEI>' to see details for a specific prime.")

    except Exception as e:
        logger.exception("Teaming partner analysis failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)
