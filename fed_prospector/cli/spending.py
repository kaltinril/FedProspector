"""CLI commands for spending analysis and burn rate (Phase 5B-Enhance)."""

import sys
import time

import click

from config.logging_config import setup_logging


@click.command("load-transactions")
@click.option("--award-id", default=None, help="USASpending generated_unique_award_id (e.g., CONT_AWD_...)")
@click.option("--solicitation", default=None, help="Solicitation number to find award and load transactions")
@click.option("--piid", default=None, help="Contract PIID to find award and load transactions")
def load_transactions(award_id, solicitation, piid):
    """Load transaction history for a USASpending award.

    Fetches the per-modification funding timeline and loads it into
    usaspending_transaction table. This data enables burn rate analysis.

    You can specify the award directly with --award-id, or search for it
    by --solicitation or --piid (requires the award to exist in the
    usaspending_award table first).

    No API rate limits (USASpending has no daily quotas).

    Examples:
        python main.py load usaspending --award-id CONT_AWD_W911NF25C0001_9700_-NONE-_-NONE-
        python main.py load usaspending --solicitation W911NF-25-R-0001
        python main.py load usaspending --piid W911NF25C0001
    """
    logger = setup_logging()

    if not any([award_id, solicitation, piid]):
        click.echo("ERROR: One of --award-id, --solicitation, or --piid is required")
        sys.exit(1)

    from api_clients.usaspending_client import USASpendingClient
    from etl.usaspending_loader import USASpendingLoader
    from etl.load_manager import LoadManager

    client = USASpendingClient()
    loader = USASpendingLoader()
    load_manager = LoadManager()

    # Resolve award_id if not provided directly
    if not award_id:
        from db.connection import get_connection
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if solicitation:
                cursor.execute(
                    "SELECT generated_unique_award_id FROM usaspending_award "
                    "WHERE solicitation_identifier = %s OR piid = %s "
                    "ORDER BY total_obligation DESC LIMIT 1",
                    (solicitation, solicitation),
                )
            else:  # piid
                cursor.execute(
                    "SELECT generated_unique_award_id FROM usaspending_award "
                    "WHERE piid = %s ORDER BY total_obligation DESC LIMIT 1",
                    (piid,),
                )
            row = cursor.fetchone()
            if not row:
                click.echo(f"ERROR: No award found in usaspending_award table for "
                          f"{'solicitation ' + solicitation if solicitation else 'PIID ' + piid}")
                click.echo("Load award data first: python main.py load usaspending")
                sys.exit(1)
            award_id = row["generated_unique_award_id"]
        finally:
            cursor.close()
            conn.close()

    click.echo(f"Loading transactions for award: {award_id}")

    load_id = load_manager.start_load(
        "USASPENDING_TXN", "INCREMENTAL",
        parameters={"award_id": award_id},
    )

    t_start = time.time()
    try:
        transactions = client.get_all_transactions(award_id)
        stats = loader.load_transactions(award_id, transactions, load_id)

        elapsed = time.time() - t_start
        load_manager.complete_load(
            load_id,
            records_read=stats["records_read"],
            records_inserted=stats["records_inserted"],
        )

        click.echo(f"\nTransaction load complete! ({elapsed:.1f}s)")
        click.echo(f"  Records read:     {stats['records_read']:>8,d}")
        click.echo(f"  Records inserted: {stats['records_inserted']:>8,d}")
        click.echo(f"  Records skipped:  {stats['records_skipped']:>8,d}")
        click.echo(f"  Records errored:  {stats['records_errored']:>8,d}")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Transaction load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("burn-rate")
@click.option("--award-id", default=None, help="USASpending generated_unique_award_id")
@click.option("--solicitation", default=None, help="Solicitation number to find award")
@click.option("--piid", default=None, help="Contract PIID to find award")
@click.option("--load-if-missing", is_flag=True, default=False,
              help="Auto-load transactions from API if not in local DB")
