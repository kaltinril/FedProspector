"""CLI commands for refreshing pre-computed summary tables.

These recompute materialized summaries from their source views/tables so the
App API can read flat, indexed rows instead of running expensive aggregates
per request.  Wired into the daily load (`job daily`).
"""

import time

import click

from config.logging_config import setup_logging


@click.command("partner-capability")
def refresh_partner_capability():
    """Refresh partner_capability_match + partner_capability_naics.

    Materializes v_partner_capability_match (a >90s 6-way aggregate that backs
    the Teaming Partner Search and Gap Analysis tabs) into a flat summary table,
    and populates the partner_capability_naics child so the NAICS filter is an
    indexed join instead of a GROUP_CONCAT substring match.

    Idempotent (TRUNCATE + INSERT ... SELECT) — safe to re-run.  Run after the
    daily load populates entity/fpds data.

    Examples:
        python main.py refresh partner-capability
    """
    setup_logging()

    from db.connection import get_connection
    from etl.etl_utils import refresh_partner_capability_match

    click.echo("Refreshing partner_capability_match (materializing v_partner_capability_match)...")
    start = time.time()

    conn = get_connection()
    try:
        summary_count = refresh_partner_capability_match(conn)
    finally:
        conn.close()

    elapsed = time.time() - start
    click.echo(f"Done: {summary_count:,d} partner rows in {elapsed:.1f}s")
