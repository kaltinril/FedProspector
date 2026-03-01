"""CLI commands for exclusion data (Phase 5E)."""

import sys
import time

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-exclusions")
@click.option("--exclusion-type", default=None,
              help="Filter by exclusion type (e.g., 'Ineligible (Proceedings Completed)')")
@click.option("--agency", default=None, help="Excluding agency code filter")
@click.option("--max-calls", default=20, type=int,
              help="Max API calls for this invocation (default: 20)")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def load_exclusions(exclusion_type, agency, max_calls, api_key_number):
    """Load exclusion records from SAM.gov Exclusions API.

    Fetches active exclusion records and loads them into the sam_exclusion
    table. Uses SHA-256 change detection to skip unchanged records.

    Uses offset-based pagination (100 records per API call). Each page
    counts as one API call against the daily SAM.gov limit.

    Examples:
        python main.py load-exclusions
        python main.py load-exclusions --exclusion-type "Ineligible (Proceedings Completed)"
        python main.py load-exclusions --agency DOD --key 2
    """
    logger = setup_logging()

    from api_clients.sam_exclusions_client import SAMExclusionsClient
    from etl.exclusions_loader import ExclusionsLoader
    from etl.load_manager import LoadManager

    client = SAMExclusionsClient(api_key_number=api_key_number)
    loader = ExclusionsLoader()
    load_manager = LoadManager()

    remaining = client._get_remaining_requests()

    click.echo("SAM.gov Exclusions Load")
    click.echo(f"  API key:     #{api_key_number} (limit: {client.max_daily_requests}/day)")
    if exclusion_type:
        click.echo(f"  Type filter: {exclusion_type}")
    if agency:
        click.echo(f"  Agency:      {agency}")
    click.echo(f"  Max calls:   {max_calls}")
    click.echo(f"  API calls remaining today: {remaining}")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today.")
        sys.exit(1)

    # Start load
    params_dict = {
        "exclusion_type": exclusion_type,
        "agency": agency,
    }
    load_id = load_manager.start_load("SAM_EXCLUSIONS", "FULL", parameters=params_dict)
    click.echo(f"\nLoad started (load_id={load_id})")

    t_start = time.time()

    try:
        # Collect exclusions with pagination (respecting max_calls)
        all_exclusions = []
        calls_made = 0
        offset = 0

        while calls_made < max_calls:
            data = client.search_exclusions(
                exclusion_type=exclusion_type,
                excluding_agency_code=agency,
                limit=100, offset=offset,
            )
            calls_made += 1

            records = data.get("excludedEntity", [])
            total = data.get("totalRecords", 0)
            all_exclusions.extend(records)

            click.echo(f"  Page {calls_made}: {len(records)} records "
                       f"(total available: {total:,d}, fetched so far: {len(all_exclusions):,d})")

            if not records or offset + 100 >= total:
                break
            offset += 100

        click.echo(f"\nFetched {len(all_exclusions):,d} exclusion records in {calls_made} API calls")

        if not all_exclusions:
            click.echo("No exclusions found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # Load into database
        click.echo("Loading into sam_exclusion table...")
        stats = loader.load_exclusions(all_exclusions, load_id)

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
        logger.exception("Exclusions load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("check-exclusion")
@click.option("--uei", default=None, help="UEI to check for exclusions")
@click.option("--name", default=None, help="Entity or individual name to search")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1 or 2, default: 2)")
def check_exclusion(uei, name, api_key_number):
    """Check a specific UEI or entity name for exclusions.

    Searches the SAM.gov Exclusions API for the given UEI or name and
    displays any matching exclusion records.

    Uses 1 API call per search. Results are also checked against the
    local sam_exclusion table if available.

    Examples:
        python main.py check-exclusion --uei ABC123DEF456
        python main.py check-exclusion --name "Acme Corp"
    """
    logger = setup_logging()

    if not uei and not name:
        click.echo("ERROR: Either --uei or --name is required")
        sys.exit(1)

    from api_clients.sam_exclusions_client import SAMExclusionsClient

    client = SAMExclusionsClient(api_key_number=api_key_number)

    remaining = client._get_remaining_requests()
    click.echo(f"SAM.gov Exclusion Check (API calls remaining: {remaining})")

    if remaining < 1:
        click.echo("\nERROR: No API calls remaining today. Checking local DB only...")
        _check_local_only(uei, name)
        return

    try:
        if uei:
            click.echo(f"  Checking UEI: {uei}")
            exclusions = client.check_entity(uei)
        else:
            click.echo(f"  Searching name: {name}")
            exclusions = client.search_by_name(name)

        if not exclusions:
            click.echo("\n  CLEAN - No exclusions found.")
            return

        click.echo(f"\n  WARNING: {len(exclusions)} exclusion(s) found!")
        click.echo(f"  {'='*60}")

        for i, exc in enumerate(exclusions, 1):
            click.echo(f"\n  --- Exclusion #{i} ---")
            click.echo(f"  UEI:              {exc.get('ueiSAM', 'N/A')}")
            click.echo(f"  Entity Name:      {exc.get('entityName', 'N/A')}")
            if exc.get("firstName"):
                click.echo(f"  Individual:       {exc.get('firstName', '')} "
                          f"{exc.get('middleName', '')} {exc.get('lastName', '')}")
            click.echo(f"  CAGE Code:        {exc.get('cageCode', 'N/A')}")
            click.echo(f"  Type:             {exc.get('exclusionType', 'N/A')}")
            click.echo(f"  Program:          {exc.get('exclusionProgram', 'N/A')}")
            click.echo(f"  Excluding Agency: {exc.get('excludingAgencyName', 'N/A')}")
            click.echo(f"  Activation Date:  {exc.get('activationDate', 'N/A')}")
            click.echo(f"  Termination Date: {exc.get('terminationDate', 'N/A')}")
            if exc.get("additionalComments"):
                comments = exc["additionalComments"]
                if len(comments) > 200:
                    comments = comments[:200] + "..."
                click.echo(f"  Comments:         {comments}")

    except Exception as e:
        logger.exception("Exclusion check failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("check-prospects")
def check_prospects():
    """Check all active prospect team members against exclusions.

    Queries the local sam_exclusion table to find any prospect_team_member
    UEIs that appear in the exclusions list. This does NOT make API calls;
    it uses locally loaded data.

    Run 'load-exclusions' first to populate the local exclusions table.

    Examples:
        python main.py check-prospects
    """
    logger = setup_logging()

    from etl.exclusions_loader import ExclusionsLoader

    loader = ExclusionsLoader()

    click.echo("Checking prospect team members against exclusions...")

    try:
        results = loader.check_prospects()

        if not results:
            click.echo("\n  CLEAN - No prospect team members found in exclusions list.")
            return

        click.echo(f"\n  WARNING: {len(results)} excluded team member(s) found!")
        click.echo(f"  {'='*70}")
        click.echo(f"  {'Prospect':>8s}  {'UEI':<14s}  {'Role':<15s}  "
                  f"{'Exclusion Type':<30s}  {'Agency'}")
        click.echo(f"  {'-'*8}  {'-'*14}  {'-'*15}  {'-'*30}  {'-'*20}")

        for row in results:
            click.echo(
                f"  {row['prospect_id']:>8d}  "
                f"{row['uei_sam']:<14s}  "
                f"{(row.get('role') or 'N/A'):<15s}  "
                f"{(row.get('exclusion_type') or 'N/A'):<30s}  "
                f"{row.get('excluding_agency_name', 'N/A')}"
            )

        click.echo(f"\n  Run 'python main.py check-exclusion --uei <UEI>' for details on each.")

    except Exception as e:
        logger.exception("Prospect exclusion check failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


def _check_local_only(uei, name):
    """Check local sam_exclusion table when API calls are unavailable."""
    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if uei:
            cursor.execute(
                "SELECT * FROM sam_exclusion WHERE uei = %s", (uei,)
            )
        else:
            cursor.execute(
                "SELECT * FROM sam_exclusion WHERE entity_name LIKE %s",
                (f"%{name}%",),
            )
        results = cursor.fetchall()

        if not results:
            click.echo("\n  CLEAN (local DB) - No exclusions found.")
            click.echo("  Note: Local data may be stale. Load fresh data with: "
                      "python main.py load-exclusions")
            return

        click.echo(f"\n  WARNING (local DB): {len(results)} exclusion(s) found!")
        for row in results:
            click.echo(f"\n  UEI:              {row.get('uei', 'N/A')}")
            click.echo(f"  Entity Name:      {row.get('entity_name', 'N/A')}")
            click.echo(f"  Type:             {row.get('exclusion_type', 'N/A')}")
            click.echo(f"  Activation Date:  {row.get('activation_date', 'N/A')}")
            click.echo(f"  Termination Date: {row.get('termination_date', 'N/A')}")

    except Exception as e:
        click.echo(f"\n  Could not check local DB: {e}")
    finally:
        cursor.close()
        conn.close()
