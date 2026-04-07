"""GSA CALC+ CLI commands.

Commands: load-calc
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("load-calc")
@click.option("--legacy", is_flag=True, default=False,
              help="Use legacy API multi-sort path (~124K rates, slower).")
@click.option("--force", is_flag=True, default=False,
              help="Bypass the 30-day staleness check and load immediately.")
def load_calc(legacy, force):
    """Load GSA CALC+ labor rates into gsa_labor_rate table. No API key needed.

    Default: bigram CSV sweep (~260K rates via 8 keyword CSV exports).
    Checks staleness first -- skips if loaded within 30 days.

    With --legacy, uses the old API multi-sort de-duplication path (~124K rates,
    no staleness check).

    With --force, bypasses the 30-day staleness check.

    No authentication or API key is required. No rate limits.

    Examples:
        python main.py load labor-rates
        python main.py load labor-rates --force
        python main.py load labor-rates --legacy
    """
    import time
    from datetime import datetime, timedelta

    logger = setup_logging()

    from api_clients.calc_client import CalcPlusClient
    from etl.calc_loader import CalcLoader
    from etl.load_manager import LoadManager

    client = CalcPlusClient()
    loader = CalcLoader()

    # Staleness check (skip for --legacy and --force)
    if not legacy and not force:
        lm = LoadManager()
        last_load = lm.get_last_load("GSA_CALC", status="SUCCESS")
        if last_load and last_load.get("started_at"):
            last_date = last_load["started_at"]
            days_ago = (datetime.now() - last_date).days
            if days_ago < 30:
                next_due = last_date + timedelta(days=30)
                click.echo(
                    "Skipping -- last loaded on %s (%d days ago). "
                    "Next load due %s. Use --force to override."
                    % (last_date.strftime("%Y-%m-%d"), days_ago,
                       next_due.strftime("%Y-%m-%d"))
                )
                return

    method = "API multi-sort de-duplication (legacy)" if legacy else "bigram CSV sweep"

    click.echo("GSA CALC+ Labor Rate Load")
    click.echo("  Data source: GSA CALC+ API (refreshed nightly by GSA)")
    click.echo("  Rates loaded: current fiscal year ceiling rates from GSA schedule contracts")
    click.echo("  Method: %s" % method)
    click.echo("  Target: gsa_labor_rate (truncate + reload)")
    click.echo("")
    click.echo("  NOTE: These are GSA schedule CEILING rates, not SCA wage")
    click.echo("        determinations. For SCA minimums, see DOL wage determinations.")
    click.echo("")

    t_start = time.time()

    def progress(seen_count, label):
        click.echo("  [%s] %s" % (label, seen_count))

    try:
        if legacy:
            stats = loader.full_refresh(client, progress_callback=progress)
        else:
            stats = loader.full_refresh_csv(client, progress_callback=progress)
        elapsed = time.time() - t_start

        click.echo("")
        click.echo("Load complete!")
        click.echo("  Records fetched:   %10d" % stats["records_read"])
        click.echo("  Records inserted:  %10d" % stats["records_inserted"])
        click.echo("  Records errored:   %10d" % stats["records_errored"])
        click.echo("  Time:              %10.1f seconds" % elapsed)

        # Show contract date range of loaded data
        try:
            from db.connection import get_connection as gc
            conn = gc()
            cur = conn.cursor()
            cur.execute(
                "SELECT MIN(contract_start), MAX(contract_end) "
                "FROM gsa_labor_rate"
            )
            row = cur.fetchone()
            if row and row[0] and row[1]:
                click.echo("")
                click.echo("  Contract date range: %s to %s" % (row[0], row[1]))
            cur.close()
            conn.close()
        except Exception:
            pass  # Non-critical, don't fail the load

        # Post-load: re-normalize labor categories and refresh summary table
        # Chain: gsa_labor_rate → labor_category_mapping → labor_rate_summary
        try:
            from etl.labor_normalizer import LaborNormalizer
            click.echo("")
            click.echo("Post-load: normalizing labor categories...")
            normalizer = LaborNormalizer()
            norm_stats = normalizer.normalize()
            click.echo("  Mapped: %d (exact=%d pattern=%d fuzzy=%d)" % (
                norm_stats.get("exact", 0) + norm_stats.get("pattern", 0) + norm_stats.get("fuzzy", 0),
                norm_stats.get("exact", 0),
                norm_stats.get("pattern", 0),
                norm_stats.get("fuzzy", 0),
            ))
            click.echo("  Unmapped: %d" % norm_stats.get("unmapped", 0))

            click.echo("Post-load: refreshing labor rate summary...")
            summary_stats = normalizer.refresh_summary()
            click.echo("  Summary rows: %d" % summary_stats.get("summary_rows", 0))
        except Exception as e:
            logger.warning("Post-load normalization failed (non-fatal): %s", e)
            click.echo("\n  WARNING: Post-load normalization failed: %s" % e)
            click.echo("  Run manually: python main.py normalize labor-categories")

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("CALC+ load failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)
