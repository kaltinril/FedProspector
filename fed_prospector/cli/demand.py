"""CLI commands for on-demand data loading (Phase 43)."""

import time

import click

from config.logging_config import setup_logging


@click.command("process-requests")
@click.option("--watch", is_flag=True, help="Run continuously, polling every 5 seconds")
@click.option("--clear-queue", is_flag=True, help="Cancel all PENDING requests before starting")
def process_requests(watch, clear_queue):
    """Process pending on-demand data load requests.

    Polls the data_load_request table for PENDING rows and processes them
    by fetching data from external APIs (USASpending, SAM.gov).

    Use --watch to run continuously as a background service.
    Use --clear-queue to cancel all pending requests before starting.

    Examples:
        python main.py demand process-requests
        python main.py demand process-requests --watch
        python main.py demand process-requests --watch --clear-queue
    """
    logger = setup_logging()

    from etl.demand_loader import DemandLoader
    loader = DemandLoader()

    if clear_queue:
        cleared = loader.clear_queue()
        click.echo(f"Cleared {cleared} pending requests from queue.")

    if watch:
        logger.info("Starting demand loader in watch mode (Ctrl+C to stop)")
        click.echo("Demand loader running in watch mode. Press Ctrl+C to stop.")
        try:
            while True:
                processed = loader.process_pending_requests()
                if processed > 0:
                    logger.info("Processed %d requests", processed)
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Demand loader stopped")
            click.echo("\nDemand loader stopped.")
    else:
        processed = loader.process_pending_requests()
        click.echo(f"Processed {processed} requests")
