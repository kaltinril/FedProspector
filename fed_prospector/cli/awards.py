"""CLI commands for contract award data (Phase 5A)."""

import re
import sys
import time

import click
import requests

from api_clients.base_client import RateLimitExceeded
from config.logging_config import setup_logging
from config import settings


# Whitelist of valid SAM.gov set-aside codes accepted by the Contract Awards
# and Opportunities APIs. Sourced from
# `thesolution/reference/vendor-apis/SAM-OPPORTUNITIES-API.md` (Tier 1-3
# table) plus the additional officially-supported codes documented in SAM.gov
# (IEE, ISBEE, RSB, VSA, VSS, BICiv). Validated against the CLI before any
# API calls are made so that typos fail loudly instead of silently returning
# zero results.
VALID_SET_ASIDE_CODES = frozenset({
    "SBA", "SBP",
    "8A", "8AN",
    "HZC", "HZS",
    "SDVOSBC", "SDVOSBS",
    "WOSB", "WOSBSS",
    "EDWOSB", "EDWOSBSS",
    "IEE", "ISBEE",
    "RSB",
    "VSA", "VSS",
    "BICiv",
})

# NAICS codes are always 6-digit numbers (per Census Bureau spec).
_NAICS_RE = re.compile(r"^\d{6}$")


