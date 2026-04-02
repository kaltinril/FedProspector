"""BLS data loading CLI commands.

Commands: load-bls
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("load-bls")
@click.option("--full", is_flag=True, help="Force full load (last 20 years) instead of incremental")
def load_bls(full):
    """Load BLS Employment Cost Index and CPI data into bls_cost_index table.

    Fetches ECI (Employment Cost Index) and CPI (Consumer Price Index) time
    series from the BLS public API. No authentication required, but an
    optional registration key can be set via BLS_API_KEY in .env for higher
    rate limits.

    First load fetches 20 years of historical data. Subsequent loads fetch
    the last 2 years for updates. Use --full to force a complete reload.

    Series loaded:
      - ECI Professional and Business Services
      - ECI All Civilian Workers
      - CPI-U All Urban Consumers
      - CPI-U Less Food and Energy

    Examples:
        python main.py load bls
        python main.py load bls --full
    """
    import time
    logger = setup_logging()

    from api_clients.bls_client import BLSClient
    from etl.bls_loader import BLSLoader

    client = BLSClient()
    loader = BLSLoader()

    click.echo("BLS Cost Index Load")
    click.echo("  Data source: Bureau of Labor Statistics API v2")
    click.echo("  Series: ECI (professional services, all civilian) + CPI-U")
    click.echo("  Target: bls_cost_index (upsert)")
    click.echo("  Mode: %s" % ("FULL (20 years)" if full else "AUTO (incremental if prior load exists)"))
    click.echo("")

    t_start = time.time()

    try:
        stats = loader.load(client, full=full)
        elapsed = time.time() - t_start

        click.echo("")
        click.echo("Load complete!")
        click.echo("  Records read:       %10d" % stats["records_read"])
        click.echo("  Records inserted:   %10d" % stats["records_inserted"])
        click.echo("  Records updated:    %10d" % stats["records_updated"])
        click.echo("  Records errored:    %10d" % stats["records_errored"])
        click.echo("  Time:               %10.1f seconds" % elapsed)

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("BLS load failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)
