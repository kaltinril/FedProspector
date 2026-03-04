"""CLI commands for subaward data (Phase 5G)."""

import sys
import time

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-subawards")
@click.option("--naics", default=None,
              help="NAICS code(s) -- comma-separated for multiple: 541512,541511. "
                   "Uses PIID-driven strategy (queries local fpds_contract table).")
@click.option("--agency", default=None, help="Four-digit contracting agency code filter")
@click.option("--piid", default=None, help="Prime contract PIID (direct API filter)")
@click.option("--years-back", default=2, type=int,
              help="Years of contract history to search for PIIDs (default: 2)")
@click.option("--max-calls", default=20, type=int,
              help="Max API calls for this invocation (default: 20)")
@click.option("--min-amount", default=750000, type=float,
              help="Min prime contract dollars_obligated to include (default: 750000). "
                   "Primes only report subawards on contracts >= $750K (FAR 52.204-10). "
                   "Use 0 to include all contracts.")
@click.option("--force", is_flag=True, default=False,
              help="Ignore previous progress and start a fresh load")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def load_subawards(naics, agency, piid, years_back, max_calls, min_amount, force, api_key_number):
    """Load subaward/subcontract data from SAM.gov API.

    Fetches subaward records from the SAM.gov Acquisition Subaward Reporting
    API and loads them into the sam_subaward table. Uses SHA-256 change
    detection to skip unchanged records.

    PIID-driven strategy (recommended): When --naics is provided, queries the
    local fpds_contract table for PIIDs signed within --years-back, then
    fetches subawards per PIID from the API. Automatically resumes from the
    last PIID if a previous partial load exists. Use --force to start fresh.

    Direct PIID mode: When --piid is provided, fetches subawards for that
    single prime contract.

    Agency mode: When --agency is provided, pages through all subawards for
    that agency.

    At least one filter is required (--naics, --agency, or --piid).

    Examples:
        python main.py load subawards --naics 541512
        python main.py load subawards --naics 541512,541511 --years-back 3
        python main.py load subawards --piid W91QVN-20-C-0001
        python main.py load subawards --agency 9700 --key 2
        python main.py load subawards --naics 541512 --force
    """
    logger = setup_logging()

    import json
    from datetime import date, timedelta
    from api_clients.sam_subaward_client import SAMSubawardClient
    from etl.subaward_loader import SubawardLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection

    # --- Validate: at least one filter required ---
    if not any([naics, agency, piid]):
        click.echo("ERROR: At least one filter is required (--naics, --agency, or --piid)")
        click.echo("  Without a filter, the API returns 2.7M+ records across 2,700+ pages.")
        click.echo("  Use --naics for PIID-driven loading (recommended) or --piid for direct lookup.")
        sys.exit(1)

    # --- Parse comma-separated NAICS ---
    naics_codes = [c.strip() for c in naics.split(',') if c.strip()] if naics else []

    # --- Compute date window from --years-back ---
    today = date.today()
    date_from = today - timedelta(days=365 * years_back)
    date_to = today
    # SAM API expects MM/DD/YYYY date strings
    date_from_str = date_from.strftime("%m/%d/%Y")
    date_to_str = date_to.strftime("%m/%d/%Y")

    # --- PIID-driven: query local fpds_contract for PIIDs ---
    all_piids = []
    if naics_codes:
        piid_conn = get_connection()
        piid_cursor = piid_conn.cursor()
        try:
            for naics_code in naics_codes:
                if min_amount > 0:
                    piid_cursor.execute(
                        "SELECT DISTINCT contract_id FROM fpds_contract "
                        "WHERE naics_code = %s AND date_signed >= %s "
                        "AND dollars_obligated >= %s",
                        (naics_code, date_from, min_amount),
                    )
                else:
                    piid_cursor.execute(
                        "SELECT DISTINCT contract_id FROM fpds_contract "
                        "WHERE naics_code = %s AND date_signed >= %s",
                        (naics_code, date_from),
                    )
                piids_for_naics = [row[0] for row in piid_cursor.fetchall()]
                click.echo(f"  NAICS {naics_code}: {len(piids_for_naics)} PIIDs found in fpds_contract")
                all_piids.extend(piids_for_naics)
        finally:
            piid_cursor.close()
            piid_conn.close()

        # De-duplicate while preserving order
        seen = set()
        unique_piids = []
        for p in all_piids:
            if p not in seen:
                seen.add(p)
                unique_piids.append(p)
        all_piids = unique_piids

        if not all_piids:
            click.echo("\nNo PIIDs found in fpds_contract for the given NAICS codes.")
            click.echo("  Load award data first: python main.py load awards --naics <code> --years-back <N>")
            return

        click.echo(f"  Total unique PIIDs: {len(all_piids)}")

    # --- Setup client/loader ---
    client = SAMSubawardClient(api_key_number=api_key_number)
    loader = SubawardLoader()
    load_manager = LoadManager()

    remaining = client._get_remaining_requests()

    click.echo("\nSAM.gov Subaward Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    if naics_codes:
        click.echo(f"  NAICS:       {', '.join(naics_codes)} ({len(naics_codes)} code{'s' if len(naics_codes) != 1 else ''})")
        click.echo(f"  Strategy:    PIID-driven ({len(all_piids)} PIIDs from fpds_contract)")
        click.echo(f"  Date range:  {date_from} to {date_to} ({years_back} year{'s' if years_back != 1 else ''} back)")
        if min_amount > 0:
            click.echo(f"  Min amount:  ${min_amount:,.0f} (FAR 52.204-10 subaward reporting threshold)")
    if piid:
        click.echo(f"  PIID:        {piid}")
        click.echo(f"  Strategy:    Direct PIID lookup")
    if agency:
        click.echo(f"  Agency:      {agency}")
        click.echo(f"  Strategy:    Agency page-through")
    click.echo(f"  Max calls:   {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # --- Resume support: check for previous partial load ---
    resume_piid_index = 0
    resume_page = 0

    if not force:
        res_conn = get_connection()
        res_cursor = res_conn.cursor(dictionary=True)
        try:
            res_cursor.execute(
                "SELECT load_id, parameters FROM etl_load_log "
                "WHERE source_system = 'SAM_SUBAWARD' "
                "AND status = 'SUCCESS' "
                "AND parameters IS NOT NULL "
                "ORDER BY started_at DESC LIMIT 1"
            )
            prev = res_cursor.fetchone()
        finally:
            res_cursor.close()
            res_conn.close()

        if prev and prev["parameters"]:
            prev_params = json.loads(prev["parameters"])
            if not prev_params.get("complete", False):
                # Check if params match current request
                if naics_codes and prev_params.get("naics_codes") == naics_codes:
                    resume_piid_index = prev_params.get("current_piid_index", 0)
                    if resume_piid_index > 0:
                        click.echo(f"  Resuming from PIID #{resume_piid_index + 1} of {len(all_piids)} "
                                   f"(load_id={prev['load_id']})")
                elif agency and prev_params.get("agency") == agency:
                    resume_page = prev_params.get("current_page", 0)
                    if resume_page > 0:
                        click.echo(f"  Resuming from page {resume_page + 1} "
                                   f"(load_id={prev['load_id']})")

    # --- Build params dict for checkpoint ---
    params_dict = {
        "naics_codes": naics_codes,
        "piids_count": len(all_piids),
        "agency": agency,
        "direct_piid": piid,
        "years_back": years_back,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "current_piid_index": resume_piid_index,
        "current_page": resume_page,
        "calls_made": 0,
        "complete": False,
    }

    load_id = load_manager.start_load("SAM_SUBAWARD", "FULL", parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    calls_made = 0

    try:
        if piid:
            # --- Direct PIID mode: paginate through all results ---
            piid_total = 0
            page_num = 0
            while calls_made < max_calls:
                data = client.search_subcontracts(
                    piid=piid, from_date=date_from_str, to_date=date_to_str,
                    page_number=page_num, page_size=1000,
                )
                calls_made += 1
                records = data.get("data", [])
                total_pages = int(data.get("totalPages", 0))

                if records:
                    batch_stats = loader.load_subaward_batch(records, load_id)
                    for k in cumulative:
                        cumulative[k] += batch_stats.get(k, 0)
                    piid_total += len(records)

                if not records or page_num + 1 >= total_pages:
                    break
                page_num += 1

            click.echo(f"  PIID {piid}: {piid_total} subawards")

            params_dict["calls_made"] = calls_made
            params_dict["complete"] = (not records or page_num + 1 >= total_pages)
            load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

        elif naics_codes:
            # --- PIID-driven NAICS mode ---
            for i, piid_val in enumerate(all_piids):
                if i < resume_piid_index:
                    continue  # skip already-fetched PIIDs

                if calls_made >= max_calls:
                    click.echo(f"\n  ** BUDGET EXHAUSTED after {calls_made} calls.")
                    click.echo(f"     {len(all_piids) - i} PIIDs remaining.")
                    click.echo(f"     Run the same command again to resume.")
                    break

                # Paginate within each PIID (most have <1000, but some have more)
                piid_total = 0
                page_num = 0
                while calls_made < max_calls:
                    data = client.search_subcontracts(
                        piid=piid_val, page_number=page_num, page_size=1000,
                    )
                    calls_made += 1
                    records = data.get("data", [])
                    total_records = int(data.get("totalRecords", 0))
                    total_pages = int(data.get("totalPages", 0))

                    if records:
                        batch_stats = loader.load_subaward_batch(records, load_id)
                        for k in cumulative:
                            cumulative[k] += batch_stats.get(k, 0)
                        piid_total += len(records)

                    # Done with this PIID if no more pages
                    if not records or page_num + 1 >= total_pages:
                        break
                    page_num += 1

                # Save checkpoint after each PIID
                params_dict["current_piid_index"] = i + 1
                params_dict["calls_made"] = calls_made
                load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

                click.echo(f"    PIID {i + 1}/{len(all_piids)}: {piid_val} -> {piid_total} subawards")

        elif agency:
            # --- Agency mode: page through results ---
            page_number = resume_page
            while calls_made < max_calls:
                data = client.search_subcontracts(
                    agency_id=agency, page_number=page_number, page_size=1000,
                )
                calls_made += 1
                records = data.get("data", [])
                total = data.get("totalRecords", 0)
                total_pages = data.get("totalPages", 0)

                if records:
                    batch_stats = loader.load_subaward_batch(records, load_id)
                    for k in cumulative:
                        cumulative[k] += batch_stats.get(k, 0)

                params_dict["current_page"] = page_number + 1
                params_dict["calls_made"] = calls_made
                load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

                click.echo(f"  Page {page_number + 1}/{total_pages or '?'}: "
                           f"{len(records)} records (total: {total:,d})")

                if not records or page_number + 1 >= total_pages:
                    break
                page_number += 1

    except KeyboardInterrupt:
        # Save progress so next run can resume
        params_dict["calls_made"] = calls_made
        load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)
        click.echo(f"\n  Interrupted. Progress saved (load_id={load_id}).")
        click.echo("  Run the same command again to resume.")
        return

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Subaward load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)

    # --- Mark complete when done ---
    is_complete = (calls_made < max_calls) or params_dict.get("complete", False)
    params_dict["complete"] = is_complete
    params_dict["calls_made"] = calls_made
    load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

    if is_complete:
        load_manager.complete_load(load_id, **cumulative)

    # --- Summary ---
    elapsed = time.time() - t_start
    status = "COMPLETE" if is_complete else "PARTIAL"
    click.echo(f"\nSubaward load {status}! ({elapsed:.1f}s)")
    click.echo(f"  Records read:      {cumulative['records_read']:>10,d}")
    click.echo(f"  Records inserted:  {cumulative['records_inserted']:>10,d}")
    click.echo(f"  Records updated:   {cumulative['records_updated']:>10,d}")
    click.echo(f"  Records unchanged: {cumulative['records_unchanged']:>10,d}")
    click.echo(f"  Records errored:   {cumulative['records_errored']:>10,d}")
    click.echo(f"  API calls used:    {calls_made}")
    click.echo(f"  API calls remaining: {client._get_remaining_requests()}")
    if not is_complete:
        click.echo("  Run the same command again to resume.")


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