def _load_awards_for_org(org_identifier, api_key_number, max_calls, dry_run):
    """Load awards for all UEIs linked to an organization."""
    import logging
    from datetime import date, timedelta

    from api_clients.sam_awards_client import SAMAwardsClient
    from db.connection import get_connection
    from etl.awards_loader import AwardsLoader
    from etl.load_manager import LoadManager

    logger = logging.getLogger("fed_prospector.cli.awards")
    today = date.today()
    date_from = date(today.year - 5, today.month, today.day)
    staleness_days = 30

    # Resolve org by name or ID
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if org_identifier.isdigit():
            cursor.execute(
                "SELECT organization_id, name, uei_sam FROM organization WHERE organization_id = %s",
                (int(org_identifier),),
            )
        else:
            cursor.execute(
                "SELECT organization_id, name, uei_sam FROM organization WHERE name = %s",
                (org_identifier,),
            )
        org = cursor.fetchone()
        if not org:
            click.echo(f"ERROR: Organization not found: {org_identifier}")
            sys.exit(1)

        org_id = org["organization_id"]
        org_name = org["name"]
        click.echo(f"\nLoading awards for org: {org_name} (id={org_id})")

        # Gather UEIs from organization_entity
        ueis = set()
        if org["uei_sam"]:
            ueis.add(org["uei_sam"])

        cursor.execute(
            "SELECT uei_sam FROM organization_entity WHERE organization_id = %s AND is_active = 'Y'",
            (org_id,),
        )
        for row in cursor.fetchall():
            if row["uei_sam"]:
                ueis.add(row["uei_sam"])

        # Also try partner_uei if column exists
        try:
            cursor.execute(
                "SELECT partner_uei FROM organization_entity WHERE organization_id = %s AND is_active = 'Y' AND partner_uei IS NOT NULL",
                (org_id,),
            )
            for row in cursor.fetchall():
                if row["partner_uei"]:
                    ueis.add(row["partner_uei"])
        except Exception:
            logger.debug("partner_uei column not available yet")

        if not ueis:
            click.echo(f"  No UEIs found for org {org_name}. Link entities first.")
            return

        click.echo(f"  Found {len(ueis)} UEI(s): {', '.join(sorted(ueis))}")

        # Check staleness per UEI
        stale_cutoff = today - timedelta(days=staleness_days)
        fresh_ueis = set()
        for uei in sorted(ueis):
            cursor.execute(
                "SELECT MAX(last_modified_date) AS latest FROM fpds_contract WHERE vendor_uei = %s",
                (uei,),
            )
            row = cursor.fetchone()
            if row and row["latest"] and row["latest"].date() >= stale_cutoff:
                fresh_ueis.add(uei)

        stale_ueis = sorted(ueis - fresh_ueis)
        click.echo(f"  Fresh ({staleness_days}d): {len(fresh_ueis)} — Stale/missing: {len(stale_ueis)}")

        if not stale_ueis:
            click.echo("  All UEIs have recent data. Nothing to load.")
            return

        for uei in sorted(fresh_ueis):
            click.echo(f"    SKIP {uei} (fresh)")
        for uei in stale_ueis:
            click.echo(f"    LOAD {uei}")

        if dry_run:
            click.echo(f"\n  API key: #{api_key_number}")
            click.echo(f"  Max calls: {max_calls}")
            click.echo(f"  Date range: {date_from} to {today}")
            click.echo("\nNo API calls made (dry run).")
            return

    finally:
        cursor.close()
        conn.close()

    # Load awards for each stale UEI
    client = SAMAwardsClient(api_key_number=api_key_number)
    loader = AwardsLoader()
    load_manager = LoadManager()

    load_id = load_manager.start_load(
        "SAM_AWARDS", "ORG_BULK",
        parameters={"org_id": org_id, "org_name": org_name, "ueis": stale_ueis},
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()
    calls_made = 0
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }

    try:
        for uei in stale_ueis:
            if calls_made >= max_calls:
                click.echo(f"\n  ** Budget exhausted ({max_calls} calls).")
                break

            click.echo(f"\n  Loading UEI {uei}...")
            try:
                awards = client.search_by_awardee(uei, date_from=date_from, date_to=today)
                calls_made += max(1, (len(awards) + 99) // 100)
            except RateLimitExceeded as e:
                click.echo(f"  ** Rate limited: {e}")
                break
            except requests.HTTPError as e:
                click.echo(f"  ** HTTP error for {uei}: {e}")
                continue

            if not awards:
                click.echo(f"    No awards found for {uei}.")
                continue

            stats = loader.load_awards(awards, load_id)
            for k in cumulative:
                cumulative[k] += stats.get(k, 0)

            click.echo(
                f"    {len(awards)} awards: "
                f"{stats.get('records_inserted', 0)} new, "
                f"{stats.get('records_updated', 0)} updated, "
                f"{stats.get('records_unchanged', 0)} unchanged"
            )

        load_manager.complete_load(load_id, **cumulative)
        elapsed = time.time() - t_start

        click.echo(f"\nOrg awards load complete ({elapsed:.1f}s)")
        click.echo(f"  Records read:      {cumulative['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {cumulative['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {cumulative['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {cumulative['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {cumulative['records_errored']:>10,d}")

    except KeyboardInterrupt:
        click.echo("\n\nAborted. Partial progress saved.")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Org awards load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("load-awards")
@click.option("--naics", default=None, help="NAICS code(s) to search — comma-separated for multiple: 541512,541511,561110")
@click.option("--set-aside", "set_aside", default=None, help="Set-aside type (WOSB, 8A, etc.)")
@click.option("--agency", default=None, help="Contracting department CGAC code")
@click.option("--awardee-uei", default=None, help="Awardee UEI to search")
@click.option("--piid", default=None, help="Contract PIID to search")
@click.option("--for-org", "for_org", default=None, help="Load awards for all UEIs linked to an org (name or ID)")
@click.option("--years-back", default=None, type=int, help="Years of history to load")
@click.option("--days-back", default=None, type=int, help="Days of history to load (overrides --years-back)")
@click.option("--fiscal-year", default=None, type=int, help="Specific fiscal year (overrides --years-back)")
@click.option("--date-from", "date_from_str", default=None, help="Start date YYYY-MM-DD (overrides --years-back/--days-back)")
@click.option("--date-to", "date_to_str", default=None, help="End date YYYY-MM-DD (overrides --years-back/--days-back)")
@click.option("--max-calls", default=10, type=int, help="Max API calls for this invocation (default: 10)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip resume and start fresh")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would load without making API calls")
def load_awards(naics, set_aside, agency, awardee_uei, piid, for_org, years_back,
                days_back, fiscal_year, date_from_str, date_to_str,
                max_calls, api_key_number, force, dry_run):
    """Load contract awards from SAM.gov Contract Awards API.

    Supports watermark-based incremental loading, resume after interruption,
    and default NAICS + set-aside filters for scheduled runs.

    When no filters are specified, uses DEFAULT_AWARDS_NAICS and
    DEFAULT_AWARDS_SET_ASIDES from settings. When no date range is given,
    resumes from the last successful load's watermark date.

    Uses offset-based pagination (100 records per API call). Each page
    counts as one API call against the daily SAM.gov limit. Progress is
    saved after every page for crash-safe resume.

    Examples:
        python main.py load awards                          # incremental from watermark
        python main.py load awards --dry-run                # preview without API calls
        python main.py load awards --naics 541512 --years-back 5
        python main.py load awards --set-aside WOSB --years-back 3
        python main.py load awards --force                  # skip resume, start fresh
        python main.py load awards --fiscal-year 2025
        python main.py load awards --for-org "Acme Corp"    # all UEIs for an org
        python main.py load awards --for-org 1 --dry-run    # preview org load
    """
    if for_org:
        _load_awards_for_org(for_org, api_key_number, max_calls, dry_run)
        return
    logger = setup_logging()
    from datetime import date, timedelta
    from api_clients.sam_awards_client import SAMAwardsClient
    from etl.awards_loader import AwardsLoader
    from etl.load_manager import LoadManager

    client = SAMAwardsClient(api_key_number=api_key_number)
    loader = AwardsLoader()
    load_manager = LoadManager()
    today = date.today()

    naics_codes = [c.strip() for c in naics.split(',') if c.strip()] if naics else []

    # A4: Validate NAICS code format (must be 6-digit number)
    invalid_naics = [c for c in naics_codes if not _NAICS_RE.match(c)]
    if invalid_naics:
        raise click.BadParameter(
            f"Invalid NAICS code(s): {', '.join(invalid_naics)}. "
            "NAICS codes must be 6-digit numbers (e.g., 541512).",
            param_hint="--naics",
        )

    # Apply default filters when none specified (fixes scheduler "no filter" error)
    using_defaults = False
    if not any([naics, set_aside, agency, awardee_uei, piid, fiscal_year]):
        from etl.etl_utils import get_tracked_naics, get_tracked_set_asides
        naics_codes = get_tracked_naics()
        naics = ",".join(naics_codes)
        set_aside_list = get_tracked_set_asides()
        set_aside = ",".join(set_aside_list)
        using_defaults = True

    # Build set-aside iteration list
    if set_aside:
        set_aside_codes = [s.strip() for s in set_aside.split(',') if s.strip()]
    else:
        set_aside_codes = [None]  # Single iteration with no set-aside filter

    # A1: Validate set-aside codes against whitelist
    invalid_set_asides = [
        s for s in set_aside_codes if s and s not in VALID_SET_ASIDE_CODES
    ]
    if invalid_set_asides:
        raise click.BadParameter(
            f"Invalid set-aside code(s): {', '.join(invalid_set_asides)}. "
            f"Valid codes: {', '.join(sorted(VALID_SET_ASIDE_CODES))}.",
            param_hint="--set-aside",
        )

    # Date range: explicit dates -> fiscal year -> days-back -> years-back -> watermark -> fallback
    explicit_date_override = (date_from_str is not None or date_to_str is not None or
                              fiscal_year is not None or years_back is not None or days_back is not None)
    watermark_date = None

    if date_from_str or date_to_str:
        from datetime import datetime as dt
        date_from = dt.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else today - timedelta(days=365)
        date_to = dt.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else today
    elif fiscal_year:
        date_from = date(fiscal_year - 1, 10, 1)
        date_to = date(fiscal_year, 9, 30)
    elif days_back is not None:
        date_from = today - timedelta(days=days_back)
        date_to = today
    elif years_back is not None:
        date_from = today - timedelta(days=365 * years_back)
        date_to = today
    else:
        # Auto-detect from watermark
        watermark_date = load_manager.get_watermark("SAM_AWARDS", date_key="date_to")
        if watermark_date:
            from datetime import datetime as dt
            wm = dt.strptime(watermark_date, "%Y-%m-%d").date() if isinstance(watermark_date, str) else watermark_date
            if wm >= today:
                click.echo(f"Awards data is current (last load: {wm}). Skipping.")
                click.echo("  Use --years-back or --fiscal-year to force a date range.")
                return
            date_from = wm
            date_to = today
        else:
            # No previous load — fall back to 1 year
            date_from = today - timedelta(days=365)
            date_to = today

    # Dynamic load_type (P90-2f)
    load_type = "HISTORICAL" if explicit_date_override else "INCREMENTAL"

    # Clean up stale RUNNING loads
    load_manager.cleanup_stale_running("SAM_AWARDS")

    # Resume check (P90-2d)
    completed_combos = []
    resume_set_aside = None
    resume_naics = None
    resume_page = 0

    if not force:
        prev_row, prev_params = load_manager.get_resumable_load("SAM_AWARDS", date_from=str(date_from), date_to=str(date_to))
        if prev_params:
            completed_combos = list(prev_params.get("completed_combos", []))
            resume_set_aside = prev_params.get("current_set_aside")
            resume_naics = prev_params.get("current_naics")
            resume_page = prev_params.get("current_page", 0)
            click.echo(f"Resuming from previous partial load (load_id={prev_row['load_id']})")
            click.echo(f"  Completed combos: {len(completed_combos)}/{len(naics_codes) * len(set_aside_codes)}")
            if resume_set_aside and resume_naics:
                click.echo(f"  Continuing from: {resume_set_aside}/{resume_naics} page {resume_page}")

    codes_to_load = naics_codes if naics_codes else [None]
    sa_to_load = set_aside_codes
    total_combos = len(codes_to_load) * len(sa_to_load)
    remaining_combos = total_combos - len(completed_combos)

    if dry_run:
        click.echo("\nSAM.gov Contract Awards — DRY RUN")
        click.echo(f"  Date range:    {date_from} to {date_to}" + (f" (watermark)" if watermark_date and not explicit_date_override else ""))
        click.echo(f"  Load type:     {load_type}")
        click.echo(f"  NAICS codes:   {len(naics_codes)}" + (f" (defaults)" if using_defaults else ""))
        click.echo(f"  Set-asides:    {', '.join(s for s in set_aside_codes if s) or 'none'}" + (f" (defaults)" if using_defaults else ""))
        click.echo(f"  Total combos:  {total_combos}")
        click.echo(f"  Completed:     {len(completed_combos)}")
        click.echo(f"  Remaining:     {remaining_combos}")
        click.echo(f"  Max calls:     {max_calls}")
        click.echo(f"  API key:       #{api_key_number}")
        if resume_set_aside and resume_naics:
            click.echo(f"  Resume from:   {resume_set_aside}/{resume_naics} page {resume_page}")
        click.echo("\nNo API calls made (dry run).")
        return

    remaining = client._get_remaining_requests()

    click.echo("\nSAM.gov Contract Awards Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    click.echo(f"  Date range:  {date_from} to {date_to}" + (f" (watermark)" if watermark_date and not explicit_date_override else ""))
    click.echo(f"  Load type:   {load_type}")
    if naics_codes:
        click.echo(f"  NAICS:       {len(naics_codes)} codes" + (f" (defaults)" if using_defaults else ""))
    if set_aside_codes[0]:
        click.echo(f"  Set-asides:  {', '.join(set_aside_codes)}" + (f" (defaults)" if using_defaults else ""))
    click.echo(f"  Combos:      {remaining_combos} remaining of {total_combos}")
    click.echo(f"  Max calls:   {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # Start load
    params_dict = {
        "naics": naics, "set_aside": set_aside,
        "date_from": str(date_from), "date_to": str(date_to),
        "completed_combos": completed_combos,
        "current_set_aside": resume_set_aside,
        "current_naics": resume_naics,
        "current_page": resume_page,
        "complete": False,
        "calls_made": 0, "total_fetched": 0,
    }
    load_id = load_manager.start_load("SAM_AWARDS", load_type, parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()
    calls_made = 0
    page_size = 100
    total_fetched = 0
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    budget_exhausted = False

    try:
        for sa_code in sa_to_load:
            if budget_exhausted:
                break

            for naics_code in codes_to_load:
                if budget_exhausted:
                    break

                # Build combo key for tracking
                combo = [naics_code or "", sa_code or ""]

                # Skip completed combos
                if combo in completed_combos:
                    continue

                # Skip combos before resume position (belt-and-suspenders with completed_combos)
                # Removed: fragile index-based skip logic. completed_combos at line 211
                # already handles skipping finished combos. Resume position only matters
                # for setting start_page within the resume combo (handled below).

                label = f"{sa_code or 'ALL'}/{naics_code or 'ALL'}"
                click.echo(f"\n  [{len(completed_combos)+1}/{total_combos}] {label}:")

                # Determine start page (resume within a combo)
                start_page = 0
                if sa_code == resume_set_aside and naics_code == resume_naics:
                    start_page = resume_page
                    resume_set_aside = None  # Clear resume state after using it
                    resume_naics = None
                    resume_page = 0
                    if start_page > 0:
                        click.echo(f"    Resuming from page {start_page}")

                page = start_page
                code_total = 0
                combo_had_results = False
                records = None  # Sentinel: detect if while loop never ran

                if calls_made >= max_calls:
                    budget_exhausted = True
                    click.echo(f"\n  ** Budget exhausted ({max_calls} calls). Progress saved.")
                    click.echo(f"     Run again to resume from {label} page {page}.")
                    break

                while calls_made < max_calls:
                    try:
                        data = client.search_awards(
                            naics_code=naics_code, set_aside=sa_code, agency_code=agency,
                            awardee_uei=awardee_uei, piid=piid,
                            date_signed_from=date_from if not fiscal_year else None,
                            date_signed_to=date_to if not fiscal_year else None,
                            fiscal_year=fiscal_year,
                            limit=page_size, offset=page,
                        )
                    except (RateLimitExceeded, requests.HTTPError) as rate_err:
                        click.echo(f"\n  ** Rate limited — saving progress.")
                        click.echo(f"     {rate_err}")
                        budget_exhausted = True
                        break
                    calls_made += 1

                    records = data.get("awardSummary", [])
                    code_total = int(data.get("totalRecords", 0))
                    total_fetched += len(records)

                    if records:
                        combo_had_results = True
                        page_stats = loader.load_awards_batch(records, load_id)
                        for k in cumulative:
                            cumulative[k] += page_stats.get(k, 0)

                    # Save progress after every page (crash safety)
                    params_dict.update({
                        "current_set_aside": sa_code,
                        "current_naics": naics_code,
                        "current_page": page,
                        "completed_combos": completed_combos,
                        "complete": False,
                        "calls_made": calls_made,
                        "total_fetched": total_fetched,
                    })
                    load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

                    db_note = ""
                    if records:
                        ins = page_stats.get("records_inserted", 0)
                        upd = page_stats.get("records_updated", 0)
                        unch = page_stats.get("records_unchanged", 0)
                        db_note = f" -> DB: {ins} new, {upd} updated, {unch} unchanged"
                    click.echo(f"    Page {page + 1}: {len(records)} records (total: {code_total:,d}){db_note}")

                    if not records or (page + 1) * page_size >= code_total:
                        break
                    page += 1

                # Check if while loop exited due to budget vs natural completion
                combo_fully_paged = (not records) or ((page + 1) * page_size >= code_total)
                if calls_made >= max_calls and not combo_fully_paged:
                    budget_exhausted = True

                # Combo finished (or budget exhausted)
                if not budget_exhausted:
                    # This combo is done — add to completed list
                    completed_combos.append(combo)
                    params_dict["completed_combos"] = completed_combos
                    load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)
                    if not combo_had_results:
                        click.echo(f"    No records found.")
                else:
                    click.echo(f"\n  ** Budget exhausted ({max_calls} calls). Progress saved.")
                    click.echo(f"     Run again to resume from {label} page {page}.")

        # Check if all combos complete
        if len(completed_combos) >= total_combos:
            params_dict["complete"] = True
            load_manager.save_load_progress(load_id, parameters=params_dict, **cumulative)

        elapsed = time.time() - t_start
        is_complete = params_dict.get("complete", False)

        click.echo(f"\nFetched {total_fetched:,d} award records in {calls_made} API calls ({elapsed:.1f}s)")
        click.echo(f"  Status:            {'COMPLETE' if is_complete else 'PARTIAL'}")
        click.echo(f"  Combos completed:  {len(completed_combos)}/{total_combos}")
        click.echo(f"  Records read:      {cumulative['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {cumulative['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {cumulative['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {cumulative['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {cumulative['records_errored']:>10,d}")

        if not is_complete:
            click.echo(f"\n  Run again to continue. Use --force to start fresh.")

    except KeyboardInterrupt:
        click.echo(f"\n\nAborted. Progress saved ({len(completed_combos)} combos complete).")
        click.echo("  Run again to resume.")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Awards load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("replay-awards")
@click.option("--load-id", required=True, type=int, help="Load ID to replay from staging")
@click.option("--status", default="E", type=click.Choice(["E", "N", "A"]),
              help="Which staging records to replay: E=errored, N=unprocessed, A=all (default: E)")
def replay_awards(load_id, status):
    """Replay staged award records through the awards loader.

    Re-processes raw JSON from stg_fpds_award_raw for a given load ID.
    Useful for retrying records that failed due to transient errors or
    after fixing a normalization bug.

    Examples:
        python main.py load replay-awards --load-id 42
        python main.py load replay-awards --load-id 42 --status A
        python main.py load replay-awards --load-id 42 --status N
    """
    logger = setup_logging()
    import json as json_mod

    from db.connection import get_connection
    from etl.awards_loader import AwardsLoader
    from etl.load_manager import LoadManager

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Build query to fetch staging records
        where = "WHERE load_id = %s"
        params = [load_id]
        if status == "E":
            where += " AND processed = 'E'"
        elif status == "N":
            where += " AND processed = 'N'"
        # status == "A" means all records, no extra filter

        cursor.execute(
            f"SELECT id, raw_json FROM stg_fpds_award_raw {where} ORDER BY id",
            params,
        )
        rows = cursor.fetchall()

        if not rows:
            click.echo(f"No staging records found for load_id={load_id} with status filter '{status}'.")
            return

        click.echo(f"Found {len(rows)} staging record(s) to replay from load_id={load_id} (filter: {status})")

        # Parse raw JSON back into dicts
        awards_data = []
        parse_errors = 0
        for row in rows:
            try:
                raw = json_mod.loads(row["raw_json"])
                awards_data.append(raw)
            except (json_mod.JSONDecodeError, TypeError) as e:
                parse_errors += 1
                logger.warning("Failed to parse raw_json for staging id=%d: %s", row["id"], e)

        if parse_errors:
            click.echo(f"  Skipped {parse_errors} record(s) with unparseable JSON")

        if not awards_data:
            click.echo("No valid records to replay.")
            return

        # Create a new load for the replay
        load_manager = LoadManager()
        replay_load_id = load_manager.start_load(
            "SAM_AWARDS_REPLAY", "REPLAY",
            parameters={"source_load_id": load_id, "status_filter": status},
        )
        click.echo(f"Replay load started (load_id={replay_load_id})")

        loader = AwardsLoader(load_manager=load_manager)
        t_start = time.time()
        stats = loader.load_awards(awards_data, replay_load_id)
        elapsed = time.time() - t_start

        load_manager.complete_load(replay_load_id, **stats)

        click.echo(f"\nReplay complete! ({elapsed:.1f}s)")
        click.echo(f"  Records read:      {stats['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {stats['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {stats['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {stats['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {stats['records_errored']:>10,d}")

    except Exception as e:
        logger.exception("Awards replay failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


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