def burn_rate(award_id, solicitation, piid, load_if_missing):
    """Calculate and display burn rate for a contract award.

    Shows monthly obligation amounts, total spending, and monthly
    burn rate from transaction history in usaspending_transaction.

    If the award or its transactions aren't in the local DB yet, use
    --load-if-missing to auto-fetch both from USASpending API.

    Examples:
        python main.py analyze burn-rate --award-id CONT_AWD_W911NF25C0001_9700_-NONE-_-NONE-
        python main.py analyze burn-rate --piid W911NF25C0001 --load-if-missing
        python main.py analyze burn-rate --solicitation W911NF-25-R-0001
    """
    logger = setup_logging()

    if not any([award_id, solicitation, piid]):
        click.echo("ERROR: One of --award-id, --solicitation, or --piid is required")
        sys.exit(1)

    from db.connection import get_connection
    from etl.usaspending_loader import USASpendingLoader

    loader = USASpendingLoader()

    # Resolve award_id
    if not award_id:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if solicitation:
                cursor.execute(
                    "SELECT generated_unique_award_id, recipient_name, total_obligation, "
                    "start_date, end_date FROM usaspending_award "
                    "WHERE solicitation_identifier = %s OR piid = %s "
                    "ORDER BY total_obligation DESC LIMIT 1",
                    (solicitation, solicitation),
                )
            else:
                cursor.execute(
                    "SELECT generated_unique_award_id, recipient_name, total_obligation, "
                    "start_date, end_date FROM usaspending_award "
                    "WHERE piid = %s ORDER BY total_obligation DESC LIMIT 1",
                    (piid,),
                )
            row = cursor.fetchone()
            if not row:
                if not load_if_missing:
                    click.echo("ERROR: Award not found in local database.")
                    click.echo("Tip: re-run with --load-if-missing to fetch from USASpending API.")
                    sys.exit(1)

                # Award missing — search USASpending API and load it
                keyword = solicitation or piid
                click.echo(f"Award not in local DB. Searching USASpending API for '{keyword}'...")
                from api_clients.usaspending_client import USASpendingClient
                from etl.load_manager import LoadManager

                client = USASpendingClient()
                lm = LoadManager()
                response = client.search_awards(keyword=keyword, limit=5)
                awards = response.get("results", [])

                if not awards:
                    click.echo(f"ERROR: No award found on USASpending for '{keyword}'.")
                    sys.exit(1)

                aw_load_id = lm.start_load(
                    "USASPENDING_AWARD", "INCREMENTAL", parameters={"keyword": keyword}
                )
                try:
                    stats = loader.load_awards(awards, aw_load_id)
                    lm.complete_load(
                        aw_load_id,
                        records_read=stats["records_read"],
                        records_inserted=stats["records_inserted"],
                    )
                    click.echo(f"  Loaded {stats['records_inserted']} award(s) from API.")
                except Exception as e:
                    lm.fail_load(aw_load_id, str(e))
                    click.echo(f"ERROR loading award: {e}")
                    sys.exit(1)

                # Build row from API data — avoids re-querying and any
                # DB snapshot / piid-format mismatch issues.
                top = awards[0]
                row = {
                    "generated_unique_award_id": (
                        top.get("generated_unique_award_id")
                        or top.get("generated_internal_id")
                    ),
                    "recipient_name": top.get("Recipient Name"),
                    "total_obligation": top.get("Award Amount"),
                    "start_date": top.get("Start Date"),
                    "end_date": top.get("End Date"),
                }
                if not row["generated_unique_award_id"]:
                    click.echo("ERROR: API returned award with no unique ID.")
                    sys.exit(1)

            award_id = row["generated_unique_award_id"]
            click.echo(f"Award: {award_id}")
            click.echo(f"  Recipient:    {row.get('recipient_name', 'N/A')}")
            click.echo(f"  Obligation:   ${float(row.get('total_obligation') or 0):,.2f}")
            click.echo(f"  Period:       {row.get('start_date', 'N/A')} to {row.get('end_date', 'N/A')}")
        finally:
            cursor.close()
            conn.close()

    # Try to calculate from local data
    result = loader.calculate_burn_rate(award_id)

    if not result and load_if_missing:
        click.echo("\nNo transactions in local DB. Loading from API...")
        from api_clients.usaspending_client import USASpendingClient
        from etl.load_manager import LoadManager

        client = USASpendingClient()
        lm = LoadManager()
        load_id = lm.start_load("USASPENDING_TXN", "INCREMENTAL", parameters={"award_id": award_id})
        try:
            txns = client.get_all_transactions(award_id)
            stats = loader.load_transactions(award_id, txns, load_id)
            lm.complete_load(load_id, records_read=stats["records_read"],
                           records_inserted=stats["records_inserted"])
            click.echo(f"  Loaded {stats['records_inserted']} transactions")
        except Exception as e:
            lm.fail_load(load_id, str(e))
            click.echo(f"ERROR loading transactions: {e}")
            sys.exit(1)

        result = loader.calculate_burn_rate(award_id)

    if not result:
        click.echo("\nNo transaction data available for burn rate calculation.")
        click.echo("Run: python main.py load usaspending --award-id " + award_id)
        return

    click.echo(f"\n{'='*50}")
    click.echo(f"  BURN RATE ANALYSIS")
    click.echo(f"{'='*50}")
    click.echo(f"  Total Obligated:    ${result['total_obligated']:>15,.2f}")
    click.echo(f"  Months Elapsed:     {result['months_elapsed']:>15d}")
    click.echo(f"  Monthly Burn Rate:  ${result['monthly_rate']:>15,.2f}")
    click.echo(f"  Transaction Count:  {result['transaction_count']:>15d}")

    click.echo(f"\n  --- Monthly Breakdown ---")
    click.echo(f"  {'Month':<10s}  {'Amount':>15s}  {'Cumulative':>15s}")
    click.echo(f"  {'-'*10}  {'-'*15}  {'-'*15}")

    cumulative = 0.0
    for month, amount in result["monthly_breakdown"]:
        cumulative += amount
        click.echo(f"  {month:<10s}  ${amount:>14,.2f}  ${cumulative:>14,.2f}")

    click.echo(f"\n{'='*50}")
